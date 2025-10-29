# Check if the instance profile was created
aws iam list-instance-profiles | grep ec2-s4-bidl-profile

# Check if the role exists
aws iam get-role --role-name EC2-Permissions-S4-BIDL

# Check terraform state
terraform state show aws_iam_instance_profile.ec2_profile
terraform state show aws_instance.ubuntu_box | grep iam_instance_profile