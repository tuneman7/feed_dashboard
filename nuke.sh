#!/bin/bash

# Remove security group rule
# Remove sg-04b0583605b770795 from sg-0aceb03556342fc21's rules

SOURCE_SG="sg-04b0583605b770795"  # Security group to remove
TARGET_SG="sg-0aceb03556342fc21"  # Security group to remove it from

echo "=============================================="
echo "REMOVE SECURITY GROUP RULE"
echo "=============================================="
echo "Removing: $SOURCE_SG"
echo "From: $TARGET_SG"
echo ""

echo "🔍 Step 1: Checking current rules in $TARGET_SG..."

# Get current rules
CURRENT_RULES=$(aws ec2 describe-security-groups --group-ids "$TARGET_SG" --output table 2>/dev/null)

if [ "$CURRENT_RULES" != "" ]; then
    echo "✅ Current security group rules:"
    echo "$CURRENT_RULES"
else
    echo "❌ Could not get current security group rules"
fi

echo ""
echo "🔍 Step 2: Finding rules that reference $SOURCE_SG..."

# Find inbound rules that reference the source security group
INBOUND_RULES=$(aws ec2 describe-security-groups --group-ids "$TARGET_SG" --query "SecurityGroups[0].IpPermissions[?UserIdGroupPairs[?GroupId==\`$SOURCE_SG\`]]" --output json 2>/dev/null)

if [ "$INBOUND_RULES" != "" ] && [ "$INBOUND_RULES" != "[]" ] && [ "$INBOUND_RULES" != "null" ]; then
    echo "✅ Found inbound rules referencing $SOURCE_SG"
    echo "$INBOUND_RULES"
    
    echo ""
    echo "🔧 Removing inbound rules..."
    
    # Remove each inbound rule
    echo "$INBOUND_RULES" | jq -c '.[]' | while read rule; do
        PROTOCOL=$(echo "$rule" | jq -r '.IpProtocol')
        FROM_PORT=$(echo "$rule" | jq -r '.FromPort // empty')
        TO_PORT=$(echo "$rule" | jq -r '.ToPort // empty')
        
        echo "   Removing inbound rule: Protocol=$PROTOCOL, FromPort=$FROM_PORT, ToPort=$TO_PORT"
        
        if [ "$FROM_PORT" != "" ] && [ "$TO_PORT" != "" ]; then
            REMOVE_RESULT=$(aws ec2 revoke-security-group-ingress \
                --group-id "$TARGET_SG" \
                --protocol "$PROTOCOL" \
                --port "$FROM_PORT-$TO_PORT" \
                --source-group "$SOURCE_SG" 2>&1)
        else
            REMOVE_RESULT=$(aws ec2 revoke-security-group-ingress \
                --group-id "$TARGET_SG" \
                --protocol "$PROTOCOL" \
                --source-group "$SOURCE_SG" 2>&1)
        fi
        
        if [ $? -eq 0 ]; then
            echo "   ✅ Successfully removed inbound rule"
        else
            echo "   ❌ Failed to remove inbound rule: $REMOVE_RESULT"
        fi
    done
else
    echo "ℹ️  No inbound rules found referencing $SOURCE_SG"
fi

echo ""
echo "🔍 Step 3: Checking outbound rules..."

# Find outbound rules that reference the source security group
OUTBOUND_RULES=$(aws ec2 describe-security-groups --group-ids "$TARGET_SG" --query "SecurityGroups[0].IpPermissionsEgress[?UserIdGroupPairs[?GroupId==\`$SOURCE_SG\`]]" --output json 2>/dev/null)

if [ "$OUTBOUND_RULES" != "" ] && [ "$OUTBOUND_RULES" != "[]" ] && [ "$OUTBOUND_RULES" != "null" ]; then
    echo "✅ Found outbound rules referencing $SOURCE_SG"
    echo "$OUTBOUND_RULES"
    
    echo ""
    echo "🔧 Removing outbound rules..."
    
    # Remove each outbound rule
    echo "$OUTBOUND_RULES" | jq -c '.[]' | while read rule; do
        PROTOCOL=$(echo "$rule" | jq -r '.IpProtocol')
        FROM_PORT=$(echo "$rule" | jq -r '.FromPort // empty')
        TO_PORT=$(echo "$rule" | jq -r '.ToPort // empty')
        
        echo "   Removing outbound rule: Protocol=$PROTOCOL, FromPort=$FROM_PORT, ToPort=$TO_PORT"
        
        if [ "$FROM_PORT" != "" ] && [ "$TO_PORT" != "" ]; then
            REMOVE_RESULT=$(aws ec2 revoke-security-group-egress \
                --group-id "$TARGET_SG" \
                --protocol "$PROTOCOL" \
                --port "$FROM_PORT-$TO_PORT" \
                --source-group "$SOURCE_SG" 2>&1)
        else
            REMOVE_RESULT=$(aws ec2 revoke-security-group-egress \
                --group-id "$TARGET_SG" \
                --protocol "$PROTOCOL" \
                --source-group "$SOURCE_SG" 2>&1)
        fi
        
        if [ $? -eq 0 ]; then
            echo "   ✅ Successfully removed outbound rule"
        else
            echo "   ❌ Failed to remove outbound rule: $REMOVE_RESULT"
        fi
    done
else
    echo "ℹ️  No outbound rules found referencing $SOURCE_SG"
fi

echo ""
echo "🔍 Step 4: Alternative removal method (if jq parsing fails)..."

# Try alternative removal methods for common rules
echo "Trying to remove common rule types..."

# Try removing common inbound rules
for protocol in tcp udp icmp; do
    for port in 22 80 443 3306 5432 6379; do
        REMOVE_RESULT=$(aws ec2 revoke-security-group-ingress \
            --group-id "$TARGET_SG" \
            --protocol "$protocol" \
            --port "$port" \
            --source-group "$SOURCE_SG" 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            echo "✅ Removed $protocol port $port inbound rule"
        fi
    done
done

# Try removing all protocols rule
REMOVE_RESULT=$(aws ec2 revoke-security-group-ingress \
    --group-id "$TARGET_SG" \
    --protocol "-1" \
    --source-group "$SOURCE_SG" 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "✅ Removed all protocols (-1) inbound rule"
fi

echo ""
echo "🔍 Step 5: Verifying removal..."

echo "📋 Current rules after removal:"
FINAL_RULES=$(aws ec2 describe-security-groups --group-ids "$TARGET_SG" --output table 2>/dev/null)

if [ "$FINAL_RULES" != "" ]; then
    echo "$FINAL_RULES"
else
    echo "❌ Could not get final security group rules"
fi

echo ""
echo "🔍 Step 6: Check if $SOURCE_SG still exists in rules..."

REMAINING_REFS=$(aws ec2 describe-security-groups --group-ids "$TARGET_SG" --query "SecurityGroups[0].IpPermissions[?UserIdGroupPairs[?GroupId==\`$SOURCE_SG\`]] | length(@)" --output text 2>/dev/null)
REMAINING_EGRESS_REFS=$(aws ec2 describe-security-groups --group-ids "$TARGET_SG" --query "SecurityGroups[0].IpPermissionsEgress[?UserIdGroupPairs[?GroupId==\`$SOURCE_SG\`]] | length(@)" --output text 2>/dev/null)

if [ "$REMAINING_REFS" = "0" ] && [ "$REMAINING_EGRESS_REFS" = "0" ]; then
    echo "✅ SUCCESS: $SOURCE_SG has been completely removed from $TARGET_SG"
elif [ "$REMAINING_REFS" != "" ] || [ "$REMAINING_EGRESS_REFS" != "" ]; then
    echo "⚠️  Some references may still exist:"
    echo "   Inbound rules: $REMAINING_REFS"
    echo "   Outbound rules: $REMAINING_EGRESS_REFS"
    echo ""
    echo "🔧 Manual removal commands if needed:"
    echo "   aws ec2 revoke-security-group-ingress --group-id $TARGET_SG --protocol <protocol> --port <port> --source-group $SOURCE_SG"
    echo "   aws ec2 revoke-security-group-egress --group-id $TARGET_SG --protocol <protocol> --port <port> --source-group $SOURCE_SG"
else
    echo "ℹ️  Could not verify removal status"
fi

echo ""
echo "🏁 REMOVAL COMPLETE"
echo "=============================================="