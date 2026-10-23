"""Utility helpers.

Deliberately empty: re-exporting from here created an import cycle
(app.utils -> bounding_boxes -> app.models -> ocr -> app.utils). Import the submodule you
need directly, which is what every caller already does.
"""
