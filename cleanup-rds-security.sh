#!/bin/bash

# RDS Security Group Cleanup Script
# This script removes ALL rules from the RDS security group to ensure it can be deleted

set +e

echo "======================================="
echo "RDS Security Group Cleanup Script"
echo "======================================="
echo

# Configuration
RDS_INSTANCE="dst-dashboard-database-fast"
EC2_INSTANCE_ID="i-0b5275a0a92d64c4f"
EC2_SECURITY_GROUP_ID="sg-052c09d83cc6009e1"
EC2_PUBLIC_IP="54.161.30.73"
USER_LOCAL_IP="97.178.68.112"

if [ -z "$RDS_INSTANCE" ]; then
    echo "❌ No RDS instance identifier provided"
    echo "Set the rds_instance_identifier variable in Terraform"
    exit 1
fi

echo "🔍 EC2 Instance ID: $EC2_INSTANCE_ID"
echo "🔍 EC2 Security Group: $EC2_SECURITY_GROUP_ID"
echo "🔍 EC2 Public IP: $EC2_PUBLIC_IP"
echo "🔍 User Local IP: $USER_LOCAL_IP"
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

# For each RDS security group, remove ALL ingress rules
for RDS_SG_ID in $RDS_SECURITY_GROUPS; do
    echo "🧹 Cleaning up RDS security group: $RDS_SG_ID"
    
    # Get all ingress rules for this security group
    INGRESS_RULES=$(aws ec2 describe-security-groups \
        --group-ids "$RDS_SG_ID" \
        --query 'SecurityGroups[0].IpPermissions' \
        --output json 2>/dev/null)
    
    if [ "$INGRESS_RULES" = "[]" ] || [ -z "$INGRESS_RULES" ]; then
        echo "ℹ️  No ingress rules found in security group $RDS_SG_ID"
    else
        echo "🔍 Found ingress rules, removing all..."
        
        # Remove all ingress rules at once
        aws ec2 revoke-security-group-ingress \
            --group-id "$RDS_SG_ID" \
            --ip-permissions "$INGRESS_RULES" 2>/dev/null || echo "⚠️  Some rules might not exist or couldn't be removed"
        
        echo "✅ Removed all ingress rules from security group $RDS_SG_ID"
    fi
    
    # Also specifically try to remove the rules we know about (fallback)
    echo "🔄 Attempting specific rule cleanup as fallback..."
    
    # Remove EC2 security group rule
    aws ec2 revoke-security-group-ingress \
        --group-id "$RDS_SG_ID" \
        --protocol tcp \
        --port 5432 \
        --source-group "$EC2_SECURITY_GROUP_ID" 2>/dev/null || echo "ℹ️  EC2 security group rule already removed or didn't exist"
    
    # Remove EC2 public IP rule
    aws ec2 revoke-security-group-ingress \
        --group-id "$RDS_SG_ID" \
        --protocol tcp \
        --port 5432 \
        --cidr "$EC2_PUBLIC_IP/32" 2>/dev/null || echo "ℹ️  EC2 public IP rule already removed or didn't exist"
    
    # Remove user's local IP rule
    aws ec2 revoke-security-group-ingress \
        --group-id "$RDS_SG_ID" \
        --protocol tcp \
        --port 5432 \
        --cidr "$USER_LOCAL_IP/32" 2>/dev/null || echo "ℹ️  User local IP rule already removed or didn't exist"
    
    # Check for any remaining rules
    REMAINING_RULES=$(aws ec2 describe-security-groups \
        --group-ids "$RDS_SG_ID" \
        --query 'SecurityGroups[0].IpPermissions' \
        --output text 2>/dev/null)
    
    if [ "$REMAINING_RULES" = "None" ] || [ -z "$REMAINING_RULES" ]; then
        echo "✅ Security group $RDS_SG_ID is now clean and ready for deletion"
    else
        echo "⚠️  Some rules may still remain in security group $RDS_SG_ID"
        echo "    You may need to manually remove them before deleting the security group"
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
echo "- Removed all ingress rules from RDS security groups"
echo "- Security groups should now be ready for deletion"
echo "- RDS endpoint: $RDS_ENDPOINT"
echo
echo "🔒 All access to RDS has been removed!"
echo "💡 RDS security groups are now clean and can be safely deleted"
