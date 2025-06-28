#!/bin/bash

echo "[1/4] Initializing Terraform..."
terraform init -upgrade || echo "Terraform init failed, continuing..."

echo "[2/4] Validating configuration..."
terraform validate || echo "Validation failed, continuing..."

echo "[3/4] Applying Terraform plan (force apply)..."
terraform apply -auto-approve -var="rds_instance_identifier=dst-dashboard-database-fast1" || echo "Apply failed, continuing..."

echo "[4/4] Build attempted. Showing outputs (if any)..."
terraform output || echo "No outputs available or failed to fetch."
