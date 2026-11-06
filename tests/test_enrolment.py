import asyncio
import unittest
from unittest.mock import Mock, patch

import requests

from moodle_mcp import enrolment
from moodle_mcp.moodle import APIFunction, MoodleAPIError, get_moodle_api_data
from moodle_mcp.server import mcp


class EnrolmentTests(unittest.TestCase):
    @patch("moodle_mcp.enrolment.get_moodle_api_data")
    def test_catalogue_search_includes_unenrolled_and_pagination(self, call):
        call.return_value = {"courses": [{"id": 42, "fullname": "Example",
                               "enrollmentmethods": ["self"]}], "total": 51}
        result = enrolment.search_courses(" Example ", page=2, perpage=10)
        self.assertEqual(result["total"], 51)
        self.assertEqual(result["courses"][0]["enrollmentmethods"], ["self"])
        self.assertEqual(call.call_args.kwargs["params"], {
            "criterianame": "search", "criteriavalue": "Example", "page": 2,
            "perpage": 10, "limittoenrolled": 0})

    @patch("moodle_mcp.enrolment.get_moodle_api_data")
    def test_invalid_input_never_calls_moodle(self, call):
        for args in [(" ", 0, 20), ("x", -1, 20), ("x", 0, 0), ("x", 0, 101)]:
            with self.assertRaises(ValueError):
                enrolment.search_courses(*args)
        with self.assertRaises(ValueError):
            enrolment.self_enrol_course(0)
        with self.assertRaises(ValueError):
            enrolment.self_enrol_course(42, instanceid=0)
        call.assert_not_called()

    @patch("moodle_mcp.enrolment.get_moodle_api_data")
    def test_key_requirement_and_multiple_instances(self, call):
        method = {"id": 7, "courseid": 42, "type": "self",
                  "name": "Students", "status": True}
        call.return_value = [method, dict(method, id=8)]
        self.assertEqual(len(enrolment.get_course_enrolment_methods(42)), 2)
        call.return_value = dict(method, enrolpassword=True)
        info = enrolment.get_self_enrolment_info(7)
        self.assertTrue(info["requires_key"])
        self.assertNotIn("enrolpassword", info)

    @patch("moodle_mcp.enrolment.get_moodle_api_data")
    def test_failed_enrolment_is_not_reported_as_success(self, call):
        warnings = [{"warningcode": "4", "message": "Invalid key"}]
        call.return_value = {"status": False, "warnings": warnings}
        result = enrolment.self_enrol_course(42, "secret", 7)
        self.assertFalse(result["status"])
        self.assertEqual(result["warnings"], warnings)
        self.assertEqual(call.call_args.kwargs["params"],
                         {"courseid": 42, "password": "secret", "instanceid": 7})
        call.return_value = {"status": True, "warnings": []}
        self.assertTrue(enrolment.self_enrol_course(42)["status"])

    @patch("moodle_mcp.moodle.requests.get")
    @patch("moodle_mcp.moodle.requests.post")
    def test_enrolment_uses_post_body(self, post, get):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {"status": True, "warnings": []}
        get_moodle_api_data(APIFunction.enrol_self_enrol_user,
                            {"courseid": 42, "password": "secret"})
        get.assert_not_called()
        self.assertEqual(post.call_args.kwargs["data"]["password"], "secret")
        self.assertNotIn("params", post.call_args.kwargs)

    @patch("moodle_mcp.moodle.requests.post")
    def test_timeout_has_unknown_outcome_without_secrets(self, post):
        post.side_effect = requests.Timeout("https://example/?wstoken=secret")
        with self.assertLogs("moodle-mcp", level="ERROR") as logs:
            with self.assertRaises(MoodleAPIError) as ctx:
                get_moodle_api_data(APIFunction.enrol_self_enrol_user)
        self.assertIn("outcome is unknown", str(ctx.exception))
        self.assertNotIn("secret", str(ctx.exception))
        self.assertNotIn("secret", " ".join(logs.output))

    def test_mcp_tools_registered_with_write_annotation(self):
        tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
        self.assertTrue(tools["search_courses"].annotations.read_only_hint)
        self.assertFalse(tools["self_enrol_course"].annotations.read_only_hint)
        self.assertIn("instanceid", tools["self_enrol_course"].input_schema["properties"])


if __name__ == "__main__":
    unittest.main()
