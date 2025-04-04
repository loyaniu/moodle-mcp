from mcp.server.fastmcp import FastMCP

import api

mcp = FastMCP("moodle-mcp", dependencies=["glom", "requests"])


@mcp.tool()
def get_upcoming_events() -> list[api.UpcomingEvent]:
    """Get upcoming events from moodle"""
    return api.get_upcoming_events()
