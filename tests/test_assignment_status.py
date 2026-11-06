from pydantic import TypeAdapter

from moodle_mcp import api

STATUS_ADAPTER = TypeAdapter(api.AssignmentStatus)


def _status_for(monkeypatch, payload):
    monkeypatch.setattr(api, "get_moodle_api_data", lambda *a, **kw: payload)
    monkeypatch.setattr(api, "to_json_file", lambda *a, **kw: None)
    result = api.get_assignment_status(1)
    # Same validation the MCP server applies to the tool's structured output.
    STATUS_ADAPTER.validate_python(result)
    return result


def test_null_extensionduedate_is_coerced(monkeypatch):
    payload = {
        "lastattempt": {
            "submission": {"status": "new"},
            "extensionduedate": None,
            "gradingstatus": "notgraded",
            "graded": False,
        },
        "warnings": [],
    }

    result = _status_for(monkeypatch, payload)

    assert result["extensionduedate"] == 0
    assert result["submitted"] is False
    assert result["submission_status"] == "new"


def test_extension_is_kept(monkeypatch):
    payload = {
        "lastattempt": {
            "submission": {"status": "submitted"},
            "extensionduedate": 1_800_000_000,
            "gradingstatus": "notgraded",
        },
    }

    result = _status_for(monkeypatch, payload)

    assert result["extensionduedate"] == 1_800_000_000
    assert result["submitted"] is True


def test_team_submission_is_used_for_group_assignments(monkeypatch):
    payload = {
        "lastattempt": {
            "submission": {"status": "new"},
            "teamsubmission": {"status": "submitted"},
            "extensionduedate": None,
            "gradingstatus": "notgraded",
        },
    }

    result = _status_for(monkeypatch, payload)

    assert result["submission_status"] == "submitted"
    assert result["submitted"] is True


def test_missing_or_null_lastattempt(monkeypatch):
    for payload in ({}, {"lastattempt": None}):
        result = _status_for(monkeypatch, payload)

        assert result == {
            "submission_status": None,
            "grading_status": None,
            "duedate": 0,
            "cutoffdate": 0,
            "extensionduedate": 0,
            "late": False,
            "submitted": False,
            "graded": False,
        }
