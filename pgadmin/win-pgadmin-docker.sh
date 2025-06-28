#!/bin/bash

# Convert Git Bash path to Windows format
WIN_PWD="$(pwd -W 2>/dev/null)"  # -W gets the full Windows path like C:/Users/Name/project
if [[ -z "$WIN_PWD" ]]; then
  echo "This script must be run from Git Bash on Windows with a directory that maps to a Windows drive (e.g., /c/Users/...)."
  return 0 2>/dev/null || exit 0
fi

# Check if we're in a system-reserved folder (e.g., C:/Windows/System32)
if [[ "$WIN_PWD" =~ ^[A-Za-z]:/Windows/System32.* ]]; then
  echo "This directory is under C:/Windows/System32 and cannot be mounted into Docker."
  echo "Please move your project to somewhere like ~/projects and rerun this script."
  return 0 2>/dev/null || exit 0
fi

CONTAINER_NAME="pgadmin4"
PGADMIN_DIR="$WIN_PWD/.pgadmin"
PGADMIN_PORT=5050
EMAIL="admin@example.com"
PASSWORD="admin"

echo "[1/7] Stopping and removing any existing container named $CONTAINER_NAME..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker stop $CONTAINER_NAME > /dev/null 2>&1
    docker rm $CONTAINER_NAME > /dev/null 2>&1
fi

echo "[2/7] Ensuring pgAdmin data directory exists at $PGADMIN_DIR"
mkdir -p "$PGADMIN_DIR"

echo "[3/7] Pulling pgAdmin image if not already present..."
docker image inspect dpage/pgadmin4:latest > /dev/null 2>&1 || docker pull dpage/pgadmin4:latest

echo "[4/7] Starting container on port $PGADMIN_PORT..."
docker run -d \
  --name $CONTAINER_NAME \
  -p $PGADMIN_PORT:80 \
  -e PGADMIN_DEFAULT_EMAIL="$EMAIL" \
  -e PGADMIN_DEFAULT_PASSWORD="$PASSWORD" \
  -v "$PGADMIN_DIR":/var/lib/pgadmin \
  dpage/pgadmin4 > /dev/null

echo "[5/7] Waiting for pgAdmin to become available..."
RETRIES=15
until curl --silent --output /dev/null --head http://localhost:$PGADMIN_PORT; do
  ((RETRIES--))
  if [ $RETRIES -le 0 ]; then
    echo "pgAdmin did not start in time. Check docker logs with: docker logs $CONTAINER_NAME"
    return 0 2>/dev/null || exit 0
  fi
  sleep 1
done

echo "[6/7] pgAdmin is now running."

echo
echo "[7/7] Access pgAdmin at: http://localhost:$PGADMIN_PORT"
echo "Login with:"
echo "  Email   : $EMAIL"
echo "  Password: $PASSWORD"
echo
echo "To connect to your local PostgreSQL instance from inside pgAdmin, use:"
echo "  Host    : host.docker.internal"
echo "  Port    : 5432"
echo "  Username/Password: as configured in your PostgreSQL"
