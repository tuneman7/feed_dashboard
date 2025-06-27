# Create the feed_management database
createdb feed_management

# Verify it was created
psql -l | grep feed_management