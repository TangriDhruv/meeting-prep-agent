"""Dispatches Claude's Gmail tool calls to the Gmail API.

Calendar tool calls are forwarded directly to the MCP session inside agent.py.
"""

import json
from google.oauth2.credentials import Credentials

from .gmail_client import fetch_emails_with_person, search_emails
from .config import MAX_EMAIL_RESULTS


class ToolExecutor:
    """Executes Gmail tool calls and returns JSON-serialized results."""

    def __init__(self, creds: Credentials) -> None:
        self._creds = creds

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """Dispatch a Gmail tool call and return the result as a JSON string."""
        try:
            result = self._dispatch(tool_name, tool_input)
            return json.dumps(result, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def _dispatch(self, tool_name: str, tool_input: dict):
        if tool_name == "get_emails_with_person":
            email = tool_input["email"]
            max_results = tool_input.get("max_results", MAX_EMAIL_RESULTS)
            return fetch_emails_with_person(self._creds, email, max_results)

        elif tool_name == "search_emails":
            query = tool_input["query"]
            max_results = tool_input.get("max_results", MAX_EMAIL_RESULTS)
            return search_emails(self._creds, query, max_results)

        else:
            raise ValueError(f"Unknown Gmail tool: {tool_name}")
