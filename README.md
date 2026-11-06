[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/loyaniu-moodle-mcp-badge.png)](https://mseep.ai/app/loyaniu-moodle-mcp)

# Moodle-MCP

> A Model Context Protocol (MCP) server implementation that provides capabilities to interact with Moodle LMS.

## Features

The server exposes the following tools.

### Courses & content

| Tool | Description |
| --- | --- |
| `get_my_courses` | Get all courses the current user is enrolled in |
| `get_course_content` | Get sections and modules for a specific course by its ID |
| `search_course_materials` | Search across all course materials by query string |
| `get_course_announcements` | Get announcements from course news forums, optionally filtered by course ID |
| `get_recent_activity` | Get recent activity and updates across courses since a given time |

### Course files

| Tool | Description |
| --- | --- |
| `list_course_files` | List downloadable files with module IDs, filenames, paths and sizes |
| `download_course_file` | Download one course file to a local directory; returns path, size and SHA-256 |
| `download_course_files` | Download all files of a course in one call; resumable, skips verified unchanged files |

### Course catalogue & enrolment

| Tool | Description |
| --- | --- |
| `search_courses` | Search the visible course catalogue, including courses you are not enrolled in |
| `get_course_enrolment_methods` | List a course's enrolment methods, availability and instance IDs |
| `get_self_enrolment_info` | Check a self-enrolment instance and whether it requires a key |
| `self_enrol_course` | Enrol the current user in a course, with an optional enrolment key |

### Assignments & deadlines

| Tool | Description |
| --- | --- |
| `get_assignments` | Get assignments for courses, optionally filtered by course IDs |
| `get_assignment_status` | Get submission and grading status for a specific assignment |
| `get_upcoming_deadlines` | Get upcoming assignment deadlines across all courses, sorted by due date |
| `get_overdue_assignments` | Get unsubmitted assignments past their due date, most overdue first |
| `get_actionable_tasks` | Get a prioritized list of tasks needing action, sorted by urgency |
| `analyze_assignment` | Analyze an assignment: status, requirements, materials, progress, deadline |
| `extract_assignment_requirements` | Extract requirements, deliverables, constraints, and evaluation criteria from an assignment |
| `find_relevant_materials` | Find course content relevant to an assignment, ranked by relevance |
| `decompose_task` | Break an assignment into subtasks with effort, dependencies, and critical path |
| `create_implementation_plan` | Build a step-by-step plan with timeline, resources, milestones, and risks |

### Grades & progress

| Tool | Description |
| --- | --- |
| `get_grades` | Get a grade overview for all courses, or detailed grades for one course |
| `get_course_progress` | Get progress and completion for one course or all courses |
| `get_course_health` | Health check for a course: progress, grades, unsubmitted and overdue counts |
| `get_study_load` | Analyze assignment distribution by week to identify heavy weeks |

### Aggregated overviews

| Tool | Description |
| --- | --- |
| `get_upcoming_events` | Get upcoming events from Moodle |
| `semester_dashboard` | Combined overview of courses, upcoming deadlines, and grades |
| `daily_briefing` | Daily summary of overdue count, today's deadlines, recent grades, events, and tasks |
| `weekly_review` | Weekly summary of submitted/graded counts, deadlines, overdue count, and progress |
| `ask_moodle` | Ask a natural language question and have it routed to the right data sources |

## Setup Instructions

### Method 1: Using `uvx` (recommended)

Go to Claude > Settings > Developer > Edit Config > claude_desktop_config.json to include the following

```json
{
  "mcpServers": {
    "moodle-mcp": {
      "command": "uvx",
      "args": ["moodle-mcp"],
      "env": {
        "MOODLE_URL": "https://{your-moodle-url}/webservice/rest/server.php",
        "MOODLE_TOKEN": "{your-moodle-token}"
      }
    }
  }
}
```

Restart Claude after changing the config or updating the server, so it picks up the new tools.

### Method 2: From a local clone, using the `mcp` CLI

1. Clone this repository and create your own `.env` file from `.env.example`
2. Run `uv sync` to install the dependencies, including the MCP CLI tools
3. Run `uv run mcp install main.py -f .env` to add the moodle-mcp server to the Claude app

## Authentication

### Getting your Moodle token

1. Navigate to your Moodle token management page `https://{your-moodle-url}/user/managetoken.php`
2. Use the token with `Moodle mobile web service` in the `Service` column
3. Add this token to your `.env` file, or to the `env` block of your Claude config

## Configuration

| Variable | Required | Description |
| --- | --- | --- |
| `MOODLE_URL` | yes | Your Moodle REST endpoint, `https://{your-moodle-url}/webservice/rest/server.php` |
| `MOODLE_TOKEN` | yes | Your Moodle web service token |
| `MOODLE_MCP_DOWNLOAD_DIR` | no | Default folder for course file downloads (default: `~/Downloads/moodle-mcp`) |
| `MOODLE_MCP_DEBUG_DIR` | no | Save the raw Moodle API responses there as JSON files, for debugging. Unset by default, so nothing is written to disk |

## Course file downloads

Downloads use Moodle's `/webservice/pluginfile.php` endpoint with token
authentication, so the token's service must permit file downloads (the
Moodle mobile web service does).

- Call `list_course_files(courseid)`, then `download_course_file(courseid, moduleid, filename, output_dir)`.
  For duplicate filenames in folder resources, also pass `filepath` from the listing.
- `download_course_files(courseid, output_dir)` downloads every file of a course in one call.
  A `moodle-downloads.json` manifest in the output folder records what was downloaded (without tokens),
  so repeating the call skips files whose source and local SHA-256 are unchanged and retries the ones that failed.
  Updated or locally edited files are kept, and the new version is saved next to them.
- Without `output_dir`, files go to `MOODLE_MCP_DOWNLOAD_DIR/<courseid>`
  (default `~/Downloads/moodle-mcp/<courseid>`).
- Existing files are never overwritten. Downloads are streamed, limited to 250 MiB per file and checked against
  Moodle's file size. Redirects and external file hosts are rejected. Tokens are never returned by these tools.
- Only files exposed by the course contents API are downloaded: not external links, embedded page/forum
  attachments or video streams. Files deleted on Moodle are not deleted locally.

## Course catalogue & self enrolment

These tools need the token's service to allow `core_course_search_courses`,
`core_enrol_get_course_enrolment_methods`, `enrol_self_get_instance_info` and
`enrol_self_enrol_user` (all part of the Moodle mobile web service).

`self_enrol_course` changes your enrolments, so check `get_course_enrolment_methods`
first and pass an `instanceid` when a course has several self-enrolment options.
Moodle's course visibility, enrolment periods, capacity and key requirements still apply.
Enrolment requests use POST, and keys are never logged or saved. If a request times out,
check `get_my_courses` before retrying, because the enrolment may already have succeeded.

## Development

Run the offline test suite (Moodle API calls and file transfers are mocked; no account is needed):

```sh
uv run pytest
```

For available Moodle API functions, please refer to the [official documentation](https://docs.moodle.org/dev/Web_service_API_functions).
