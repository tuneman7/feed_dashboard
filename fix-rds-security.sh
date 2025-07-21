#!/bin/bash

# Improved RDS Security Group Fix Script
# This script adds the EC2 instance and local user IP to the RDS security group to allow database connections

echo "======================================="
echo "RDS Security Group Configuration Script"
echo "======================================="
echo

# Configuration - these will be substituted by Terraform
RDS_INSTANCE="dst-dashboard-database-fast"
EC2_INSTANCE_ID="i-003b289714d54b611"
EC2_SECURITY_GROUP_ID="sg-01da7476096196601"
EC2_PUBLIC_IP="34.239.138.193"
USER_LOCAL_IP="68.107.83.168"

# Validation
if [ -z "$RDS_INSTANCE" ]; then
    echo "❌ No RDS instance identifier provided"
    echo "Set the rds_instance_identifier variable in Terraform"
    return 1 2>/dev/null || { echo "Script terminated"; return; }
fi

echo "🔍 Configuration:"
echo "   EC2 Instance ID: $EC2_INSTANCE_ID"
echo "   EC2 Security Group: $EC2_SECURITY_GROUP_ID"
echo "   EC2 Public IP: $EC2_PUBLIC_IP"
echo "   User Local IP: $USER_LOCAL_IP"
echo "   RDS Instance: $RDS_INSTANCE"
echo

# Get RDS instance details
echo "🔍 Getting RDS instance details..."
RDS_INFO=$(aws rds describe-db-instances --db-instance-identifier "$RDS_INSTANCE" --output json 2>/dev/null)

if [ $? -ne 0 ] || [ -z "$RDS_INFO" ]; then
    echo "❌ Could not find RDS instance: $RDS_INSTANCE"
    echo "   Please check the RDS instance name and ensure it exists."
    echo "   Available instances:"
    aws rds describe-db-instances --query 'DBInstances[].DBInstanceIdentifier' --output text 2>/dev/null || echo "   Could not list instances"
    return 1 2>/dev/null || { echo "Script terminated"; return; }
fi

# Extract details
RDS_ENGINE=$(echo "$RDS_INFO" | jq -r '.DBInstances[0].Engine')
RDS_PORT=$(echo "$RDS_INFO" | jq -r '.DBInstances[0].Endpoint.Port')
RDS_ENDPOINT=$(echo "$RDS_INFO" | jq -r '.DBInstances[0].Endpoint.Address')
RDS_STATUS=$(echo "$RDS_INFO" | jq -r '.DBInstances[0].DBInstanceStatus')
RDS_SECURITY_GROUPS=$(echo "$RDS_INFO" | jq -r '.DBInstances[0].VpcSecurityGroups[].VpcSecurityGroupId' | tr '\n' ' ' | sed 's/[[:space:]]*$//')

echo "✅ RDS Details:"
echo "   Engine: $RDS_ENGINE"
echo "   Port: $RDS_PORT"
echo "   Endpoint: $RDS_ENDPOINT"
echo "   Status: $RDS_STATUS"
echo "   Security Groups: $RDS_SECURITY_GROUPS"
echo

if [ "$RDS_STATUS" != "available" ]; then
    echo "⚠️  Warning: RDS instance status is '$RDS_STATUS', not 'available'"
    echo "   Connection may not work until the instance is available"
fi

# Function to safely add security group rule
add_sg_rule() {
    local sg_id=$1
    local rule_type=$2
    local rule_value=$3
    local description=$4
    
    echo "➕ Adding $description..."
    
    if [ "$rule_type" = "source-group" ]; then
        # Check if rule exists
        EXISTING=$(aws ec2 describe-security-groups --group-ids "$sg_id" \
            --query "SecurityGroups[0].IpPermissions[?FromPort==\`$RDS_PORT\` && ToPort==\`$RDS_PORT\` && UserIdGroupPairs[?GroupId==\`$rule_value\`]]" \
            --output text 2>/dev/null)
        
        if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
            echo "   ✅ Rule already exists"
        else
            aws ec2 authorize-security-group-ingress \
                --group-id "$sg_id" \
                --protocol tcp \
                --port "$RDS_PORT" \
                --source-group "$rule_value" 2>/dev/null && echo "   ✅ Added successfully" || echo "   ⚠️  Failed to add (might already exist)"
           
            #Manually add ecs security group
            aws ec2 authorize-security-group-ingress \
                --group-id "$sg_id" \
                --protocol tcp \
                --port "$RDS_PORT" \
                --source-group "sg-0aceb03556342fc21" 2>/dev/null && echo "   ✅ Added successfully" || echo "   ⚠️  Failed to add (might already exist)"
                
        fi
    else
        # CIDR rule
        EXISTING=$(aws ec2 describe-security-groups --group-ids "$sg_id" \
            --query "SecurityGroups[0].IpPermissions[?FromPort==\`$RDS_PORT\` && ToPort==\`$RDS_PORT\` && IpRanges[?CidrIp==\`$rule_value\`]]" \
            --output text 2>/dev/null)
        
        if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
            echo "   ✅ Rule already exists"
        else
            aws ec2 authorize-security-group-ingress \
                --group-id "$sg_id" \
                --protocol tcp \
                --port "$RDS_PORT" \
                --cidr "$rule_value" 2>/dev/null && echo "   ✅ Added successfully" || echo "   ⚠️  Failed to add (might already exist)"
        fi
    fi
}

# Configure each RDS security group
for RDS_SG_ID in $RDS_SECURITY_GROUPS; do
    echo "🔧 Configuring RDS security group: $RDS_SG_ID"
    
    # Get security group name for better identification
    SG_NAME=$(aws ec2 describe-security-groups --group-ids "$RDS_SG_ID" --query 'SecurityGroups[0].GroupName' --output text 2>/dev/null || echo "unknown")
    echo "   Security Group Name: $SG_NAME"
    
    # Add EC2 security group access
    add_sg_rule "$RDS_SG_ID" "source-group" "$EC2_SECURITY_GROUP_ID" "EC2 security group access"
    
    # Add EC2 public IP access
    add_sg_rule "$RDS_SG_ID" "cidr" "$EC2_PUBLIC_IP/32" "EC2 public IP access"
    
    # Add user's local IP access
    add_sg_rule "$RDS_SG_ID" "cidr" "$USER_LOCAL_IP/32" "user's local IP access"
    
    echo
done

echo "🎉 Security group configuration complete!"
echo

# Test connectivity
echo "🧪 Testing connectivity..."
echo "   From local machine:"
echo "     nslookup $RDS_ENDPOINT"
echo "     telnet $RDS_ENDPOINT $RDS_PORT"
echo "   From EC2 instance:"
echo "     ssh to EC2 and run: telnet $RDS_ENDPOINT $RDS_PORT"
echo

# Connection examples based on database engine
echo "🔌 Connection Examples:"
case $RDS_ENGINE in
    "postgres")
        echo "   PostgreSQL: psql -h $RDS_ENDPOINT -p $RDS_PORT -U username -d database"
        echo "   Connection String: postgresql://username:password@$RDS_ENDPOINT:$RDS_PORT/database"
        ;;
    "mysql")
        echo "   MySQL: mysql -h $RDS_ENDPOINT -P $RDS_PORT -u username -p database"
        echo "   Connection String: mysql://username:password@$RDS_ENDPOINT:$RDS_PORT/database"
        ;;
    "mariadb")
        echo "   MariaDB: mysql -h $RDS_ENDPOINT -P $RDS_PORT -u username -p database"
        echo "   Connection String: mysql://username:password@$RDS_ENDPOINT:$RDS_PORT/database"
        ;;
    *)
        echo "   Database: Connect using appropriate client for $RDS_ENGINE on $RDS_ENDPOINT:$RDS_PORT"
        ;;
esac

echo
echo "📋 Summary:"
echo "- Added EC2 security group ($EC2_SECURITY_GROUP_ID) to RDS security groups"
echo "- Added EC2 public IP ($EC2_PUBLIC_IP/32) to RDS security groups"
echo "- Added user's local IP ($USER_LOCAL_IP/32) to RDS security groups"
echo "- Database engine: $RDS_ENGINE on port $RDS_PORT"
echo "- RDS endpoint: $RDS_ENDPOINT"
echo
echo "🔧 Both your EC2 instance and local machine should now be able to connect to RDS!"

