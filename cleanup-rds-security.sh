#!/bin/bash

# RDS Security Group Cleanup Script
# This script removes the EC2 instance from the RDS security group

set -e

echo "======================================="
echo "RDS Security Group Cleanup Script"
echo "======================================="
echo

# Configuration
RDS_INSTANCE="dst-dashboard-database-fast1"
EC2_INSTANCE_ID="i-046149f7944caaaa4"
EC2_SECURITY_GROUP_ID="sg-01ee91a79da8c236e"
EC2_PUBLIC_IP="34.227.102.88"

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

# For each RDS security group, remove the EC2 security group and IP
for RDS_SG_ID in $RDS_SECURITY_GROUPS; do
    echo "🧹 Cleaning up RDS security group: $RDS_SG_ID"
    
    # Check if security group rule exists and remove it
    EXISTING_RULE=$(aws ec2 describe-security-groups \
        --group-ids "$RDS_SG_ID" \
        --query "SecurityGroups[0].IpPermissions[?FromPort==\`5432\` && ToPort==\`5432\` && UserIdGroupPairs[?GroupId==\`$EC2_SECURITY_GROUP_ID\`]]" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$EXISTING_RULE" ]; then
        echo "➖ Removing EC2 security group from RDS security group..."
        aws ec2 revoke-security-group-ingress \
            --group-id "$RDS_SG_ID" \
            --protocol tcp \
            --port 5432 \
            --source-group "$EC2_SECURITY_GROUP_ID" 2>/dev/null || echo "⚠️  Could not remove security group rule (might not exist)"
        echo "✅ Removed EC2 security group rule"
    else
        echo "ℹ️  EC2 security group rule not found"
    fi
    
    # Check if public IP rule exists and remove it
    EXISTING_IP_RULE=$(aws ec2 describe-security-groups \
        --group-ids "$RDS_SG_ID" \
        --query "SecurityGroups[0].IpPermissions[?FromPort==\`5432\` && ToPort==\`5432\` && IpRanges[?CidrIp==\`$EC2_PUBLIC_IP/32\`]]" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$EXISTING_IP_RULE" ]; then
        echo "➖ Removing EC2 public IP from RDS security group..."
        aws ec2 revoke-security-group-ingress \
            --group-id "$RDS_SG_ID" \
            --protocol tcp \
            --port 5432 \
            --cidr "$EC2_PUBLIC_IP/32" 2>/dev/null || echo "⚠️  Could not remove IP rule (might not exist)"
        echo "✅ Removed EC2 public IP rule"
    else
        echo "ℹ️  EC2 public IP rule not found"
    fi
    
    echo
done

echo "🎉 Security group cleanup complete!"
echo

# Get RDS endpoint for reference
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier "$RDS_INSTANCE" \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text 2>/dev/null || echo "unknown")

echo "📋 Summary:"
echo "- Removed security group: $EC2_SECURITY_GROUP_ID from RDS"
echo "- Removed public IP: $EC2_PUBLIC_IP/32 from RDS" 
echo "- RDS endpoint: $RDS_ENDPOINT"
echo
echo "🔒 Your EC2 instance can no longer connect to RDS!"
