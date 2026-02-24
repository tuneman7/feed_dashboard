#!/bin/bash

# Deploy and Connect Script
# Copies current directory to the Ubuntu box for the given environment

ENV="${1:-dev}"
KEY_FILE="id_rsa_${ENV}"

echo "==============================="
echo "Deploy and Connect to Ubuntu EC2"
echo "Environment: $ENV"
echo "==============================="
echo

# Select the correct Terraform workspace so output reads from the right state
terraform workspace select "$ENV" 2>/dev/null || true

# Get the public IP from terraform output
PUBLIC_IP=$(terraform output -raw public_ip 2>/dev/null)

# Check if we got a valid IP
if [ -z "$PUBLIC_IP" ] || [ "$PUBLIC_IP" = "null" ]; then
    echo "❌ Could not retrieve public IP from Terraform output ($ENV)"
    echo "   Make sure you've run '. terraform-build.sh $ENV' successfully"
    return 1 2>/dev/null || true
fi

# Check if private key exists
if [ ! -f "$KEY_FILE" ]; then
    echo "❌ Private key file '$KEY_FILE' not found"
    echo "   Make sure you've run '. terraform-build.sh $ENV' successfully"
    return 1 2>/dev/null || true
fi

# Fix private key permissions
chmod 400 "$KEY_FILE"

echo "🔗 Target: ubuntu@$PUBLIC_IP"
echo "🔑 Key   : $KEY_FILE"
echo "📁 Deploying current directory to ~/app/"
echo

# Create .deployignore if it doesn't exist with sensible defaults
if [ ! -f ".deployignore" ]; then
    echo "📝 Creating .deployignore with default exclusions..."
    cat > .deployignore << 'EOL'
# Terraform files
*.tfstate*
.terraform/
.terraform.lock.hcl
terraform.tfvars

# SSH keys
id_rsa*
*.pem

# Scripts
connect*.sh
deploy.sh
destroy.sh
destroy_and_build.sh
terraform-build.sh

# Version control
.git/
.gitignore

# IDE and editor files
.vscode/
.idea/
*.swp
*.swo
*~

# OS files
.DS_Store
Thumbs.db

# Dependencies
node_modules/
__pycache__/
*.pyc
.env
venv/
env/

# Build artifacts
dist/
build/
*.log
EOL
fi

# Function to check if path should be excluded
should_exclude() {
    local path="$1"
    while IFS= read -r pattern || [ -n "$pattern" ]; do
        # Skip empty lines and comments
        [[ -z "$pattern" || "$pattern" =~ ^[[:space:]]*# ]] && continue
        if [[ "$path" == $pattern* ]] || [[ "$path" == *"$pattern"* ]]; then
            return 0  # Should exclude
        fi
    done < .deployignore
    return 1  # Should not exclude
}

# Create a temporary directory for files to copy
TEMP_DIR=$(mktemp -d)
echo "📦 Preparing files for deployment..."

# Copy files while respecting .deployignore
find . -type f -not -path "./.git/*" | while read -r file; do
    clean_path="${file#./}"
    if ! should_exclude "$clean_path"; then
        mkdir -p "$TEMP_DIR/$(dirname "$clean_path")"
        cp "$file" "$TEMP_DIR/$clean_path"
    fi
done

echo "🚀 Copying files to remote server..."

# Test SSH connectivity first
if ! ssh -i "$KEY_FILE" -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'echo "Connection test successful"' > /dev/null 2>&1; then
    echo "❌ Cannot connect to server. Instance might still be starting up."
    echo "   Wait a minute and try again."
    rm -rf "$TEMP_DIR"
    return 1 2>/dev/null || true
fi

# Kill any existing Streamlit processes before deployment
echo "🔄 Stopping any running Streamlit applications..."
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP '
    pkill -f streamlit 2>/dev/null || true
    pkill -f "python.*streamlit" 2>/dev/null || true
    sleep 2
    if pgrep -f streamlit > /dev/null 2>&1; then
        echo "   Force killing remaining streamlit processes..."
        pkill -9 -f streamlit 2>/dev/null || true
        sleep 1
    fi
    echo "   Streamlit processes stopped"
' || echo "   Note: No streamlit processes were running"

# Clear the app directory and copy new files
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'rm -rf ~/app && mkdir -p ~/app'

# Copy files using scp
echo "📤 Copying files..."
if scp -i "$KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r "$TEMP_DIR"/* ubuntu@$PUBLIC_IP:~/app/; then
    echo "✅ SCP completed!"

    echo "🔍 Verifying deployment..."
    sleep 2

    # Wait for the specific sr.sh file to be present
    echo "⏳ Waiting for sr.sh to be ready..."
    RETRY_COUNT=0
    MAX_RETRIES=30

    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'test -f ~/app/feed_management_system/sr.sh' 2>/dev/null; then
            echo "✅ sr.sh found! Deployment verified."
            break
        fi
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "   Attempt $RETRY_COUNT/$MAX_RETRIES - waiting for sr.sh..."
        sleep 1
    done

    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Timeout waiting for sr.sh to appear"
        echo "   Files may not have copied correctly"
        rm -rf "$TEMP_DIR"
        return 1 2>/dev/null || true
    fi

    # Fix line endings for all shell scripts
    echo "🔧 Fixing line endings for shell scripts..."
    ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'find ~/app -name "*.sh" -type f -exec dos2unix {} \; 2>/dev/null && echo "Line endings fixed for shell scripts"' || echo "Note: dos2unix not available or no .sh files found"

    # Make all shell scripts executable
    echo "🔧 Making shell scripts executable..."
    ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'find ~/app -name "*.sh" -type f -exec chmod +x {} \; && echo "Shell scripts made executable"' || true

else
    echo "❌ File deployment failed"
    rm -rf "$TEMP_DIR"
    return 1 2>/dev/null || true
fi

# Clean up temp directory
rm -rf "$TEMP_DIR"

echo "📊 Deployment summary:"
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'echo "Files in ~/app:"; ls -la ~/app/ 2>/dev/null | wc -l | xargs echo "Total files/dirs:" || echo "Directory empty or not accessible"'

echo
echo "🔌 Connecting to server and changing to app directory..."
echo "   You are now in the ~/app directory on the remote server"
echo "   Type 'exit' to return to your local machine"
echo

# Connect and change to appropriate directory
ssh -i "$KEY_FILE" \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -o ServerAliveInterval=60 \
    -t ubuntu@$PUBLIC_IP \
    'TARGET_DIR=~/app/feed_management_system; if [ ! -d "$TARGET_DIR" ]; then TARGET_DIR=~/app; fi; cd "$TARGET_DIR" && echo "=== Welcome to your Ubuntu development box ===" && echo "Current directory: $(pwd)" && echo "Files:" && ls -la && echo && echo "Installed tools:" && echo "- Python: $(python --version 2>/dev/null || echo "not found")" && echo "- Docker: $(docker --version 2>/dev/null || echo "not found")" && echo "- Node.js: $(node --version 2>/dev/null || echo "not found")" && echo && if [ -f sr.sh ]; then . sr.sh; fi && exec bash'

# Check if SSH failed
if [ $? -ne 0 ]; then
    echo
    echo "❌ SSH connection failed after deployment"
    echo "   Files were deployed successfully, but connection failed"
    echo "   Try running ./connect_${ENV}.sh manually"
fi

###############################################################################
# Install/Update cron to run the alert processor every 2 minutes (prod only)
###############################################################################
echo

if [ "$ENV" != "prod" ]; then
    echo "⏭️  Skipping alert processor cron install (dev environment)."
    echo "   The following commands would run on prod:"
    echo
    echo '   ssh ubuntu@$PUBLIC_IP <<"REMOTE"'
    echo '     APP_DIR="$HOME/app/feed_management_system"'
    echo '     RUN_SCRIPT="$APP_DIR/run_processor.sh"'
    echo '     LOG_DIR="$APP_DIR/logs"'
    echo '     CRON_MARK="# ALERT_PROCESSOR_CRON"'
    echo '     mkdir -p "$LOG_DIR" && chmod 777 "$LOG_DIR"'
    echo '     chmod +x "$RUN_SCRIPT" || true'
    echo '     CRON_LINE="*/2 * * * * cd $APP_DIR && /bin/bash $RUN_SCRIPT >> $LOG_DIR/alert_processor.log 2>&1 $CRON_MARK"'
    echo '     { crontab -l 2>/dev/null || true; } | grep -vF "$CRON_MARK" | crontab - || true'
    echo '     ( crontab -l 2>/dev/null || true; echo "$CRON_LINE" ) | crontab -'
    echo '   REMOTE'
    echo
    echo "   ▶  To run the processor on dev manually: . deploy.sh prod"
else
    echo "⏲️  Installing/Updating cron job for alert processor..."

    ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP <<'REMOTE'
set -euo pipefail

APP_DIR="$HOME/app/feed_management_system"
RUN_SCRIPT="$APP_DIR/run_processor.sh"
LOG_DIR="$APP_DIR/logs"
CRON_MARK="# ALERT_PROCESSOR_CRON"

mkdir -p "$LOG_DIR"
chmod 777 "$LOG_DIR"
chmod +x "$RUN_SCRIPT" || true

CRON_LINE="*/2 * * * * cd $APP_DIR && /bin/bash $RUN_SCRIPT >> $LOG_DIR/alert_processor.log 2>&1 $CRON_MARK"

{ crontab -l 2>/dev/null || true; } | grep -vF "$CRON_MARK" | crontab - || true
( crontab -l 2>/dev/null || true; echo "$CRON_LINE" ) | crontab -

echo "✅ Cron installed/updated."
echo "Current crontab tail:"
crontab -l | tail -n 5 || true
REMOTE
fi
