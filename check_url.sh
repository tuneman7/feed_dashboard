#!/bin/bash

# Ultra-defensive DNS flush - never fails, never prompts

ENV="${1:-dev}"

# Resolve URL based on environment
if [ "$ENV" = "prod" ]; then
  URL="https://dmtdashboard.link/"
else
  URL="https://dmdashboard.link/"
fi

echo "🌍 Environment: $ENV"
echo "🔗 URL: $URL"

flush_dns_safe() {
    # Windows (Git Bash)
    if command -v ipconfig.exe &> /dev/null; then
        ipconfig.exe //flushdns &> /dev/null
        echo "DNS flush attempted (Windows)"
        return 0
    fi

    # macOS (only if we have sudo access already)
    if [[ "$OSTYPE" == "darwin"* ]] && command -v dscacheutil &> /dev/null; then
        if sudo -n true 2>/dev/null; then
            sudo dscacheutil -flushcache &> /dev/null
            sudo killall -HUP mDNSResponder &> /dev/null 2>&1
            echo "DNS flush attempted (macOS)"
        else
            echo "DNS flush skipped (macOS - no sudo)"
        fi
        return 0
    fi

    # Linux (only if we have sudo access already)
    if command -v resolvectl &> /dev/null; then
        if sudo -n true 2>/dev/null; then
            sudo resolvectl flush-caches &> /dev/null
            echo "DNS flush attempted (Linux)"
        else
            echo "DNS flush skipped (Linux - no sudo)"
        fi
        return 0
    fi

    echo "DNS flush not available or not needed"
    return 0
}

flush_dns_safe

# Also try the Windows command directly (harmless if not on Windows)
ipconfig.exe //flushdns 2>/dev/null || true

# Configuration
RETRY_DELAY=5  # seconds between retries
MAX_RETRIES=0  # 0 = infinite retries, set to positive number to limit

echo "Making request to: $URL"
echo "This may take some time..."

sleep 10

attempt=1

while true; do
    if curl -s -S -o /dev/null "$URL"; then
        echo "✅ Site is up!"
        curl "$URL"
        break
    else
        echo "Attempt $attempt failed, retrying in $RETRY_DELAY seconds..."

        if [ $MAX_RETRIES -gt 0 ] && [ $attempt -ge $MAX_RETRIES ]; then
            echo "Max retries ($MAX_RETRIES) reached. Giving up."
            return 1
        fi

        sleep $RETRY_DELAY
        ((attempt++))
    fi
done