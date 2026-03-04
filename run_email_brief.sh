#!/usr/bin/env bash
# run_email_brief.sh — launchd wrapper for the meeting-prep-agent email delivery.
# Install: chmod +x run_email_brief.sh
# Then copy the plist to ~/Library/LaunchAgents/ and load with launchctl.

set -euo pipefail

# Resolve the project root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure npx and other tools are available (launchd has a minimal PATH)
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH"

# Activate the project virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Source .env so EMAIL_RECIPIENT and ANTHROPIC_API_KEY are available
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Wait for network (up to 30s) before attempting OAuth token refresh
for i in $(seq 1 30); do
    ping -c1 -W1 8.8.8.8 &>/dev/null && break
    sleep 1
done

cd "$SCRIPT_DIR"

exec python -m meeting_prep_agent.main --days 1 --email
