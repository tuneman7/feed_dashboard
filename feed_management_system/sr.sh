#!/bin/bash

source ./venv-bootstrap.sh

APP="streamlit_app.py"
LOG_FILE="streamlit.log"
PID_FILE=".streamlit_pid"
ENV_FILE="db.env"

select_database() {
  echo "Select database to connect to:"
  echo "1) Local (.env-based)"
  echo "2) AWS RDS (dst-pipeline-dashboard)"
  echo "3) AWS RDS (dst-dashboard-fast)"
  read -rp "Enter choice [1-3]: " choice

  case "$choice" in
    1)
      DB_HOST="localhost"
      DB_PORT="5432"
      DB_NAME="feed_management"
      DB_USER="$USER"
      DB_PASSWORD=""
      ;;
    2)
      DB_HOST="dst-pipeline-dashboard.ckqboenmhdca.us-east-1.rds.amazonaws.com"
      DB_PORT="5432"
      DB_NAME="feed_management"
      DB_USER="postgres"
      DB_PASSWORD="Dashboard2025!$"
      ;;
    3)
               
      DB_HOST="dst-dashboard-database-fast.ckqboenmhdca.us-east-1.rds.amazonaws.com"
      DB_PORT="5432"
      DB_NAME="feed_management"
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

  echo "✅ Environment configured and exported."
}

start_streamlit() {
  echo "🚀 Starting Streamlit..."
  nohup streamlit run "$APP" > "$LOG_FILE" 2>&1 &
  PID=$!
  echo $PID > "$PID_FILE"
  echo "✅ Streamlit started with PID $PID"
  tail -f "$LOG_FILE" &
  TAIL_PID=$!
}

kill_streamlit() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "🛑 Killing Streamlit process $PID"
      kill "$PID"
    fi
    rm -f "$PID_FILE"
  fi
  if [ -n "$TAIL_PID" ]; then
    kill "$TAIL_PID" 2>/dev/null
  fi
}

# Prompt DB config & always export fresh
select_database

# Start Streamlit and tail log
start_streamlit

# Interactive control loop
while true; do
  echo -n "[K]ill / [R]estart / [Q]uit: "
  read -r action
  case "$action" in
    [Kk])
      kill_streamlit
      echo "✅ Streamlit stopped."
      break
      ;;
    [Rr])
      kill_streamlit
      select_database
      start_streamlit
      ;;
    [Qq])
      echo "👋 Goodbye."
      break
      ;;
    *)
      echo "Invalid option. Please choose K, R, or Q."
      ;;
  esac
done
