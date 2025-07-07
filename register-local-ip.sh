#!/bin/bash

# RDS Security Group Fix Script for Local Development
# This script adds your local computer's IP address to the RDS security group

set +e  # Don't exit on errors

echo "======================================="
echo "RDS Security Group Configuration Script"
echo "======================================="
echo

# Configuration
RDS_INSTANCE="dst-dashboard-database-fast1"

if [ -z "$RDS_INSTANCE" ]; then
    echo "❌ No RDS instance identifier provided"
    echo "Set the RDS_INSTANCE variable in the script"
    exit 1
fi

echo "🔍 Getting your local public IP address..."

# Try multiple methods to get public IP
LOCAL_IP=""

# Method 1: Try curl with ifconfig.me
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(curl -s --connect-timeout 5 ifconfig.me 2>/dev/null)
    if [ -n "$LOCAL_IP" ]; then
        echo "✅ Got IP from ifconfig.me: $LOCAL_IP"
    fi
fi

# Method 2: Try curl with ipinfo.io
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(curl -s --connect-timeout 5 ipinfo.io/ip 2>/dev/null)
    if [ -n "$LOCAL_IP" ]; then
        echo "✅ Got IP from ipinfo.io: $LOCAL_IP"
    fi
fi

# Method 3: Try curl with httpbin.org
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(curl -s --connect-timeout 5 httpbin.org/ip | grep -o '[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}' 2>/dev/null)
    if [ -n "$LOCAL_IP" ]; then
        echo "✅ Got IP from httpbin.org: $LOCAL_IP"
    fi
fi

# Method 4: Try with icanhazip.com
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(curl -s --connect-timeout 5 icanhazip.com 2>/dev/null | tr -d '\n')
    if [ -n "$LOCAL_IP" ]; then
        echo "✅ Got IP from icanhazip.com: $LOCAL_IP"
    fi
fi

if [ -z "$LOCAL_IP" ]; then
    echo "❌ Could not determine your public IP address"
    echo "Please check your internet connection and try again"
    echo "Or manually set LOCAL_IP variable in the script"
    echo ""
    echo "Press any key to exit..."
    read -n 1
    exit 1
fi

# Validate IP format
if [[ ! $LOCAL_IP =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
    echo "❌ Invalid IP address format: $LOCAL_IP"
    echo "Please check your internet connection or set LOCAL_IP manually"
    echo ""
    echo "Press any key to exit..."
    read -n 1
    exit 1
fi

echo "🔍 Your Local Public IP: $LOCAL_IP"
echo "🔍 RDS Instance: $RDS_INSTANCE"
echo

echo "🔍 Finding RDS instance security groups..."
RDS_SECURITY_GROUPS=$(aws rds describe-db-instances \
    --db-instance-identifier "$RDS_INSTANCE" \
    --query 'DBInstances[0].VpcSecurityGroups[*].VpcSecurityGroupId' \
    --output text 2>/dev/null)

if [ -z "$RDS_SECURITY_GROUPS" ]; then
    echo "❌ Could not find RDS instance: $RDS_INSTANCE"
    echo "Please check the RDS instance name and ensure it exists."
    echo "Also ensure AWS CLI is configured with proper credentials."
    echo ""
    echo "Press any key to exit..."
    read -n 1
    exit 1
fi

echo "✅ Found RDS Security Groups: $RDS_SECURITY_GROUPS"
echo

# For each RDS security group, add the local IP
for RDS_SG_ID in $RDS_SECURITY_GROUPS; do
    echo "🔧 Configuring RDS security group: $RDS_SG_ID"
    
    # Check if rule already exists
    EXISTING_IP_RULE=$(aws ec2 describe-security-groups \
        --group-ids "$RDS_SG_ID" \
        --query "SecurityGroups[0].IpPermissions[?FromPort==\`5432\` && ToPort==\`5432\` && IpRanges[?CidrIp==\`$LOCAL_IP/32\`]]" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$EXISTING_IP_RULE" ]; then
        echo "✅ Your IP rule already exists in security group"
    else
        echo "➕ Adding your local IP to RDS security group..."
        RESULT=$(aws ec2 authorize-security-group-ingress \
            --group-id "$RDS_SG_ID" \
            --protocol tcp \
            --port 5432 \
            --cidr "$LOCAL_IP/32" 2>&1)
        
        if [ $? -eq 0 ]; then
            echo "✅ Successfully added your IP to security group"
        else
            echo "⚠️  Could not add IP rule: $RESULT"
            echo "   This might mean the rule already exists or you lack permissions"
        fi
    fi
    
    echo
done

echo "🎉 Security group configuration complete!"
echo

# Get RDS endpoint for testing
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier "$RDS_INSTANCE" \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text 2>/dev/null || echo "unknown")

echo "📋 Summary:"
echo "- Added local IP: $LOCAL_IP/32 to RDS security group(s)"
echo "- RDS endpoint: $RDS_ENDPOINT"
echo "- RDS port: 5432"
echo
echo "🔧 Your local computer should now be able to connect to RDS!"
echo "Test with DataGrip, pgAdmin, or psql using:"
echo "  Host: $RDS_ENDPOINT"
echo "  Port: 5432"
echo "  Database: [your-database-name]"
echo "  Username: [your-username]"
echo "  Password: [your-password]"
echo
echo "💡 Note: If your IP changes, you'll need to run this script again"
echo

echo "Press any key to exit..."
read -n 1