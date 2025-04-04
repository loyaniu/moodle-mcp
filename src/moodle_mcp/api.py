from typing import TypedDict

from glom import glom

from .logger import logger
from .moodle import APIFunction, get_moodle_api_data
from .utils import to_json_file


class UpcomingEvent(TypedDict):
    id: int
    name: str
    formattedtime: str
    url: str
    description: str
    popupname: str


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


if __name__ == "__main__":
    upcoming_events = get_upcoming_events()
    to_json_file(upcoming_events, "upcoming_events.json")
