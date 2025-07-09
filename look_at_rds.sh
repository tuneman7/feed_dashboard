#!/bin/bash

# RDS Connectivity Troubleshooting Script
# Usage: ./rds_troubleshoot.sh <rds-instance-identifier>
# Or source it: source ./rds_troubleshoot.sh <rds-instance-identifier>

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if RDS instance name is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: Please provide RDS instance identifier${NC}"
    echo "Usage: $0 <rds-instance-identifier>"
    echo "Or: source $0 <rds-instance-identifier>"
    return 1 2>/dev/null || { echo "Script must be sourced or run as executable"; }
fi

RDS_INSTANCE=$1
echo -e "${BLUE}=== RDS Connectivity Troubleshooting for: $RDS_INSTANCE ===${NC}\n"

# Function to print section headers
print_section() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to print status
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "OK" ]; then
        echo -e "${GREEN}✓ $message${NC}"
    elif [ "$status" = "WARNING" ]; then
        echo -e "${YELLOW}⚠ $message${NC}"
    else
        echo -e "${RED}✗ $message${NC}"
    fi
}

# Check if AWS CLI is installed and configured
if ! command -v aws &> /dev/null; then
    print_status "ERROR" "AWS CLI not found. Please install AWS CLI first."
    return 1 2>/dev/null || { echo "Exiting script"; return; }
fi

# Test AWS credentials
echo "Testing AWS CLI access..."
AWS_IDENTITY=$(aws sts get-caller-identity --output json 2>&1)
if [ $? -ne 0 ]; then
    print_status "ERROR" "AWS credentials not configured or invalid."
    echo "Error: $AWS_IDENTITY"
    return 1 2>/dev/null || { echo "Exiting script"; return; }
else
    print_status "OK" "AWS CLI configured and working"
fi

print_section "1. RDS Instance Details"

# First, let's check what region we're using
CURRENT_REGION=$(aws configure get region 2>/dev/null || echo "not-set")
echo "Current AWS region: $CURRENT_REGION"

# List all RDS instances to help with debugging
echo "Listing all RDS instances in current region:"
ALL_INSTANCES=$(aws rds describe-db-instances --query 'DBInstances[].DBInstanceIdentifier' --output text 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "Available instances: $ALL_INSTANCES"
else
    echo "Failed to list RDS instances - check permissions"
fi

# Get RDS instance details
echo -e "\nAttempting to describe RDS instance: $RDS_INSTANCE"
RDS_DETAILS=$(aws rds describe-db-instances --db-instance-identifier "$RDS_INSTANCE" --output json 2>&1)
RDS_EXIT_CODE=$?

if [ $RDS_EXIT_CODE -ne 0 ]; then
    print_status "ERROR" "RDS instance '$RDS_INSTANCE' not found or access denied."
    echo "AWS CLI Error Output:"
    echo "$RDS_DETAILS"
    return 1 2>/dev/null || { echo "Exiting script"; return; }
fi

# Check if the output is valid JSON
if ! echo "$RDS_DETAILS" | jq empty 2>/dev/null; then
    print_status "ERROR" "Invalid JSON response from AWS CLI"
    echo "Raw AWS CLI Output:"
    echo "$RDS_DETAILS"
    return 1 2>/dev/null || { echo "Exiting script"; return; }
fi

# Check if the instance exists in the response
INSTANCE_COUNT=$(echo "$RDS_DETAILS" | jq '.DBInstances | length')
if [ "$INSTANCE_COUNT" -eq 0 ]; then
    print_status "ERROR" "No RDS instances found in response"
    echo "Raw AWS CLI Output:"
    echo "$RDS_DETAILS"
    return 1 2>/dev/null || { echo "Exiting script"; return; }
fi

# Extract key information
DB_ENGINE=$(echo "$RDS_DETAILS" | jq -r '.DBInstances[0].Engine')
DB_STATUS=$(echo "$RDS_DETAILS" | jq -r '.DBInstances[0].DBInstanceStatus')
DB_ENDPOINT=$(echo "$RDS_DETAILS" | jq -r '.DBInstances[0].Endpoint.Address')
DB_PORT=$(echo "$RDS_DETAILS" | jq -r '.DBInstances[0].Endpoint.Port')
PUBLICLY_ACCESSIBLE=$(echo "$RDS_DETAILS" | jq -r '.DBInstances[0].PubliclyAccessible')
VPC_ID=$(echo "$RDS_DETAILS" | jq -r '.DBInstances[0].DBSubnetGroup.VpcId')
SUBNET_GROUP=$(echo "$RDS_DETAILS" | jq -r '.DBInstances[0].DBSubnetGroup.DBSubnetGroupName')
SECURITY_GROUPS=$(echo "$RDS_DETAILS" | jq -r '.DBInstances[0].VpcSecurityGroups[].VpcSecurityGroupId' | tr '\n' ' ')

echo "Engine: $DB_ENGINE"
echo "Status: $DB_STATUS"
echo "Endpoint: $DB_ENDPOINT"
echo "Port: $DB_PORT"
echo "Publicly Accessible: $PUBLICLY_ACCESSIBLE"
echo "VPC ID: $VPC_ID"
echo "Subnet Group: $SUBNET_GROUP"
echo "Security Groups: $SECURITY_GROUPS"

if [ "$DB_STATUS" != "available" ]; then
    print_status "WARNING" "Database status is '$DB_STATUS', not 'available'"
else
    print_status "OK" "Database is available"
fi

print_section "2. VPC Configuration"

# Get VPC details
VPC_DETAILS=$(aws ec2 describe-vpcs --vpc-ids "$VPC_ID" --output json)
VPC_CIDR=$(echo "$VPC_DETAILS" | jq -r '.Vpcs[0].CidrBlock')
echo "VPC CIDR: $VPC_CIDR"

# Check if VPC has internet gateway
IGW_COUNT=$(aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC_ID" --query 'InternetGateways | length(@)' --output text)
if [ "$IGW_COUNT" -gt 0 ]; then
    print_status "OK" "Internet Gateway attached to VPC"
else
    print_status "WARNING" "No Internet Gateway found - external connectivity may be limited"
fi

print_section "3. Subnet Analysis"

# Get subnet details from DB subnet group
SUBNET_IDS=$(aws rds describe-db-subnet-groups --db-subnet-group-name "$SUBNET_GROUP" --query 'DBSubnetGroups[0].Subnets[].SubnetIdentifier' --output text)

echo "Subnets in DB Subnet Group:"
for subnet_id in $SUBNET_IDS; do
    SUBNET_DETAILS=$(aws ec2 describe-subnets --subnet-ids "$subnet_id" --output json)
    SUBNET_AZ=$(echo "$SUBNET_DETAILS" | jq -r '.Subnets[0].AvailabilityZone')
    SUBNET_CIDR=$(echo "$SUBNET_DETAILS" | jq -r '.Subnets[0].CidrBlock')
    PUBLIC_SUBNET=$(echo "$SUBNET_DETAILS" | jq -r '.Subnets[0].MapPublicIpOnLaunch')
    
    echo "  - $subnet_id ($SUBNET_AZ) - $SUBNET_CIDR - Public: $PUBLIC_SUBNET"
    
    # Check route table for each subnet
    ROUTE_TABLE_ID=$(aws ec2 describe-route-tables --filters "Name=association.subnet-id,Values=$subnet_id" --query 'RouteTables[0].RouteTableId' --output text)
    if [ "$ROUTE_TABLE_ID" = "None" ]; then
        # Check main route table
        ROUTE_TABLE_ID=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" "Name=association.main,Values=true" --query 'RouteTables[0].RouteTableId' --output text)
        echo "    Using main route table: $ROUTE_TABLE_ID"
    else
        echo "    Route table: $ROUTE_TABLE_ID"
    fi
    
    # Check for internet gateway route
    IGW_ROUTE=$(aws ec2 describe-route-tables --route-table-ids "$ROUTE_TABLE_ID" --query 'RouteTables[0].Routes[?GatewayId && starts_with(GatewayId, `igw-`)]' --output text)
    if [ -n "$IGW_ROUTE" ]; then
        print_status "OK" "Internet Gateway route found in subnet $subnet_id"
    else
        print_status "WARNING" "No Internet Gateway route in subnet $subnet_id"
    fi
done

print_section "4. Security Group Analysis"

for sg_id in $SECURITY_GROUPS; do
    echo -e "\n${YELLOW}Security Group: $sg_id${NC}"
    
    # Get security group details
    SG_DETAILS=$(aws ec2 describe-security-groups --group-ids "$sg_id" --output json)
    SG_NAME=$(echo "$SG_DETAILS" | jq -r '.SecurityGroups[0].GroupName')
    echo "Name: $SG_NAME"
    
    # Check inbound rules
    echo "Inbound Rules:"
    INBOUND_RULES=$(echo "$SG_DETAILS" | jq -r '.SecurityGroups[0].IpPermissions[]')
    
    if [ -z "$INBOUND_RULES" ] || [ "$INBOUND_RULES" = "null" ]; then
        print_status "ERROR" "No inbound rules found"
    else
        echo "$SG_DETAILS" | jq -r '.SecurityGroups[0].IpPermissions[] | 
            "  Protocol: \(.IpProtocol) | Port: \(if .FromPort then "\(.FromPort)-\(.ToPort)" else "All" end) | Source: \(
                if .IpRanges then .IpRanges[].CidrIp else 
                if .UserIdGroupPairs then .UserIdGroupPairs[].GroupId else "N/A" end end
            )"'
        
        # Check for database port access
        DB_PORT_OPEN=$(echo "$SG_DETAILS" | jq -r --arg port "$DB_PORT" '.SecurityGroups[0].IpPermissions[] | select(.FromPort <= ($port | tonumber) and .ToPort >= ($port | tonumber))')
        if [ -n "$DB_PORT_OPEN" ] && [ "$DB_PORT_OPEN" != "null" ]; then
            print_status "OK" "Database port $DB_PORT is accessible"
        else
            print_status "ERROR" "Database port $DB_PORT is NOT accessible"
        fi
    fi
    
    # Check outbound rules
    echo "Outbound Rules:"
    OUTBOUND_RULES=$(echo "$SG_DETAILS" | jq -r '.SecurityGroups[0].IpPermissionsEgress[]')
    echo "$SG_DETAILS" | jq -r '.SecurityGroups[0].IpPermissionsEgress[] | 
        "  Protocol: \(.IpProtocol) | Port: \(if .FromPort then "\(.FromPort)-\(.ToPort)" else "All" end) | Destination: \(
            if .IpRanges then .IpRanges[].CidrIp else 
            if .UserIdGroupPairs then .UserIdGroupPairs[].GroupId else "N/A" end end
        )"'
done

print_section "5. Network ACL Analysis"

# Get Network ACLs for subnets
for subnet_id in $SUBNET_IDS; do
    NACL_ID=$(aws ec2 describe-network-acls --filters "Name=association.subnet-id,Values=$subnet_id" --query 'NetworkAcls[0].NetworkAclId' --output text)
    if [ "$NACL_ID" = "None" ]; then
        # Get default NACL
        NACL_ID=$(aws ec2 describe-network-acls --filters "Name=vpc-id,Values=$VPC_ID" "Name=default,Values=true" --query 'NetworkAcls[0].NetworkAclId' --output text)
        echo "Subnet $subnet_id using default NACL: $NACL_ID"
    else
        echo "Subnet $subnet_id using custom NACL: $NACL_ID"
    fi
    
    # Check NACL rules
    NACL_DETAILS=$(aws ec2 describe-network-acls --network-acl-ids "$NACL_ID" --output json)
    
    echo "  Inbound NACL Rules:"
    echo "$NACL_DETAILS" | jq -r '.NetworkAcls[0].Entries[] | select(.Egress == false) | 
        "    Rule \(.RuleNumber): \(.RuleAction) | Protocol: \(.Protocol) | Port: \(if .PortRange then "\(.PortRange.From)-\(.PortRange.To)" else "All" end) | Source: \(.CidrBlock)"'
    
    echo "  Outbound NACL Rules:"
    echo "$NACL_DETAILS" | jq -r '.NetworkAcls[0].Entries[] | select(.Egress == true) | 
        "    Rule \(.RuleNumber): \(.RuleAction) | Protocol: \(.Protocol) | Port: \(if .PortRange then "\(.PortRange.From)-\(.PortRange.To)" else "All" end) | Destination: \(.CidrBlock)"'
    
    # Check if database port is allowed
    DB_PORT_ALLOWED=$(echo "$NACL_DETAILS" | jq -r --arg port "$DB_PORT" '.NetworkAcls[0].Entries[] | select(.Egress == false and .RuleAction == "allow" and (.PortRange.From <= ($port | tonumber) and .PortRange.To >= ($port | tonumber)))')
    if [ -n "$DB_PORT_ALLOWED" ] && [ "$DB_PORT_ALLOWED" != "null" ]; then
        print_status "OK" "NACL allows database port $DB_PORT"
    else
        # Check for allow-all rule
        ALLOW_ALL=$(echo "$NACL_DETAILS" | jq -r '.NetworkAcls[0].Entries[] | select(.Egress == false and .RuleAction == "allow" and .Protocol == "-1")')
        if [ -n "$ALLOW_ALL" ] && [ "$ALLOW_ALL" != "null" ]; then
            print_status "OK" "NACL allows all traffic (including database port)"
        else
            print_status "WARNING" "NACL may be blocking database port $DB_PORT"
        fi
    fi
done

print_section "6. Connectivity Test"

if [ "$PUBLICLY_ACCESSIBLE" = "true" ]; then
    print_status "OK" "RDS is publicly accessible"
    echo "Testing connectivity to $DB_ENDPOINT:$DB_PORT..."
    
    # Test connectivity using nc (netcat) if available
    if command -v nc &> /dev/null; then
        if timeout 10 nc -z "$DB_ENDPOINT" "$DB_PORT" 2>/dev/null; then
            print_status "OK" "Successfully connected to $DB_ENDPOINT:$DB_PORT"
        else
            print_status "ERROR" "Cannot connect to $DB_ENDPOINT:$DB_PORT"
        fi
    else
        echo "netcat (nc) not available for connectivity test"
    fi
else
    print_status "WARNING" "RDS is not publicly accessible - can only be accessed from within VPC"
fi

print_section "7. Summary and Recommendations"

echo -e "\n${YELLOW}Common Issues to Check:${NC}"
echo "1. Ensure security group allows inbound traffic on port $DB_PORT"
echo "2. If accessing from internet, ensure 'Publicly Accessible' is enabled"
echo "3. Check that subnets have proper route tables with internet gateway routes"
echo "4. Verify Network ACLs are not blocking traffic"
echo "5. Confirm RDS endpoint is resolving correctly"
echo "6. Check that your client IP is included in security group rules"

echo -e "\n${YELLOW}Next Steps:${NC}"
echo "1. Review the security group rules above"
echo "2. Test connectivity from an EC2 instance in the same VPC"
echo "3. Check VPC Flow Logs if enabled"
echo "4. Verify DNS resolution: nslookup $DB_ENDPOINT"

echo -e "\n${BLUE}=== Troubleshooting Complete ===${NC}"