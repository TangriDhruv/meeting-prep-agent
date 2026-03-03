"""Core agentic loop — drives Claude through calendar (MCP) + email (direct API) research."""

import asyncio
import json
import os
import time

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console

from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL, DAYS_AHEAD, MAX_TOKENS, GOOGLE_CALENDAR_CREDENTIALS, GOOGLE_CALENDAR_MCP_TOKEN_PATH
from .tools import GMAIL_TOOL_DEFINITIONS
from .tool_executor import ToolExecutor

console = Console(stderr=True)

INTER_MEETING_SLEEP_SECONDS = 10

DISCOVERY_SYSTEM_PROMPT = """You are a calendar assistant. Your only job is to list upcoming meetings.

Use the calendar tools to find meetings in the requested time range, then return ONLY a JSON array.

Each object in the array must have exactly these fields:
- "title": string — meeting name
- "datetime": string — date and time (e.g. "2026-03-05T14:00:00")
- "duration_minutes": integer — meeting length in minutes
- "location": string — location or video link (empty string if none)
- "attendees": array of strings — attendee email addresses
- "description": string — meeting description or agenda (empty string if none)

Output ONLY the raw JSON array. No markdown fences, no explanation, no preamble."""

PER_MEETING_SYSTEM_PROMPT = """You are a professional meeting preparation assistant. Your job is to research one specific meeting and produce a concise prep brief.

Process:
1. For each attendee email provided, call get_emails_with_person to review recent communication history.
2. Call search_emails using the meeting title and relevant keywords to find email threads about this topic.
3. Synthesize everything into a structured Meeting Prep Brief using TABLES.

Your output must use markdown tables throughout. Use this exact structure:

---

## [Meeting Title] — [Date & Time]

### Overview
| Field | Details |
|---|---|
| Date & Time | |
| Duration | |
| Location / Link | |
| Attendees | |
| Round / Stage | |

### Key Email Themes
| Thread | Key Takeaway |
|---|---|
| [Subject] | [What was discussed / decided / pending] |

### Suggested Agenda
| # | Topic | Time |
|---|---|---|
| 1 | | |

### Things to Prepare
| Priority | Action Item | Why |
|---|---|---|
| 🔴 High | | |
| 🟡 Medium | | |

### Open Action Items
| Item | Status | Action Needed |
|---|---|---|

---

Be specific and actionable. Draw directly from email content — quote specific details where useful.
If you find no relevant emails, say so clearly rather than making things up.
Output ONLY the markdown brief section. No preamble or commentary."""


def _mcp_tool_to_anthropic(tool) -> dict:
    """Convert an MCP Tool object to the Anthropic tool dict format."""
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema,
    }


def _fmt_input(input_dict: dict) -> str:
    """Format tool input for display, truncating long values."""
    parts = []
    for k, v in input_dict.items():
        v_str = str(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        parts.append(f"{k}={v_str!r}")
    return ", ".join(parts)


def _parse_meeting_list(text: str) -> list[dict]:
    """Parse a JSON array of meetings from Claude's discovery response."""
    text = text.strip()
    # Strip optional ```json ... ``` fences
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        return []
    except Exception:
        return []


def _build_meeting_context(meeting: dict) -> str:
    """Format a meeting dict into the user message for the per-meeting agent."""
    attendees = meeting.get("attendees", [])
    attendees_str = ", ".join(attendees) if attendees else "None listed"
    return (
        f"Meeting: {meeting.get('title', 'Untitled')}\n"
        f"Date/Time: {meeting.get('datetime', 'Unknown')}\n"
        f"Duration: {meeting.get('duration_minutes', '?')} minutes\n"
        f"Location: {meeting.get('location', '') or 'Not specified'}\n"
        f"Attendees: {attendees_str}\n"
        f"Description: {meeting.get('description', '') or 'None'}\n"
        f"\n"
        f"Fetch emails for each attendee and search for this meeting topic, "
        f"then write the complete meeting prep brief."
    )


async def _run_discovery_agent_async(
    days_ahead: int, meeting_filter: str | None
) -> list[dict]:
    """Phase 1: Discover meetings via calendar MCP. Returns a list of meeting dicts."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    mcp_env = {
        **os.environ,
        "GOOGLE_OAUTH_CREDENTIALS": GOOGLE_CALENDAR_CREDENTIALS,
        "GOOGLE_CALENDAR_MCP_TOKEN_PATH": GOOGLE_CALENDAR_MCP_TOKEN_PATH,
    }

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@cocal/google-calendar-mcp"],
        env=mcp_env,
    )

    console.print("[bold]Phase 1: Starting calendar discovery...[/bold]")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools_response = await session.list_tools()
            calendar_tool_names = {t.name for t in mcp_tools_response.tools}
            calendar_tools = [_mcp_tool_to_anthropic(t) for t in mcp_tools_response.tools]

            console.print(
                f"[dim]MCP server ready — {len(calendar_tools)} calendar tool(s) available[/dim]"
            )

            if meeting_filter:
                user_content = (
                    f"Find my upcoming meeting matching '{meeting_filter}' and return the JSON array."
                )
            else:
                user_content = (
                    f"Find all my upcoming meetings in the next {days_ahead} days "
                    f"and return the JSON array."
                )

            messages = [{"role": "user", "content": user_content}]

            while True:
                for attempt in range(5):
                    try:
                        response = client.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=2048,
                            system=DISCOVERY_SYSTEM_PROMPT,
                            tools=calendar_tools,
                            messages=messages,
                        )
                        break
                    except (anthropic.RateLimitError, anthropic.APIStatusError) as exc:
                        if attempt == 4:
                            raise
                        wait = 2 ** attempt
                        console.print(f"[yellow]API rate limited, retrying in {wait}s...[/yellow]")
                        time.sleep(wait)

                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason == "end_turn":
                    for block in response.content:
                        if block.type == "text":
                            return _parse_meeting_list(block.text)
                    return []

                if response.stop_reason == "tool_use":
                    tool_results = []

                    for block in response.content:
                        if block.type != "tool_use":
                            continue

                        console.print(
                            f"[dim][tool][/dim] {block.name}({_fmt_input(block.input)})"
                        )

                        if block.name in calendar_tool_names:
                            try:
                                mcp_result = await session.call_tool(block.name, block.input)
                                result_str = "\n".join(
                                    c.text for c in mcp_result.content if hasattr(c, "text")
                                ) or json.dumps({"result": "ok", "content": []})
                            except Exception as exc:
                                result_str = json.dumps({"error": str(exc)})
                        else:
                            result_str = json.dumps({"error": f"Unknown tool: {block.name}"})

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_str,
                            }
                        )

                    messages.append({"role": "user", "content": tool_results})

                else:
                    console.print(
                        f"[yellow]Unexpected stop_reason: {response.stop_reason}[/yellow]"
                    )
                    break

    return []


def _run_per_meeting_agent(gmail_executor: ToolExecutor, meeting: dict) -> str:
    """Phase 2: Research one meeting via Gmail and produce a prep brief. Sync."""
    title = meeting.get("title", "Untitled")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_content = _build_meeting_context(meeting)
    messages = [{"role": "user", "content": user_content}]

    console.print(f"\n[bold]Phase 2: Preparing brief for '{title}'...[/bold]")

    while True:
        for attempt in range(5):
            try:
                response = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=MAX_TOKENS,
                    system=PER_MEETING_SYSTEM_PROMPT,
                    tools=GMAIL_TOOL_DEFINITIONS,
                    messages=messages,
                )
                break
            except (anthropic.RateLimitError, anthropic.APIStatusError) as exc:
                if attempt == 4:
                    raise
                wait = 2 ** attempt
                console.print(f"[yellow]API rate limited, retrying in {wait}s...[/yellow]")
                time.sleep(wait)

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    return block.text.strip()
            return ""

        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                console.print(
                    f"[bold cyan][tool][/bold cyan] [{title}] {block.name}({_fmt_input(block.input)})"
                )

                result_str = gmail_executor.execute(block.name, block.input)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        else:
            console.print(
                f"[yellow]Unexpected stop_reason: {response.stop_reason}[/yellow]"
            )
            break

    return ""


async def _run_agent_async(
    gmail_creds, days_ahead: int, meeting_filter: str | None
) -> str:
    """Orchestrator: runs discovery then per-meeting agents sequentially."""
    # Phase 1: Discover meetings via calendar MCP
    meetings = await _run_discovery_agent_async(days_ahead, meeting_filter)

    if not meetings:
        return (
            "No upcoming meetings found. "
            "Try increasing the time range with `--days N` or check your calendar."
        )

    console.print(f"\n[green]Discovery found {len(meetings)} meeting(s)[/green]")

    # Phase 2: Research each meeting with an isolated Gmail agent
    gmail_executor = ToolExecutor(gmail_creds)
    briefs = []

    for i, meeting in enumerate(meetings):
        if i > 0:
            console.print(
                f"[dim]Sleeping {INTER_MEETING_SLEEP_SECONDS}s before next meeting...[/dim]"
            )
            time.sleep(INTER_MEETING_SLEEP_SECONDS)
        try:
            brief = _run_per_meeting_agent(gmail_executor, meeting)
            if brief:
                briefs.append(brief)
        except Exception as exc:
            title = meeting.get("title", "Unknown")
            console.print(f"[red]Failed to prepare brief for '{title}': {exc}[/red]")
            briefs.append(f"---\n\n## {title}\n\n_Failed to generate brief: {exc}_\n\n---")

    return "\n\n".join(briefs) if briefs else "Meetings found but no briefs could be generated."


def run_agent(gmail_creds, days_ahead: int = DAYS_AHEAD, meeting_filter: str | None = None) -> str:
    """Synchronous entry point — runs the async agent loop via asyncio."""
    return asyncio.run(_run_agent_async(gmail_creds, days_ahead, meeting_filter))
