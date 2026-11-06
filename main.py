# `mcp run` / `mcp install` look for a server object named `mcp` in this file.
from src.moodle_mcp.server import main, mcp  # noqa: F401

if __name__ == "__main__":
    main()
