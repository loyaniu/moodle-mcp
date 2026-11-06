"""Course catalogue search and self enrolment for the authenticated user."""

from typing_extensions import TypedDict

from .moodle import APIFunction, get_moodle_api_data


class CatalogueCourse(TypedDict):
    id: int
    fullname: str
    shortname: str
    summary: str
    categoryid: int
    categoryname: str
    enrollmentmethods: list[str]


class CourseSearch(TypedDict):
    courses: list[CatalogueCourse]
    total: int
    page: int
    perpage: int
    warnings: list[dict]


class EnrolmentMethod(TypedDict):
    id: int
    courseid: int
    type: str
    name: str
    status: bool | str


class SelfEnrolmentInfo(EnrolmentMethod):
    requires_key: bool


class EnrolmentResult(TypedDict):
    courseid: int
    status: bool
    warnings: list[dict]


def _positive_id(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def search_courses(query: str, page: int = 0, perpage: int = 20) -> CourseSearch:
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    if page < 0 or not 1 <= perpage <= 100:
        raise ValueError("page must be >= 0 and perpage must be between 1 and 100")
    data = get_moodle_api_data(APIFunction.core_course_search_courses, params={
        "criterianame": "search", "criteriavalue": query,
        "page": page, "perpage": perpage, "limittoenrolled": 0,
    })
    fields = CatalogueCourse.__annotations__
    courses = [{key: course.get(key, [] if key == "enrollmentmethods" else
                 0 if key in {"id", "categoryid"} else "") for key in fields}
               for course in data.get("courses", [])]
    return {"courses": courses, "total": data["total"], "page": page,
            "perpage": perpage, "warnings": data.get("warnings", [])}


def get_course_enrolment_methods(courseid: int) -> list[EnrolmentMethod]:
    _positive_id(courseid, "courseid")
    data = get_moodle_api_data(APIFunction.core_enrol_get_course_enrolment_methods,
                               params={"courseid": courseid})
    return [{key: method[key] for key in EnrolmentMethod.__annotations__}
            for method in data]


def get_self_enrolment_info(instanceid: int) -> SelfEnrolmentInfo:
    _positive_id(instanceid, "instanceid")
    data = get_moodle_api_data(APIFunction.enrol_self_get_instance_info,
                               params={"instanceid": instanceid})
    result = {key: data[key] for key in EnrolmentMethod.__annotations__}
    # Moodle returns a requirement flag, never expose it as a password.
    result["requires_key"] = bool(data.get("enrolpassword", False))
    return result


def self_enrol_course(courseid: int, password: str = "",
                     instanceid: int | None = None) -> EnrolmentResult:
    _positive_id(courseid, "courseid")
    if instanceid is not None:
        _positive_id(instanceid, "instanceid")
    params = {"courseid": courseid, "password": password}
    if instanceid is not None:
        params["instanceid"] = instanceid
    data = get_moodle_api_data(APIFunction.enrol_self_enrol_user, params=params)
    # A wrong key is a normal HTTP 200 response with status=false and warnings.
    return {"courseid": courseid, "status": data["status"],
            "warnings": data.get("warnings", [])}
