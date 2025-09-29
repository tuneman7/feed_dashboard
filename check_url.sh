#!/bin/bash

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