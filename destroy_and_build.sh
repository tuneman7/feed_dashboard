#!/bin/bash

set +e

ENV="${1:-dev}"

echo "🌍 Environment: $ENV"
echo

[ -f "cleanup-rds-security_${ENV}.sh" ] && bash "cleanup-rds-security_${ENV}.sh" "$ENV" || echo "ℹ️  cleanup-rds-security_${ENV}.sh not yet generated — skipping."
bash destroy.sh              "$ENV"
bash terraform-build.sh      "$ENV"
[ -f "fix-rds-security_${ENV}.sh" ] && bash "fix-rds-security_${ENV}.sh" "$ENV" || echo "ℹ️  fix-rds-security_${ENV}.sh not yet generated — skipping."
bash deploy.sh               "$ENV"
bash check_url.sh            "$ENV"
