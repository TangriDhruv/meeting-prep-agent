#!/usr/bin/env bash
# run_email_brief.sh — launchd wrapper for the meeting-prep-agent email delivery.
# Install: chmod +x run_email_brief.sh
# Then copy the plist to ~/Library/LaunchAgents/ and load with launchctl.

set -euo pipefail

# Ensure system binaries and common Homebrew/pyenv paths are available
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$HOME/.pyenv/shims:$HOME/.pyenv/bin:$PATH"

# Resolve the project root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source .env so EMAIL_RECIPIENT and ANTHROPIC_API_KEY are available
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env"
    set +a
fi

cd "$SCRIPT_DIR"

exec /opt/anaconda3/bin/python3 -m meeting_prep_agent.main --days 1 --email
