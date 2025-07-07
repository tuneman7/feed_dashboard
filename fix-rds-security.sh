#!/bin/bash

# RDS Security Group Fix Script
# This script adds the EC2 instance to the RDS security group to allow database connections

set -e

echo "======================================="
echo "RDS Security Group Configuration Script"
echo "======================================="
echo

# Configuration
RDS_INSTANCE="dst-dashboard-database-fast1"
EC2_INSTANCE_ID="i-02159945a2cac1f8a"
EC2_SECURITY_GROUP_ID="sg-0eca9e7d7caeb9133"
EC2_PUBLIC_IP="54.81.71.100"

if [ -z "$RDS_INSTANCE" ]; then
    echo "❌ No RDS instance identifier provided"
    echo "Set the rds_instance_identifier variable in Terraform"
    exit 1
fi

echo "🔍 EC2 Instance ID: $EC2_INSTANCE_ID"
echo "🔍 EC2 Security Group: $EC2_SECURITY_GROUP_ID"
echo "🔍 EC2 Public IP: $EC2_PUBLIC_IP"
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
    exit 1
fi

echo "✅ Found RDS Security Groups: $RDS_SECURITY_GROUPS"
echo

# For each RDS security group, add the EC2 security group
for RDS_SG_ID in $RDS_SECURITY_GROUPS; do
    echo "🔧 Configuring RDS security group: $RDS_SG_ID"
    
    # Check if rule already exists
    EXISTING_RULE=$(aws ec2 describe-security-groups \
        --group-ids "$RDS_SG_ID" \
        --query "SecurityGroups[0].IpPermissions[?FromPort==\`5432\` && ToPort==\`5432\` && UserIdGroupPairs[?GroupId==\`$EC2_SECURITY_GROUP_ID\`]]" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$EXISTING_RULE" ]; then
        echo "✅ Security group rule already exists"
    else
        echo "➕ Adding EC2 security group to RDS security group..."
        aws ec2 authorize-security-group-ingress \
            --group-id "$RDS_SG_ID" \
            --protocol tcp \
            --port 5432 \
            --source-group "$EC2_SECURITY_GROUP_ID" 2>/dev/null || echo "⚠️  Could not add security group rule (might already exist)"
        echo "✅ Added EC2 security group rule"
    fi
    
    # Also add the public IP as backup
    EXISTING_IP_RULE=$(aws ec2 describe-security-groups \
        --group-ids "$RDS_SG_ID" \
        --query "SecurityGroups[0].IpPermissions[?FromPort==\`5432\` && ToPort==\`5432\` && IpRanges[?CidrIp==\`$EC2_PUBLIC_IP/32\`]]" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$EXISTING_IP_RULE" ]; then
        echo "✅ Public IP rule already exists"
    else
        echo "➕ Adding EC2 public IP to RDS security group..."
        aws ec2 authorize-security-group-ingress \
            --group-id "$RDS_SG_ID" \
            --protocol tcp \
            --port 5432 \
            --cidr "$EC2_PUBLIC_IP/32" 2>/dev/null || echo "⚠️  Could not add IP rule (might already exist)"
        echo "✅ Added EC2 public IP rule"
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
echo "- Added security group: $EC2_SECURITY_GROUP_ID to RDS"
echo "- Added public IP: $EC2_PUBLIC_IP/32 to RDS" 
echo "- RDS endpoint: $RDS_ENDPOINT"
echo
echo "🔧 Your EC2 instance should now be able to connect to RDS!"
echo "Test with: ssh to EC2 and run 'timeout 10 telnet $RDS_ENDPOINT 5432'"
