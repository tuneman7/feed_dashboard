#!/bin/bash

# Terraform Destroy Script
# This script safely destroys the Terraform infrastructure

echo "========================================="
echo "Terraform Infrastructure Destroy Script"
echo "========================================="
echo

# Check if terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "❌ Error: Terraform is not installed or not in PATH"
    echo "Please install Terraform and try again"
    return 1 2>/dev/null || true
fi

# Check if we're in a terraform directory
if [ ! -f "main.tf" ] && [ ! -f "*.tf" ]; then
    echo "❌ Error: No Terraform configuration files found in current directory"
    echo "Please run this script from your Terraform project directory"
    return 1 2>/dev/null || true
fi

# Check if terraform has been initialized
if [ ! -d ".terraform" ]; then
    echo "⚠️  Warning: Terraform not initialized. Running terraform init..."
    terraform init
fi

echo "🔍 Showing current infrastructure state..."
echo
terraform show

echo
echo "⚠️  WARNING: This will DESTROY all infrastructure managed by this Terraform configuration!"
echo "   - EC2 instance will be terminated"
echo "   - Security group will be deleted"
echo "   - SSH key pair will be removed from AWS"
echo "   - Local private key file will remain (you can delete manually if needed)"
echo

echo
echo "🚀 Starting terraform destroy..."
echo

# Run terraform destroy with auto-approve
if terraform destroy -auto-approve; then
    echo
    echo "✅ Infrastructure successfully destroyed!"
    echo
    echo "📋 Post-destroy cleanup:"
    echo "   - AWS resources have been removed"
    echo "   - Terraform state has been updated"
    echo "   - Private key file 'id_rsa' still exists locally"
    echo
    echo "💡 Optional manual cleanup:"
    echo "   - Delete the private key: rm -f id_rsa"
    echo "   - Remove Terraform state: rm -f terraform.tfstate*"
    echo "   - Remove Terraform cache: rm -rf .terraform"
    echo
else
    echo
    echo "❌ Terraform destroy failed!"
    echo "Please check the error messages above and resolve any issues."
    echo "You may need to:"
    echo "   - Check your AWS credentials"
    echo "   - Verify resource dependencies"
    echo "   - Run 'terraform plan -destroy' to see what would be destroyed"
    return 1 2>/dev/null || true
fi

# Optional: Ask if user wants to clean up local files
echo
#read -p "Do you want to clean up local Terraform files? (yes/no): " cleanup

cleanup="yes"

if [[ $cleanup == "yes" ]]; then
    echo "🧹 Cleaning up local files..."
    rm -f id_rsa
    rm -f terraform.tfstate*
    rm -rf .terraform
    rm -f .terraform.lock.hcl
    echo "✅ Local cleanup complete!"
else
    echo "ℹ️  Local files preserved. You can clean them up manually later if needed."
fi

echo
echo "🎉 Destroy process complete!"
echo "========================================="