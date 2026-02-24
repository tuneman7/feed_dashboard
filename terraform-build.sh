#!/bin/bash

set +e

ENV="${1:-dev}"

# RDS instance identifier (same for both dev and prod)
RDS_ID="dst-dashboard-database-fast"

echo "========================================="
echo "Terraform Build Script"
echo "Environment : $ENV"
echo "RDS Instance: $RDS_ID"
echo "========================================="
echo

# Check if terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "❌ Error: Terraform is not installed or not in PATH"
    return 1 2>/dev/null || true
fi

echo "[0/4] Selecting Terraform workspace: $ENV"
terraform workspace select "$ENV" 2>/dev/null || terraform workspace new "$ENV"
echo "   Active workspace: $(terraform workspace show)"
echo

echo "[1/4] Initializing Terraform..."
terraform init -upgrade || echo "Terraform init failed, continuing..."

echo "[2/4] Validating configuration..."
terraform validate || echo "Validation failed, continuing..."

echo "[3/4] Applying Terraform plan ($ENV)..."
terraform apply -auto-approve \
  -var="env=$ENV" \
  -var="rds_instance_identifier=$RDS_ID" || echo "Apply failed, continuing..."

echo "[4/4] Build complete. Showing outputs..."
terraform output || echo "No outputs available or failed to fetch."
