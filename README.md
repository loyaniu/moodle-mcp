# Moodle-MCP

> A Model Context Protocol (MCP) server implementation that provides capabilities to interact with Moodle LMS.
>
> **Warning:** This project is still in development, only some functions are available.

## Features

- [x] Get upcoming events from Moodle

## API Reference

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
