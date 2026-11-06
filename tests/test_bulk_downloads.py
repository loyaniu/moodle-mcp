import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from moodle_mcp import downloads


class BulkTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.meta = {"moduleid": 7, "module": "Slides", "section": "Week 1",
                     "filename": "slides.pdf", "filepath": "/", "filesize": 3,
                     "mimetype": "application/pdf", "timemodified": 1}
        self.items = [(self.meta, "https://example/webservice/pluginfile.php/42/test?token=secret")]

    def fake_download(self, meta, url, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"abc")
        return {"path": str(destination), "filename": meta["filename"],
                "bytes_written": 3, "sha256": downloads._hash_file(destination),
                "mimetype": "application/pdf"}

    def run_bulk(self):
        with patch.object(downloads, "_files", return_value=iter(self.items)) as listing:
            with patch.object(downloads, "_download_file", side_effect=self.fake_download):
                result = downloads.download_course_files(42, self.directory.name)
        listing.assert_called_once_with(42)
        return result

    def test_resume_skips_verified_files_and_has_no_token(self):
        first = self.run_bulk()
        self.assertEqual(first["downloaded"], 1)
        second = self.run_bulk()
        self.assertEqual(second["skipped"], 1)
        manifest = Path(self.directory.name) / "moodle-downloads.json"
        self.assertNotIn("secret", manifest.read_text())

    def test_updated_source_keeps_old_file(self):
        first = self.run_bulk()
        self.meta["timemodified"] = 2
        second = self.run_bulk()
        self.assertEqual(second["downloaded"], 1)
        self.assertNotEqual(first["files"][0]["path"], second["files"][0]["path"])
        self.assertTrue(Path(first["files"][0]["path"]).is_file())

    def test_local_edits_are_preserved(self):
        first = self.run_bulk()
        path = Path(first["files"][0]["path"])
        path.write_bytes(b"local changes")
        second = self.run_bulk()
        self.assertEqual(second["downloaded"], 1)
        self.assertEqual(path.read_bytes(), b"local changes")

    def test_duplicate_names_in_different_folders(self):
        self.items.append((dict(self.meta, filepath="/sub/"), "https://example/other"))
        result = self.run_bulk()
        self.assertEqual(result["downloaded"], 2)
        self.assertNotEqual(result["files"][0]["path"], result["files"][1]["path"])

    def test_partial_failure_continues_and_can_resume(self):
        self.items.append((dict(self.meta, moduleid=8), "https://example/other"))
        def fail_one(meta, url, destination):
            if meta["moduleid"] == 7:
                raise RuntimeError("Download rejected")
            return self.fake_download(meta, url, destination)
        with patch.object(downloads, "_files", return_value=iter(self.items)):
            with patch.object(downloads, "_download_file", side_effect=fail_one):
                result = downloads.download_course_files(42, self.directory.name)
        self.assertEqual((result["downloaded"], result["failed"]), (1, 1))
        retry = self.run_bulk()
        self.assertEqual((retry["downloaded"], retry["skipped"], retry["failed"]), (1, 1, 0))

    def test_other_course_manifest_rejected(self):
        self.run_bulk()
        with patch.object(downloads, "_files", return_value=iter([])):
            with self.assertRaisesRegex(ValueError, "another course"):
                downloads.download_course_files(43, self.directory.name)
