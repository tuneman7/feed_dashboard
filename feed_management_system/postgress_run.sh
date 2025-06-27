DB_HOST=localhost
DB_PORT=5432
DB_NAME=feed_management
DB_USER=your_username
DB_PASSWORD=your_password

# Start PostgreSQL service
brew services start postgresql

# Check if it's running
brew services list | grep postgresql

# Check if PostgreSQL is listening on port 5432
lsof -i :5432

# Or check processes
ps aux | grep postgres
