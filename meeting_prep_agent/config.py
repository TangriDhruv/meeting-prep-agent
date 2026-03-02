"""Configuration — loads .env and exposes typed constants."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
DAYS_AHEAD: int = int(os.getenv("DAYS_AHEAD", "7"))
MAX_EMAIL_RESULTS: int = int(os.getenv("MAX_EMAIL_RESULTS", "10"))
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))
# Credentials file for the Google Calendar MCP server (calendar OAuth)
GOOGLE_CALENDAR_CREDENTIALS: str = os.getenv(
    "GOOGLE_CALENDAR_CREDENTIALS", str(_project_root / "credentials.json")
)
# Where the MCP server stores its OAuth token (defaults to project root to avoid .config permission issues)
GOOGLE_CALENDAR_MCP_TOKEN_PATH: str = os.getenv(
    "GOOGLE_CALENDAR_MCP_TOKEN_PATH", str(_project_root / "calendar_token.json")
)
# Credentials + token files for Gmail (direct API OAuth)
CREDENTIALS_FILE: str = os.getenv("CREDENTIALS_FILE", str(_project_root / "credentials.json"))
TOKEN_FILE: str = os.getenv("TOKEN_FILE", str(_project_root / "token.json"))
EMAIL_RECIPIENT: str = os.getenv("EMAIL_RECIPIENT", "")
EMAIL_SUBJECT_PREFIX: str = os.getenv("EMAIL_SUBJECT_PREFIX", "Meeting Prep Brief")
