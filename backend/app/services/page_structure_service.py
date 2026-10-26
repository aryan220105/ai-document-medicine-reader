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
import unicodedata
from dataclasses import dataclass, field as dataclass_field

import cv2
import numpy as np

from app.models.common import PixelBoundingBox
from app.models.ocr import OCRResult, OCRWord
from app.utils.text_normalization import dominant_script, fold, is_rtl

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
MAX_CAPTION_WORDS = 12
MAX_CAPTION_CHARS = 80

# A signature or attestation caption runs a little longer than an inline one
# ("Signature/Left Thumb Impression of Elector with date").
SIGNATURE_CAPTION_WORDS = 10

# More tick boxes than this on one page means the mark detector is misfiring, not that
# the form really asks that many questions.
MAX_PLAUSIBLE_MARKS = 8

# Recognising an instruction sheet. Paragraphs run close to the full measure of the page;
# form captions are short with space beside them.
PROSE_MIN_LINES = 8
# How close a typical line must sit to the widest one for the page to read as paragraphs.
PROSE_LINE_SHARE = 0.6
# A caption is markedly shorter than the page's longest line.
PROSE_CAPTION_WIDTH = 0.45
# This many short captions ending in a colon mean it is a form, not an instruction sheet.
PROSE_MIN_CAPTIONS = 2

# A caption and its writing space share a line, so the caption cannot fill the measure.
CAPTION_LINE_WIDTH = 0.6

# A tick box belongs to a short option line. One beside a paragraph is printed text.
MARK_LINE_WIDTH = 0.6

# A dedicated value cell is clearly wider than the padding beside a caption.
SIBLING_VALUE_MARGIN = 1.3
# Two cells of near-equal width in one row are two columns of the same question, not a
# label and its answer box.
SIBLING_SAME_WIDTH = 0.15

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


def word_lines(words: list[OCRWord]) -> list[list[OCRWord]]:
    """Group words into visual lines. Order inside a line is decided later."""
    lines: list[list[OCRWord]] = []
    for word in sorted(words, key=lambda item: (item.pixel.y, item.pixel.x)):
        placed = False
        for line in lines:
            ref = line[0].pixel
            overlap = min(word.pixel.y + word.pixel.height, ref.y + ref.height) - max(word.pixel.y, ref.y)
            if overlap > min(word.pixel.height, ref.height) * 0.45:
                line.append(word)
                placed = True
                break
        if not placed:
            lines.append([word])
    return lines


def reading_text(words: list[OCRWord]) -> str:
    """Join words in reading order.

    Tesseract reports Urdu words at their true coordinates, so left-to-right order is
    the reverse of how the line is read. Captions built that way came out backwards and
    the colon sat at the start, which made a row of questions look like a table header
    and dropped the voter's name, EPIC number, and address on the Urdu form.
    """
    parts: list[str] = []
    for line in word_lines(words):
        if all(item.reading_index is not None for item in line):
            ordered = sorted(line, key=lambda item: item.reading_index or 0)
        else:
            ordered = sorted(line, key=lambda item: item.pixel.x)
            raw = " ".join(item.text for item in ordered).strip()
            if raw and dominant_script(raw) == "arabic":
                ordered = list(reversed(ordered))
        text = _tidy_caption(" ".join(item.text for item in ordered).strip())
        if text:
            parts.append(text)
    return " ".join(parts).strip()


_KEPT_LATIN = {"epic", "sir", "blo", "ac", "no", "dob"}


def _tidy_caption(text: str) -> str:
    """Drop a repeated token and a stray Latin scrap inside a regional caption.

    A second OCR pass of the same ink produces "حصہ حصہ" and "کا کا". A Latin
    scrap such as "cou" inside an Urdu line is not a word of that line. Real
    abbreviations printed on these forms are kept.
    """
    collapsed: list[str] = []
    for part in text.split():
        if collapsed and collapsed[-1] == part:
            continue
        collapsed.append(part)
    if dominant_script(text) == "latin":
        return " ".join(collapsed)
    kept: list[str] = []
    for part in collapsed:
        # A right-to-left mark glued to "cou" kept the scrap, because the token
        # was no longer plain ASCII. Format characters are not letters.
        core = "".join(ch for ch in part if unicodedata.category(ch) != "Cf")
        core = core.strip("()[]:/.,").strip()
        if core.isascii() and core.isalpha() and len(core) <= 3 and core.lower() not in _KEPT_LATIN:
            continue
        kept.append(part)
    return " ".join(kept)


def question_caption(text: str) -> str | None:
    """The label of a line that invites an answer, without the colon.

    Urdu OCR sometimes leaves the colon on the left of the phrase even after the words
    are ordered. Both ends count.
    """
    stripped = text.strip()
    for mark in (":", "："):
        if stripped.endswith(mark):
            caption = stripped[: -len(mark)].strip()
            return caption or None
        if stripped.startswith(mark):
            caption = stripped[len(mark) :].strip()
            return caption or None
    return None


def _is_short_caption(line: TextLine, widest: float) -> bool:
    if question_caption(line.text) is None:
        return False
    return widest > 0 and line.width < widest * PROSE_CAPTION_WIDTH


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
        return reading_text(self.words)

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
    # Reading direction of the page. Everything that reasons about "before" and "after"
    # a caption depends on it, so it is decided once and passed down.
    rtl: bool = False

    @property
    def looks_like_prose(self) -> bool:
        """True when the page is instructions rather than a form to fill.

        Judged from the writing itself, not from whether anything happened to look like a
        blank. The earlier version asked "no tables and no blanks", which meant a single
        sentence ending in a colon was enough to classify an instruction sheet as a form:
        on the Kannada information page, two wrapped paragraph lines ending in ':' turned
        into two fields drawn over the text.

        An instruction sheet is recognisable before any blank is looked for. It has no
        ruled grid, and most of its lines are long, running close to the full measure of
        the page, because that is what paragraphs do. A form's lines are short captions
        with space beside them.
        """
        if self.tables:
            return False
        if len(self.text_lines) < PROSE_MIN_LINES:
            return False
        widths = sorted(line.width for line in self.text_lines)
        widest = widths[-1]
        if widest <= 0:
            return False

        # Measured against the widest line rather than the page, so the test does not
        # depend on margins or on how much of the sheet the text happens to occupy.
        # Paragraphs fill their measure, so most lines sit close to the widest; a form's
        # captions are far shorter than its longest element.
        median = widths[len(widths) // 2]

        # A page with several short captions ending in a colon is a form, whatever the
        # rest of its text looks like. Declarations and footnotes on a real form run long
        # enough to look like prose on their own.
        captions = sum(1 for line in self.text_lines if _is_short_caption(line, widest))
        if captions >= PROSE_MIN_CAPTIONS:
            return False
        if median / widest >= PROSE_LINE_SHARE:
            return True
        # An instruction sheet mixes full-width paragraphs with short bullets, so the
        # median line is short and the test above misses it. The English information
        # page was classified as a form for that reason and the shape detector then
        # drew answer boxes on the instructions. Several lines that span the page,
        # and almost no captions, is still an instruction sheet.
        long_lines = sum(1 for line in self.text_lines if line.width >= self.image_width * 0.42)
        return long_lines >= 4


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
            # A tick under a declaration sentence, with no short option beside it,
            # is the reader marking the paper. It is not a question, and reading the
            # empty space beside it only invents a caption.
            if self._is_declaration_mark(blank):
                continue
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

        # A box sitting inside a sentence is part of the printed text: the reader ticks
        # it by hand on paper. Offering an answer box for it, while a real signature line
        # goes undetected, is the wrong way round. A genuine tick box belongs to a short
        # option line, not to a paragraph.
        for line in layout.text_lines:
            if abs(line.y + line.height / 2 - centre_y) > max(blank.height, 14):
                continue
            # Judged against the page, not the longest line. A title can be the longest
            # thing on a form, and a paragraph then looks "short" beside it. That let a
            # crowd of false tick boxes through and the real declaration box was thrown
            # out with them.
            if line.width > layout.image_width * MARK_LINE_WIDTH:
                return False
            # A tick box at the end of a sentence is part of the declaration, not a
            # separate question. Kannada draws that sentence shorter than the page,
            # so width alone did not reject it.
            if len(line.text) > 48 or len(line.text.split()) > 8:
                return False

        # A tick box with nothing written beside it is not asking anything.
        for line in layout.text_lines:
            if abs(line.y + line.height / 2 - centre_y) > max(blank.height, 14):
                continue
            if abs(line.x - (blank.x + blank.width)) <= 260 or abs(blank.x - (line.x + line.width)) <= 260:
                return True
        return False

    @staticmethod
    def _is_declaration_mark(blank: Blank) -> bool:
        """A tick under a declaration, with no short option beside it, is not a field."""
        section = (blank.section or "").strip()
        nearby = (blank.nearby_text or "").strip()
        long_section = len(section) > 40 and len(section.split()) >= 6
        if long_section and len(nearby) < 2:
            return True
        if len(nearby) > 48 or len(nearby.split()) > 8:
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

        layout.rtl = ocr.rtl or is_rtl(ocr.full_text)
        horizontal, vertical = self._rules(image)
        layout.tables = self._tables(horizontal, vertical, width, height)
        self._assign_words(layout.tables, ocr, width, height)
        self._index_cells(layout.tables, layout.rtl)
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
    def _index_cells(tables: list[Table], rtl: bool = False) -> None:
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
                for column_index, cell in enumerate(sorted(row, key=lambda item: item.x, reverse=rtl)):
                    cell.row = row_index
                    cell.column = column_index
            # A header row is a top row whose cells are all text *and* leave no room to
            # write in. That last part matters: on the ECI form the row below the real
            # header reads "Elector Name: ____ | Name: ____", which is every bit as
            # "all text" as the header but is a data row with space for an answer. Using
            # free space to tell them apart stops the header being read as "Elector Name"
            # and losing that row's two fields.
            for row_index, row in enumerate(rows):
                if row_index > 0 or len(row) < 2:
                    break
                if any(cell.is_blank for cell in row):
                    break
                # A caption ending in a colon is a question, not a heading. On the real
                # form the row under the header reads "Elector Name: ____ | Name: ____",
                # which is every bit as "all text" as the header above it. Reading that
                # row as a header costs its two fields and mislabels everything below.
                if any(question_caption(cell.text) is not None for cell in row):
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
                    text=reading_text(words),
                    x=left,
                    y=top,
                    width=right - left,
                    height=bottom - top,
                    words=words,
                )
            )
        lines.sort(key=lambda item: (item.y, item.x))
        return PageStructureService._drop_double_readings(lines)

    @staticmethod
    def _drop_double_readings(lines: list[TextLine]) -> list[TextLine]:
        """Two OCR passes of one printed line were becoming two fields.

        The Kannada mobile number was read twice, a few pixels apart, and both
        readings were offered. Side-by-side captions in a comparison row do not
        overlap horizontally, so they both stay.
        """
        kept: list[TextLine] = []
        for line in lines:
            replaced = False
            for index, other in enumerate(kept):
                overlap_y = min(line.bottom, other.bottom) - max(line.y, other.y)
                if overlap_y <= min(line.height, other.height) * 0.55:
                    continue
                overlap_x = min(line.x + line.width, other.x + other.width) - max(line.x, other.x)
                if overlap_x <= min(line.width, other.width) * 0.5:
                    continue
                if PageStructureService._line_score(line) > PageStructureService._line_score(other):
                    kept[index] = line
                replaced = True
                break
            if not replaced:
                kept.append(line)
        kept.sort(key=lambda item: (item.y, item.x))
        return kept

    @staticmethod
    def _line_score(line: TextLine) -> float:
        confidences = [word.confidence for word in line.words if word.confidence > 0]
        mean = sum(confidences) / len(confidences) if confidences else 0.0
        return mean + min(len(line.text), 40) * 0.15

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
                stacked = self._stacked_blanks(cell, layout)
                if stacked:
                    blanks.extend(stacked)
                    continue
                if self._has_blank_sibling(table, cell, layout.rtl):
                    # The row already provides a separate empty cell for the answer, so
                    # the leftover space beside this caption is just padding.
                    continue
                inline = self._inline_blank(cell, layout.rtl)
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
        if layout.looks_like_prose:
            # An instruction sheet. A sentence that happens to end in a colon is not an
            # invitation to write, and a field drawn over a paragraph is worse than no
            # field at all.
            logger.debug("page %s reads as prose; not looking for free blanks", layout.page_index)
            return blanks
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
            # A signature line is a place to sign whether or not the form left much room
            # under it. Requiring a wide gap found the officer's signature block at the
            # foot of the page, where there is nothing below, and missed the elector's own
            # a few lines above, where the next paragraph follows closely -- the one place
            # on the form the applicant certainly has to write.
            if gap < max(line.height * 0.8, MIN_BLANK_H):
                continue
            height = max(MIN_BLANK_H, min(int(gap) - 6, 90))
            if self.covers_text(layout, line.x, line.bottom + 4, max(MIN_BLANK_W, line.width), height):
                continue
            if any(self._overlaps(blank, line) for blank in layout.blanks):
                continue
            blanks.append(
                Blank(
                    id=f"p{layout.page_index}-under{index}",
                    x=line.x,
                    y=line.bottom + 4,
                    width=max(MIN_BLANK_W, line.width),
                    height=height,
                    origin="space_below",
                    caption=caption,
                )
            )
        return blanks

    @staticmethod
    def covers_text(layout: PageLayout, x: int, y: int, width: int, height: int) -> bool:
        """Whether a proposed writing area lands on top of printed words.

        A blank is somewhere to write, which means somewhere nothing is already written.
        Anything overlapping a line of text is a misreading -- a rule inside a paragraph,
        a gap between wrapped lines -- and drawing a field there puts an answer box over
        the form's own sentences.
        """
        right, bottom = x + width, y + height
        for line in layout.text_lines:
            for word in line.words:
                pixel = word.pixel
                if (
                    pixel.x < right
                    and pixel.x + pixel.width > x
                    and pixel.y < bottom
                    and pixel.y + pixel.height > y
                ):
                    return True
        return False

    @staticmethod
    def _overlaps(blank: Blank, line: TextLine) -> bool:
        return not (
            blank.x + blank.width < line.x
            or blank.x > line.x + line.width
            or blank.y + blank.height < line.y
            or blank.y > line.bottom
        )

    @staticmethod
    def _has_blank_sibling(table: Table, cell: Cell, rtl: bool = False) -> bool:
        """Whether this row already provides a separate cell to write the answer in.

        Only a dedicated value cell counts, which means one clearly wider than the space
        left over beside this caption. Treating any empty neighbour as the answer cell
        breaks a two-column comparison table: when OCR misses one column's caption that
        cell reads as empty, and it then cancels the *other* column's field too, so a row
        that asks two questions produces one.
        """
        free = PageStructureService._inline_blank(cell, rtl)
        free_width = free[2] if free else 0
        own_header = PageStructureService._header_text(table, cell)
        for other in table.cells:
            if other.row != cell.row or not other.is_blank:
                continue
            if other.width < MIN_BLANK_W or other.height < MIN_BLANK_H:
                continue
            after = other.x < cell.x if rtl else other.x > cell.x
            other_header = PageStructureService._header_text(table, other)
            parallel = bool(own_header and other_header and fold(own_header) != fold(other_header))
            if parallel and not after:
                continue
            if parallel:
                # Same width as the cell holding this caption, under a different column
                # heading: the other half of a comparison table, empty only because OCR
                # missed its own caption. Cancelling this side would turn two questions
                # into one.
                if abs(other.width - cell.width) <= cell.width * SIBLING_SAME_WIDTH:
                    continue
                if free_width and other.width <= free_width * SIBLING_VALUE_MARGIN:
                    continue
            # No separate heading. Hindi, Kannada, and Urdu enumeration tables use equal
            # columns for the label and the blank. The empty cell is the answer; the gap
            # beside the label is padding, and keeping both draws two boxes for one field.
            return True
        return False

    @staticmethod
    def _header_text(table: Table, cell: Cell) -> str:
        if not table.header_rows:
            return ""
        centre = cell.x + cell.width / 2
        best = ""
        for row_index in table.header_rows:
            for other in table.cells:
                if other.row != row_index:
                    continue
                if other.x - 4 <= centre <= other.right + 4 and other.text:
                    best = other.text
        return best

    @staticmethod
    def _stacked_blanks(cell: Cell, layout: PageLayout) -> list[Blank]:
        """One writing space per caption when several questions share a cell.

        On the Hindi and Urdu enumeration forms the top band is a single ruled cell
        holding "name", "EPIC", and "address" on three lines. Treating the cell as one
        field kept one of them and lost the other two.
        """
        raw_lines = []
        for line in word_lines(cell.words):
            text = reading_text(line)
            if text.strip():
                raw_lines.append((text, line))
        # "विधानसभा/संसदीय निर्वाचन" / "क्षेत्र का नाम :" is one wrapped label.
        # A line with no colon followed by a line that has one is the wrap, not
        # a second question. Lines that all lost their colons stay separate.
        merged_lines: list[tuple[str, list]] = []
        index = 0
        while index < len(raw_lines):
            text, line = raw_lines[index]
            if (
                question_caption(text) is None
                and index + 1 < len(raw_lines)
                and question_caption(raw_lines[index + 1][0]) is not None
            ):
                next_text, next_line = raw_lines[index + 1]
                merged_lines.append((f"{text.strip()} {next_text.strip()}", list(line) + list(next_line)))
                index += 2
                continue
            merged_lines.append((text, line))
            index += 1
        questions = []
        for text, line in merged_lines:
            caption = question_caption(text)
            # The Urdu top band often loses its colons in OCR. Several short lines
            # stacked in one tall cell are still one question each, as long as the
            # line does not itself fill the cell the way a wrapped sentence does.
            if caption is None:
                stripped = text.strip().strip(":：").strip()
                width = 0
                if line:
                    width = max(word.pixel.x + word.pixel.width for word in line) - min(word.pixel.x for word in line)
                if not stripped or width > cell.width * 0.72:
                    continue
                caption = stripped
            if len(caption.split()) > MAX_CAPTION_WORDS or len(caption) > MAX_CAPTION_CHARS:
                continue
            questions.append((caption, line))
        # "نئی تصویر" / "چسپاں کریں" is one photo instruction, not two questions.
        # A cell of three colon-less lines is still three questions.
        if (
            len(questions) == 2
            and all(question_caption(text) is None for text, _line in merged_lines)
            and len(questions[0][0].split()) <= 3
            and len(questions[1][0].split()) <= 2
        ):
            return []
        if len(questions) < 2:
            return []
        blanks: list[Blank] = []
        for index, (caption, line) in enumerate(questions):
            top = min(word.pixel.y for word in line)
            bottom = max(word.pixel.y + word.pixel.height for word in line)
            height = max(MIN_BLANK_H, bottom - top)
            if layout.rtl:
                text_left = min(word.pixel.x for word in line)
                free = text_left - cell.x
                if free < MIN_BLANK_W:
                    continue
                box = (cell.x + 2, max(cell.y, top - 2), free - 8, height)
            else:
                text_right = max(word.pixel.x + word.pixel.width for word in line)
                free = cell.right - text_right
                if free < MIN_BLANK_W:
                    continue
                box = (text_right + 6, max(cell.y, top - 2), free - 8, height)
            blanks.append(
                Blank(
                    id=f"p{layout.page_index}-{cell.id}s{index}",
                    x=box[0],
                    y=box[1],
                    width=box[2],
                    height=box[3],
                    origin="inline_cell",
                    caption=caption,
                    table_index=cell.table,
                    row=cell.row,
                    column=cell.column,
                )
            )
        return blanks

    @staticmethod
    def _inline_blank(cell: Cell, rtl: bool = False) -> tuple[int, int, int, int] | None:
        """A caption and its blank sharing one cell: `Elector Name: ______`.

        The free part of the cell is where the applicant writes, and it is a field in its
        own right even though the cell is not empty. Which part is free depends on the
        script: after the caption in reading order, so to its right on a left-to-right
        page and to its **left** on an Urdu one. Measuring it the wrong way round put
        every Urdu inline blank on top of its own caption.
        """
        if not cell.words:
            return None
        if rtl:
            text_left = min(word.pixel.x for word in cell.words)
            free = text_left - cell.x
            if not PageStructureService._free_is_a_blank(cell, free):
                return None
            return (cell.x + 2, cell.y + 2, free - 8, cell.height - 4)
        text_right = max(word.pixel.x + word.pixel.width for word in cell.words)
        free = cell.right - text_right
        if not PageStructureService._free_is_a_blank(cell, free):
            return None
        return (text_right + 6, cell.y + 2, free - 8, cell.height - 4)

    @staticmethod
    def _free_is_a_blank(cell: Cell, free: float) -> bool:
        """Whether the empty part of a caption cell is somewhere to write.

        A short label needs a large share of the cell, otherwise a heading with a
        little padding becomes a field. A long label in a wide cell -- the Kannada
        EPIC line fills most of a 500px cell and still leaves a writing gap -- is a
        field when that gap can hold an answer, even if it is under a third of the cell.
        """
        if free < MIN_BLANK_W:
            return False
        # A section heading has no colon and runs to a sentence. The gap beside
        # it is padding. A label, even a long Kannada one, is shorter than that.
        caption = question_caption(cell.text)
        if caption is None and len(cell.text.split()) > 8:
            return False
        # A real question can leave only a narrow gap. The last row of the Hindi
        # enumeration form puts "constituency number :" in a 270px cell.
        if (
            caption is not None
            and len(caption.split()) <= MAX_CAPTION_WORDS
            and len(caption) <= MAX_CAPTION_CHARS
        ):
            return True
        if free >= cell.width * INLINE_BLANK_RATIO:
            return True
        caption = question_caption(cell.text) or cell.text.strip()
        long_label = len(caption) >= 24
        return long_label and free >= 100

    def _free_blanks(self, layout: PageLayout, gray: np.ndarray) -> list[Blank]:
        """Captions outside any table that end in a colon and are followed by space.

        `Applicant's Name:` has no box around it; the blank is simply the rest of the line.
        """
        blanks: list[Blank] = []
        rtl = layout.rtl
        page_right = int(layout.image_width * 0.93)
        page_left = int(layout.image_width * 0.07)
        for index, line in enumerate(layout.text_lines):
            caption = question_caption(line.text)
            if caption is None:
                continue
            # A caption is short. A sentence of prose that happens to end in a colon --
            # "provide the documents based upon the following categories:" -- is not an
            # invitation to write, and treating it as one invents fields on an
            # instruction sheet.
            if len(caption.split()) > MAX_CAPTION_WORDS or len(caption) > MAX_CAPTION_CHARS:
                continue
            # A declaration clause that happens to end in a colon is not a label.
            # On the Kannada form, "not included in any other constituency" was
            # short of the page width, so the width test let it through.
            if len(caption) > 42 and len(caption.split()) >= 4:
                continue
            # A caption shares its line with the space someone writes in, so it occupies
            # a fraction of the page. A wrapped paragraph whose last line happens to end
            # in a colon runs most of the way across. Word counts do not separate the two
            # in an agglutinative language -- a five-word Kannada sentence fills a line --
            # but the geometry does. Measured against the page, not against the longest
            # line, because on a page of nothing but captions the longest line is one.
            if line.width > layout.image_width * CAPTION_LINE_WIDTH:
                continue
            # The writing space follows the caption in reading order, which on an Urdu
            # page runs the other way: from the caption's left edge to the left margin.
            free = (line.x - page_left) if rtl else (page_right - (line.x + line.width))
            if free < MIN_BLANK_W:
                continue
            start_x = page_left if rtl else line.x + line.width + 8
            if self.covers_text(layout, start_x, line.y - 2, free - 8, max(MIN_BLANK_H, line.height + 6)):
                continue
            blanks.append(
                Blank(
                    id=f"p{layout.page_index}-line{index}",
                    x=start_x,
                    y=line.y - 2,
                    width=free - 8,
                    height=max(MIN_BLANK_H, line.height + 6),
                    origin="colon_gap",
                    caption=caption,
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
                blank.sub_header = self._sub_header(table, blank, layout.rtl)
                if not blank.caption:
                    blank.caption = self._row_caption(table, blank, layout.rtl)
                blank.row_header = self._row_caption(table, blank, layout.rtl)
            blank.section = self._section_above(layout, blank, table)
            blank.nearby_text = self._nearby(layout, blank)
            # A digital Urdu export glues the colon to the front of the first word.
            if blank.caption[:1] in ":：":
                blank.caption = blank.caption[1:].strip()

    @staticmethod
    def _sub_header(table: Table, blank: Blank, rtl: bool = False) -> str:
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
            if any(PageStructureService._inline_blank(cell, rtl) is not None for cell in row):
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
    def _row_caption(table: Table, blank: Blank, rtl: bool = False) -> str:
        """The caption that precedes a blank in reading order, within its own row.

        On a left-to-right page that is the cell to its left; on an Urdu page it is the
        cell to its right. Reading the wrong side gives every Urdu row the caption
        belonging to the next field along.
        """
        if rtl:
            candidates = [
                cell
                for cell in table.cells
                if cell.row == blank.row and cell.x >= blank.x + blank.width - 6 and not cell.is_blank
            ]
            if candidates:
                return min(candidates, key=lambda cell: cell.x).text
        else:
            candidates = [
                cell
                for cell in table.cells
                if cell.row == blank.row and cell.right <= blank.x + 6 and not cell.is_blank
            ]
            if candidates:
                return max(candidates, key=lambda cell: cell.x).text
        # One label in the row, on the other side from the one the script predicted.
        # Urdu value cells were left unnamed when the blank sat to the right of its caption.
        labelled = [cell for cell in table.cells if cell.row == blank.row and not cell.is_blank and cell.text]
        if len(labelled) == 1:
            return labelled[0].text
        return ""

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
