#!/bin/bash

# Instance Readiness Checker
# This script waits until the Ubuntu box is fully set up

echo "======================================="
echo "Checking Ubuntu EC2 Instance Readiness"
echo "======================================="

PUBLIC_IP="34.239.138.193"

if [ ! -f "id_rsa" ]; then
    echo "❌ Private key file 'id_rsa' not found"
    exit 1
fi

chmod 400 id_rsa

echo "🔍 Checking instance: ubuntu@$PUBLIC_IP"
echo "⏳ Waiting for instance to be fully ready..."
echo

# Function to check if instance is ready
check_ready() {
    # Test basic SSH connectivity
    if ! ssh -i id_rsa -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'echo "SSH OK"' >/dev/null 2>&1; then
        return 1
    fi
    
    # Check if setup completion file exists
    if ! ssh -i id_rsa -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'test -f ~/setup_complete.txt' >/dev/null 2>&1; then
        return 1
    fi
    
    # Check if Docker is working
    if ! ssh -i id_rsa -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'docker --version' >/dev/null 2>&1; then
        return 1
    fi
    
    # Check if Python is working
    if ! ssh -i id_rsa -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'python --version' >/dev/null 2>&1; then
        return 1
    fi
    
    return 0
}

# Wait loop
ATTEMPTS=0
MAX_ATTEMPTS=60  # 5 minutes max wait time

while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
    if check_ready; then
        echo
        echo "✅ Instance is ready!"
        echo
        
        # Show setup summary
        echo "📋 Setup Summary:"
        ssh -i id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@$PUBLIC_IP 'cat ~/setup_complete.txt' 2>/dev/null || echo "Setup details not available"
        
        echo
        echo "🎉 Your Ubuntu development box is ready to use!"
        echo "   Run ./deploy.sh to deploy your code and connect"
        echo "   Or run ./connect.sh to just connect"
        
        exit 0
    fi
    
    ATTEMPTS=$((ATTEMPTS + 1))
    printf "."
    sleep 5
done

echo
echo "❌ Timeout: Instance did not become ready within 5 minutes"
echo "   This might indicate an issue with the setup process"
echo "   You can try connecting manually: ./connect.sh"
