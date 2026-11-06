from enum import Enum

import requests
from glom import delete

from .logger import logger
from .utils import getenv

MOODLE_URL = getenv("MOODLE_URL")
MOODLE_TOKEN = getenv("MOODLE_TOKEN")


class MoodleAPIError(Exception):
    """Raised when the Moodle API returns an error response."""

    def __init__(self, error_code: str, message: str, function: str):
        self.error_code = error_code
        self.message = message
        self.function = function
        super().__init__(f"Moodle API error [{error_code}] in {function}: {message}")


class APIFunction(Enum):
    core_calendar_get_calendar_upcoming_view = (
        "core_calendar_get_calendar_upcoming_view"
    )
    core_webservice_get_site_info = "core_webservice_get_site_info"
    core_enrol_get_users_courses = "core_enrol_get_users_courses"
    core_course_get_contents = "core_course_get_contents"
    mod_assign_get_assignments = "mod_assign_get_assignments"
    mod_assign_get_submission_status = "mod_assign_get_submission_status"
    gradereport_overview_get_course_grades = (
        "gradereport_overview_get_course_grades"
    )
    gradereport_user_get_grade_items = "gradereport_user_get_grade_items"
    core_course_get_updates_since = "core_course_get_updates_since"
    mod_forum_get_forums_by_courses = "mod_forum_get_forums_by_courses"
    mod_forum_get_forum_discussions = "mod_forum_get_forum_discussions"
    core_completion_get_course_completion_status = (
        "core_completion_get_course_completion_status"
    )
    core_calendar_get_calendar_events = "core_calendar_get_calendar_events"


# Fields not needed for specific API functions
# Using `glom` to extract fields not needed
DELETE_FIELDS = {
    APIFunction.core_calendar_get_calendar_upcoming_view: [
        "events.*.course.courseimage"
    ],
    APIFunction.core_course_get_contents: [
        "*.modules.*.modicon",
        "*.modules.*.modplural",
        "*.modules.*.onclick",
        "*.modules.*.afterlink",
        "*.modules.*.customdata",
        "*.modules.*.contents.*.filepath",
        "*.modules.*.contents.*.timecreated",
        "*.modules.*.contents.*.timemodified",
        "*.modules.*.contents.*.sortorder",
        "*.modules.*.contents.*.isexternalfile",
        "*.modules.*.contents.*.repositorytype",
        "*.modules.*.contents.*.userid",
        "*.modules.*.contents.*.author",
        "*.modules.*.contents.*.license",
        "*.modules.*.contents.*.mimetype",
        "*.modules.*.completiondata",
        "*.modules.*.contentsinfo",
    ],
    APIFunction.mod_assign_get_submission_status: [
        "lastattempt.submission.plugins",
        "feedback.plugins",
        "feedback.grade.grader",
    ],
    APIFunction.mod_forum_get_forum_discussions: [
        "discussions.*.messageinlinefiles",
        "discussions.*.attachments",
    ],
}


def format_moodle_array_params(key: str, values: list) -> dict:
    """Format a list of values as Moodle-style array parameters.

    e.g. format_moodle_array_params('courseids', [5, 10])
         -> {'courseids[0]': 5, 'courseids[1]': 10}
    """
    return {f"{key}[{i}]": v for i, v in enumerate(values)}


def get_moodle_api_data(
    function: APIFunction, params: dict = None, use_original_data=True
):
    request_params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": function.value,
        "moodlewsrestformat": "json",
    }
    if params:
        request_params.update(params)

    logger.info(
        f"Getting moodle data for `{function.value}`"
        f" with params: {list(params.keys()) if params else 'none'}"
    )

    try:
        rsp = requests.get(MOODLE_URL, params=request_params, timeout=30)
    except requests.RequestException as e:
        logger.error(f"Network error calling {function.value}: {e}")
        raise MoodleAPIError("network_error", str(e), function.value) from e

    if rsp.status_code != 200:
        logger.error(f"Moodle API HTTP error: {rsp.status_code} for {function.value}")
        raise MoodleAPIError(
            "http_error",
            f"HTTP {rsp.status_code}: {rsp.text[:200]}",
            function.value,
        )

    data = rsp.json()

    # Moodle returns errors as JSON with 'errorcode' and 'message' fields
    if isinstance(data, dict) and "errorcode" in data:
        error_msg = data.get("message", "Unknown Moodle API error")
        error_code = data.get("errorcode", "unknown")
        logger.error(f"Moodle API error: [{error_code}] {error_msg}")
        raise MoodleAPIError(error_code, error_msg, function.value)

    if use_original_data:
        return data

    for field_path in DELETE_FIELDS.get(function, []):
        delete(data, field_path, ignore_missing=True)

    return data