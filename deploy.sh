#!/bin/bash

# Deploy and Connect Script
# This script copies the current directory to the Ubuntu box and connects

echo "==============================="
echo "Deploy and Connect to Ubuntu EC2"
echo "==============================="
echo

# Get the public IP from terraform output
PUBLIC_IP=$(terraform output -raw public_ip 2>/dev/null)

# Check if we got a valid IP
if [ -z "$PUBLIC_IP" ] || [ "$PUBLIC_IP" = "null" ]; then
    echo "❌ Could not retrieve public IP from Terraform output"
    echo "   Make sure you've run 'terraform apply' successfully"
    return 1 2>/dev/null || true
fi

# Check if private key exists
if [ ! -f "id_rsa" ]; then
    echo "❌ Private key file 'id_rsa' not found"
    echo "   Make sure you've run 'terraform apply' successfully"
    return 1 2>/dev/null || true
fi

# Fix private key permissions
chmod 400 id_rsa

echo "🔗 Target: ubuntu@$PUBLIC_IP"
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
connect.sh
deploy.sh
destroy.sh

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
        
        # Simple pattern matching (you could enhance this with more complex glob patterns)
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
    # Remove leading ./
    clean_path="${file#./}"
    
    if ! should_exclude "$clean_path"; then
        # Create directory structure in temp dir
        mkdir -p "$TEMP_DIR/$(dirname "$clean_path")"
        cp "$file" "$TEMP_DIR/$clean_path"
    fi
done

echo "🚀 Copying files to remote server..."

# Test SSH connectivity first
if ! ssh -i id_rsa -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'echo "Connection test successful"' >/dev/null 2>&1; then
    echo "❌ Cannot connect to server. Instance might still be starting up."
    echo "   Wait a minute and try again."
    rm -rf "$TEMP_DIR"
    return 1 2>/dev/null || true
fi

# Clear the app directory and copy new files
ssh -i id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'rm -rf ~/app && mkdir -p ~/app'

# Copy files using scp (show progress)
echo "📤 Copying files..."
if scp -i id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r "$TEMP_DIR"/* ubuntu@$PUBLIC_IP:~/app/; then
    echo "✅ SCP completed!"
    
    # Verify the copy is complete by checking for expected files/directories
    echo "🔍 Verifying deployment..."
    sleep 2  # Give filesystem a moment to sync
    
    # Wait for the specific sr.sh file to be present
    echo "⏳ Waiting for sr.sh to be ready..."
    RETRY_COUNT=0
    MAX_RETRIES=30
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if ssh -i id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'test -f ~/app/feed_management_system/sr.sh' 2>/dev/null; then
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
    ssh -i id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'find ~/app -name "*.sh" -type f -exec dos2unix {} \; 2>/dev/null && echo "Line endings fixed for shell scripts"' || echo "Note: dos2unix not available or no .sh files found"
    
    # Make all shell scripts executable
    echo "🔧 Making shell scripts executable..."
    ssh -i id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'find ~/app -name "*.sh" -type f -exec chmod +x {} \; && echo "Shell scripts made executable"' || true
    
else
    echo "❌ File deployment failed"
    rm -rf "$TEMP_DIR"
    return 1 2>/dev/null || true
fi

# Clean up temp directory
rm -rf "$TEMP_DIR"

echo "📊 Deployment summary:"
ssh -i id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'echo "Files in ~/app:"; ls -la ~/app/ 2>/dev/null | wc -l | xargs echo "Total files/dirs:" || echo "Directory empty or not accessible"'

echo
echo "🔌 Connecting to server and changing to app directory..."
echo "   You are now in the ~/app directory on the remote server"
echo "   Type 'exit' to return to your local machine"
echo

# Check if feed_management_system directory exists, if not use app directory
# Connect and change to appropriate directory
ssh -i id_rsa \
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
    echo "   Try running ./connect.sh manually"
fi