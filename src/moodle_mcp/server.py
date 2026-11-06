from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import api
from . import enrolment
from . import downloads
from .logger import logger

mcp = MCPServer("moodle-mcp", dependencies=["glom", "requests"])


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
def list_course_files(courseid: int) -> list[downloads.CourseFile]:
    """List downloadable course files with module IDs, names, paths and sizes, without tokens."""
    return downloads.list_course_files(courseid)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                    open_world_hint=True))
def download_course_files(courseid: int, output_dir: str | None = None) -> downloads.CourseDownloadResult:
    """Download all course files exposed by Moodle's course contents API in one call.

    Use an absolute output_dir; default is ~/Downloads/moodle-mcp/<courseid>/course
    (or $MOODLE_MCP_DOWNLOAD_DIR/<courseid>/course when that is set).
    Files are grouped by module ID and file identity to avoid duplicate names.
    Repeat with the same directory to skip unchanged files verified by SHA-256.
    New versions are saved separately; existing/local files are preserved.
    A local manifest tracks progress for resuming after failures. Each file's
    status is returned; one failed download does not stop the other files.
    Excludes external links, embedded page/forum attachments and video streams.
    Maximum size is 250 MiB per file; removed remote files are kept locally.
    """
    return downloads.download_course_files(courseid, output_dir)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                    open_world_hint=True))
def download_course_file(courseid: int, moduleid: int, filename: str | None = None,
                         output_dir: str | None = None,
                         filepath: str | None = None) -> downloads.DownloadResult:
    """Download a Moodle course file to the local machine using token authentication.

    Use list_course_files to find moduleid and filename. Specify filepath when
    duplicate names exist in a folder resource. output_dir should be an absolute
    local directory; default is ~/Downloads/moodle-mcp/<courseid> (or
    $MOODLE_MCP_DOWNLOAD_DIR/<courseid> when that is set).
    Returns the local path, size and SHA-256. Existing files are never overwritten.
    Maximum download size is 250 MiB. External links are not downloaded.
    """
    return downloads.download_course_file(courseid, moduleid, filename, output_dir, filepath)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
def search_courses(query: str, page: int = 0, perpage: int = 20) -> enrolment.CourseSearch:
    """Search the visible Moodle course catalogue, including courses not enrolled in.

    Page is zero-based; perpage is 1-100. Returns total matches and enrolment types.
    """
    return enrolment.search_courses(query, page, perpage)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
def get_course_enrolment_methods(courseid: int) -> list[enrolment.EnrolmentMethod]:
    """List enrolment methods and instance IDs. Status is true if available, otherwise a reason."""
    return enrolment.get_course_enrolment_methods(courseid)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
def get_self_enrolment_info(instanceid: int) -> enrolment.SelfEnrolmentInfo:
    """Check a self-enrolment instance's availability and whether an enrolment key is required."""
    return enrolment.get_self_enrolment_info(instanceid)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                    idempotent_hint=False, open_world_hint=True))
def self_enrol_course(courseid: int, password: str = "",
                      instanceid: int | None = None) -> enrolment.EnrolmentResult:
    """Enrol the authenticated user in a course using Moodle self enrolment.

    Use when the user requests joining that course. Check enrolment methods first;
    specify instanceid if multiple self-enrolment options exist. Password is the
    optional enrolment key. Only status=true means success; inspect warnings on
    failure. Moodle restrictions still apply. After a network error, check
    get_my_courses before retrying because enrolment may already have succeeded.
    """
    return enrolment.self_enrol_course(courseid, password, instanceid)


@mcp.tool()
def get_upcoming_events() -> list[api.UpcomingEvent]:
    """Get upcoming events from moodle"""
    return api.get_upcoming_events()


@mcp.tool()
def get_my_courses() -> list[api.Course]:
    """Get all courses the current user is enrolled in"""
    return api.get_my_courses()


@mcp.tool()
def get_course_content(courseid: int) -> list[api.CourseSection]:
    """Get sections and modules for a specific course by its ID"""
    return api.get_course_content(courseid)


@mcp.tool()
def get_assignments(courseids: list[int] | None = None) -> list[api.Assignment]:
    """Get assignments for courses. Optionally filter by course IDs. Returns all enrolled courses' assignments if no course IDs are provided."""
    return api.get_assignments(courseids)


@mcp.tool()
def get_assignment_status(assignid: int) -> api.AssignmentStatus:
    """Get submission and grading status for a specific assignment by its ID"""
    return api.get_assignment_status(assignid, with_dates=True)


@mcp.tool()
def get_upcoming_deadlines() -> list[api.UpcomingDeadline]:
    """Get upcoming assignment deadlines across all courses, sorted by due date"""
    return api.get_upcoming_deadlines()


@mcp.tool()
def get_grades(courseid: int | None = None) -> list[api.CourseGrade] | list[api.GradeItem]:
    """Get grade overview for all courses, or detailed grades for a specific course if courseid is provided"""
    return api.get_grades(courseid)


@mcp.tool()
def search_course_materials(query: str) -> list[api.SearchResult]:
    """Search across all course materials by query string"""
    return api.search_course_materials(query)


@mcp.tool()
def semester_dashboard() -> api.SemesterDashboard:
    """Get an aggregated overview combining courses, upcoming deadlines, and grades"""
    return api.semester_dashboard()


@mcp.tool()
def get_actionable_tasks() -> list[api.ActionableTask]:
    """Returns prioritized list of tasks needing action, sorted by urgency (overdue first)"""
    return api.get_actionable_tasks()


@mcp.tool()
def get_overdue_assignments() -> list[api.OverdueAssignment]:
    """Returns assignments past due date that are unsubmitted, sorted by most overdue first"""
    return api.get_overdue_assignments()


@mcp.tool()
def get_recent_activity(since: int | None = None) -> list[api.RecentActivity]:
    """Returns recent activity/updates across courses. Optionally specify 'since' as Unix timestamp (defaults to 7 days ago)"""
    return api.get_recent_activity(since)


@mcp.tool()
def get_course_announcements(courseid: int | None = None) -> list[api.CourseAnnouncement]:
    """Gets announcements from course news forums. Optionally filter by course ID"""
    return api.get_course_announcements(courseid)


@mcp.tool()
def get_course_health(courseid: int) -> api.CourseHealth:
    """Overall health check for a course: progress, grades, unsubmitted/overdue counts"""
    return api.get_course_health(courseid)


@mcp.tool()
def get_course_progress(courseid: int | None = None) -> list[api.CourseProgress]:
    """Progress/completion for courses. Optionally specify a course ID, or get all courses"""
    return api.get_course_progress(courseid)


@mcp.tool()
def get_study_load() -> api.StudyLoad:
    """Study load analysis showing assignment distribution by week, identifying heavy weeks"""
    return api.get_study_load()


@mcp.tool()
def daily_briefing() -> api.DailyBriefing:
    """Aggregated daily summary: overdue count, today's deadlines, recent grades, upcoming events, actionable tasks"""
    return api.daily_briefing()


@mcp.tool()
def weekly_review() -> api.WeeklyReview:
    """Aggregated weekly summary: submitted/graded counts, upcoming deadlines, overdue count, progress"""
    return api.weekly_review()


@mcp.tool()
def ask_moodle(question: str) -> api.MoodleAnswer:
    """Ask a natural language question about your Moodle data. Routes to the right data sources based on your question"""
    return api.ask_moodle(question)


@mcp.tool()
def analyze_assignment(assignid: int) -> api.AssignmentAnalysis:
    """Comprehensive analysis of an assignment: status, requirements, materials count, course progress, and deadline info"""
    return api.analyze_assignment(assignid)


@mcp.tool()
def extract_assignment_requirements(assignid: int) -> api.AssignmentRequirements:
    """Extract and structure requirements, deliverables, constraints, and evaluation criteria from an assignment description"""
    return api.extract_assignment_requirements(assignid)


@mcp.tool()
def find_relevant_materials(assignid: int) -> api.RelevantMaterials:
    """Find course content and search results relevant to a specific assignment, ranked by relevance"""
    return api.find_relevant_materials(assignid)


@mcp.tool()
def decompose_task(assignid: int) -> api.TaskDecomposition:
    """Break down an assignment into subtasks with estimated effort, dependencies, and critical path"""
    return api.decompose_task(assignid)


@mcp.tool()
def create_implementation_plan(assignid: int) -> api.ImplementationPlan:
    """Create a step-by-step implementation plan for completing an assignment, with timeline, resources, milestones, and risk factors"""
    return api.create_implementation_plan(assignid)


def main():
    logger.info("Starting moodle-mcp server")
    mcp.run()
