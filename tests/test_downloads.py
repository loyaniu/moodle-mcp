import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from moodle_mcp import downloads


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.meta = {"moduleid": 7, "module": "Slides", "section": "Week 1",
                     "filename": "slides.pdf", "filepath": "/", "filesize": 9,
                     "mimetype": "application/pdf"}
        self.url = "https://moodle.example/webservice/pluginfile.php/42/slides.pdf?forcedownload=1"
        for name, value in [("MOODLE_URL", "https://moodle.example/webservice/rest/server.php"),
                            ("MOODLE_TOKEN", "private-token")]:
            patcher = patch.object(downloads, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.files = patch.object(downloads, "_files", return_value=iter([]))

    def response(self, body=b"%PDF-test", content_type="application/pdf", status=200):
        response = Mock(status_code=status, headers={"Content-Type": content_type})
        response.iter_content.return_value = [body[:3], body[3:]]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def download(self, response):
        with patch.object(downloads, "_files", return_value=iter([(self.meta, self.url)])):
            with patch.object(downloads.requests, "get", return_value=response) as get:
                result = downloads.download_course_file(42, 7, output_dir=self.directory.name)
                self.assertFalse(get.call_args.kwargs["allow_redirects"])
                return result

    def test_authenticated_download_and_hash(self):
        result = self.download(self.response())
        self.assertEqual(Path(result["path"]).read_bytes(), b"%PDF-test")
        self.assertEqual(result["sha256"], hashlib.sha256(b"%PDF-test").hexdigest())
        self.assertNotIn("private-token", str(result))
        self.assertEqual([p.name for p in Path(self.directory.name).iterdir()], ["slides.pdf"])

    def test_no_overwrite(self):
        target = Path(self.directory.name) / "slides.pdf"
        target.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            self.download(self.response())
        self.assertEqual(target.read_bytes(), b"existing")

    def test_rejects_errors_and_partial_downloads(self):
        for response in [self.response(content_type="text/html"),
                         self.response(status=302), self.response(body=b"short"),
                         self.response(body=b'{"errorcode":"denied"}', content_type="application/json")]:
            with self.subTest(response=response):
                with self.assertRaises(RuntimeError):
                    self.download(response)
                self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_network_error_does_not_expose_token(self):
        response = self.response()
        response.iter_content.side_effect = requests.ConnectionError("private-token")
        with self.assertRaisesRegex(RuntimeError, "network error") as ctx:
            self.download(response)
        self.assertNotIn("private-token", str(ctx.exception))
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_only_moodle_file_endpoint_accepts_token(self):
        for url in ["https://evil.example/webservice/pluginfile.php/1/file",
                    "https://moodle.example/login/index.php",
                    "http://moodle.example/webservice/pluginfile.php/1/file"]:
            with self.assertRaises(ValueError):
                downloads._authenticated_url(url)
        url = downloads._authenticated_url(self.url + "&token=old")
        self.assertIn("token=private-token", url)
        self.assertNotIn("token=old", url)
        self.assertIn("forcedownload=1", url)

    def test_ambiguous_file_requires_selection(self):
        with patch.object(downloads, "_files", return_value=iter([(self.meta, self.url)] * 2)):
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                downloads.download_course_file(42, 7)

    def test_file_listing_omits_authenticated_url(self):
        sections = [{"name": "Week 1", "modules": [{"id": 7, "name": "Slides",
                    "contents": [{"type": "file", "filename": "slides.pdf",
                                  "fileurl": self.url, "filesize": 9}]}]}]
        with patch.object(downloads, "get_moodle_api_data", return_value=sections):
            result = downloads.list_course_files(42)
        self.assertEqual(result[0]["moduleid"], 7)
        self.assertNotIn("fileurl", result[0])

    def test_windows_filename_safety(self):
        self.assertEqual(downloads._safe_filename("CON.pdf"), "_CON.pdf")
        self.assertNotIn("/", downloads._safe_filename("../slides.pdf"))


if __name__ == "__main__":
    unittest.main()
