"""Geometry rules shared by triad submission and spatial exploration."""


def is_point_in_triad_triangle(x: float, y: float) -> bool:
    """Match normalized vertices (0.5, 0), (0, 1), and (1, 1), including edges."""
    return 0 <= y <= 1 and 0 <= x <= 1 and abs(x - 0.5) <= y / 2
