"""Deterministic page-structure extraction.

A ruled form is a grid, not a bag of rectangles. The previous detector treated every
rectangle as a candidate field and then suppressed overlaps, which on a real table keeps
the outer table border and discards every cell inside it -- on the ECI declaration form
that collapsed 121 detected rectangles into 2 fields and lost the entire parentage table.

This module recovers the grid instead: it finds the rules, derives the cells between them,
assigns the OCR words to cells, and works out which cells are captions and which are
blanks waiting to be filled. It also records, for every blank, the row caption and the
column header above it, because that context is the only thing that distinguishes the two
`Relative's Name:` cells that sit side by side on that form.

Nothing here decides what a field *means*. It decides what is on the page and how it is
arranged. Meaning is assigned later, by the dictionary or by the interpreter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dataclass_field

import cv2
import numpy as np

from app.models.common import PixelBoundingBox
from app.models.ocr import OCRResult, OCRWord
from app.utils.text_normalization import fold

logger = logging.getLogger(__name__)

# A cell smaller than this in either direction is a rule artefact, not a cell.
MIN_CELL_W = 24
MIN_CELL_H = 14

# A blank narrower than this cannot hold a written answer.
MIN_BLANK_W = 40
MIN_BLANK_H = 16

# Fraction of a cell's width that must be free of ink, to the right of its caption, for
# the caption and the blank to be treated as sharing one cell ("Elector Name: ______").
INLINE_BLANK_RATIO = 0.35

# A caption that invites an answer is short. Anything longer is prose.
MAX_CAPTION_WORDS = 6
MAX_CAPTION_CHARS = 48

# A signature or attestation caption runs a little longer than an inline one
# ("Signature/Left Thumb Impression of Elector with date").
SIGNATURE_CAPTION_WORDS = 10

# More tick boxes than this on one page means the mark detector is misfiring, not that
# the form really asks that many questions.
MAX_PLAUSIBLE_MARKS = 8

# Wording that marks a place to sign, thumb-print, or attest, in the four supported
# languages. A writing area is proposed under such a caption and nowhere else: a looser
# rule proposed fields under headings and under the last line of a paragraph.
ATTESTATION_TERMS = (
    "signature",
    "sign here",
    "thumb impression",
    "attested",
    "attestation",
    "name and phone",
    "undertaking",
    "seal",
    "stamp",
    "हस्ताक्षर",
    "अंगूठे का निशान",
    "प्रमाणित",
    "ಸಹಿ",
    "ಹೆಬ್ಬೆಟ್ಟಿನ ಗುರುತು",
    "ದೃಢೀಕರಣ",
    "دستخط",
    "انگوٹھے کا نشان",
    "تصدیق",
)


@dataclass
class Cell:
    """One rectangle of a ruled grid."""

    id: str
    x: int
    y: int
    width: int
    height: int
    words: list[OCRWord] = dataclass_field(default_factory=list)
    row: int = -1
    column: int = -1
    table: int = -1

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def text(self) -> str:
        ordered = sorted(self.words, key=lambda item: (item.pixel.y, item.pixel.x))
        return " ".join(item.text for item in ordered).strip()

    @property
    def is_blank(self) -> bool:
        return not self.text


@dataclass
class Table:
    index: int
    x: int
    y: int
    width: int
    height: int
    cells: list[Cell] = dataclass_field(default_factory=list)
    header_rows: list[int] = dataclass_field(default_factory=list)

    @property
    def row_count(self) -> int:
        return max((cell.row for cell in self.cells), default=-1) + 1


@dataclass
class TextLine:
    text: str
    x: int
    y: int
    width: int
    height: int
    words: list[OCRWord] = dataclass_field(default_factory=list)

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass
class Blank:
    """A place on the page where something can be written."""

    id: str
    x: int
    y: int
    width: int
    height: int
    origin: str  # table_cell | inline_cell | ruled_line | colon_gap | mark
    caption: str = ""
    column_header: str = ""
    row_header: str = ""
    section: str = ""
    sub_header: str = ""
    nearby_text: str = ""
    table_index: int = -1
    row: int = -1
    column: int = -1

    def to_pixel(self, image_width: int, image_height: int, page_index: int) -> PixelBoundingBox:
        return PixelBoundingBox(
            x=self.x,
            y=self.y,
            width=max(1, self.width),
            height=max(1, self.height),
            image_width=image_width,
            image_height=image_height,
            page_index=page_index,
        )


@dataclass
class PageLayout:
    page_index: int
    image_width: int
    image_height: int
    tables: list[Table] = dataclass_field(default_factory=list)
    text_lines: list[TextLine] = dataclass_field(default_factory=list)
    blanks: list[Blank] = dataclass_field(default_factory=list)

    @property
    def looks_like_prose(self) -> bool:
        """True when the page is instructions rather than a form to fill.

        The second page of the ECI declaration form is an information sheet with no
        fields at all. Inventing fields there is worse than finding none, so a page with
        no grid and no caption-and-gap pattern is reported as prose and left alone.
        """
        if self.tables or self.blanks:
            return False
        return len(self.text_lines) >= 8


class PageStructureService:
    def add_marks(self, layout: PageLayout, marks) -> None:
        """Fold detected tick boxes into the page's blanks.

        Marks go through the same interpretation as everything else so that the two real
        declaration boxes on a form survive and the ones the detector imagined inside the
        title text are rejected by the model rather than by yet another heuristic.
        """
        candidates: list[Blank] = []
        for field in marks:
            pixel = field.input_box.to_pixel(layout.image_width, layout.image_height)
            blank = Blank(
                id=field.id,
                x=pixel.x,
                y=pixel.y,
                width=pixel.width,
                height=pixel.height,
                origin="mark",
            )
            if not self._plausible_mark(layout, blank):
                continue
            blank.nearby_text = self._nearby(layout, blank)
            blank.section = self._section_above(layout, blank, None)
            candidates.append(blank)

        # A page with a crowd of tick boxes is a page where the detector is misfiring:
        # a real declaration has a handful. Run against a government form with two, it
        # proposed thirty-one, mostly loops and dots inside the title text. Passing those
        # on would double the interpreter's work and cost for nothing, so when the count
        # is implausible the whole set is discarded rather than half-trusted.
        if len(candidates) > MAX_PLAUSIBLE_MARKS:
            logger.info(
                "Discarding %s mark candidates on page %s: too many to be real",
                len(candidates),
                layout.page_index,
            )
            return
        layout.blanks.extend(candidates)

    @staticmethod
    def _plausible_mark(layout: PageLayout, blank: Blank) -> bool:
        """A tick box is square, sits clear of the text, and has a caption beside it."""
        if blank.width <= 0 or blank.height <= 0:
            return False
        ratio = blank.width / blank.height
        if not 0.65 <= ratio <= 1.55:
            return False
        centre_x = blank.x + blank.width / 2
        centre_y = blank.y + blank.height / 2

        # Inside a word: the detector found a loop in a glyph, not a box.
        for line in layout.text_lines:
            for word in line.words:
                pixel = word.pixel
                if (
                    pixel.x <= centre_x <= pixel.x + pixel.width
                    and pixel.y <= centre_y <= pixel.y + pixel.height
                ):
                    return False

        # Inside a cell that is already offered as a place to write.
        for other in layout.blanks:
            if other.x <= centre_x <= other.x + other.width and other.y <= centre_y <= other.y + other.height:
                return False

        # A tick box with nothing written beside it is not asking anything.
        for line in layout.text_lines:
            if abs(line.y + line.height / 2 - centre_y) > max(blank.height, 14):
                continue
            if abs(line.x - (blank.x + blank.width)) <= 260 or abs(blank.x - (line.x + line.width)) <= 260:
                return True
        return False

    def analyse(self, image_path: str, ocr: OCRResult, page_index: int = 0) -> PageLayout:
        image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            return PageLayout(page_index=page_index, image_width=ocr.image_width, image_height=ocr.image_height)

        height, width = image.shape[:2]
        layout = PageLayout(page_index=page_index, image_width=width, image_height=height)

        horizontal, vertical = self._rules(image)
        layout.tables = self._tables(horizontal, vertical, width, height)
        self._assign_words(layout.tables, ocr, width, height)
        self._index_cells(layout.tables)
        layout.text_lines = self._text_lines(ocr, layout.tables, width, height)
        layout.blanks = self._blanks(layout, horizontal, image)
        self._attach_context(layout)
        logger.debug(
            "page %s structure: %s tables, %s text lines, %s blanks",
            page_index,
            len(layout.tables),
            len(layout.text_lines),
            len(layout.blanks),
        )
        return layout

    # --- rules and cells ---------------------------------------------------------

    @staticmethod
    def _rules(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        height, width = gray.shape[:2]
        ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
        horizontal = cv2.morphologyEx(
            ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, width // 30), 1))
        )
        vertical = cv2.morphologyEx(
            ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(18, height // 60)))
        )
        # Close small breaks so a scan's dashed-looking rule still forms a closed cell.
        horizontal = cv2.dilate(horizontal, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1)))
        vertical = cv2.dilate(vertical, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 9)))
        return horizontal, vertical

    def _tables(self, horizontal: np.ndarray, vertical: np.ndarray, width: int, height: int) -> list[Table]:
        grid = cv2.bitwise_or(horizontal, vertical)
        # A table is a region where horizontal and vertical rules actually cross.
        joints = cv2.bitwise_and(horizontal, vertical)
        if cv2.countNonZero(joints) == 0:
            return []
        region_mask = cv2.dilate(grid, np.ones((7, 7), np.uint8))
        count, labels, stats, _ = cv2.connectedComponentsWithStats(region_mask, connectivity=8)

        tables: list[Table] = []
        for index in range(1, count):
            x, y, w, h = (
                int(stats[index, cv2.CC_STAT_LEFT]),
                int(stats[index, cv2.CC_STAT_TOP]),
                int(stats[index, cv2.CC_STAT_WIDTH]),
                int(stats[index, cv2.CC_STAT_HEIGHT]),
            )
            if w < width * 0.25 or h < MIN_CELL_H * 2:
                continue
            local_joints = joints[y : y + h, x : x + w]
            if cv2.countNonZero(local_joints) < 50:
                continue
            cells = self._cells_in(grid, x, y, w, h, len(tables))
            if len(cells) < 2:
                continue
            tables.append(Table(index=len(tables), x=x, y=y, width=w, height=h, cells=cells))
        return tables

    @staticmethod
    def _cells_in(grid: np.ndarray, x: int, y: int, w: int, h: int, table_index: int) -> list[Cell]:
        """Cells are the holes in the grid: connected components of its complement."""
        region = grid[y : y + h, x : x + w]
        holes = cv2.bitwise_not(region)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(holes, connectivity=4)
        cells: list[Cell] = []
        for index in range(1, count):
            cx, cy, cw, ch = (
                int(stats[index, cv2.CC_STAT_LEFT]),
                int(stats[index, cv2.CC_STAT_TOP]),
                int(stats[index, cv2.CC_STAT_WIDTH]),
                int(stats[index, cv2.CC_STAT_HEIGHT]),
            )
            if cw < MIN_CELL_W or ch < MIN_CELL_H:
                continue
            # The component that wraps the whole table is the outside, not a cell.
            if cw > w * 0.98 and ch > h * 0.98:
                continue
            area = int(stats[index, cv2.CC_STAT_AREA])
            if area < cw * ch * 0.55:
                continue  # ragged shape: not a rectangular cell
            cells.append(
                Cell(
                    id=f"t{table_index}c{len(cells)}",
                    x=x + cx,
                    y=y + cy,
                    width=cw,
                    height=ch,
                    table=table_index,
                )
            )
        return cells

    @staticmethod
    def _assign_words(tables: list[Table], ocr: OCRResult, width: int, height: int) -> None:
        for word in ocr.words:
            pixel = word.pixel
            mid_x = pixel.x + pixel.width / 2
            mid_y = pixel.y + pixel.height / 2
            for table in tables:
                if not (table.x <= mid_x <= table.x + table.width and table.y <= mid_y <= table.y + table.height):
                    continue
                for cell in table.cells:
                    if cell.x <= mid_x <= cell.right and cell.y <= mid_y <= cell.bottom:
                        cell.words.append(word)
                        break
                break

    @staticmethod
    def _index_cells(tables: list[Table]) -> None:
        """Give every cell a row and column index, and find the header rows."""
        for table in tables:
            rows: list[list[Cell]] = []
            for cell in sorted(table.cells, key=lambda item: (item.y, item.x)):
                for row in rows:
                    reference = row[0]
                    overlap = min(cell.bottom, reference.bottom) - max(cell.y, reference.y)
                    if overlap > min(cell.height, reference.height) * 0.5:
                        row.append(cell)
                        break
                else:
                    rows.append([cell])
            for row_index, row in enumerate(rows):
                for column_index, cell in enumerate(sorted(row, key=lambda item: item.x)):
                    cell.row = row_index
                    cell.column = column_index
            # A header row is a top row whose cells are all text *and* leave no room to
            # write in. That last part matters: on the ECI form the row below the real
            # header reads "Elector Name: ____ | Name: ____", which is every bit as
            # "all text" as the header but is a data row with space for an answer. Using
            # free space to tell them apart stops the header being read as "Elector Name"
            # and losing that row's two fields.
            for row_index, row in enumerate(rows):
                if row_index > 1 or len(row) < 2:
                    break
                if any(cell.is_blank for cell in row):
                    break
                # A caption ending in a colon is a question, not a heading. On the real
                # form the row under the header reads "Elector Name: ____ | Name: ____",
                # which is every bit as "all text" as the header above it. Reading that
                # row as a header costs its two fields and mislabels everything below.
                if any(cell.text.rstrip().endswith(":") for cell in row):
                    break
                table.header_rows.append(row_index)

    # --- text outside tables -----------------------------------------------------

    @staticmethod
    def _text_lines(ocr: OCRResult, tables: list[Table], width: int, height: int) -> list[TextLine]:
        inside = set()
        for table in tables:
            for cell in table.cells:
                inside.update(word.id for word in cell.words)
        lines: list[TextLine] = []
        for line in ocr.lines:
            words = [word for word in ocr.words if word.id in set(line.word_ids) and word.id not in inside]
            if not words:
                continue
            left = min(word.pixel.x for word in words)
            top = min(word.pixel.y for word in words)
            right = max(word.pixel.x + word.pixel.width for word in words)
            bottom = max(word.pixel.y + word.pixel.height for word in words)
            lines.append(
                TextLine(
                    text=" ".join(w.text for w in sorted(words, key=lambda i: i.pixel.x)).strip(),
                    x=left,
                    y=top,
                    width=right - left,
                    height=bottom - top,
                    words=words,
                )
            )
        lines.sort(key=lambda item: (item.y, item.x))
        return lines

    # --- blanks ------------------------------------------------------------------

    def _blanks(self, layout: PageLayout, horizontal: np.ndarray, gray: np.ndarray) -> list[Blank]:
        blanks: list[Blank] = []
        for table in layout.tables:
            for cell in table.cells:
                if cell.row in table.header_rows:
                    continue
                if cell.is_blank:
                    if cell.width >= MIN_BLANK_W and cell.height >= MIN_BLANK_H:
                        blanks.append(
                            Blank(
                                id=f"p{layout.page_index}-{cell.id}",
                                x=cell.x + 2,
                                y=cell.y + 2,
                                width=cell.width - 4,
                                height=cell.height - 4,
                                origin="table_cell",
                                table_index=table.index,
                                row=cell.row,
                                column=cell.column,
                            )
                        )
                    continue
                if self._has_blank_sibling(table, cell):
                    # The row already provides a separate empty cell for the answer, so
                    # the leftover space beside this caption is just padding.
                    continue
                inline = self._inline_blank(cell)
                if inline is not None:
                    blanks.append(
                        Blank(
                            id=f"p{layout.page_index}-{cell.id}i",
                            x=inline[0],
                            y=inline[1],
                            width=inline[2],
                            height=inline[3],
                            origin="inline_cell",
                            caption=cell.text,
                            table_index=table.index,
                            row=cell.row,
                            column=cell.column,
                        )
                    )
        blanks.extend(self._free_blanks(layout, gray))
        blanks.extend(self._space_below_captions(layout))
        return blanks

    def _space_below_captions(self, layout: PageLayout) -> list[Blank]:
        """A short line with a wide empty gap under it: a signature or attestation area.

        These carry no colon and no rule, so nothing else finds them, yet they are real
        places the form expects something. They are proposed here and the interpreter is
        free to reject any that turn out to be headings.
        """
        blanks: list[Blank] = []
        lines = layout.text_lines
        for index, line in enumerate(lines):
            caption = line.text.strip().rstrip(":").strip()
            if not caption or len(caption.split()) > SIGNATURE_CAPTION_WORDS:
                continue
            if not any(term in fold(caption) for term in ATTESTATION_TERMS):
                continue
            following = lines[index + 1] if index + 1 < len(lines) else None
            gap = (following.y - line.bottom) if following else (layout.image_height - line.bottom)
            if gap < line.height * 1.8 or gap < MIN_BLANK_H * 2:
                continue
            if any(self._overlaps(blank, line) for blank in layout.blanks):
                continue
            blanks.append(
                Blank(
                    id=f"p{layout.page_index}-under{index}",
                    x=line.x,
                    y=line.bottom + 6,
                    width=max(MIN_BLANK_W, line.width),
                    height=min(int(gap) - 10, 90),
                    origin="space_below",
                    caption=caption,
                )
            )
        return blanks

    @staticmethod
    def _overlaps(blank: Blank, line: TextLine) -> bool:
        return not (
            blank.x + blank.width < line.x
            or blank.x > line.x + line.width
            or blank.y + blank.height < line.y
            or blank.y > line.bottom
        )

    @staticmethod
    def _has_blank_sibling(table: Table, cell: Cell) -> bool:
        return any(
            other.row == cell.row and other.x > cell.x and other.is_blank
            and other.width >= MIN_BLANK_W and other.height >= MIN_BLANK_H
            for other in table.cells
        )

    @staticmethod
    def _inline_blank(cell: Cell) -> tuple[int, int, int, int] | None:
        """A caption and its blank sharing one cell: `Elector Name: ______`.

        The right-hand part of the cell is free space the applicant writes into, and it is
        a field in its own right even though the cell is not empty.
        """
        if not cell.words:
            return None
        text_right = max(word.pixel.x + word.pixel.width for word in cell.words)
        free = cell.right - text_right
        if free < MIN_BLANK_W or free < cell.width * INLINE_BLANK_RATIO:
            return None
        return (text_right + 6, cell.y + 2, free - 8, cell.height - 4)

    def _free_blanks(self, layout: PageLayout, gray: np.ndarray) -> list[Blank]:
        """Captions outside any table that end in a colon and are followed by space.

        `Applicant's Name:` has no box around it; the blank is simply the rest of the line.
        """
        blanks: list[Blank] = []
        page_right = int(layout.image_width * 0.93)
        for index, line in enumerate(layout.text_lines):
            text = line.text.strip()
            if not text.endswith(":"):
                continue
            caption = text.rstrip(":").strip()
            # A caption is short. A sentence of prose that happens to end in a colon --
            # "provide the documents based upon the following categories:" -- is not an
            # invitation to write, and treating it as one invents fields on an
            # instruction sheet.
            if len(caption.split()) > MAX_CAPTION_WORDS or len(caption) > MAX_CAPTION_CHARS:
                continue
            free = page_right - (line.x + line.width)
            if free < MIN_BLANK_W:
                continue
            blanks.append(
                Blank(
                    id=f"p{layout.page_index}-line{index}",
                    x=line.x + line.width + 8,
                    y=line.y - 2,
                    width=free - 8,
                    height=max(MIN_BLANK_H, line.height + 6),
                    origin="colon_gap",
                    caption=text.rstrip(":").strip(),
                )
            )
        return blanks

    # --- context -----------------------------------------------------------------

    def _attach_context(self, layout: PageLayout) -> None:
        """Give every blank the captions that explain it.

        This is where the two side-by-side `Relative's Name:` cells stop being
        indistinguishable: one carries the elector column's header, the other the
        relative column's.
        """
        for blank in layout.blanks:
            table = next((item for item in layout.tables if item.index == blank.table_index), None)
            if table is not None:
                blank.column_header = self._column_header(table, blank)
                blank.sub_header = self._sub_header(table, blank)
                if not blank.caption:
                    blank.caption = self._row_caption(table, blank)
                blank.row_header = self._row_caption(table, blank)
            blank.section = self._section_above(layout, blank, table)
            blank.nearby_text = self._nearby(layout, blank)

    @staticmethod
    def _sub_header(table: Table, blank: Blank) -> str:
        """The nearest all-text row above this one, for tables with nested headings.

        The ECI form ends with a band of six narrow cells under their own
        "AC Number | Part No. | Sr No." strip, which sits below the table's main header.
        Without this the six blanks would be indistinguishable from one another.
        """
        if blank.row <= 0:
            return ""
        rows_above = sorted({cell.row for cell in table.cells if cell.row < blank.row}, reverse=True)
        centre = blank.x + blank.width / 2
        for row_index in rows_above:
            row = [cell for cell in table.cells if cell.row == row_index]
            if not row or any(cell.is_blank for cell in row):
                continue
            if any(PageStructureService._inline_blank(cell) is not None for cell in row):
                # A row of "Caption: ____" cells is data, not a heading for what follows.
                return ""
            if row_index in table.header_rows:
                return ""
            for cell in row:
                if cell.x - 4 <= centre <= cell.right + 4 and cell.text:
                    return cell.text
            return ""
        return ""

    @staticmethod
    def _column_header(table: Table, blank: Blank) -> str:
        if not table.header_rows:
            return ""
        centre = blank.x + blank.width / 2
        best = ""
        for row_index in table.header_rows:
            for cell in table.cells:
                if cell.row != row_index:
                    continue
                if cell.x - 4 <= centre <= cell.right + 4 and cell.text:
                    best = cell.text
        return best

    @staticmethod
    def _row_caption(table: Table, blank: Blank) -> str:
        """The caption to the left of a blank, within its own row."""
        candidates = [
            cell
            for cell in table.cells
            if cell.row == blank.row and cell.right <= blank.x + 6 and not cell.is_blank
        ]
        if not candidates:
            return ""
        return max(candidates, key=lambda cell: cell.x).text

    @staticmethod
    def _section_above(layout: PageLayout, blank: Blank, table: Table | None) -> str:
        """The nearest line of text above the blank that is not part of a table."""
        ceiling = table.y if table is not None else blank.y
        above = [line for line in layout.text_lines if line.bottom <= ceiling + 4]
        if not above:
            return ""
        return max(above, key=lambda line: line.bottom).text

    @staticmethod
    def _nearby(layout: PageLayout, blank: Blank) -> str:
        mid_y = blank.y + blank.height / 2
        words: list[OCRWord] = []
        for line in layout.text_lines:
            if abs(line.y + line.height / 2 - mid_y) <= max(blank.height, 20):
                words.extend(line.words)
        for table in layout.tables:
            for cell in table.cells:
                if cell.is_blank:
                    continue
                if abs(cell.y + cell.height / 2 - mid_y) <= max(blank.height, 20):
                    words.extend(cell.words)
        ordered = sorted(words, key=lambda item: item.pixel.x)
        return " ".join(word.text for word in ordered)[:300]
