#!/bin/bash

# Simple PostgreSQL setup - quick and dirty for development
# Creates postgres user with 'postgres' password and 'feed_management' database

echo "🔧 Setting up PostgreSQL for development..."

# Stop any existing postgres
sudo pkill postgres || true

# Install PostgreSQL
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    brew install postgresql || true
    brew services start postgresql
else
    # Linux
    sudo apt update
    sudo apt install -y postgresql postgresql-contrib
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
fi

sleep 3

# Create user and database (works on both macOS and Linux)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - create via current user
    createuser -s postgres 2>/dev/null || true
    psql -d postgres -c "ALTER USER postgres PASSWORD 'postgres';"
    createdb -O postgres feed_management 2>/dev/null || true
else
    # Linux - create via postgres user
    sudo -u postgres createuser -s postgres 2>/dev/null || true
    sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
    sudo -u postgres createdb -O postgres feed_management 2>/dev/null || true
    
    # Make it wide open - trust all local connections
    sudo sed -i 's/local   all             all                                     peer/local   all             all                                     trust/' /etc/postgresql/*/main/pg_hba.conf
    sudo sed -i 's/local   all             all                                     md5/local   all             all                                     trust/' /etc/postgresql/*/main/pg_hba.conf
    sudo systemctl restart postgresql
fi

echo "✅ Done! Use: host=localhost, user=postgres, password=postgres, db=feed_management"