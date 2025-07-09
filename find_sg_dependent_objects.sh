# Replace sg-03a3f2b518b988b7f with your security group ID
SG_ID="sg-03a3f2b518b988b7f"

# Find EC2 instances using this security group
aws ec2 describe-instances --filters "Name=instance.group-id,Values=$SG_ID" --query 'Reservations[*].Instances[*].{InstanceId:InstanceId,State:State.Name}'

# Find RDS instances using this security group
aws rds describe-db-instances --query "DBInstances[?VpcSecurityGroups[?VpcSecurityGroupId=='$SG_ID']].[DBInstanceIdentifier,DBInstanceStatus]"

# Find Load Balancers using this security group
aws elbv2 describe-load-balancers --query "LoadBalancers[?SecurityGroups[?@=='$SG_ID']].[LoadBalancerName,State.Code]"

# Find Network Interfaces using this security group
aws ec2 describe-network-interfaces --filters "Name=group-id,Values=$SG_ID" --query 'NetworkInterfaces[*].{NetworkInterfaceId:NetworkInterfaceId,Description:Description}'

# Find security group rules that reference this security group
aws ec2 describe-security-groups --query "SecurityGroups[?IpPermissions[?UserIdGroupPairs[?GroupId=='$SG_ID']] || IpPermissionsEgress[?UserIdGroupPairs[?GroupId=='$SG_ID']]].[GroupId,GroupName]"

# Find Lambda functions using this security group
aws lambda list-functions --query "Functions[?VpcConfig.SecurityGroupIds[?@=='$SG_ID']].[FunctionName]"