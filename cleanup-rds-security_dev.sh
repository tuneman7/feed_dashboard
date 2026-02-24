#!/bin/bash

# RDS Security Group Detachment Script
# This script detaches the environment-specific security group from the shared RDS instance

echo "======================================="
echo "RDS Security Group Detachment Script"
echo "======================================="
echo

# Configuration
ENV="dev"
RDS_INSTANCE="dst-dashboard-database-fast"
RDS_ACCESS_SG_ID="sg-05b04a7b31dc78413"

echo "🔍 Environment: $ENV"
echo "🔍 RDS Instance: $RDS_INSTANCE"
echo "🔍 SG to Detach: $RDS_ACCESS_SG_ID"
echo

echo "➖ Detaching environment SG from RDS instance..."

# Get current SGs attached to the RDS
CURRENT_SGS=$(aws rds describe-db-instances \
    --db-instance-identifier "$RDS_INSTANCE" \
    --query 'DBInstances[0].VpcSecurityGroups[*].VpcSecurityGroupId' \
    --output text 2>/dev/null)

if [ $? -ne 0 ] || [ -z "$CURRENT_SGS" ]; then
    echo "ℹ️  Could not get current SGs or RDS instance not found. Skipping detachment."
    exit 0
fi

# Filter out our SG from the list
NEW_SGS=""
for SG in $CURRENT_SGS; do
    if [ "$SG" != "$RDS_ACCESS_SG_ID" ]; then
        NEW_SGS="$NEW_SGS $SG"
    fi
done

if [ "$CURRENT_SGS" == "$NEW_SGS" ]; then
    echo "   ✅ SG $RDS_ACCESS_SG_ID is not attached to $RDS_INSTANCE"
else
    # Update RDS with the filtered list
    echo "   🔄 Updating RDS security groups (removing $RDS_ACCESS_SG_ID)..."
    
    aws rds modify-db-instance \
        --db-instance-identifier "$RDS_INSTANCE" \
        --vpc-security-group-ids $NEW_SGS \
        --apply-immediately > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "   ✅ SG detached successfully"
    else
        echo "   ❌ Failed to detach SG (Note: If it's the last SG, AWS may require at least one)"
        exit 1
    fi
fi

echo "🎉 Detachment complete!"
