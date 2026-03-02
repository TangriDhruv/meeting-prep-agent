"""CLI entry point for the Meeting Prep Agent."""

import argparse
import sys

from .config import DAYS_AHEAD
from .google_auth import get_credentials
from .agent import run_agent
from .formatter import print_brief


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meeting-prep-agent",
        description="Generate an AI-powered Meeting Prep Brief from your calendar and email.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DAYS_AHEAD,
        metavar="INT",
        help=f"How many days ahead to look for meetings (default: {DAYS_AHEAD}).",
    )
    parser.add_argument(
        "--meeting",
        type=str,
        default=None,
        metavar="TEXT",
        help="Filter to a specific meeting by keyword (e.g. 'Q4 Planning').",
    )
    parser.add_argument(
        "--output",
        choices=["terminal", "markdown"],
        default="terminal",
        help="Output format: 'terminal' (rich, default) or 'markdown' (plain text for piping).",
    )
    parser.add_argument(
        "--email",
        action="store_true",
        default=False,
        help="Send the brief to EMAIL_RECIPIENT in .env instead of printing.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        # Gmail credentials (calendar auth is handled by the MCP server separately)
        gmail_creds = get_credentials()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    brief = run_agent(gmail_creds, days_ahead=args.days, meeting_filter=args.meeting)

    if not brief:
        print("No brief was generated. The agent may have encountered an error.", file=sys.stderr)
        sys.exit(1)

    if args.email:
        from .email_sender import send_brief_email
        send_brief_email(gmail_creds, brief)
        print("Brief sent via email.", file=sys.stderr)
    else:
        print_brief(brief, output_format=args.output)


if __name__ == "__main__":
    main()
