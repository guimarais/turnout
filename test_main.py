"""Run with: uv run python -m unittest -v"""

import math
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import main

OVAL = ["24130"] * 6 + ["24188"] + ["24130"] * 6 + ["24188"]


class LayoutTests(unittest.TestCase):
    def test_catalogue_filters_special_tracks(self):
        parts = {p["part_number"]: p for p in main.list_parts()}
        self.assertAlmostEqual(parts["24130"]["radius_mm"], 360, places=3)
        self.assertAlmostEqual(parts["24188"]["length_mm"], 188.3, places=3)
        self.assertNotIn("24612", parts)
        self.assertEqual(main.list_parts("24130"), [parts["24130"]])

    def test_oval_export_connections_and_dimensions(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "OUTPUT", Path(directory)):
            result = main.build_layout(OVAL)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["parts"], {"24130": 12, "24188": 2})
            self.assertLess(result["closure_gap_mm"], 0.001)
            self.assertAlmostEqual(result["centreline_footprint_mm"][0], 908.3, places=3)
            self.assertAlmostEqual(result["centreline_footprint_mm"][1], 720, places=3)
            text = Path(result["path"]).read_text()
            self.assertIn("L3 8421376 0.030000 0.000000 0.787400 0 7.413386 0.787400 0", text)
            self.assertIn("A3 8421376 0.030000 -13.385828 0.000000 14.173228 0 150.000000 30.000000", text)
            self.assertTrue(text.endswith("END$TRACKS\n"))
            # Read exported records independently: reciprocal links, distances and
            # opposing tangents must survive conversion to six-decimal inches.
            tracks = {}
            current = None
            for line in text.splitlines():
                fields = line.split()
                if fields and fields[0] == "TURNOUT":
                    current = int(fields[1])
                    tracks[current] = []
                elif fields and fields[0] == "T4":
                    tracks[current].append((int(fields[1]), *map(float, fields[2:5])))
            self.assertEqual(len(tracks), 14)
            for index, ends in tracks.items():
                self.assertEqual(len(ends), 2)
                for neighbor, x, y, angle in ends:
                    matches = [e for e in tracks[neighbor] if e[0] == index]
                    self.assertEqual(len(matches), 1)
                    _, nx, ny, na = matches[0]
                    self.assertLess(math.hypot(nx - x, ny - y) * 25.4, 0.001)
                    self.assertAlmostEqual((angle - na) % 360, 180, places=4)
                    self.assertTrue(50 <= x * 25.4 <= 1950)
                    self.assertTrue(50 <= y * 25.4 <= 1150)
            second = main.build_layout(OVAL)
            self.assertNotEqual(result["path"], second["path"])
            self.assertEqual(Path(result["path"]).read_text(), text)

    def test_invalid_designs_write_nothing(self):
        cases = [([], {}, "parts"), (["24612"] * 3, {}, "unsupported_parts"),
                 (["24130"] * 11 + ["24188"], {}, "closure"),
                 (["24130"] * 13, {}, "closure"),
                 (OVAL, {"width_mm": 900}, "boundary"),
                 (OVAL, {"height_mm": 800}, "boundary"),
                 (OVAL, {"width_mm": float("nan")}, "board"),
                 (OVAL, {"height_mm": float("inf")}, "board"),
                 (["24130"] * 24, {}, "intersection")]
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "OUTPUT", Path(directory)):
            for parts, kwargs, error_type in cases:
                with self.subTest(parts=len(parts), kwargs=kwargs, error_type=error_type):
                    result = main.build_layout(parts, **kwargs)
                    self.assertFalse(result["ok"])
                    self.assertIn(error_type, [e["type"] for e in result["errors"]])
                    self.assertEqual(list(Path(directory).iterdir()), [])

    def test_arc_extrema_are_included_between_endpoints(self):
        arc = main.Segment((0, 0), (0, 0), (0, 0), 10, 45, 90)
        arc.a, arc.b = arc.point(45), arc.point(135)
        self.assertIn((10.0, math.cos(math.pi / 2) * 10), arc.bounds_points())

    def test_intersections_crossings_tangencies_and_overlaps(self):
        line = main.Segment((-20, 0), (20, 0))
        vertical = main.Segment((0, -20), (0, 20))
        circle = main.Segment((0, 10), (0, 10), (0, 0), 10, 0, 360)
        self.assertEqual(main.intersections(line, vertical), [(0, 0)])
        self.assertEqual(len(main.intersections(line, circle)), 2)
        self.assertTrue(main.intersections(main.Segment((-20, 10), (20, 10)), circle))
        self.assertFalse(main.intersections(main.Segment((-20, 11), (20, 11)), circle))
        self.assertFalse(main.intersections(line, main.Segment((30, 0), (40, 0))))
        self.assertTrue(main.intersections(line, main.Segment((-10, 0), (10, 0))))
        self.assertTrue(main.intersections(circle, circle))
        other = main.Segment((10, 10), (10, 10), (10, 0), 10, 0, 360)
        self.assertEqual(len(main.intersections(circle, other)), 2)
        top = main.Segment((0, 10), (10, 0), (0, 0), 10, 0, 90)
        self.assertFalse(main.intersections(top, main.Segment((-20, -5), (20, -5))))


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_client(self):
        import sys
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=sys.executable, args=[str(main.ROOT / "main.py")])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=10)) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.assertEqual({t.name for t in tools.tools}, {"list_parts", "build_layout"})
                catalogue = await session.call_tool("list_parts", {"query": "24130"})
                self.assertFalse(catalogue.isError)
                result = await session.call_tool("build_layout", {"parts": OVAL})
                self.assertFalse(result.isError)
                data = result.structuredContent
                self.assertTrue(data["ok"], data)
                path = Path(data["path"])
                try:
                    self.assertEqual(path.parent, main.OUTPUT)
                    self.assertTrue(path.is_file())
                    self.assertEqual(data["piece_count"], 14)
                finally:
                    if path.parent == main.OUTPUT:
                        path.unlink(missing_ok=True)
                invalid = await session.call_tool("build_layout", {"parts": ["not-a-part"] * 3})
                self.assertFalse(invalid.structuredContent["ok"])


if __name__ == "__main__":
    unittest.main()
