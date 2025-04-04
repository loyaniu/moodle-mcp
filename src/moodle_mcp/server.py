from mcp.server.fastmcp import FastMCP

from . import api
from .logger import logger

mcp = FastMCP("moodle-mcp", dependencies=["glom", "requests"])


@mcp.tool()
def get_upcoming_events() -> list[api.UpcomingEvent]:
    """Get upcoming events from moodle"""
    return api.get_upcoming_events()


def main():
    logger.info("Starting moodle-mcp server")
    mcp.run()
