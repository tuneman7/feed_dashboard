# Create the pipeline_management database
createdb pipeline_management

# Verify it was created
psql -l | grep pipeline_management