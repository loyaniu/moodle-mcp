import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing_extensions import TypedDict

from glom import Coalesce, glom

from .logger import logger
from .moodle import (
    APIFunction,
    MoodleAPIError,
    format_moodle_array_params,
    get_moodle_api_data,
)
from .utils import to_json_file


# ---------------------------------------------------------------------------
# TypedDict definitions
# ---------------------------------------------------------------------------


class UpcomingEvent(TypedDict):
    id: int
    name: str
    formattedtime: str
    url: str
    description: str
    popupname: str


class Course(TypedDict):
    id: int
    fullname: str
    shortname: str
    category: int
    progress: float | None
    format: str
    startdate: int
    enddate: int


class CourseModule(TypedDict):
    id: int
    name: str
    modname: str
    url: str | None
    contents: list[dict] | None


class CourseSection(TypedDict):
    name: str
    section: int
    visible: int
    uservisible: bool
    modules: list[CourseModule]


class Assignment(TypedDict):
    id: int
    name: str
    duedate: int
    cutoffdate: int
    intro: str | None
    courseid: int
    coursename: str


class AssignmentStatus(TypedDict):
    submission_status: str | None
    grading_status: str | None
    duedate: int
    cutoffdate: int
    extensionduedate: int
    late: bool
    submitted: bool
    graded: bool


class UpcomingDeadline(TypedDict):
    assignment_id: int
    assignment_name: str
    course_name: str
    duedate: int
    duedate_formatted: str
    submitted: bool
    submission_status: str | None


class CourseGrade(TypedDict):
    courseid: int
    course_name: str
    grade: str
    rank: str | None


class GradeItem(TypedDict):
    itemname: str
    grade: str | None
    percentage: str | None
    feedback: str | None


class SearchResult(TypedDict):
    title: str
    url: str
    content: str
    course_name: str | None


class SemesterDashboardCourse(TypedDict):
    id: int
    fullname: str
    shortname: str
    progress: float | None
    grade: str | None


class SemesterDashboard(TypedDict):
    courses: list[SemesterDashboardCourse]
    upcoming_deadlines: list[UpcomingDeadline]
    recent_grades: list[GradeItem]


class ActionableTask(TypedDict):
    id: int
    name: str
    course: str
    duedate: int
    duedate_formatted: str | None
    status: str
    urgency: str
    type: str


class OverdueAssignment(TypedDict):
    id: int
    name: str
    course: str
    duedate: int
    duedate_formatted: str
    days_overdue: int
    submission_status: str | None


class RecentActivity(TypedDict):
    course: str
    type: str
    description: str
    timestamp: int
    timestamp_formatted: str
    url: str | None


class CourseAnnouncement(TypedDict):
    id: int
    subject: str
    message: str
    course: str
    author: str
    date: int
    date_formatted: str


class CourseHealth(TypedDict):
    courseid: int
    coursename: str
    progress: float | None
    grade: str | None
    unsubmitted_count: int
    overdue_count: int
    total_assignments: int
    last_activity: str | None


class CourseProgress(TypedDict):
    courseid: int
    coursename: str
    progress_percentage: float | None
    completed_activities: int
    total_activities: int


class WeekLoad(TypedDict):
    week_start: str
    week_end: str
    assignment_count: int
    courses: list[str]
    load_level: str


class StudyLoad(TypedDict):
    weeks: list[WeekLoad]
    total_assignments: int
    heaviest_week: str | None
    average_per_week: float


class DailyBriefing(TypedDict):
    date: str
    overdue_count: int
    today_deadlines: list[UpcomingDeadline]
    recent_grades: list[GradeItem]
    upcoming_events: list[UpcomingEvent]
    actionable_tasks_summary: list[dict]


class WeeklyReview(TypedDict):
    week_start: str
    week_end: str
    submitted_count: int
    graded_count: int
    upcoming_deadlines: list[UpcomingDeadline]
    overdue_count: int
    progress_summary: list[CourseProgress]


class MoodleAnswer(TypedDict):
    question: str
    answer: str
    data_sources: list[str]
    relevant_items: list[dict]


class RequirementItem(TypedDict):
    requirement: str
    category: str  # "deliverable", "format", "constraint", "evaluation", "deadline"
    priority: str  # "must", "should", "optional"
    source: str  # which part of the assignment text this came from


class AssignmentAnalysis(TypedDict):
    assignment_id: int
    assignment_name: str
    course_name: str
    status: str | None
    submitted: bool
    graded: bool
    duedate: int
    duedate_formatted: str | None
    days_remaining: int | None
    is_overdue: bool
    intro_length: int
    has_intro: bool
    requirements_count: int
    requirements: list[RequirementItem]
    relevant_materials_count: int
    course_progress: float | None
    course_grade: str | None


class AssignmentRequirements(TypedDict):
    assignment_id: int
    assignment_name: str
    course_name: str
    intro: str | None
    requirements: list[RequirementItem]
    deliverables: list[str]
    constraints: list[str]
    evaluation_criteria: list[str]
    deadlines: list[str]
    summary: str


class MaterialItem(TypedDict):
    title: str
    type: str  # "file", "url", "page", "forum", "assignment", "search_result"
    course_name: str
    relevance_score: float  # 0.0-1.0 how relevant to the assignment
    url: str | None
    description: str | None
    section: str | None  # which course section it's in


class RelevantMaterials(TypedDict):
    assignment_id: int
    assignment_name: str
    course_name: str
    course_content_items: list[MaterialItem]
    search_results: list[MaterialItem]
    total_count: int


class SubTask(TypedDict):
    id: str  # e.g. "1.1", "2.3"
    title: str
    description: str
    estimated_effort: str  # "low", "medium", "high"
    dependencies: list[str]  # ids of subtasks this depends on
    category: str  # "research", "writing", "coding", "review", "submission"


class TaskDecomposition(TypedDict):
    assignment_id: int
    assignment_name: str
    course_name: str
    total_subtasks: int
    subtasks: list[SubTask]
    critical_path: list[str]  # ordered list of subtask ids on the critical path
    estimated_total_effort: str  # "low", "medium", "high"


class PlanStep(TypedDict):
    step_number: int
    title: str
    description: str
    subtask_ids: list[str]  # references to SubTask ids from decomposition
    estimated_duration: str  # e.g. "2-3 hours", "1 day"
    resources: list[str]  # material titles or descriptions


class ImplementationPlan(TypedDict):
    assignment_id: int
    assignment_name: str
    course_name: str
    duedate: int
    duedate_formatted: str | None
    days_remaining: int | None
    total_steps: int
    steps: list[PlanStep]
    milestones: list[str]  # key checkpoints
    risk_factors: list[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_user_id_cache: int | None = None


def _get_user_id() -> int:
    """Get the current Moodle user ID, caching the result."""
    global _user_id_cache
    if _user_id_cache is not None:
        return _user_id_cache

    data = get_moodle_api_data(APIFunction.core_webservice_get_site_info)
    _user_id_cache = glom(data, "userid")
    logger.info(f"Retrieved and cached Moodle user ID: {_user_id_cache}")
    return _user_id_cache


# ---------------------------------------------------------------------------
# Tool: get_upcoming_events (existing)
# ---------------------------------------------------------------------------


def get_upcoming_events() -> list[UpcomingEvent]:
    data = get_moodle_api_data(APIFunction.core_calendar_get_calendar_upcoming_view)

    to_json_file(data, "calendar_upcoming_view.json")

    # define the extraction specification to get the required fields
    upcoming_events_spec = (
        "events",
        [
            {
                "id": "id",
                "name": "name",
                "formattedtime": "formattedtime",
                "url": "url",
                "description": "description",
                "popupname": "popupname",
            }
        ],
    )

    # use glom to extract the data
    upcoming_events = glom(data, upcoming_events_spec)

    logger.info(f"Extracted {len(upcoming_events)} upcoming events")

    return upcoming_events


# ---------------------------------------------------------------------------
# Tool: get_my_courses
# ---------------------------------------------------------------------------


def get_my_courses() -> list[Course]:
    user_id = _get_user_id()
    data = get_moodle_api_data(
        APIFunction.core_enrol_get_users_courses,
        params={"userid": str(user_id)},
    )

    to_json_file(data, "user_courses.json")

    spec = [
        {
            "id": "id",
            "fullname": "fullname",
            "shortname": "shortname",
            "category": Coalesce("category", default=0),
            "progress": Coalesce("progress", default=None),
            "format": Coalesce("format", default=""),
            "startdate": Coalesce("startdate", default=0),
            "enddate": Coalesce("enddate", default=0),
        }
    ]

    courses = glom(data, spec)
    logger.info(f"Extracted {len(courses)} courses")
    return courses


# ---------------------------------------------------------------------------
# Tool: get_course_content
# ---------------------------------------------------------------------------


def get_course_content(courseid: int) -> list[CourseSection]:
    data = get_moodle_api_data(
        APIFunction.core_course_get_contents,
        params={"courseid": str(courseid)},
        use_original_data=False,
    )

    to_json_file(data, f"course_content_{courseid}.json")

    module_spec = {
        "id": "id",
        "name": "name",
        "modname": "modname",
        "url": Coalesce("url", default=None),
        "contents": Coalesce("contents", default=None),
    }

    section_spec = {
        "name": "name",
        "section": "section",
        "visible": Coalesce("visible", default=1),
        "uservisible": Coalesce("uservisible", default=True),
        "modules": (Coalesce("modules", default=[]), [module_spec]),
    }

    sections = glom(data, [section_spec])
    logger.info(f"Extracted {len(sections)} sections for course {courseid}")
    return sections


# ---------------------------------------------------------------------------
# Tool: get_assignments
# ---------------------------------------------------------------------------


def get_assignments(courseids: list[int] | None = None) -> list[Assignment]:
    params = None
    if courseids:
        params = format_moodle_array_params("courseids", courseids)

    data = get_moodle_api_data(
        APIFunction.mod_assign_get_assignments,
        params=params,
    )

    to_json_file(data, "assignments.json")

    # The response is {"courses": [{"id": ..., "fullname": ..., "assignments": [...]}]}
    courses_data = data.get("courses", [])

    result: list[Assignment] = []
    for course in courses_data:
        course_id = course.get("id", 0)
        course_name = course.get("fullname", "")
        for assign in course.get("assignments", []):
            result.append(
                {
                    "id": assign.get("id", 0),
                    "name": assign.get("name", ""),
                    "duedate": assign.get("duedate", 0),
                    "cutoffdate": assign.get("cutoffdate", 0),
                    "intro": assign.get("intro", None),
                    "courseid": course_id,
                    "coursename": course_name,
                }
            )

    logger.info(f"Extracted {len(result)} assignments across {len(courses_data)} courses")
    return result


# ---------------------------------------------------------------------------
# Tool: get_assignment_status
# ---------------------------------------------------------------------------


def _get_assignment_dates(assignid: int) -> tuple[int, int]:
    """Due date and cut-off date of an assignment, (0, 0) if not found."""
    for assign in get_assignments():
        if assign["id"] == assignid:
            return assign["duedate"] or 0, assign["cutoffdate"] or 0
    logger.warning(f"Assignment {assignid} not found in enrolled courses")
    return 0, 0


def get_assignment_status(assignid: int, with_dates: bool = False) -> AssignmentStatus:
    """Submission and grading status of one assignment.

    mod_assign_get_submission_status does not return the assignment's due
    or cut-off date. With ``with_dates=True`` they are looked up through
    mod_assign_get_assignments (one extra request); otherwise they are 0.
    Internal callers that already have the dates leave it off.
    """
    data = get_moodle_api_data(
        APIFunction.mod_assign_get_submission_status,
        params={"assignid": str(assignid)},
        use_original_data=False,
    )

    to_json_file(data, f"assignment_status_{assignid}.json")

    # Moodle sends JSON null for fields that are not set (e.g. extensionduedate
    # when no extension was granted), so `.get(key, default)` is not enough:
    # coerce None to the default as well, otherwise the AssignmentStatus
    # output schema rejects the result.
    lastattempt = data.get("lastattempt") or {}
    # Group assignments report the submission under "teamsubmission".
    submission = lastattempt.get("teamsubmission") or lastattempt.get("submission") or {}
    submission_status = submission.get("status")
    duedate, cutoffdate = _get_assignment_dates(assignid) if with_dates else (0, 0)

    return {
        "submission_status": submission_status,
        "grading_status": lastattempt.get("gradingstatus"),
        "duedate": duedate,
        "cutoffdate": cutoffdate,
        "extensionduedate": lastattempt.get("extensionduedate") or 0,
        "late": bool(lastattempt.get("late")),
        "submitted": submission_status == "submitted",
        "graded": bool(lastattempt.get("graded")),
    }


# ---------------------------------------------------------------------------
# Tool: get_upcoming_deadlines
# ---------------------------------------------------------------------------


def get_upcoming_deadlines() -> list[UpcomingDeadline]:
    assignments = get_assignments()
    now = int(datetime.now(timezone.utc).timestamp())

    # Filter to assignments with future due dates
    upcoming = [a for a in assignments if a["duedate"] > now and a["duedate"] > 0]

    result: list[UpcomingDeadline] = []
    for assign in upcoming:
        submitted = False
        submission_status = None

        try:
            status = get_assignment_status(assign["id"])
            submitted = status["submitted"]
            submission_status = status["submission_status"]
        except Exception as e:
            logger.warning(
                f"Could not get status for assignment {assign['id']}: {e}"
            )

        result.append(
            {
                "assignment_id": assign["id"],
                "assignment_name": assign["name"],
                "course_name": assign["coursename"],
                "duedate": assign["duedate"],
                "duedate_formatted": datetime.fromtimestamp(
                    assign["duedate"], tz=timezone.utc
                ).isoformat(),
                "submitted": submitted,
                "submission_status": submission_status,
            }
        )

    # Sort by due date
    result.sort(key=lambda x: x["duedate"])
    logger.info(f"Found {len(result)} upcoming deadlines")
    return result


# ---------------------------------------------------------------------------
# Tool: get_grades
# ---------------------------------------------------------------------------


def get_grades(courseid: int | None = None) -> list[CourseGrade] | list[GradeItem]:
    if courseid:
        return _get_course_grades_detail(courseid)
    return _get_course_grades_overview()


def _get_course_grades_overview() -> list[CourseGrade]:
    user_id = _get_user_id()
    data = get_moodle_api_data(
        APIFunction.gradereport_overview_get_course_grades,
        params={"userid": str(user_id)},
    )

    to_json_file(data, "grades_overview.json")

    # Merge course names from get_my_courses
    courses = get_my_courses()
    course_map = {c["id"]: c["fullname"] for c in courses}

    grades = data.get("grades", [])
    result: list[CourseGrade] = []
    for g in grades:
        course_id = g.get("courseid", 0)
        result.append(
            {
                "courseid": course_id,
                "course_name": course_map.get(course_id, "Unknown"),
                "grade": g.get("grade", ""),
                "rank": g.get("rank"),
            }
        )

    logger.info(f"Extracted {len(result)} course grade overviews")
    return result


def _get_course_grades_detail(courseid: int) -> list[GradeItem]:
    user_id = _get_user_id()
    data = get_moodle_api_data(
        APIFunction.gradereport_user_get_grade_items,
        params={"courseid": str(courseid), "userid": str(user_id)},
    )

    to_json_file(data, f"grades_detail_{courseid}.json")

    user_grades = data.get("usergrades", [])
    if not user_grades:
        return []

    grade_items_raw = user_grades[0].get("gradeitems", [])

    result: list[GradeItem] = []
    for item in grade_items_raw:
        # itemname can be a string or an object with a 'value' key
        itemname = item.get("itemname", "")
        if isinstance(itemname, dict):
            itemname = itemname.get("value", "")

        result.append(
            {
                "itemname": itemname,
                "grade": item.get("gradeformatted", None) or item.get("grade", None),
                "percentage": item.get("percentageformatted", None)
                or item.get("percentage", None),
                "feedback": item.get("feedback", None),
            }
        )

    logger.info(f"Extracted {len(result)} grade items for course {courseid}")
    return result


# ---------------------------------------------------------------------------
# Tool: search_course_materials
# ---------------------------------------------------------------------------


def search_course_materials(query: str) -> list[SearchResult]:
    """Search the user's course materials for a query string.

    Moodle global search (core_search_*) is an optional subsystem that is
    disabled by default and needs a configured search engine, so it cannot be
    relied on. Instead we search client-side over the contents of the enrolled
    courses, matching section names, activity names and file names. This works
    on any Moodle instance.
    """
    needle = query.lower().strip()
    results: list[SearchResult] = []

    for course in get_my_courses():
        try:
            sections = get_course_content(course["id"])
        except MoodleAPIError as e:
            logger.warning(f"Skipping course {course['id']} in search: {e}")
            continue

        for section in sections:
            section_name = section.get("name") or ""
            for module in section.get("modules", []):
                name = module.get("name") or ""
                filenames = [
                    c.get("filename", "")
                    for c in (module.get("contents") or [])
                    if isinstance(c, dict)
                ]
                haystack = " ".join([name, section_name, *filenames]).lower()
                if needle and needle in haystack:
                    results.append(
                        {
                            "title": name,
                            "url": module.get("url") or "",
                            "content": section_name,
                            "course_name": course.get("fullname"),
                        }
                    )

    logger.info(f"Search for '{query}' matched {len(results)} materials")
    return results


# ---------------------------------------------------------------------------
# Tool: semester_dashboard
# ---------------------------------------------------------------------------


def semester_dashboard() -> SemesterDashboard:
    # Fetch courses
    courses: list[Course] = []
    try:
        courses = get_my_courses()
    except Exception as e:
        logger.warning(f"Failed to fetch courses for dashboard: {e}")

    # Fetch upcoming deadlines
    deadlines: list[UpcomingDeadline] = []
    try:
        deadlines = get_upcoming_deadlines()
    except Exception as e:
        logger.warning(f"Failed to fetch deadlines for dashboard: {e}")

    # Fetch grade overview
    grade_overview: list[CourseGrade] = []
    try:
        grade_overview = _get_course_grades_overview()
    except Exception as e:
        logger.warning(f"Failed to fetch grades for dashboard: {e}")

    # Build recent grades from overview (only courses that have a grade)
    recent_grades: list[GradeItem] = [
        {
            "itemname": g["course_name"],
            "grade": g["grade"],
            "percentage": None,
            "feedback": None,
        }
        for g in grade_overview
        if g["grade"]
    ]

    # Build course list with grades attached
    dashboard_courses: list[SemesterDashboardCourse] = []
    for c in courses:
        course_grade = next(
            (
                g["grade"]
                for g in grade_overview
                if g["courseid"] == c["id"] and g["grade"]
            ),
            None,
        )
        dashboard_courses.append(
            {
                "id": c["id"],
                "fullname": c["fullname"],
                "shortname": c["shortname"],
                "progress": c["progress"],
                "grade": course_grade,
            }
        )

    return {
        "courses": dashboard_courses,
        "upcoming_deadlines": deadlines,
        "recent_grades": recent_grades,
    }


# ---------------------------------------------------------------------------
# Tool: get_actionable_tasks
# ---------------------------------------------------------------------------


def get_actionable_tasks() -> list[ActionableTask]:
    """Returns prioritized list of tasks needing action, sorted by urgency."""
    assignments = get_assignments()
    now = int(datetime.now(timezone.utc).timestamp())

    tasks: list[ActionableTask] = []

    for assign in assignments:
        try:
            status = get_assignment_status(assign["id"])
        except Exception as e:
            logger.warning(f"Could not get status for assignment {assign['id']}: {e}")
            continue

        submitted = status["submitted"]
        graded = status["graded"]
        duedate = assign["duedate"]

        # Determine urgency
        if not submitted:
            if duedate > 0 and duedate < now:
                urgency = "overdue"
            elif duedate > 0 and (duedate - now) < 3 * 86400:
                urgency = "due_soon"
            elif duedate > 0:
                urgency = "upcoming"
            else:
                urgency = "no_due_date"
        elif graded:
            urgency = "recently_graded"
        else:
            continue  # submitted but not yet graded — no action needed

        # Determine status string
        if submitted:
            task_status = "graded" if graded else "submitted"
        else:
            task_status = status["submission_status"] or "not_started"

        duedate_formatted = None
        if duedate > 0:
            duedate_formatted = datetime.fromtimestamp(
                duedate, tz=timezone.utc
            ).isoformat()

        tasks.append(
            {
                "id": assign["id"],
                "name": assign["name"],
                "course": assign["coursename"],
                "duedate": duedate,
                "duedate_formatted": duedate_formatted,
                "status": task_status,
                "urgency": urgency,
                "type": "assignment",
            }
        )

    # Sort: overdue first, then by due date, no_due_date last
    urgency_order = {
        "overdue": 0,
        "due_soon": 1,
        "upcoming": 2,
        "recently_graded": 3,
        "no_due_date": 4,
    }
    tasks.sort(
        key=lambda t: (
            urgency_order.get(t["urgency"], 99),
            t["duedate"] if t["duedate"] > 0 else float("inf"),
        )
    )

    logger.info(f"Found {len(tasks)} actionable tasks")
    return tasks


# ---------------------------------------------------------------------------
# Tool: get_overdue_assignments
# ---------------------------------------------------------------------------


def get_overdue_assignments() -> list[OverdueAssignment]:
    """Returns assignments past due date that are unsubmitted, sorted by most overdue first."""
    assignments = get_assignments()
    now = int(datetime.now(timezone.utc).timestamp())

    overdue: list[OverdueAssignment] = []
    for assign in assignments:
        if assign["duedate"] <= 0 or assign["duedate"] >= now:
            continue

        try:
            status = get_assignment_status(assign["id"])
        except Exception as e:
            logger.warning(f"Could not get status for assignment {assign['id']}: {e}")
            continue

        if status["submitted"]:
            continue

        days_overdue = (now - assign["duedate"]) // 86400

        overdue.append(
            {
                "id": assign["id"],
                "name": assign["name"],
                "course": assign["coursename"],
                "duedate": assign["duedate"],
                "duedate_formatted": datetime.fromtimestamp(
                    assign["duedate"], tz=timezone.utc
                ).isoformat(),
                "days_overdue": days_overdue,
                "submission_status": status["submission_status"],
            }
        )

    # Sort by days_overdue descending (most overdue first)
    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)
    logger.info(f"Found {len(overdue)} overdue assignments")
    return overdue


# ---------------------------------------------------------------------------
# Tool: get_recent_activity
# ---------------------------------------------------------------------------


def get_recent_activity(since: int | None = None) -> list[RecentActivity]:
    """Returns recent activity/updates across courses."""
    if since is None:
        # Default: last 7 days
        since = int(datetime.now(timezone.utc).timestamp()) - 7 * 86400

    activities: list[RecentActivity] = []

    # Primary: try Moodle's course updates API
    courses = get_my_courses()
    for course in courses:
        try:
            data = get_moodle_api_data(
                APIFunction.core_course_get_updates_since,
                params={"courseid": str(course["id"]), "since": str(since)},
            )
            to_json_file(data, f"course_updates_{course['id']}.json")
            # Parse updates from response
            instances = data.get("instances", []) if isinstance(data, dict) else []
            for inst in instances:
                activities.append(
                    {
                        "course": course["fullname"],
                        "type": "update",
                        "description": f"Update in {inst.get('component', 'unknown')}: {inst.get('name', '')}",
                        "timestamp": inst.get("timecreated", since),
                        "timestamp_formatted": datetime.fromtimestamp(
                            inst.get("timecreated", since), tz=timezone.utc
                        ).isoformat(),
                        "url": None,
                    }
                )
        except MoodleAPIError as e:
            logger.warning(
                f"Course updates API unavailable for course {course['id']}: {e}"
            )
            continue
        except Exception as e:
            logger.warning(f"Unexpected error for course {course['id']}: {e}")
            continue

    # Fallback supplement: recent grade changes if no updates API data
    if not activities:
        try:
            grades_overview = _get_course_grades_overview()
            for g in grades_overview:
                if g["grade"]:
                    activities.append(
                        {
                            "course": g["course_name"],
                            "type": "grade",
                            "description": f"Grade received: {g['grade']}",
                            "timestamp": since,
                            "timestamp_formatted": datetime.fromtimestamp(
                                since, tz=timezone.utc
                            ).isoformat(),
                            "url": None,
                        }
                    )
        except Exception as e:
            logger.warning(f"Failed to fetch grades for activity fallback: {e}")

    # Sort by timestamp descending (newest first)
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    logger.info(f"Found {len(activities)} recent activities since {since}")
    return activities


# ---------------------------------------------------------------------------
# Tool: get_course_announcements
# ---------------------------------------------------------------------------


def get_course_announcements(courseid: int | None = None) -> list[CourseAnnouncement]:
    """Gets announcements from course news forums."""
    announcements: list[CourseAnnouncement] = []

    # Step 1: Get course IDs and name map
    if courseid:
        course_ids = [courseid]
        # Get the course name
        courses = get_my_courses()
        course_map = {c["id"]: c["fullname"] for c in courses if c["id"] == courseid}
    else:
        courses = get_my_courses()
        course_ids = [c["id"] for c in courses]
        course_map = {c["id"]: c["fullname"] for c in courses}

    # Step 2: Get forums for courses
    params = format_moodle_array_params("courseids", course_ids)
    try:
        forums_data = get_moodle_api_data(
            APIFunction.mod_forum_get_forums_by_courses,
            params=params,
        )
    except MoodleAPIError as e:
        logger.warning(f"Forum API unavailable: {e}")
        return announcements

    to_json_file(forums_data, "forums.json")

    # Handle both dict and list response formats
    forums_list = forums_data if isinstance(forums_data, list) else forums_data.get("forums", [])

    # Step 3: Find news/announcement forums (type "news")
    for forum in forums_list:
        forum_type = forum.get("type", "")
        if forum_type != "news":
            continue

        forum_id = forum.get("id", 0)
        course_id = forum.get("course", 0)
        course_name = course_map.get(course_id, "")

        # Step 4: Get discussions from this forum
        try:
            discussions_data = get_moodle_api_data(
                APIFunction.mod_forum_get_discussions,
                params={"forumid": str(forum_id), "perpage": "20"},
            )
        except MoodleAPIError as e:
            logger.warning(f"Could not get discussions for forum {forum_id}: {e}")
            continue

        to_json_file(discussions_data, f"forum_discussions_{forum_id}.json")

        discussion_list = discussions_data.get("discussions", []) if isinstance(discussions_data, dict) else discussions_data
        for disc in discussion_list:
            # Strip HTML tags from message for cleaner output
            message = disc.get("message", "")
            message = re.sub(r"<[^>]+>", "", message).strip()

            created = disc.get("created", 0) or disc.get("timemodified", 0)

            announcements.append(
                {
                    "id": disc.get("id", 0),
                    "subject": disc.get("subject", ""),
                    "message": message,
                    "course": course_name,
                    "author": disc.get("userfullname", ""),
                    "date": created,
                    "date_formatted": datetime.fromtimestamp(
                        created, tz=timezone.utc
                    ).isoformat() if created > 0 else "",
                }
            )

    # Sort by date descending (newest first)
    announcements.sort(key=lambda x: x["date"], reverse=True)
    logger.info(f"Found {len(announcements)} announcements")
    return announcements


# ---------------------------------------------------------------------------
# Tool: get_course_health
# ---------------------------------------------------------------------------


def get_course_health(courseid: int) -> CourseHealth:
    """Overall health check for a course: progress, grades, unsubmitted/overdue counts."""
    now = int(datetime.now(timezone.utc).timestamp())
    course_name = ""

    # Get course info
    courses = get_my_courses()
    course = next((c for c in courses if c["id"] == courseid), None)
    progress = None
    if course:
        course_name = course["fullname"]
        progress = course.get("progress")

    # Get course grade
    grade = None
    try:
        grade_items = _get_course_grades_detail(courseid)
        for item in grade_items:
            if item["grade"] and "course" in item["itemname"].lower():
                grade = item["grade"]
                break
    except Exception as e:
        logger.warning(f"Could not fetch grades for course {courseid}: {e}")

    # Get assignments and their statuses
    assignments = get_assignments(courseids=[courseid])
    total_assignments = len(assignments)
    unsubmitted_count = 0
    overdue_count = 0

    for assign in assignments:
        try:
            status = get_assignment_status(assign["id"])
        except Exception:
            continue

        if not status["submitted"]:
            unsubmitted_count += 1
            if assign["duedate"] > 0 and assign["duedate"] < now:
                overdue_count += 1

    # Determine last activity from course content
    last_activity = None
    try:
        sections = get_course_content(courseid)
        last_activity_ts = 0
        for section in sections:
            for module in section.get("modules", []):
                contents = module.get("contents")
                if contents:
                    for content in contents:
                        ts = content.get("timemodified", 0) or content.get("timecreated", 0)
                        if ts and ts > last_activity_ts:
                            last_activity_ts = ts
        if last_activity_ts > 0:
            last_activity = datetime.fromtimestamp(
                last_activity_ts, tz=timezone.utc
            ).isoformat()
    except Exception as e:
        logger.warning(f"Could not fetch course content for course {courseid}: {e}")

    return {
        "courseid": courseid,
        "coursename": course_name,
        "progress": progress,
        "grade": grade,
        "unsubmitted_count": unsubmitted_count,
        "overdue_count": overdue_count,
        "total_assignments": total_assignments,
        "last_activity": last_activity,
    }


# ---------------------------------------------------------------------------
# Tool: get_course_progress
# ---------------------------------------------------------------------------


def get_course_progress(courseid: int | None = None) -> list[CourseProgress]:
    """Progress/completion for courses. Optionally specify a course ID, or get all courses."""
    user_id = _get_user_id()
    results: list[CourseProgress] = []

    if courseid:
        courses = [c for c in get_my_courses() if c["id"] == courseid]
    else:
        courses = get_my_courses()

    for course in courses:
        cid = course["id"]
        progress_percentage = course.get("progress")
        completed = 0
        total = 0

        # Try official completion status API
        try:
            data = get_moodle_api_data(
                APIFunction.core_completion_get_course_completion_status,
                params={"courseid": str(cid), "userid": str(user_id)},
            )
            to_json_file(data, f"completion_{cid}.json")
            # Response structure varies; try common fields
            completion_status = data.get("completed", False)
            statuses = data.get("status", []) if isinstance(data, dict) else []
            total = len(statuses)
            completed = sum(1 for s in statuses if s.get("complete", False))
            if total > 0:
                progress_percentage = round((completed / total) * 100, 1)
        except MoodleAPIError as e:
            logger.warning(f"Completion API unavailable for course {cid}: {e}")
            # Fallback: calculate from assignment submissions
            try:
                assignments = get_assignments(courseids=[cid])
                total = len(assignments)
                if total == 0:
                    completed = 0
                else:
                    submitted_count = 0
                    for a in assignments:
                        try:
                            s = get_assignment_status(a["id"])
                            if s["submitted"]:
                                submitted_count += 1
                        except Exception:
                            pass
                    completed = submitted_count
                    progress_percentage = round((submitted_count / total) * 100, 1)
            except Exception as inner_e:
                logger.warning(f"Fallback progress calc failed for course {cid}: {inner_e}")

        results.append(
            {
                "courseid": cid,
                "coursename": course["fullname"],
                "progress_percentage": progress_percentage,
                "completed_activities": completed,
                "total_activities": total,
            }
        )

    logger.info(f"Calculated progress for {len(results)} courses")
    return results


# ---------------------------------------------------------------------------
# Tool: get_study_load
# ---------------------------------------------------------------------------


def get_study_load() -> StudyLoad:
    """Study load analysis showing assignment distribution by week."""
    assignments = get_assignments()

    # Only consider assignments with due dates
    relevant = [a for a in assignments if a["duedate"] > 0]

    if not relevant:
        return {
            "weeks": [],
            "total_assignments": 0,
            "heaviest_week": None,
            "average_per_week": 0.0,
        }

    # Group by ISO week (Monday-Sunday)
    week_map: dict[str, list[Assignment]] = defaultdict(list)
    for a in relevant:
        dt = datetime.fromtimestamp(a["duedate"], tz=timezone.utc)
        # Find the Monday of that week
        monday = dt.date() - timedelta(days=dt.weekday())
        week_key = monday.isoformat()
        week_map[week_key].append(a)

    # Build WeekLoad entries
    weeks: list[WeekLoad] = []
    for week_start_str, week_assignments in sorted(week_map.items()):
        monday = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        sunday = monday + timedelta(days=6)
        course_names = sorted(set(a["coursename"] for a in week_assignments))
        count = len(week_assignments)

        if count <= 2:
            load_level = "light"
        elif count <= 4:
            load_level = "medium"
        else:
            load_level = "heavy"

        weeks.append(
            {
                "week_start": week_start_str,
                "week_end": sunday.isoformat(),
                "assignment_count": count,
                "courses": course_names,
                "load_level": load_level,
            }
        )

    # Find heaviest week
    heaviest = max(weeks, key=lambda w: w["assignment_count"]) if weeks else None

    total = sum(w["assignment_count"] for w in weeks)
    avg = round(total / len(weeks), 1) if weeks else 0.0

    return {
        "weeks": weeks,
        "total_assignments": total,
        "heaviest_week": heaviest["week_start"] if heaviest else None,
        "average_per_week": avg,
    }


# ---------------------------------------------------------------------------
# Tool: daily_briefing
# ---------------------------------------------------------------------------


def daily_briefing() -> DailyBriefing:
    """Aggregated daily summary: overdue count, today's deadlines, recent grades, upcoming events, actionable tasks."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Overdue count
    overdue_items: list[OverdueAssignment] = []
    try:
        overdue_items = get_overdue_assignments()
    except Exception as e:
        logger.warning(f"Failed to fetch overdue assignments for briefing: {e}")

    # Today's deadlines
    today_deadlines: list[UpcomingDeadline] = []
    try:
        deadlines = get_upcoming_deadlines()
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_end = today_start + timedelta(days=1)
        ts_start = int(today_start.timestamp())
        ts_end = int(today_end.timestamp())
        today_deadlines = [d for d in deadlines if ts_start <= d["duedate"] < ts_end]
    except Exception as e:
        logger.warning(f"Failed to fetch deadlines for briefing: {e}")

    # Recent grades
    recent_grades: list[GradeItem] = []
    try:
        grade_overview = _get_course_grades_overview()
        recent_grades = [
            {
                "itemname": g["course_name"],
                "grade": g["grade"],
                "percentage": None,
                "feedback": None,
            }
            for g in grade_overview
            if g["grade"]
        ]
    except Exception as e:
        logger.warning(f"Failed to fetch grades for briefing: {e}")

    # Upcoming events
    upcoming_events: list[UpcomingEvent] = []
    try:
        upcoming_events = get_upcoming_events()
    except Exception as e:
        logger.warning(f"Failed to fetch events for briefing: {e}")

    # Actionable tasks summary
    actionable_summary: list[dict] = []
    try:
        tasks = get_actionable_tasks()
        urgency_counts: dict[str, int] = {}
        for t in tasks:
            urgency_counts[t["urgency"]] = urgency_counts.get(t["urgency"], 0) + 1
        actionable_summary = [
            {"urgency": k, "count": v} for k, v in urgency_counts.items()
        ]
    except Exception as e:
        logger.warning(f"Failed to fetch tasks for briefing: {e}")

    return {
        "date": today,
        "overdue_count": len(overdue_items),
        "today_deadlines": today_deadlines,
        "recent_grades": recent_grades,
        "upcoming_events": upcoming_events,
        "actionable_tasks_summary": actionable_summary,
    }


# ---------------------------------------------------------------------------
# Tool: weekly_review
# ---------------------------------------------------------------------------


def weekly_review() -> WeeklyReview:
    """Aggregated weekly summary: submitted/graded counts, upcoming deadlines, overdue count, progress."""
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=now.weekday())  # Monday of current week
    week_start_ts = int(
        week_start.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )
    week_end = week_start + timedelta(days=7)
    week_end_ts = int(
        week_end.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )

    # Submitted count this week
    submitted_count = 0
    try:
        assignments = get_assignments()
        for a in assignments:
            if a["duedate"] > 0 and week_start_ts <= a["duedate"] < week_end_ts:
                try:
                    status = get_assignment_status(a["id"])
                    if status["submitted"]:
                        submitted_count += 1
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Failed to fetch assignments for weekly review: {e}")

    # Graded count this week (from grades)
    graded_count = 0
    try:
        grades_overview = _get_course_grades_overview()
        graded_count = sum(1 for g in grades_overview if g["grade"])
    except Exception as e:
        logger.warning(f"Failed to fetch grades for weekly review: {e}")

    # Upcoming deadlines next week
    upcoming_deadlines: list[UpcomingDeadline] = []
    try:
        all_deadlines = get_upcoming_deadlines()
        upcoming_deadlines = [
            d
            for d in all_deadlines
            if week_start_ts <= d["duedate"] < week_end_ts + 7 * 86400
        ]
    except Exception as e:
        logger.warning(f"Failed to fetch deadlines for weekly review: {e}")

    # Overdue count
    overdue_count = 0
    try:
        overdue_count = len(get_overdue_assignments())
    except Exception:
        pass

    # Progress summary
    progress_summary: list[CourseProgress] = []
    try:
        progress_summary = get_course_progress()
    except Exception as e:
        logger.warning(f"Failed to fetch progress for weekly review: {e}")

    return {
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
        "submitted_count": submitted_count,
        "graded_count": graded_count,
        "upcoming_deadlines": upcoming_deadlines,
        "overdue_count": overdue_count,
        "progress_summary": progress_summary,
    }


# ---------------------------------------------------------------------------
# Tool: ask_moodle
# ---------------------------------------------------------------------------

_QUESTION_KEYWORDS: dict[str, list[str]] = {
    "deadlines": ["deadline", "due", "due date", "overdue", "late", "submit", "дедлайн", "завдання"],
    "grades": ["grade", "score", "mark", "result", "gpa", "оцінк", "бал"],
    "courses": ["course", "class", "enroll", "progress", "курс", "предмет"],
    "assignments": ["assignment", "homework", "task", "project", "робот", "практ"],
    "announcements": ["announcement", "news", "notice", "forum", "post", "оголошення", "новин"],
    "schedule": ["schedule", "calendar", "event", "upcoming", "timetable", "розклад"],
    "search": ["search", "find", "look for", "material", "resource", "знайти", "пошук"],
}


def ask_moodle(question: str) -> MoodleAnswer:
    """Natural language query tool that routes to the right data sources based on the question."""
    question_lower = question.lower()
    data_sources_used: list[str] = []
    relevant_items: list[dict] = []
    answer_parts: list[str] = []

    # Determine which data sources to query
    sources_to_fetch = set()
    for source, keywords in _QUESTION_KEYWORDS.items():
        if any(kw in question_lower for kw in keywords):
            sources_to_fetch.add(source)

    # If no specific keywords detected, provide a general overview
    if not sources_to_fetch:
        sources_to_fetch = {"deadlines", "courses"}

    # Fetch data from each source
    if "deadlines" in sources_to_fetch:
        try:
            deadlines = get_upcoming_deadlines()
            data_sources_used.append("upcoming_deadlines")
            for d in deadlines[:5]:
                relevant_items.append({"type": "deadline", "data": d})
            if deadlines:
                answer_parts.append(f"You have {len(deadlines)} upcoming deadline(s).")
            else:
                answer_parts.append("You have no upcoming deadlines.")
        except Exception as e:
            answer_parts.append(f"Could not fetch deadlines: {e}")

    if "grades" in sources_to_fetch:
        try:
            grades = _get_course_grades_overview()
            data_sources_used.append("grades_overview")
            for g in grades:
                if g["grade"]:
                    relevant_items.append({"type": "grade", "data": g})
            graded = [g for g in grades if g["grade"]]
            if graded:
                answer_parts.append(f"Grades available for {len(graded)} course(s).")
        except Exception as e:
            answer_parts.append(f"Could not fetch grades: {e}")

    if "courses" in sources_to_fetch:
        try:
            courses = get_my_courses()
            data_sources_used.append("my_courses")
            for c in courses:
                relevant_items.append(
                    {
                        "type": "course",
                        "data": {
                            "id": c["id"],
                            "name": c["fullname"],
                            "progress": c.get("progress"),
                        },
                    }
                )
            answer_parts.append(f"You are enrolled in {len(courses)} course(s).")
        except Exception as e:
            answer_parts.append(f"Could not fetch courses: {e}")

    if "assignments" in sources_to_fetch:
        try:
            tasks = get_actionable_tasks()
            data_sources_used.append("actionable_tasks")
            urgent = [t for t in tasks if t["urgency"] in ("overdue", "due_soon")]
            if urgent:
                relevant_items.extend([{"type": "task", "data": t} for t in urgent[:5]])
                answer_parts.append(f"You have {len(urgent)} urgent task(s).")
        except Exception as e:
            answer_parts.append(f"Could not fetch assignments: {e}")

    if "announcements" in sources_to_fetch:
        try:
            announcements = get_course_announcements()
            data_sources_used.append("course_announcements")
            for a in announcements[:5]:
                relevant_items.append({"type": "announcement", "data": a})
            if announcements:
                answer_parts.append(
                    f"There are {len(announcements)} recent announcement(s)."
                )
        except Exception as e:
            answer_parts.append(f"Could not fetch announcements: {e}")

    if "schedule" in sources_to_fetch:
        try:
            events = get_upcoming_events()
            data_sources_used.append("upcoming_events")
            for e in events[:5]:
                relevant_items.append({"type": "event", "data": e})
            if events:
                answer_parts.append(f"You have {len(events)} upcoming event(s).")
        except Exception as e:
            answer_parts.append(f"Could not fetch events: {e}")

    if "search" in sources_to_fetch:
        # Extract a search query from the question
        search_query = question_lower
        for word in ["search", "find", "look for", "знайти", "пошук"]:
            search_query = search_query.replace(word, "")
        search_query = search_query.strip()
        if search_query:
            try:
                results = search_course_materials(search_query)
                data_sources_used.append("search")
                for r in results[:5]:
                    relevant_items.append({"type": "search_result", "data": r})
                if results:
                    answer_parts.append(f"Found {len(results)} result(s) for '{search_query}'.")
                else:
                    answer_parts.append(f"No results found for '{search_query}'.")
            except Exception as e:
                answer_parts.append(f"Could not search: {e}")

    answer_text = " ".join(answer_parts) if answer_parts else "No relevant information found."
    return {
        "question": question,
        "answer": answer_text,
        "data_sources": data_sources_used,
        "relevant_items": relevant_items,
    }


# ---------------------------------------------------------------------------
# Tool: analyze_assignment
# ---------------------------------------------------------------------------


def _extract_requirements_from_intro(intro: str | None) -> list[RequirementItem]:
    """Parse assignment intro text to extract structured requirements."""
    if not intro:
        return []

    requirements: list[RequirementItem] = []

    # Clean HTML tags from intro
    clean_text = re.sub(r"<[^>]+>", " ", intro)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    # Split into sentences for analysis
    sentences = re.split(r"(?<=[.!?])\s+", clean_text)

    # Keywords for categorization
    deliverable_keywords = [
        "submit", "write", "create", "develop", "design", "implement", "build",
        "prepare", "present", "report", "essay", "paper", "project", "portfolio",
        "зда", "напиш", "створ", "розроб", "підготув", "звіт",
    ]
    format_keywords = [
        "format", "length", "words", "pages", "font", "size", "spacing", "margin",
        "apa", "mla", "chicago", "harvard", "docx", "pdf", "pptx", "zip",
        "формат", "обсяг", "сторінк", "шрифт",
    ]
    constraint_keywords = [
        "must", "should", "required", "mandatory", "must not", "do not",
        "cannot", "limit", "maximum", "minimum", "at least", "no more than",
        "обов'язк", "необхід", "заборон", "ліміт", "максимум", "мінімум",
    ]
    evaluation_keywords = [
        "grade", "score", "rubric", "criteria", "evaluat", "assess", "mark",
        "weight", "percent", "point", "bonus", "penalty",
        "оцінк", "бал", "критер", "штра",
    ]
    deadline_keywords = [
        "deadline", "due", "submit by", "no later than", "before",
        "дедлайн", "до", "не пізніш",
    ]

    for sentence in sentences:
        sentence_lower = sentence.lower()
        if len(sentence.strip()) < 5:
            continue

        # Determine category
        if any(kw in sentence_lower for kw in format_keywords):
            category = "format"
        elif any(kw in sentence_lower for kw in evaluation_keywords):
            category = "evaluation"
        elif any(kw in sentence_lower for kw in deadline_keywords):
            category = "deadline"
        elif any(kw in sentence_lower for kw in deliverable_keywords):
            category = "deliverable"
        elif any(kw in sentence_lower for kw in constraint_keywords):
            category = "constraint"
        else:
            category = "deliverable"

        # Determine priority
        if any(kw in sentence_lower for kw in ["must", "required", "mandatory", "обов'язк"]):
            priority = "must"
        elif any(kw in sentence_lower for kw in ["should", "recommend", "бажано"]):
            priority = "should"
        else:
            priority = "optional"

        requirements.append(
            {
                "requirement": sentence.strip(),
                "category": category,
                "priority": priority,
                "source": "intro",
            }
        )

    return requirements


def analyze_assignment(assignid: int) -> AssignmentAnalysis:
    """Comprehensive analysis of an assignment: status, requirements, materials, progress."""
    now = int(datetime.now(timezone.utc).timestamp())

    # Get assignment details
    assignments = get_assignments()
    assignment = next((a for a in assignments if a["id"] == assignid), None)
    if not assignment:
        raise MoodleAPIError("not_found", f"Assignment {assignid} not found", "analyze_assignment")

    # Get submission status
    submission_status = None
    submitted = False
    graded = False
    status = None
    try:
        status_data = get_assignment_status(assignid)
        submission_status = status_data["submission_status"]
        submitted = status_data["submitted"]
        graded = status_data["graded"]
    except Exception as e:
        logger.warning(f"Could not get status for assignment {assignid}: {e}")

    # Calculate time remaining
    duedate = assignment["duedate"]
    days_remaining = None
    if duedate > 0:
        days_remaining = (duedate - now) // 86400
    is_overdue = duedate > 0 and duedate < now and not submitted

    duedate_formatted = None
    if duedate > 0:
        duedate_formatted = datetime.fromtimestamp(duedate, tz=timezone.utc).isoformat()

    # Extract requirements from intro
    intro = assignment.get("intro")
    requirements = _extract_requirements_from_intro(intro)
    has_intro = intro is not None and len(intro.strip()) > 0
    intro_length = len(intro) if intro else 0

    # Get course progress and grade
    course_progress = None
    course_grade = None
    try:
        progress_data = get_course_progress(courseid=assignment["courseid"])
        for p in progress_data:
            if p["courseid"] == assignment["courseid"]:
                course_progress = p["progress_percentage"]
                break
    except Exception as e:
        logger.warning(f"Could not fetch progress for course {assignment['courseid']}: {e}")

    try:
        grade_items = _get_course_grades_detail(assignment["courseid"])
        for item in grade_items:
            if item["grade"] and assignment["name"].lower() in item["itemname"].lower():
                course_grade = item["grade"]
                break
    except Exception as e:
        logger.warning(f"Could not fetch grades for course {assignment['courseid']}: {e}")

    # Count relevant materials from course content
    relevant_materials_count = 0
    try:
        content = get_course_content(assignment["courseid"])
        for section in content:
            for module in section.get("modules", []):
                if module.get("contents") or module.get("url"):
                    relevant_materials_count += 1
    except Exception as e:
        logger.warning(f"Could not fetch course content for course {assignment['courseid']}: {e}")

    return {
        "assignment_id": assignid,
        "assignment_name": assignment["name"],
        "course_name": assignment["coursename"],
        "status": submission_status,
        "submitted": submitted,
        "graded": graded,
        "duedate": duedate,
        "duedate_formatted": duedate_formatted,
        "days_remaining": days_remaining,
        "is_overdue": is_overdue,
        "intro_length": intro_length,
        "has_intro": has_intro,
        "requirements_count": len(requirements),
        "requirements": requirements[:10],  # cap at 10 for readability
        "relevant_materials_count": relevant_materials_count,
        "course_progress": course_progress,
        "course_grade": course_grade,
    }


# ---------------------------------------------------------------------------
# Tool: extract_assignment_requirements
# ---------------------------------------------------------------------------


def extract_assignment_requirements(assignid: int) -> AssignmentRequirements:
    """Extract and structure requirements, deliverables, constraints, and evaluation criteria from an assignment."""
    # Get assignment details
    assignments = get_assignments()
    assignment = next((a for a in assignments if a["id"] == assignid), None)
    if not assignment:
        raise MoodleAPIError("not_found", f"Assignment {assignid} not found", "extract_assignment_requirements")

    intro = assignment.get("intro")
    clean_intro = None
    if intro:
        clean_intro = re.sub(r"<[^>]+>", " ", intro)
        clean_intro = re.sub(r"\s+", " ", clean_intro).strip()

    # Extract all requirements
    all_requirements = _extract_requirements_from_intro(intro)

    # Categorize into specific lists
    deliverables: list[str] = []
    constraints: list[str] = []
    evaluation_criteria: list[str] = []
    deadlines: list[str] = []

    for req in all_requirements:
        text = req["requirement"]
        if req["category"] == "deliverable":
            deliverables.append(text)
        elif req["category"] == "constraint":
            constraints.append(text)
        elif req["category"] == "evaluation":
            evaluation_criteria.append(text)
        elif req["category"] == "deadline":
            deadlines.append(text)

    # Add the formal due date as a deadline if present
    if assignment["duedate"] > 0:
        duedate_str = datetime.fromtimestamp(assignment["duedate"], tz=timezone.utc).isoformat()
        deadlines.append(f"Official due date: {duedate_str}")

    # If we found no structured deliverables but have intro, create a general one
    if not deliverables and clean_intro:
        deliverables.append("Complete the assignment as described")

    # Build a summary
    summary_parts: list[str] = []
    if deliverables:
        summary_parts.append(f"Deliverables: {len(deliverables)}")
    if constraints:
        summary_parts.append(f"Constraints: {len(constraints)}")
    if evaluation_criteria:
        summary_parts.append(f"Evaluation criteria: {len(evaluation_criteria)}")
    if deadlines:
        summary_parts.append(f"Deadlines: {len(deadlines)}")

    summary = f"Assignment '{assignment['name']}' in {assignment['coursename']}"
    if summary_parts:
        summary += " — " + ", ".join(summary_parts)

    return {
        "assignment_id": assignid,
        "assignment_name": assignment["name"],
        "course_name": assignment["coursename"],
        "intro": clean_intro,
        "requirements": all_requirements,
        "deliverables": deliverables,
        "constraints": constraints,
        "evaluation_criteria": evaluation_criteria,
        "deadlines": deadlines,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Tool: find_relevant_materials
# ---------------------------------------------------------------------------


def _compute_relevance_score(text: str, keywords: list[str]) -> float:
    """Compute a simple relevance score based on keyword matches in text."""
    if not text:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for kw in keywords if kw in text_lower)
    if matches == 0:
        return 0.0
    # Normalize: more matches = higher score, capped at 1.0
    return min(matches / max(len(keywords), 1), 1.0)


def _extract_keywords_from_name(name: str) -> list[str]:
    """Extract meaningful keywords from an assignment name for search."""
    # Remove common filler words
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "this", "that",
        "these", "those", "it", "its", "not", "no", "lab", "hw", "homework",
        "task", "assignment", "project", "work", "exercise", "lesson",
        "лаб", "практ", "завдання", "робота",
    }
    # Split on spaces and punctuation, keep words > 2 chars
    words = re.findall(r"[a-zA-Zа-яА-ЯіІєЄїЇґҐ]{3,}", name)
    return [w.lower() for w in words if w.lower() not in stop_words]


def find_relevant_materials(assignid: int) -> RelevantMaterials:
    """Find course content and search results relevant to an assignment."""
    # Get assignment details
    assignments = get_assignments()
    assignment = next((a for a in assignments if a["id"] == assignid), None)
    if not assignment:
        raise MoodleAPIError("not_found", f"Assignment {assignid} not found", "find_relevant_materials")

    courseid = assignment["courseid"]
    keywords = _extract_keywords_from_name(assignment["name"])
    # Also extract keywords from the intro if available
    if assignment.get("intro"):
        intro_clean = re.sub(r"<[^>]+>", " ", assignment["intro"])
        intro_words = re.findall(r"[a-zA-Zа-яА-ЯіІєЄїЇґҐ]{3,}", intro_clean)
        intro_keywords = [w.lower() for w in intro_words[:20]]  # top 20 words from intro
        # Merge with name keywords, prioritizing name
        all_keywords = list(dict.fromkeys(keywords + intro_keywords))
    else:
        all_keywords = keywords

    # --- Course content items ---
    content_items: list[MaterialItem] = []
    try:
        sections = get_course_content(courseid)
        for section in sections:
            section_name = section.get("name", "")
            for module in section.get("modules", []):
                # Compute relevance
                mod_name = module.get("name", "")
                mod_text = f"{section_name} {mod_name}"
                score = _compute_relevance_score(mod_text, all_keywords)

                # Also check module contents for extra relevance
                contents = module.get("contents")
                if contents:
                    for c in contents:
                        fname = c.get("filename", "")
                        if fname:
                            score = max(score, _compute_relevance_score(fname, all_keywords))

                # Include items with any relevance or all items if we have no keywords
                if score > 0 or not all_keywords:
                    item_type = module.get("modname", "unknown")
                    content_items.append(
                        {
                            "title": mod_name or section_name,
                            "type": item_type,
                            "course_name": assignment["coursename"],
                            "relevance_score": round(score, 2),
                            "url": module.get("url"),
                            "description": None,
                            "section": section_name,
                        }
                    )
    except Exception as e:
        logger.warning(f"Could not fetch course content for course {courseid}: {e}")

    # Sort by relevance (highest first)
    content_items.sort(key=lambda x: x["relevance_score"], reverse=True)

    # Limit to top 20 most relevant items
    content_items = content_items[:20]

    # --- Search results from Moodle search ---
    search_results: list[MaterialItem] = []
    if keywords:
        try:
            # Search using assignment name keywords
            search_query = " ".join(keywords[:5])  # Use top 5 keywords
            raw_results = search_course_materials(search_query)
            for r in raw_results[:10]:
                # Compute relevance of search result to assignment
                score = _compute_relevance_score(
                    f"{r.get('title', '')} {r.get('content', '')}", all_keywords
                )
                search_results.append(
                    {
                        "title": r.get("title", ""),
                        "type": "search_result",
                        "course_name": r.get("course_name") or assignment["coursename"],
                        "relevance_score": round(score, 2),
                        "url": r.get("url"),
                        "description": r.get("content"),
                        "section": None,
                    }
                )
        except Exception as e:
            logger.warning(f"Could not search course materials: {e}")

    total_count = len(content_items) + len(search_results)

    return {
        "assignment_id": assignid,
        "assignment_name": assignment["name"],
        "course_name": assignment["coursename"],
        "course_content_items": content_items,
        "search_results": search_results,
        "total_count": total_count,
    }


# ---------------------------------------------------------------------------
# Tool: decompose_task
# ---------------------------------------------------------------------------


def decompose_task(assignid: int) -> TaskDecomposition:
    """Break down an assignment into subtasks with estimated effort and dependencies."""
    # Get assignment details
    assignments = get_assignments()
    assignment = next((a for a in assignments if a["id"] == assignid), None)
    if not assignment:
        raise MoodleAPIError("not_found", f"Assignment {assignid} not found", "decompose_task")

    # Get requirements for more context
    requirements_data = extract_assignment_requirements(assignid)
    deliverables = requirements_data["deliverables"]
    constraints = requirements_data["constraints"]
    intro = requirements_data.get("intro") or ""

    # Get course content to understand what topics are covered
    section_names: list[str] = []
    try:
        sections = get_course_content(assignment["courseid"])
        section_names = [s.get("name", "") for s in sections if s.get("name")]
    except Exception:
        pass

    subtasks: list[SubTask] = []
    subtask_id = 0

    # Phase 1: Understanding
    subtask_id += 1
    subtasks.append(
        {
            "id": "1",
            "title": "Understand the assignment",
            "description": f"Read and analyze the assignment description for '{assignment['name']}'. Identify all requirements, deliverables, and constraints.",
            "estimated_effort": "low",
            "dependencies": [],
            "category": "research",
        }
    )

    # Phase 2: Research — based on course content topics
    if section_names:
        subtask_id += 1
        topic_list = ", ".join(section_names[:5])
        subtasks.append(
            {
                "id": "2",
                "title": "Review course materials",
                "description": f"Study relevant course sections: {topic_list}. Take notes on key concepts related to the assignment.",
                "estimated_effort": "medium",
                "dependencies": ["1"],
                "category": "research",
            }
        )

    # Phase 3: Plan — based on deliverables
    subtask_id += 1
    plan_id = str(subtask_id)
    subtasks.append(
        {
            "id": plan_id,
            "title": "Create a work plan",
            "description": "Outline the structure and approach for completing the assignment. Define milestones and allocate time.",
            "estimated_effort": "low",
            "dependencies": ["1"],
            "category": "review",
        }
    )

    # Phase 4: Implementation — one subtask per deliverable
    impl_base_id = subtask_id + 1
    impl_dependencies = [plan_id]
    if section_names:
        impl_dependencies.append("2")

    for i, deliverable in enumerate(deliverables[:5], start=1):
        sub_id = f"{3 + i}"
        subtasks.append(
            {
                "id": sub_id,
                "title": f"Complete: {deliverable[:60]}{'...' if len(deliverable) > 60 else ''}",
                "description": f"Work on deliverable: {deliverable}. Follow the format and quality requirements specified in the assignment.",
                "estimated_effort": "high",
                "dependencies": list(impl_dependencies),
                "category": "writing",
            }
        )
        impl_dependencies = [sub_id]  # next deliverable depends on previous

    # Phase 5: Review and refinement
    review_id = str(len(subtasks) + 1)
    last_impl_id = subtasks[-1]["id"] if len(subtasks) > 3 else plan_id
    subtasks.append(
        {
            "id": review_id,
            "title": "Review and refine",
            "description": "Review all deliverables against the requirements and constraints. Check for completeness and quality.",
            "estimated_effort": "medium",
            "dependencies": [last_impl_id],
            "category": "review",
        }
    )

    # Phase 6: Submit
    submit_id = str(len(subtasks) + 1)
    subtasks.append(
        {
            "id": submit_id,
            "title": "Submit the assignment",
            "description": f"Prepare final submission and upload to Moodle before the deadline. Assignment ID: {assignid}.",
            "estimated_effort": "low",
            "dependencies": [review_id],
            "category": "submission",
        }
    )

    # Determine critical path (longest chain of dependencies)
    critical_path: list[str] = []
    current_id = "1"
    while current_id:
        critical_path.append(current_id)
        # Find the next subtask that depends on current
        next_deps = [s for s in subtasks if current_id in s["dependencies"]]
        if next_deps:
            # Pick the one with highest effort
            effort_order = {"high": 0, "medium": 1, "low": 2}
            next_dep = min(next_deps, key=lambda s: effort_order.get(s["estimated_effort"], 1))
            current_id = next_dep["id"]
        else:
            break

    # Estimate total effort
    effort_counts = {"high": 0, "medium": 0, "low": 0}
    for s in subtasks:
        effort_counts[s["estimated_effort"]] = effort_counts.get(s["estimated_effort"], 0) + 1

    if effort_counts["high"] >= 3:
        estimated_total_effort = "high"
    elif effort_counts["high"] >= 1 or effort_counts["medium"] >= 2:
        estimated_total_effort = "medium"
    else:
        estimated_total_effort = "low"

    return {
        "assignment_id": assignid,
        "assignment_name": assignment["name"],
        "course_name": assignment["coursename"],
        "total_subtasks": len(subtasks),
        "subtasks": subtasks,
        "critical_path": critical_path,
        "estimated_total_effort": estimated_total_effort,
    }


# ---------------------------------------------------------------------------
# Tool: create_implementation_plan
# ---------------------------------------------------------------------------


def create_implementation_plan(assignid: int) -> ImplementationPlan:
    """Create a step-by-step implementation plan for completing an assignment."""
    now = int(datetime.now(timezone.utc).timestamp())

    # Get assignment details
    assignments = get_assignments()
    assignment = next((a for a in assignments if a["id"] == assignid), None)
    if not assignment:
        raise MoodleAPIError("not_found", f"Assignment {assignid} not found", "create_implementation_plan")

    duedate = assignment["duedate"]
    duedate_formatted = None
    if duedate > 0:
        duedate_formatted = datetime.fromtimestamp(duedate, tz=timezone.utc).isoformat()

    days_remaining = None
    if duedate > 0:
        days_remaining = (duedate - now) // 86400

    # Get task decomposition
    decomposition = decompose_task(assignid)

    # Get relevant materials for resource references
    materials: list[MaterialItem] = []
    try:
        materials_data = find_relevant_materials(assignid)
        materials = materials_data["course_content_items"][:5]  # top 5 most relevant
    except Exception as e:
        logger.warning(f"Could not fetch materials for plan: {e}")

    # Build plan steps from decomposition subtasks
    steps: list[PlanStep] = []
    step_number = 0

    # Duration estimates based on effort and time available
    if days_remaining is not None and days_remaining > 0:
        # Distribute time across steps
        if days_remaining <= 1:
            duration_map = {"high": "1-2 hours", "medium": "30-60 minutes", "low": "15-30 minutes"}
        elif days_remaining <= 3:
            duration_map = {"high": "3-5 hours", "medium": "1-3 hours", "low": "30-60 minutes"}
        elif days_remaining <= 7:
            duration_map = {"high": "5-10 hours", "medium": "2-4 hours", "low": "1-2 hours"}
        else:
            duration_map = {"high": "1-3 days", "medium": "4-8 hours", "low": "1-2 hours"}
    else:
        duration_map = {"high": "5-10 hours", "medium": "2-4 hours", "low": "1-2 hours"}

    for subtask in decomposition["subtasks"]:
        step_number += 1

        # Find relevant materials for this step's category
        step_resources: list[str] = []
        if subtask["category"] == "research":
            step_resources = [m["title"] for m in materials[:3]]
        elif subtask["category"] == "writing":
            step_resources = [m["title"] for m in materials[:2]]

        steps.append(
            {
                "step_number": step_number,
                "title": subtask["title"],
                "description": subtask["description"],
                "subtask_ids": [subtask["id"]],
                "estimated_duration": duration_map.get(subtask["estimated_effort"], "1-2 hours"),
                "resources": step_resources,
            }
        )

    # Build milestones from critical path
    milestones: list[str] = []
    critical_path = decomposition["critical_path"]
    for i, cp_id in enumerate(critical_path):
        cp_task = next((s for s in decomposition["subtasks"] if s["id"] == cp_id), None)
        if cp_task:
            if i == 0:
                milestones.append(f"✓ Start: {cp_task['title']}")
            elif i == len(critical_path) - 1:
                milestones.append(f"🎯 Final: {cp_task['title']}")
            else:
                milestones.append(f"→ Checkpoint: {cp_task['title']}")

    # Identify risk factors
    risk_factors: list[str] = []
    if days_remaining is not None:
        if days_remaining < 0:
            risk_factors.append(f"Assignment is overdue by {abs(days_remaining)} day(s)")
        elif days_remaining <= 1:
            risk_factors.append("Very tight deadline — less than 1 day remaining")
        elif days_remaining <= 3:
            risk_factors.append("Short deadline — prioritize critical path tasks")

    if not assignment.get("intro") or len(assignment.get("intro") or "") < 50:
        risk_factors.append("Assignment description is minimal — clarify requirements with instructor")

    if decomposition["estimated_total_effort"] == "high":
        risk_factors.append("High overall effort required — start early and allocate sufficient time")

    if not materials:
        risk_factors.append("Limited course materials found — may need external resources")

    return {
        "assignment_id": assignid,
        "assignment_name": assignment["name"],
        "course_name": assignment["coursename"],
        "duedate": duedate,
        "duedate_formatted": duedate_formatted,
        "days_remaining": days_remaining,
        "total_steps": len(steps),
        "steps": steps,
        "milestones": milestones,
        "risk_factors": risk_factors,
    }


if __name__ == "__main__":
    upcoming_events = get_upcoming_events()
    to_json_file(upcoming_events, "upcoming_events.json")