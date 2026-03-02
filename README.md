# Meeting Prep Agent

AI-powered daily meeting prep briefs from Google Calendar and Gmail, delivered to your inbox every morning.

## What it does

Meeting Prep Agent reads your Google Calendar and Gmail, then uses Claude to generate a structured, actionable prep brief for each of your upcoming meetings. For every meeting it:

- Pulls the event details (time, attendees, location/link)
- Searches your Gmail for relevant threads with attendees and meeting topics
- Synthesises everything into a markdown brief with an overview, key email themes, suggested agenda, things to prepare, and open action items

You can run it manually in the terminal, save output to a markdown file, or have it email you the brief automatically every morning at 9 AM via macOS launchd.

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│                        SCHEDULER (macOS)                        │
│                                                                 │
│   launchd (9 AM daily)                                          │
│       └──► run_email_brief.sh                                   │
│                └──► python3 -m meeting_prep_agent.main          │
│                             --days 1 --email                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         CLI (main.py)                           │
│                                                                 │
│   --days N   --meeting TEXT   --output terminal|markdown        │
│   --email                                                       │
│                                                                 │
│   1. google_auth.py  →  OAuth 2.0 (gmail.readonly + gmail.send) │
│   2. run_agent()     →  generates the brief                     │
│   3a. print_brief()  →  terminal / markdown output              │
│   3b. send_brief_email() → email delivery                       │
└───────────┬─────────────────────────────┬───────────────────────┘
            │                             │
            ▼                             ▼
┌───────────────────────┐     ┌───────────────────────────┐
│    AGENT (agent.py)   │     │  EMAIL SENDER             │
│                       │     │  (email_sender.py)        │
│  Agentic loop:        │     │                           │
│  while tools needed:  │     │  markdown → HTML          │
│    call Claude API    │     │  MIMEMultipart (alt.)     │
│    execute tools      │     │  Gmail API → send()       │
│    feed results back  │     └───────────────────────────┘
│  until end_turn       │
└───────┬───────────────┘
        │
        │  Tools available to Claude
        ├──────────────────────────────────────────────────┐
        │                                                  │
        ▼                                                  ▼
┌───────────────────────┐                    ┌────────────────────────┐
│  GOOGLE CALENDAR      │                    │  GMAIL                 │
│  (MCP via stdio)      │                    │  (direct API)          │
│                       │                    │                        │
│  @cocal/google-       │                    │  tools.py              │
│  calendar-mcp (npx)   │                    │    get_emails_with_    │
│                       │                    │      person()          │
│  list-calendars       │                    │    search_emails()     │
│  list-events          │                    │    get_email_body()    │
│  get-current-time     │                    │                        │
│  + 10 more tools      │                    │  tool_executor.py      │
│                       │                    │    routes calls to     │
│  calendar_token.json  │                    │    gmail_client.py     │
└───────────────────────┘                    └────────────────────────┘
        │                                                  │
        ▼                                                  ▼
┌───────────────────────┐                    ┌────────────────────────┐
│  Google Calendar API  │                    │  Gmail API             │
│  (OAuth via MCP)      │                    │  (OAuth via            │
│                       │                    │   google_auth.py)      │
└───────────────────────┘                    └────────────────────────┘
```

**Data flow:**

1. **launchd** fires `run_email_brief.sh` at 9 AM
2. **main.py** authenticates with Google OAuth and kicks off the agent
3. **agent.py** enters an agentic loop — calls Claude, which decides what tools to use
4. Claude calls **Calendar tools** (via MCP server over stdio) and **Gmail tools** (via direct API) iteratively until it has enough context
5. Claude writes the final markdown brief and returns it
6. **email_sender.py** converts it to HTML and sends it via Gmail API to `EMAIL_RECIPIENT`

## Project structure

```
meeting-prep-agent/
├── meeting_prep_agent/
│   ├── agent.py          # Agentic loop (Claude + MCP + Gmail tools)
│   ├── calendar_client.py
│   ├── config.py         # Env var constants
│   ├── email_sender.py   # Markdown → HTML email via Gmail API
│   ├── formatter.py      # Terminal / markdown output
│   ├── gmail_client.py   # Gmail API client
│   ├── google_auth.py    # OAuth 2.0 (gmail.readonly + gmail.send)
│   ├── main.py           # CLI entry point
│   ├── tool_executor.py  # Routes tool calls to Gmail client
│   └── tools.py          # Gmail tool definitions for Claude
├── com.meenusankar.meeting-prep-agent.plist  # macOS launchd job
├── run_email_brief.sh    # Shell wrapper for launchd
├── requirements.txt
├── .env.example
└── .gitignore
```

## Prerequisites

- Python 3.11+
- Node.js + npm (for the Google Calendar MCP server via `npx`)
- An [Anthropic API key](https://console.anthropic.com/)
- A Google Cloud project with the Gmail API and Google Calendar API enabled

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/TangriDhruv/meeting-prep-agent.git
cd meeting-prep-agent
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Google Cloud credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create an **OAuth 2.0 Client ID** (Desktop app)
3. Enable the **Gmail API** and **Google Calendar API** for your project
4. Download the credentials JSON and save it as `credentials.json` in the project root

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Required only for email delivery
EMAIL_RECIPIENT=you@gmail.com
```

### 5. Authenticate with Google

On first run, a browser window will open asking you to authorise access to your Google Calendar and Gmail. The token is cached in `token.json` for subsequent runs.

```bash
python3 -m meeting_prep_agent.main
```

## Usage

### Print brief in the terminal (default)

```bash
python3 -m meeting_prep_agent.main
```

### Look ahead a custom number of days

```bash
python3 -m meeting_prep_agent.main --days 3
```

### Filter to a specific meeting

```bash
python3 -m meeting_prep_agent.main --meeting "Q4 Planning"
```

### Save as a markdown file

```bash
python3 -m meeting_prep_agent.main --output markdown > brief.md
```

### Send to your inbox

```bash
python3 -m meeting_prep_agent.main --days 1 --email
```

### All CLI flags

| Flag | Default | Description |
|---|---|---|
| `--days N` | 7 | How many days ahead to look for meetings |
| `--meeting TEXT` | — | Filter to a specific meeting by keyword |
| `--output` | `terminal` | Output format: `terminal` or `markdown` |
| `--email` | off | Send brief to `EMAIL_RECIPIENT` instead of printing |

## Daily email delivery (macOS)

The repo includes a launchd setup that emails you a brief every morning at 9 AM.

### 1. Make the wrapper executable

```bash
chmod +x run_email_brief.sh
```

### 2. Install the launchd job

```bash
cp com.dhruv.meeting-prep-agent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dhruv.meeting-prep-agent.plist
```

### 3. Verify it's registered

```bash
launchctl list | grep meeting-prep-agent
```

Logs are written to `launchd_stdout.log` and `launchd_stderr.log` in the project root.

### Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.dhruv.meeting-prep-agent.plist
rm ~/Library/LaunchAgents/com.dhruv.meeting-prep-agent.plist
```

## Environment variables reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Your Anthropic API key |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-6` | Claude model to use |
| `DAYS_AHEAD` | No | `7` | Default days ahead to look |
| `MAX_EMAIL_RESULTS` | No | `10` | Max emails to fetch per search |
| `MAX_TOKENS` | No | `4096` | Max tokens for Claude response |
| `CREDENTIALS_FILE` | No | `credentials.json` | Path to Google OAuth credentials |
| `TOKEN_FILE` | No | `token.json` | Path to cached Gmail OAuth token |
| `EMAIL_RECIPIENT` | For `--email` | — | Email address to send the brief to |
| `EMAIL_SUBJECT_PREFIX` | No | `Meeting Prep Brief` | Subject line prefix |

## Security notes

- `credentials.json`, `token.json`, `calendar_token.json`, and `.env` are all listed in `.gitignore` and will never be committed
- OAuth tokens are stored locally only
- The app requests `gmail.readonly` (to read emails) and `gmail.send` (to send the brief) scopes only
