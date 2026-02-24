#!/bin/bash

# RDS Security Group Attachment Script
# This script attaches the environment-specific security group to the shared RDS instance

echo "======================================="
echo "RDS Security Group Attachment Script"
echo "======================================="
echo

# Configuration
ENV="dev"
RDS_INSTANCE="dst-dashboard-database-fast"
RDS_ACCESS_SG_ID="sg-05b04a7b31dc78413"

echo "🔍 Environment: $ENV"
echo "🔍 RDS Instance: $RDS_INSTANCE"
echo "🔍 SG to Attach: $RDS_ACCESS_SG_ID"
echo

echo "➕ Attaching environment SG to RDS instance..."

# Get current SGs attached to the RDS
CURRENT_SGS=$(aws rds describe-db-instances \
    --db-instance-identifier "$RDS_INSTANCE" \
    --query 'DBInstances[0].VpcSecurityGroups[*].VpcSecurityGroupId' \
    --output text 2>/dev/null)

if [ $? -ne 0 ]; then
    echo "❌ Error: Could not get current SGs for RDS instance $RDS_INSTANCE"
    exit 1
fi

# Check if our SG is already in the list
if [[ $CURRENT_SGS =~ $RDS_ACCESS_SG_ID ]]; then
    echo "   ✅ SG $RDS_ACCESS_SG_ID is already attached to $RDS_INSTANCE"
else
    # Append our SG to the existing list to avoid dropping other envs
    NEW_SGS="$CURRENT_SGS $RDS_ACCESS_SG_ID"
    echo "   � Updating RDS security groups: $NEW_SGS"
    
    aws rds modify-db-instance \
        --db-instance-identifier "$RDS_INSTANCE" \
        --vpc-security-group-ids $NEW_SGS \
        --apply-immediately > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "   ✅ SG attached successfully"
    else
        echo "   ❌ Failed to attach SG"
        exit 1
    fi
fi

echo
echo "🎉 RDS security configuration complete for $ENV!"
