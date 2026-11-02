"""Catalogue-wide attachment and preservation regressions."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from turnout import server


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ("OUTPUT", "PREVIEWS"):
            patcher = patch.object(server, name, self.root / name.lower())
            patcher.start()
            self.addCleanup(patcher.stop)
        self.source = self.root / "input.xtc"
        self.source.write_bytes((server.ROOT / "examples/mrkln_sample.xtc").read_bytes())

    def seed(self, origin=(4000, 4000), angle=0):
        part = server.load_catalogue()["24064"]
        self.source.write_text(server.layout_header(10000, 10000)
                               + server.piece_text(part, 7, origin, angle)
                               + "END$TRACKS\n")

    def test_every_catalogue_piece_and_entry_can_attach_and_be_reinspected(self):
        parts = server.load_catalogue()
        self.assertEqual(len(parts), 43)
        self.assertEqual(parts["24624"].options, 512)
        self.assertIn('P "Normal" 1 0 2', parts["24640"].rows)
        self.seed()
        for number, part in parts.items():
            for entry in range(len(part.ends)):
                with self.subTest(number=number, entry=entry):
                    result = server.attach_track(str(self.source), "7:1", number, entry)
                    self.assertTrue(result["ok"], result)
                    report = server.inspect_layout(result["path"])
                    self.assertEqual(report["status"], "complete", report)
                    self.assertEqual(report["track_system"]["catalogue"], "mrklnhoc-de.xtp")
                    self.assertEqual(report["connection_issues"], [])
                    self.assertEqual(report["components"], [[7, 8]])
                    added = next(p for p in report["pieces"] if p["id"] == 8)
                    if number == "24624":
                        self.assertEqual(added["kind"], "turnout")
                    elif number == "24640":
                        self.assertEqual(added["kind"], "crossing")
                    self.assertEqual(report["open_endpoint_count"], len(part.ends))
                    self.assertEqual(result["changes"]["parts_delta"], {number: 1})
                    self.assertEqual(len(result["changes"]["new_open_endpoints"]), len(part.ends) - 1)
                    Path(result["path"]).unlink()
                    Path(result["preview_path"]).unlink()
                    Path(report["preview_path"]).unlink()

    def test_preserves_bytes_positions_and_supports_repeated_extension(self):
        original = self.source.read_bytes()
        original = b"\xef\xbb\xbf" + original.replace(b"TITLE1 mcptest", b"# keep this comment exactly\nTITLE1 mcptest").replace(b"\n", b"\r\n")
        self.source.write_bytes(original)
        result = server.attach_track(str(self.source), "4:2", "24188")
        self.assertTrue(result["ok"], result)
        revision = Path(result["path"]).read_bytes()
        # Removing the insertion and restoring the single endpoint gives exact source bytes.
        start = revision.index(b"TURNOUT 5 ")
        end = revision.index(b"END$TRACKS", start)
        restored = (revision[:start] + revision[end:]).replace(b"T4 5 17.924706", b"E4 17.924706", 1)
        self.assertEqual(restored, original)
        self.assertEqual(self.source.read_bytes(), original)
        before, _ = server.read_layout(original.decode("utf-8-sig"))
        after, _ = server.read_layout(revision.decode("utf-8-sig"))
        for a, b in zip(before["pieces"], after["pieces"]):
            self.assertEqual(a["position_mm"], b["position_mm"])
            self.assertEqual(a["rotation_deg"], b["rotation_deg"])
        terminal = server.attach_track(result["path"], "5:1", "24978")
        self.assertTrue(terminal["ok"], terminal)
        self.assertEqual(terminal["changes"]["new_open_endpoints"], [])
        self.assertEqual(Path(result["path"]).read_bytes(), revision)
        self.assertEqual(terminal["open_endpoint_count"], 2)

    def test_system_resolution_never_guesses_or_permits_mixed_track(self):
        catalogue_dir = self.root / "catalogues"
        catalogue_dir.mkdir()
        original = server.CATALOGUE.read_text()
        (catalogue_dir / "one.xtp").write_text(original)
        (catalogue_dir / "two.xtp").write_text(original)
        with patch.object(server, "CATALOGUES", catalogue_dir):
            result = server.attach_track(str(self.source), "4:2", "24188")
            self.assertFalse(result["ok"])
            self.assertEqual(result["track_system"]["candidates"], ["one.xtp", "two.xtp"])
            result = server.attach_track(str(self.source), "4:2", "24188", catalogue="one.xtp")
            self.assertTrue(result["ok"], result)
            (catalogue_dir / "one.xtp").write_text(original.replace('TURNOUT HO "Märklin C-Gleis\tGerade 188.3mm', 'TURNOUT N "Märklin C-Gleis\tGerade 188.3mm'))
            result = server.attach_track(str(self.source), "4:2", "24188", catalogue="one.xtp")
            self.assertFalse(result["ok"])
            for mutation in (original.replace("\t24229\"", "\tforeign-part\""), original.replace("Märklin", "Other")):
                (catalogue_dir / "one.xtp").write_text(mutation)
                result = server.attach_track(str(self.source), "4:2", "24188", catalogue="one.xtp")
                self.assertFalse(result["ok"])
        self.assertFalse(server.attach_track(str(self.source), "4:2", "24188", catalogue="../outside.xtp")["ok"])

    def test_bad_requests_do_not_write_outputs(self):
        cases = [dict(endpoint="1:0"), dict(endpoint="4:99"), dict(endpoint="bogus"),
                 dict(entry_endpoint=-1), dict(entry_endpoint=2), dict(entry_endpoint=True),
                 dict(part_number="no-such-part"), dict(catalogue="missing.xtp")]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                args = dict(path=str(self.source), endpoint="4:2", part_number="24188")
                args.update(kwargs)
                self.assertFalse(server.attach_track(**args)["ok"])
        self.assertFalse(server.OUTPUT.exists())
        self.assertFalse(server.PREVIEWS.exists())

    def test_incomplete_broken_and_altered_inputs_are_rejected(self):
        sample = self.source.read_text()
        for text in (sample.replace("END$TRACKS", "MYSTERY 1\nEND$TRACKS"),
                     sample.replace("T4 4 18.250000", "T4 999 18.250000"),
                     sample.replace("9.027559 0.000000", "9.500000 0.000000"),
                     sample.replace("SCALE HO", "SCALE N"),
                     sample.replace('P "Normal" 1', 'P "Normal" 0 1', 1)):
            with self.subTest(text=text[-50:]):
                self.source.write_text(text)
                self.assertFalse(server.attach_track(str(self.source), "4:2", "24188")["ok"])
        self.assertFalse(server.OUTPUT.exists())
        self.assertFalse(server.PREVIEWS.exists())

    def test_overflow_collision_and_reversed_curve(self):
        result = server.attach_track(str(self.source), "3:1", "24188")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["errors"][0]["type"], "boundary")
        self.seed()
        text = self.source.read_text()
        part = server.load_catalogue()["24064"]
        # A second unconnected piece occupies the proposed extension.
        blocker = server.piece_text(part, 90, (4064.3, 4000), 0)
        self.source.write_text(text.replace("END$TRACKS", blocker + "END$TRACKS"))
        result = server.attach_track(str(self.source), "7:1", "24188")
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["type"], "intersection")
        self.assertFalse(server.OUTPUT.exists())
        self.seed()
        result = server.attach_track(str(self.source), "7:1", "24130", 1)
        self.assertTrue(result["ok"], result)
        report = server.inspect_layout(result["path"])
        added = next(p for p in report["pieces"] if p["id"] == 8)
        self.assertLess(added["endpoints"][0]["position_mm"][1], 4000)

    def test_malformed_polygons_and_paths_fail_safely(self):
        part = server.load_catalogue()["24978"]
        text = server.layout_header() + server.piece_text(part, 1, (500, 500), 0) + "END$TRACKS\n"
        for malformed in (text.replace("F3 8421504 0.026667 4", "F3 8421504 0.026667 5"),
                          text.replace("1.653333 -0.769333 0", "nan -0.769333 0"),
                          text.replace('P "Normal" 1', 'P "Normal" 2')):
            self.source.write_text(malformed)
            self.assertFalse(server.inspect_layout(str(self.source))["ok"])
            self.assertFalse(server.attach_track(str(self.source), "1:0", "24188")["ok"])

    def test_representative_compatibility_fixture(self):
        result = server.inspect_layout(str(Path(__file__).parent / "fixtures/connected-track-families.xtc"))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["track_system"]["status"], "matched")
        self.assertEqual(result["piece_count"], 22)
        self.assertEqual(result["component_count"], 11)
        self.assertEqual(result["connection_issues"], [])


if __name__ == "__main__":
    unittest.main()
