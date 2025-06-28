#!/bin/bash

REGION=${1:-us-east-1}
GROUP_NAME="default-ssh-access-group"

echo "Checking default VPC in region: $REGION"

# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true --query "Vpcs[0].VpcId" --output text 2>/dev/null)

if [[ "$VPC_ID" == "None" || -z "$VPC_ID" ]]; then
  echo "❌ No default VPC found in region $REGION."
  exit 1
else
  echo "✅ Found default VPC: $VPC_ID"
fi

# Ensure there is at least one public subnet
SUBNET_ID=$(aws ec2 describe-subnets \
  --region "$REGION" \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[?MapPublicIpOnLaunch==\`true\`].[SubnetId]" \
  --output text | head -n 1)

if [[ -z "$SUBNET_ID" ]]; then
  echo "⚠️ No public subnets with automatic public IPs found. Creating one is not handled in this script."
else
  echo "✅ Found public subnet: $SUBNET_ID"
fi

# Check if the security group exists
SG_ID=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=$GROUP_NAME" \
  --query "SecurityGroups[0].GroupId" \
  --output text 2>/dev/null)

if [[ "$SG_ID" == "None" || -z "$SG_ID" ]]; then
  echo "🔧 Creating security group '$GROUP_NAME' to allow SSH..."
  SG_ID=$(aws ec2 create-security-group \
    --region "$REGION" \
    --group-name "$GROUP_NAME" \
    --description "Allow SSH from anywhere" \
    --vpc-id "$VPC_ID" \
    --query "GroupId" --output text)
else
  echo "✅ Found existing security group: $SG_ID"
fi

# Check if port 22 is already open
SSH_RULE_PRESENT=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --group-ids "$SG_ID" \
  --query "SecurityGroups[0].IpPermissions[?FromPort==\`22\` && ToPort==\`22\`]" \
  --output text)

if [[ -z "$SSH_RULE_PRESENT" ]]; then
  echo "🔧 Adding inbound SSH rule to security group..."
  aws ec2 authorize-security-group-ingress \
    --region "$REGION" \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0
else
  echo "✅ Security group already allows SSH."
fi

echo "✅ Default VPC is ready for public SSH access using security group: $SG_ID"
