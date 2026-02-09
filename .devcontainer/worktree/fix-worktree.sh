#!/bin/bash

# Fix git worktree paths for devcontainer usage
# This script converts absolute paths in .git to relative paths

if [ -f .git ] && [ ! -d .git ]; then
    # This is a worktree, .git is a file
    echo "🔧 Detected git worktree, fixing git directory reference..."
    
    # Read the current gitdir
    GITDIR=$(cat .git | sed 's/gitdir: //')
    
    # Check if it's an absolute path
    if [[ "$GITDIR" == /* ]]; then
        echo "📝 Found absolute path, converting to relative..."
        
        # Extract worktree name from gitdir
        WORKTREE_NAME=$(basename "$GITDIR")
        
        # Create relative path pointing to .repo
        RELATIVE_PATH="../.repo/.git/worktrees/$WORKTREE_NAME"
        
        # Update .git file
        echo "gitdir: $RELATIVE_PATH" > .git
        
        echo "✅ Updated .git to use relative path: $RELATIVE_PATH"
    else
        echo "✅ Path is already relative, nothing to fix."
    fi
else
    echo "ℹ️  Regular git repository (not a worktree), nothing to fix."
fi

# Verify git is working
if git status > /dev/null 2>&1; then
    echo "✅ Git is working correctly!"
else
    echo "❌ Warning: Git commands may not work properly. Please check your worktree setup."
fi