"""Geometry utilities for cleaning and grouping linework."""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, isclose
from typing import Iterable, List, Sequence, Tuple, Union

from .pdf_processor import Segment


@dataclass
class Polyline:
    points: List[Tuple[float, float]]

    def to_segments(self) -> List[Segment]:
        return list(zip(self.points[:-1], self.points[1:]))


def _segment_length(segment: Segment) -> float:
    (x0, y0), (x1, y1) = segment
    return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5


def filter_short_segments(segments: Sequence[Segment], min_length: float) -> List[Segment]:
    return [segment for segment in segments if _segment_length(segment) >= min_length]


def _angle(segment: Segment) -> float:
    (x0, y0), (x1, y1) = segment
    return degrees(atan2(y1 - y0, x1 - x0))


def snap_angle(angle: float, snap_increment: float = 45.0) -> float:
    return round(angle / snap_increment) * snap_increment


def snap_segment_angles(segments: Sequence[Segment], snap_increment: float = 45.0) -> List[Segment]:
    snapped: List[Segment] = []
    for segment in segments:
        (x0, y0), (x1, y1) = segment
        angle = _angle(segment)
        snapped_angle = snap_angle(angle, snap_increment)
        length = _segment_length(segment)
        rad = snapped_angle * 3.1415926535 / 180.0
        x1_snapped = x0 + length * float(round(math_cos(rad), 6))
        y1_snapped = y0 + length * float(round(math_sin(rad), 6))
        snapped.append(((x0, y0), (x1_snapped, y1_snapped)))
    return snapped


def math_cos(value: float) -> float:
    # Split out to avoid importing math globally which simplifies testing.
    from math import cos

    return cos(value)


def math_sin(value: float) -> float:
    from math import sin

    return sin(value)


Tolerance = Union[float, Tuple[float, float]]


def _tolerance_components(tolerance: Tolerance) -> Tuple[float, float]:
    if isinstance(tolerance, tuple):
        return tolerance
    return (tolerance, tolerance)


def group_segments_into_polylines(segments: Sequence[Segment], tolerance: Tolerance = 2.0) -> List[Polyline]:
    polylines: List[Polyline] = []
    remaining = list(segments)
    tol_x, tol_y = _tolerance_components(tolerance)

    while remaining:
        current = remaining.pop()
        polyline_points = [current[0], current[1]]
        changed = True
        while changed:
            changed = False
            for other in list(remaining):
                if _join_if_close(polyline_points, other, tol_x, tol_y):
                    remaining.remove(other)
                    changed = True
        polylines.append(Polyline(points=polyline_points))
    return polylines


def _join_if_close(points: List[Tuple[float, float]], segment: Segment, tol_x: float, tol_y: float) -> bool:
    start, end = segment
    if _points_close(points[-1], start, tol_x, tol_y):
        points.append(end)
        return True
    if _points_close(points[-1], end, tol_x, tol_y):
        points.append(start)
        return True
    if _points_close(points[0], end, tol_x, tol_y):
        points.insert(0, start)
        return True
    if _points_close(points[0], start, tol_x, tol_y):
        points.insert(0, end)
        return True
    return False


def _points_close(a: Tuple[float, float], b: Tuple[float, float], tol_x: float, tol_y: float) -> bool:
    return isclose(a[0], b[0], abs_tol=tol_x) and isclose(a[1], b[1], abs_tol=tol_y)


def segments_from_polylines(polylines: Iterable[Polyline]) -> List[Segment]:
    segments: List[Segment] = []
    for polyline in polylines:
        segments.extend(polyline.to_segments())
    return segments
