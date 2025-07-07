#!/bin/bash

# Simple script to copy entire current directory to another branch

# Check if branch name was provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <target-branch-name>"
    echo "Example: $0 feat/linux-ec2"
    exit 1
fi

TARGET_BRANCH=$1

# Get current branch name
CURRENT_BRANCH=$(git branch --show-current)

echo "Copying entire directory from '$CURRENT_BRANCH' to '$TARGET_BRANCH'"

# Switch to target branch
echo "Switching to $TARGET_BRANCH..."
git checkout $TARGET_BRANCH

# Copy everything from current branch (except .git directory)
echo "Copying all files from $CURRENT_BRANCH..."
git checkout $CURRENT_BRANCH -- .

# Add all changes
echo "Adding all files..."
git add .

# Commit the changes
echo "Committing changes..."
git commit -m "Copy entire directory from $CURRENT_BRANCH branch"

# Switch back to original branch
echo "Switching back to $CURRENT_BRANCH..."
git checkout $CURRENT_BRANCH

echo "Successfully copied entire directory to $TARGET_BRANCH branch!"
echo "To push changes: git checkout $TARGET_BRANCH && git push origin $TARGET_BRANCH"