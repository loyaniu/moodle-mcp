from enum import Enum

import requests
from glom import delete

from .logger import logger
from .utils import getenv

MOODLE_URL = getenv("MOODLE_URL")
MOODLE_TOKEN = getenv("MOODLE_TOKEN")


class APIFunction(Enum):
    core_calendar_get_calendar_upcoming_view = (
        "core_calendar_get_calendar_upcoming_view"
    )


# Fields not needed for specific API functions
# Using `glom` to extract fields not needed
DELETE_FIELDS = {
    APIFunction.core_calendar_get_calendar_upcoming_view: [
        "events.*.course.courseimage"
    ]
}


def get_moodle_api_data(function: APIFunction, use_original_data=True):
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": function.value,
        "moodlewsrestformat": "json",
    }

    logger.info(f"Getting moodle data for `{function.value}`")
    rsp = requests.get(MOODLE_URL, params=params)

    data = rsp.json()

    if use_original_data:
        return data

    for field_path in DELETE_FIELDS.get(function, []):
        delete(data, field_path)

    return data
