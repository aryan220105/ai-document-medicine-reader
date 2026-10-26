"""Turns a measured page layout into the fields the rest of the application works with.

Keeps two sources of candidates and merges them:

* the page structure, which understands ruled tables, cells that hold a caption and a
  blank together, and captions followed by writing space;
* the original shape detector, which finds tick boxes, free-standing boxes and ruled
  lines on forms that have no table at all.

Neither alone is enough. The structure analysis is what makes a ruled government form
work; the shape detector is what makes an unruled one work. Where both describe the same
place on the page, the structural reading wins, because it is the one that carries the
captions and column headers.
"""

from __future__ import annotations

import logging

from app.models.common import FieldType
from app.models.fields import DetectedField
from app.services.page_structure_service import Blank, PageLayout, PageStructureService
from app.utils.bounding_boxes import iou, normalize_box

logger = logging.getLogger(__name__)

# How a blank's shape maps to an input type before anything is known about its meaning.
ORIGIN_TYPES = {
    "mark": FieldType.CHECKBOX,
    "table_cell": FieldType.TEXT,
    "inline_cell": FieldType.TEXT,
    "colon_gap": FieldType.TEXT,
    "ruled_line": FieldType.TEXT,
    "space_below": FieldType.SIGNATURE,
}

OVERLAP_SAME_PLACE = 0.3


class FieldAssemblyService:
    def build(
        self,
        layout: PageLayout,
        legacy: list[DetectedField],
        page_index: int,
    ) -> list[DetectedField]:
        """Tick boxes are not passed here; they reach the layout through
        `PageStructureService.add_marks`, which is where an implausible set is rejected.
        """
        fields = [self._from_blank(blank, layout, page_index) for blank in layout.blanks]
        if not layout.tables:
            # The shape detector earns its place on an unruled form, where there is no
            # grid to read. On a ruled one it only adds noise: run against a government
            # form whose structure was already understood, it contributed twenty-two
            # spurious boxes, most of them slices of the title text.
            #
            # Even here, anything it proposes on top of printed words is discarded. A
            # blank is somewhere to write, so it cannot be somewhere already written: its
            # underline detector finds rules inside dense paragraphs and those became
            # answer boxes drawn across the form's own sentences.
            usable = [field for field in legacy if not self._covers_text(field, layout)]
            if len(usable) < len(legacy):
                logger.debug(
                    "page %s: dropped %s shape candidates that lay over text",
                    page_index,
                    len(legacy) - len(usable),
                )
            fields.extend(self._merge_in(usable, fields))
        else:
            logger.debug("page %s is ruled; shape detector results not merged", page_index)
        fields.sort(key=lambda item: (item.page_index, item.input_box.y, item.input_box.x))
        return fields

    @staticmethod
    def _from_blank(blank: Blank, layout: PageLayout, page_index: int) -> DetectedField:
        pixel = blank.to_pixel(layout.image_width, layout.image_height, page_index)
        field_type = ORIGIN_TYPES.get(blank.origin, FieldType.TEXT)
        if field_type is FieldType.TEXT and blank.height > layout.image_height * 0.05:
            field_type = FieldType.MULTILINE
        # A caption on its own line with the rest of the line free is usually one line of
        # writing; a tall cell is not.
        # A cell with no caption of its own is named by the heading above its column.
        # On the ECI form the six narrow cells under "AC Number | Part No. | Sr No." have
        # nothing written in them, and the strip above is the only thing that names them.
        label = blank.caption or blank.sub_header or blank.column_header
        return DetectedField(
            id=blank.id,
            page_index=page_index,
            label=label,
            field_type=field_type,
            input_box=normalize_box(pixel),
            confidence=0.86 if blank.caption else (0.74 if label else 0.62),
            confidence_reasons=[f"structure:{blank.origin}"],
            caption=blank.caption,
            column_header=blank.column_header,
            sub_header=blank.sub_header,
            section_hint=blank.section,
            structure_origin=blank.origin,
        )

    @staticmethod
    def _covers_text(field: DetectedField, layout: PageLayout) -> bool:
        pixel = field.input_box.to_pixel(layout.image_width, layout.image_height)
        return PageStructureService.covers_text(layout, pixel.x, pixel.y, pixel.width, pixel.height)

    @staticmethod
    def _merge_in(extra: list[DetectedField], existing: list[DetectedField]) -> list[DetectedField]:
        kept: list[DetectedField] = []
        for candidate in extra:
            if any(iou(candidate.input_box, field.input_box) >= OVERLAP_SAME_PLACE for field in existing + kept):
                continue
            kept.append(candidate)
        return kept
