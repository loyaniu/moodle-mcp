from moodle_mcp import api
from moodle_mcp.moodle import APIFunction, MoodleAPIError

# Web service functions that exist in Moodle core (mod/forum/db/services.php).
KNOWN_FUNCTIONS = {
    "mod_forum_get_forums_by_courses",
    "mod_forum_get_forum_discussions",
}


def fake_moodle(function, params=None, use_original_data=True):
    """Behave like the Moodle REST endpoint for the calls under test."""
    if function.value not in KNOWN_FUNCTIONS:
        # What Moodle answers for a function name it does not know.
        raise MoodleAPIError(
            "invalidrecord",
            "Can't find data record in database table external_functions.",
            function.value,
        )
    if function is APIFunction.mod_forum_get_forums_by_courses:
        return [
            {"id": 11, "course": 7, "type": "news", "name": "Announcements"},
            {"id": 12, "course": 7, "type": "general", "name": "Q&A"},
        ]
    assert params["forumid"] == "11"
    return {
        "discussions": [
            {
                "id": 101,
                "subject": "Exam room changed",
                "message": "<p>The exam takes place in room <b>A1</b>.</p>",
                "created": 1_790_000_000,
                "userfullname": "Teacher",
            }
        ],
        "warnings": [],
    }


def test_announcements_are_returned(monkeypatch):
    monkeypatch.setattr(api, "get_moodle_api_data", fake_moodle)
    monkeypatch.setattr(api, "to_json_file", lambda *a, **kw: None)
    monkeypatch.setattr(
        api, "get_my_courses", lambda: [{"id": 7, "fullname": "Course 7"}]
    )

    result = api.get_course_announcements()

    assert len(result) == 1
    assert result[0]["subject"] == "Exam room changed"
    assert result[0]["message"] == "The exam takes place in room A1."
    assert result[0]["course"] == "Course 7"
    assert result[0]["author"] == "Teacher"
    assert result[0]["date"] == 1_790_000_000
