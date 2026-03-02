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

SYSTEM_PROMPT = """You are a professional meeting preparation assistant. Your job is to help the user prepare for their upcoming meetings by researching relevant context from their calendar and email.

Follow this process:
1. Use the available calendar tools to list upcoming events.
2. For each meeting, look at the attendees and call get_emails_with_person for each attendee to understand your recent communication history.
3. Call search_emails using the meeting title or relevant keywords to find email threads about the meeting topic.
4. Synthesize everything into a structured Meeting Prep Brief using TABLES.

Your final output must use markdown tables throughout. Use this structure:

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
If there are no upcoming meetings, say so and suggest the user check their calendar or try a longer time range."""


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


async def _run_agent_async(
    gmail_creds, days_ahead: int, meeting_filter: str | None
) -> str:
    """Inner async implementation of the agentic loop."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    gmail_executor = ToolExecutor(gmail_creds)

    # Inherit the full shell environment so npx/node are on PATH
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

    console.print("[dim]Starting Google Calendar MCP server...[/dim]")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover calendar tools from the MCP server
            mcp_tools_response = await session.list_tools()
            calendar_tool_names = {t.name for t in mcp_tools_response.tools}
            calendar_tools = [_mcp_tool_to_anthropic(t) for t in mcp_tools_response.tools]

            console.print(
                f"[dim]MCP server ready — {len(calendar_tools)} calendar tool(s) available[/dim]"
            )

            # Merge calendar (MCP) + Gmail (direct) tools
            all_tools = calendar_tools + GMAIL_TOOL_DEFINITIONS

            if meeting_filter:
                user_content = (
                    f"Please prepare a meeting prep brief for my upcoming meeting matching '{meeting_filter}'. "
                    f"Look up my calendar and relevant emails to give me actionable preparation notes."
                )
            else:
                user_content = (
                    f"Please prepare a meeting prep brief for all my upcoming meetings "
                    f"in the next {days_ahead} days. "
                    f"Look up my calendar and relevant emails for each meeting, "
                    f"then give me actionable preparation notes."
                )

            messages = [{"role": "user", "content": user_content}]

            while True:
                for attempt in range(5):
                    try:
                        response = client.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=MAX_TOKENS,
                            system=SYSTEM_PROMPT,
                            tools=all_tools,
                            messages=messages,
                        )
                        break
                    except anthropic.OverloadedError:
                        if attempt == 4:
                            raise
                        wait = 2 ** attempt
                        console.print(f"[yellow]API overloaded, retrying in {wait}s...[/yellow]")
                        time.sleep(wait)

                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason == "end_turn":
                    for block in response.content:
                        if block.type == "text":
                            return block.text
                    return ""

                if response.stop_reason == "tool_use":
                    tool_results = []

                    for block in response.content:
                        if block.type != "tool_use":
                            continue

                        console.print(
                            f"[bold cyan][tool][/bold cyan] {block.name}({_fmt_input(block.input)})"
                        )

                        if block.name in calendar_tool_names:
                            # Route to Google Calendar MCP server
                            try:
                                mcp_result = await session.call_tool(block.name, block.input)
                                result_str = "\n".join(
                                    c.text for c in mcp_result.content if hasattr(c, "text")
                                ) or json.dumps({"result": "ok", "content": []})
                            except Exception as exc:
                                result_str = json.dumps({"error": str(exc)})
                        else:
                            # Route to Gmail direct API
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


def run_agent(gmail_creds, days_ahead: int = DAYS_AHEAD, meeting_filter: str | None = None) -> str:
    """Synchronous entry point — runs the async agent loop via asyncio."""
    return asyncio.run(_run_agent_async(gmail_creds, days_ahead, meeting_filter))
