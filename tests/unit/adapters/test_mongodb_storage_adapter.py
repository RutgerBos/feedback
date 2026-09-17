"""Unit tests for MongoDB storage adapter spatial geometry."""


def test_point_in_polygon_includes_interior_and_boundary_but_excludes_exterior():
    """Polygon selection treats its edge as selected evidence."""
    from src.adapters.mongodb_storage import _point_in_polygon

    triangle = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]

    assert _point_in_polygon((0.5, 0.25), triangle)
    assert _point_in_polygon((0.25, 0.5), triangle)
    assert not _point_in_polygon((0.9, 0.9), triangle)
