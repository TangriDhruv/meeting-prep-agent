"""Gmail tool definitions in Anthropic tool-use JSON schema format.

Calendar tools are discovered at runtime from the Google Calendar MCP server
and merged with these Gmail tools inside agent.py.
"""

GMAIL_TOOL_DEFINITIONS = [
    {
        "name": "get_emails_with_person",
        "description": (
            "Search Gmail for recent email threads sent to or received from a specific person. "
            "Returns thread summaries with subject, snippet, and message count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "The email address of the person to search for.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of threads to return (default: 5).",
                },
            },
            "required": ["email"],
        },
    },
    {
        "name": "search_emails",
        "description": (
            "Search Gmail using any Gmail search query (e.g. topic keywords, subject lines, labels). "
            "Returns thread summaries with subject, snippet, and message count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query string (same syntax as Gmail search box).",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of threads to return (default: 5).",
                },
            },
            "required": ["query"],
        },
    },
]
