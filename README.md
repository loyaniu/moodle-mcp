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

## API Reference

For available Moodle API functions, please refer to the [official documentation](https://docs.moodle.org/dev/Web_service_API_functions).

## Setup Instructions

### Method 1: Using `mcp` CLI (recommended)

1. Create your own `.env` file from `.env.example`
2. Run `uv sync` to install dependencies and MCP CLI tools
3. Run `uv run --with-editable . mcp install src/moodle_mcp/server.py -f .env --with-editable .` to add the moodle-mcp server to Claude app

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
