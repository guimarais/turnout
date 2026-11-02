"""Run with: uv run --locked python -m unittest discover -s tests -v"""

import math
from datetime import timedelta
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

from turnout import server

OVAL = ["24130"] * 6 + ["24188"] + ["24130"] * 6 + ["24188"]


class LayoutTests(unittest.TestCase):
    def test_catalogue_includes_special_tracks(self):
        parts = {p["part_number"]: p for p in server.list_parts()}
        self.assertAlmostEqual(parts["24130"]["radius_mm"], 360, places=3)
        self.assertAlmostEqual(parts["24188"]["length_mm"], 188.3, places=3)
        self.assertIn("24612", parts)
        self.assertEqual(len(parts), 43)
        self.assertEqual(server.list_parts("24130"), [parts["24130"]])

    def test_oval_export_connections_and_dimensions(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "OUTPUT", Path(directory)):
            result = server.build_layout(OVAL)
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
            second = server.build_layout(OVAL)
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
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "OUTPUT", Path(directory)):
            for parts, kwargs, error_type in cases:
                with self.subTest(parts=len(parts), kwargs=kwargs, error_type=error_type):
                    result = server.build_layout(parts, **kwargs)
                    self.assertFalse(result["ok"])
                    self.assertIn(error_type, [e["type"] for e in result["errors"]])
                    self.assertEqual(list(Path(directory).iterdir()), [])

    def test_arc_extrema_are_included_between_endpoints(self):
        arc = server.Segment((0, 0), (0, 0), (0, 0), 10, 45, 90)
        arc.a, arc.b = arc.point(45), arc.point(135)
        self.assertIn((10.0, math.cos(math.pi / 2) * 10), arc.bounds_points())

    def test_intersections_crossings_tangencies_and_overlaps(self):
        line = server.Segment((-20, 0), (20, 0))
        vertical = server.Segment((0, -20), (0, 20))
        circle = server.Segment((0, 10), (0, 10), (0, 0), 10, 0, 360)
        self.assertEqual(server.intersections(line, vertical), [(0, 0)])
        self.assertEqual(len(server.intersections(line, circle)), 2)
        self.assertTrue(server.intersections(server.Segment((-20, 10), (20, 10)), circle))
        self.assertFalse(server.intersections(server.Segment((-20, 11), (20, 11)), circle))
        self.assertFalse(server.intersections(line, server.Segment((30, 0), (40, 0))))
        self.assertTrue(server.intersections(line, server.Segment((-10, 0), (10, 0))))
        self.assertTrue(server.intersections(circle, circle))
        other = server.Segment((10, 10), (10, 10), (10, 0), 10, 0, 360)
        self.assertEqual(len(server.intersections(circle, other)), 2)
        top = server.Segment((0, 10), (10, 0), (0, 0), 10, 0, 90)
        self.assertFalse(server.intersections(top, server.Segment((-20, -5), (20, -5))))


class InspectionTests(unittest.TestCase):
    sample = (server.ROOT / "examples/mrkln_sample.xtc").read_text()

    def inspect_text(self, text):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.xtc"
            source.write_text(text)
            before = source.read_bytes()
            with patch.object(server, "PREVIEWS", Path(directory) / "previews"):
                result = server.inspect_layout(str(source))
            self.assertEqual(source.read_bytes(), before)
            if result["ok"]:
                preview = Path(result["preview_path"])
                self.assertNotEqual(preview, source)
                svg = preview.read_text()
                from xml.etree import ElementTree
                ElementTree.fromstring(svg)
            else:
                self.assertFalse((Path(directory) / "previews").exists())
                svg = ""
            return result, svg

    def test_sample_turnout_all_segments_and_open_end_references(self):
        result, svg = self.inspect_text(self.sample)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["parts"], {"24229": 1, "24130": 2, "24612": 1})
        self.assertEqual(result["components"], [[1, 2, 3, 4]])
        self.assertEqual(result["connection_issues"], [])
        self.assertEqual({e["ref"] for e in result["open_endpoints"]}, {"3:1", "4:0", "4:2"})
        turnout = next(p for p in result["pieces"] if p["id"] == 4)
        self.assertEqual(turnout["kind"], "turnout")
        self.assertEqual(turnout["endpoints"][1]["connected_to"], "1:0")
        self.assertEqual(svg.count('data-piece-id="4"'), 4)
        self.assertIn("3:1</text>", svg)
        self.assertIn("#c65d00", svg)
        self.assertAlmostEqual(result["board_mm"][0], 2438.4)
        self.assertAlmostEqual(turnout["position_mm"][0], 275.25, places=3)
        # Endpoint coordinates in the file are already world coordinates.
        self.assertAlmostEqual(result["open_endpoints"][0]["position_mm"][0], 1004.619, places=2)

    def test_generated_and_xtrackcad_saved_ovals(self):
        for name in ("layout-_c4rr1_w.xtc", "layout-w7r0lfkz.xtc", "mrkln_sample2.xtc"):
            source = Path(__file__).parent / "fixtures" / name
            with self.subTest(source=source.name):
                result, _ = self.inspect_text(source.read_text())
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["status"], "complete")
                self.assertEqual(result["piece_count"], 14)
                self.assertEqual(result["open_endpoint_count"], 0)
                self.assertEqual(result["component_count"], 1)
                self.assertEqual(result["connection_issues"], [])
        # Also exercise the current writer without relying on saved fixtures.
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "OUTPUT", Path(directory)):
            built = server.build_layout(OVAL)
            result, _ = self.inspect_text(Path(built["path"]).read_text())
            self.assertEqual(result["open_endpoint_count"], 0)
            self.assertEqual(result["connection_issues"], [])

    def test_broken_links_are_not_open_ends_or_confirmed_connections(self):
        cases = [
            (self.sample.replace("T4 4 18.250000", "T4 999 18.250000"), "missing_neighbor"),
            (self.sample.replace("T4 1 18.250000", "T4 2 18.250000"), "nonreciprocal_link"),
            (self.sample.replace("T4 1 18.250000", "T4 1 18.350000"), "position_gap"),
            (self.sample.replace("T4 1 18.250000 39.125000 90.000000", "T4 1 18.250000 39.125000 95.000000"), "angle_mismatch"),
        ]
        for text, expected in cases:
            with self.subTest(expected=expected):
                report, svg = self.inspect_text(text)
                self.assertTrue(report["ok"], report)
                self.assertIn(expected, [issue["type"] for issue in report["connection_issues"]])
                self.assertEqual(report["open_endpoint_count"], 3)
                self.assertGreater(report["component_count"], 1)
                self.assertIn("#dc2626", svg)

    def test_ambiguous_links_are_not_guessed(self):
        first = self.sample.index('\tT4 1 18.250000')
        end = self.sample.index('\n', first)
        text = self.sample[:end] + "\n" + self.sample[first:end] + self.sample[end:]
        report, _ = self.inspect_text(text)
        self.assertIn("ambiguous_link", [i["type"] for i in report["connection_issues"]])

    def test_nearby_open_ends_stay_open(self):
        text = self.sample.replace('T4 4 18.250000', 'E4 18.250000').replace('T4 1 18.250000', 'E4 18.250000')
        result, _ = self.inspect_text(text)
        self.assertEqual(result["open_endpoint_count"], 5)
        self.assertEqual(result["component_count"], 2)
        self.assertEqual(result["connection_issues"], [])

    def test_unsupported_records_make_partial_results_explicit(self):
        cases = [self.sample.replace('END$TRACKS', 'MYSTERY 99\n\tS 0 0 0 0 1 1\n\tEND$SEGS\nEND$TRACKS'),
                 self.sample.replace('\tD 0.000000', '\tUNKNOWN 1 2\n\tD 0.000000', 1)]
        for text in cases:
            report, svg = self.inspect_text(text)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["status"], "incomplete")
            self.assertFalse(report["topology_complete"])
            self.assertEqual(report["piece_count"], 4)
            self.assertTrue(report["warnings"])
            self.assertIn("INCOMPLETE", svg)
        report, _ = self.inspect_text(self.sample.replace('T4 4 ', 'T3 4 ', 1))
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["pieces"][0]["endpoints"][0]["ref"], "1:1")
        report, _ = self.inspect_text(self.sample.replace('T4 ', 'T3 ').replace('E4 ', 'E3 '))
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["open_endpoint_count"], 0)
        report, svg = self.inspect_text(self.sample.replace('VERSION 12', 'VERSION 99'))
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["piece_count"], 0)
        self.assertEqual(report["warnings"][0]["record"], "VERSION")
        self.assertIn("Board: dimensions unavailable", svg)

    def test_malformed_records_return_errors_without_previews(self):
        cases = [self.sample.replace('END$TRACKS', ''),
                 self.sample.replace('\tEND$SEGS', '', 1),
                 self.sample.replace('TURNOUT  2 ', 'TURNOUT  1 '),
                 self.sample.replace('96.000000 x', 'nan x'),
                 self.sample.replace('18.250000 39.125000 270.000000', 'nan 39.125000 270.000000', 1),
                 self.sample.replace('E4 39.551934 46.211615 30.000000', 'E4 39.551934 46.211615', 1),
                 self.sample.replace('P "Normal" 1', 'P "Normal" 99', 1),
                 self.sample.replace('TITLE1 mcptest', 'TITLE1 null\x00byte')]
        for case, text in enumerate(cases):
            self.assertNotEqual(text, self.sample)
            with self.subTest(case=case):
                report, _ = self.inspect_text(text)
                self.assertFalse(report["ok"], report)
                self.assertTrue(report["errors"][0]["message"])

    def test_missing_file_and_wrong_extension(self):
        for path in ('does-not-exist.xtc', 'README.md'):
            report = server.inspect_layout(path)
            self.assertFalse(report["ok"])

    def test_svg_escapes_file_labels(self):
        text = self.sample.replace('TITLE1 mcptest', 'TITLE1 <script>alert(1)</script> & title')
        report, svg = self.inspect_text(text)
        self.assertTrue(report["ok"], report)
        self.assertNotIn('<script>', svg)
        self.assertIn('&lt;script&gt;', svg)


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_module_launcher_from_outside_checkout(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=sys.executable, args=["-m", "turnout"], cwd=tempfile.gettempdir())
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=10)) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.assertEqual({t.name for t in tools.tools}, {"list_parts", "build_layout", "inspect_layout", "attach_track"})
                catalogue = await session.call_tool("list_parts", {"query": "24130"})
                self.assertFalse(catalogue.isError)
                result = await session.call_tool("build_layout", {"parts": OVAL})
                self.assertFalse(result.isError)
                data = result.structuredContent
                self.assertTrue(data["ok"], data)
                path = Path(data["path"])
                try:
                    self.assertEqual(path.parent, server.OUTPUT)
                    self.assertTrue(path.is_file())
                    self.assertEqual(data["piece_count"], 14)
                finally:
                    if path.parent == server.OUTPUT:
                        path.unlink(missing_ok=True)
                inspected = await session.call_tool("inspect_layout", {"path": "examples/mrkln_sample.xtc"})
                self.assertFalse(inspected.isError)
                report = inspected.structuredContent
                preview = Path(report["preview_path"])
                try:
                    self.assertEqual(report["piece_count"], 4)
                    self.assertEqual(report["open_endpoint_count"], 3)
                    self.assertEqual(report["status"], "complete")
                    self.assertEqual(preview.parent, server.PREVIEWS)
                finally:
                    if preview.parent == server.PREVIEWS:
                        preview.unlink(missing_ok=True)
                invalid = await session.call_tool("build_layout", {"parts": ["not-a-part"] * 3})
                self.assertFalse(invalid.structuredContent["ok"])
                attached = await session.call_tool("attach_track", {
                    "path": "examples/mrkln_sample.xtc", "endpoint": "4:2", "part_number": "24188"})
                self.assertFalse(attached.isError)
                data = attached.structuredContent
                self.assertTrue(data["ok"], data)
                try:
                    self.assertEqual(data["changes"]["added_piece_ids"], [5])
                    self.assertEqual(data["connection_issues"], [])
                finally:
                    Path(data["path"]).unlink(missing_ok=True)
                    Path(data["preview_path"]).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
