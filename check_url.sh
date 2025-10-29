#!/bin/bash

# Ultra-defensive DNS flush - never fails, never prompts

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

ipconfig.exe //flushdns


# Set your URL here
URL="https://dmtdashboard.link/"

# Alternative: Get URL from command line argument
# URL="$1"

# Configuration
RETRY_DELAY=5  # seconds between retries
MAX_RETRIES=0  # 0 = infinite retries, set to positive number to limit

echo "Making request to: $URL"
echo "This may take some time..."

sleep 10

attempt=1

while true; do
    # Perform curl with suppressed output
    # -s = silent mode (no progress bar)
    # -S = show errors even in silent mode
    # -o /dev/null = discard output
    if curl -s -S -o /dev/null "$URL"; then
        echo "okay"
        curl "$URL"
        break
    else
        echo "Attempt $attempt failed, retrying in $RETRY_DELAY seconds..."
        
        # Check if we've hit max retries (if set)
        if [ $MAX_RETRIES -gt 0 ] && [ $attempt -ge $MAX_RETRIES ]; then
            echo "Max retries ($MAX_RETRIES) reached. Giving up."
            return 1
        fi
        
        sleep $RETRY_DELAY
        ((attempt++))
    fi
done