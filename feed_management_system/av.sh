deactivate

source ./venv/bin/activate

select_database() {
  # Default to option 3 without prompting
  choice=3
  case "$choice" in
    1)
      DB_HOST="localhost"
      DB_PORT="5432"
      DB_NAME="pipeline_management"
      DB_USER="$USER"
      DB_PASSWORD=""
      ;;
    2)
      DB_HOST="dst-pipeline-dashboard.ckqboenmhdca.us-east-1.rds.amazonaws.com"
      DB_PORT="5432"
      DB_NAME="pipeline_management"
      DB_USER="postgres"
      DB_PASSWORD="Dashboard2025!$"
      ;;
    3)
      DB_HOST="dst-dashboard-database-fast.ckqboenmhdca.us-east-1.rds.amazonaws.com"
      DB_PORT="5432"
      DB_NAME="pipeline_management"
      DB_USER="postgres"
      DB_PASSWORD="Dashboard2025!$"
      ;;
    *)
      echo "Invalid choice. Please choose 1, 2, or 3."
      select_database
      return
      ;;
  esac
  # Write values to db.env (with quoting for special characters)
  cat > "$ENV_FILE" <<EOF
DB_HOST="$DB_HOST"
DB_PORT="$DB_PORT"
DB_NAME="$DB_NAME"
DB_USER="$DB_USER"
DB_PASSWORD="$DB_PASSWORD"
EOF
  # Export values for current shell
  export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
  echo "✅ Environment configured and exported (using AWS RDS dst-dashboard-fast)."
}

select_database

python alert_processor.py
