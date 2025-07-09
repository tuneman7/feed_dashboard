# Remove Terraform state lock (if stuck)
rm -f .terraform.lock.hcl

# Remove Terraform cache directory
rm -rf .terraform/

# Remove cached provider plugins
rm -rf .terraform.d/

# Remove terraform plan files
rm -f terraform.plan
rm -f *.tfplan

# Optional: Remove state backup files (be careful!)
rm -f terraform.tfstate.backup*

# Re-initialize Terraform
terraform init