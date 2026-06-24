#!/bin/bash

# Fix git worktree paths for devcontainer usage
# Converts absolute paths to relative paths in both directions:
#   1. Worktree/.git      → ../.repo/worktrees/<name>
#   2. .repo/worktrees/<name>/gitdir → ../../../<name>/.git

set -e

if [ ! -f .git ] || [ -d .git ]; then
    echo "ℹ️  Regular git repository (not a worktree), nothing to fix."
    exit 0
fi

echo "🔧 Detected git worktree, fixing git directory references..."

# ── 1. Read current gitdir ────────────────────────────────────────────────────

GITDIR=$(sed 's/gitdir: //' .git)
WORKTREE_NAME=$(basename "$(pwd)")

echo "   Worktree name : $WORKTREE_NAME"
echo "   Current gitdir: $GITDIR"

# ── 2. Fix .git file (Worktree → Bare Repo) ──────────────────────────────────

EXPECTED_GITDIR="../.repo/worktrees/$WORKTREE_NAME"

if [ "$GITDIR" != "$EXPECTED_GITDIR" ]; then
    echo "📝 Fixing .git (absolute → relative)..."
    echo "gitdir: $EXPECTED_GITDIR" > .git
    echo "✅ .git updated: $EXPECTED_GITDIR"
else
    echo "✅ .git already correct."
fi

# ── 3. Fix gitdir back-reference (Bare Repo → Worktree) ──────────────────────
#
# Relative path is calculated from:
#   .repo/worktrees/<name>/gitdir
# to:
#   <name>/.git
#
# Both on host and in devcontainer the directory structure is:
#   <root>/
#     .repo/worktrees/<name>/gitdir   (3 levels deep)
#     <name>/.git
#
# So the relative path is always: ../../../<name>/.git

BACK_REF_FILE="../.repo/worktrees/$WORKTREE_NAME/gitdir"
EXPECTED_BACK_REF="../../../$WORKTREE_NAME/.git"

if [ ! -f "$BACK_REF_FILE" ]; then
    echo "⚠️  Back-reference file not found: $BACK_REF_FILE"
    echo "   Make sure the .repo mount is available."
else
    CURRENT_BACK_REF=$(cat "$BACK_REF_FILE")
    echo "   Current back-ref: $CURRENT_BACK_REF"

    if [ "$CURRENT_BACK_REF" != "$EXPECTED_BACK_REF" ]; then
        echo "📝 Fixing back-reference (absolute → relative)..."
        echo "$EXPECTED_BACK_REF" > "$BACK_REF_FILE"
        echo "✅ Back-reference updated: $BACK_REF_FILE → $EXPECTED_BACK_REF"
    else
        echo "✅ Back-reference already correct."
    fi
fi

# ── 4. Verify ─────────────────────────────────────────────────────────────────

echo ""
echo "🔍 Verifying git..."

if git status > /dev/null 2>&1; then
    echo "✅ Git is working correctly!"
    git worktree list
else
    echo "❌ Git commands not working. Current state:"
    echo "   .git contents  : $(cat .git)"
    echo "   back-ref       : $(cat "$BACK_REF_FILE" 2>/dev/null || echo 'not readable')"
    exit 1
fi
