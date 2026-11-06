[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/loyaniu-moodle-mcp-badge.png)](https://mseep.ai/app/loyaniu-moodle-mcp)

# Moodle-MCP

> A Model Context Protocol (MCP) server implementation that provides capabilities to interact with Moodle LMS.

## Features

The server exposes the following tools.

### Courses & content

| Tool | Description |
| --- | --- |
| `get_my_courses` | Get all courses the current user is enrolled in |
| `list_course_files` | List downloadable files with module IDs, filenames, paths and sizes |
| `download_course_files` | Download all API-listed course files in one call; resume and skip verified unchanged files |
| `download_course_file` | Download a course file with token authentication to a local directory; returns path, size and SHA-256 |
| `search_courses` | Search the visible course catalogue, including courses not enrolled in; zero-based page and 1-100 results per page |
| `get_course_enrolment_methods` | List a course's enrolment methods, availability messages and instance IDs |
| `get_self_enrolment_info` | Check a self-enrolment instance and whether it requires a key |
| `self_enrol_course` | Enrol the current user, with optional key (`password`) and `instanceid`; check returned status and warnings |
| `get_course_content` | Get sections and modules for a specific course by its ID |
| `search_course_materials` | Search across all course materials by query string |
| `get_course_announcements` | Get announcements from course news forums, optionally filtered by course ID |
| `get_recent_activity` | Get recent activity and updates across courses since a given time |

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

## Tests

Run the offline regression suite from the project directory:

```sh
python -m unittest discover -s tests -v
```

The tests mock Moodle API calls and file transfers. They do not require a real
account or perform enrolment. Live file-download verification should use your
own Moodle account and a local output directory outside version control.

## Moodle API requirements

File downloads use Moodle's `/webservice/pluginfile.php` endpoint with token
authentication. The token's service must permit file downloads. First call
`list_course_files(courseid)`, then `download_course_file(courseid, moduleid,
filename, output_dir)`. Use an absolute `output_dir` to choose the destination;
otherwise downloads go to `output/downloads/<courseid>` in the server directory.
For duplicate filenames in folder resources, also specify `filepath` from the
listing. Existing files are never overwritten. Downloads are streamed, limited
to 250 MiB and checked against Moodle's file size. Redirects and external file
hosts are rejected. Authentication tokens are not returned by these tools.

For a complete batch, use `download_course_files(courseid, output_dir)`.
The course contents API is fetched once. Files are grouped by module and file
identity, and `moodle-downloads.json` stores source fingerprints and local hashes
without tokens. Repeating the call skips files whose source metadata and local
SHA-256 are unchanged. Updated or locally edited files are preserved and a new
copy is downloaded. Failures are reported per file and can be retried by repeating
the call. Remote deletions do not delete local files. This downloads the files
exposed by the course contents API, not external links, embedded page/forum
attachments or video streams. Each file is limited to 250 MiB.

Catalogue search and self enrolment require the token's service to allow
`core_course_search_courses`, `core_enrol_get_course_enrolment_methods`,
`enrol_self_get_instance_info` and `enrol_self_enrol_user`. Moodle course
visibility, enrolment periods, capacity and key requirements still apply.
Enrolment requests use POST and keys are not saved in output files or logged.
Check enrolment methods before joining, and select an instance ID when there
are multiple self-enrolment options. If a request times out, check
`get_my_courses` before retrying. Restart the MCP connection after updating
the server so the client discovers the new tools.

For available Moodle API functions, please refer to the [official documentation](https://docs.moodle.org/dev/Web_service_API_functions).

## Setup Instructions

### Method 1: Using `mcp` CLI (recommended)

1. Create your own `.env` file from `.env.example`
2. Assume you have `uv` installed, run `uv add "mcp[cli]"` to install the MCP CLI tools
3. Run `mcp install main.py -f .env` to add the moodle-mcp server to Claude app

### Method 2: Using `uvx`

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

## Authentication

### Getting your Moodle token

1. Navigate to your Moodle token management page `https://{your-moodle-url}/user/managetoken.php`
2. Use the token with `Moodle mobile web service` in the `Service` column
3. Add this token to your `.env` file

### Optional: debug output

Set `MOODLE_MCP_DEBUG_DIR` to a writable directory to save the raw Moodle API responses there as JSON files. It is unset by default, so nothing is written to disk.
