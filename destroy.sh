#!/bin/bash

set +e

ENV="${1:-dev}"

# Derive RDS identifier
RDS_BASE="dst-dashboard-database-fast"
if [ "$ENV" = "prod" ]; then
RDS_ID="$RDS_BASE"
else
  #RDS_ID="${RDS_BASE}-dev"
  RDS_ID="$RDS_BASE"
fi

KEY_FILE="id_rsa_${ENV}"

echo "========================================="
echo "Terraform Infrastructure Destroy Script"
echo "Environment : $ENV"
echo "RDS Instance: $RDS_ID"
echo "========================================="
echo

# Run surgical cleanup first (removes RDS security group rules for this env's EC2)
[ -f "cleanup-rds-security_${ENV}.sh" ] && bash "cleanup-rds-security_${ENV}.sh" "$ENV" || echo "ℹ️  No cleanup-rds-security_${ENV}.sh found — skipping (expected on first run)."

# Check if terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "❌ Error: Terraform is not installed or not in PATH"
    echo "Please install Terraform and try again"
    return 1 2>/dev/null || true
fi

# Check if we're in a terraform directory
if [ ! -f "main.tf" ]; then
    echo "❌ Error: No Terraform configuration files found in current directory"
    echo "Please run this script from your Terraform project directory"
    return 1 2>/dev/null || true
fi

# Select the correct workspace
echo "🗂️  Selecting Terraform workspace: $ENV"
terraform workspace select "$ENV" 2>/dev/null || {
    echo "⚠️  Workspace '$ENV' not found. Nothing to destroy."
    return 0 2>/dev/null || true
}
echo "   Active workspace: $(terraform workspace show)"
echo

# Check if terraform has been initialized
if [ ! -d ".terraform" ]; then
    echo "⚠️  Warning: Terraform not initialized. Running terraform init..."
    terraform init
fi

echo "🔍 Showing current infrastructure state..."
echo
terraform show

echo
echo "⚠️  WARNING: This will DESTROY all $ENV infrastructure!"
echo "   - EC2 instance will be terminated"
echo "   - Security groups will be deleted"
echo "   - SSH key pair will be removed from AWS"
echo "   - RDS security rules will have been cleaned up already"
echo

echo "🚀 Starting terraform destroy ($ENV)..."
echo

# Run terraform destroy with auto-approve, passing env vars
if terraform destroy -auto-approve \
     -var="env=$ENV" \
     -var="rds_instance_identifier=$RDS_BASE"; then
    echo
    echo "✅ $ENV infrastructure successfully destroyed!"
    echo
    echo "📋 Post-destroy cleanup:"
    echo "   - AWS resources have been removed"
    echo "   - Terraform state has been updated"
    echo
else
    echo
    echo "❌ Terraform destroy failed!"
    echo "Please check the error messages above and resolve any issues."
    echo "You may need to:"
    echo "   - Check your AWS credentials"
    echo "   - Verify resource dependencies"
    echo "   - Run 'terraform plan -destroy -var=env=$ENV' to see what would be destroyed"
    return 1 2>/dev/null || true
fi

# Clean up env-specific local files
echo "🧹 Cleaning up local files for $ENV..."
rm -f "$KEY_FILE"
rm -f "connect_${ENV}.sh"

# Clean Terraform state only if switching back to default workspace
terraform workspace select default 2>/dev/null || true
terraform workspace delete "$ENV" 2>/dev/null || echo "   (workspace kept for re-use)"

echo "✅ Local cleanup complete!"

echo
echo "🎉 Destroy process complete for: $ENV"
echo "========================================="