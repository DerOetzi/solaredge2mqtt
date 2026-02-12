#!/bin/bash

# Worktree Management Script for solaredge2mqtt
# Self-contained version that can be downloaded standalone
#
# Standalone usage:
#   curl -O https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/main/scripts/manage-worktrees.sh
#   chmod +x manage-worktrees.sh
#   ./manage-worktrees.sh setup /path/to/project/directory

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

GITHUB_REPO="git@github.com:DerOetzi/solaredge2mqtt.git"
SCRIPT_NAME="manage-worktrees.sh"

# Save script paths at the very beginning
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================================
# OUTPUT FUNCTIONS (Single Responsibility: User Communication)
# ============================================================================

error() {
    echo -e "${RED}❌ ERROR: $1${NC}" >&2
    exit 1
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# ============================================================================
# PATH RESOLUTION (Single Responsibility: Path Management)
# ============================================================================

resolve_absolute_path() {
    local INPUT_PATH=$1
    
    # Expand tilde
    INPUT_PATH="${INPUT_PATH/#\~/$HOME}"
    
    if [ -d "$INPUT_PATH" ]; then
        echo "$(cd "$INPUT_PATH" && pwd)"
    elif [ -d "$(dirname "$INPUT_PATH")" ]; then
        echo "$(cd "$(dirname "$INPUT_PATH")" && pwd)/$(basename "$INPUT_PATH")"
    else
        echo "$INPUT_PATH"
    fi
}

detect_project_root() {
    info "Detect project root and .repo directory"

    # If already set and valid, return
    if [ -n "$PROJECT_ROOT" ] && [ -d "$PROJECT_ROOT/.repo" ]; then
        export REPO_DIR="$PROJECT_ROOT/.repo"
        return 0
    fi
    
    if [ -d "$SCRIPT_DIR/.repo" ]; then
        export PROJECT_ROOT="$SCRIPT_DIR"
        export REPO_DIR="$PROJECT_ROOT/.repo"
        return 0
    fi
    
    # Check current directory
    if [ -d ".repo" ]; then
        export PROJECT_ROOT="$(pwd)"
        export REPO_DIR="$PROJECT_ROOT/.repo"
        return 0
    fi
    
    # Check if script is in project (scripts/ or root)
    if [ -d "$SCRIPT_DIR/../.repo" ]; then
        export PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
        export REPO_DIR="$PROJECT_ROOT/.repo"
        return 0
    fi
    
    error "Cannot detect project root.\n\nPlease run from project directory or specify path"
}

check_repo_exists() {
    info "Check repo exists"
    [ -z "$PROJECT_ROOT" ] && error "Project root not set"
    [ ! -d "$REPO_DIR" ] && error ".repo directory not found at $REPO_DIR\n\nRun: $SCRIPT_NAME setup <directory>"
    return 0
}

# ============================================================================
# GIT OPERATIONS (Single Responsibility: Git Management)
# ============================================================================

configure_bare_repository() {
    cd "$REPO_DIR" || \
        error "Failed to change to repository directory: $REPO_DIR"
    
    local CURRENT_REFSPEC=$(git config --get remote.origin.fetch || \
        echo "")
    local DESIRED_REFSPEC="+refs/heads/*:refs/remotes/origin/*"
    
    [ "$CURRENT_REFSPEC" != "$DESIRED_REFSPEC" ] && \
        git config remote.origin.fetch "$DESIRED_REFSPEC"
    
    # Add PR fetch refspec to enable git pull in PR worktrees
    if ! git config --get-all remote.origin.fetch | \
        grep -qF '+refs/pull/*/head:'; then
        git config --add remote.origin.fetch \
            "+refs/pull/*/head:refs/remotes/origin/pr/*"
    fi
    
    git config fetch.prune true 2>/dev/null || true
    git config core.bare true 2>/dev/null || true
}

set_branch_upstream() {
    local BRANCH_NAME=$1
    local WORKTREE_PATH=$2
    local DESIRED_UPSTREAM=${3:-origin/$BRANCH_NAME}
    
    cd "$WORKTREE_PATH" || \
        error "Failed to change to worktree directory: \
$WORKTREE_PATH"
    
    # Check if the correct upstream is already set
    if git rev-parse --abbrev-ref --symbolic-full-name \
        @{u} &>/dev/null; then
        local CURRENT_UPSTREAM
        CURRENT_UPSTREAM=$(git rev-parse --abbrev-ref \
            --symbolic-full-name @{u})
        if [ "$CURRENT_UPSTREAM" = "$DESIRED_UPSTREAM" ]; then
            info "Upstream correctly set: $CURRENT_UPSTREAM"
            return 0
        else
            info "Updating upstream from $CURRENT_UPSTREAM to \
$DESIRED_UPSTREAM"
        fi
    fi
    
    # Verify the desired upstream exists
    if ! git show-ref --verify --quiet \
        "refs/remotes/$DESIRED_UPSTREAM"; then
        warning "Remote ref $DESIRED_UPSTREAM not found, \
skipping upstream configuration"
        return 1
    fi
    
    # Set or update the upstream
    if git branch --set-upstream-to="$DESIRED_UPSTREAM" \
        "$BRANCH_NAME" 2>/dev/null; then
        success "Upstream configured: $DESIRED_UPSTREAM"
        return 0
    else
        warning "Failed to set upstream to $DESIRED_UPSTREAM"
        return 1
    fi
}

convert_git_to_relative() {
    local WORKTREE_PATH=$1
    local GIT_FILE="$WORKTREE_PATH/.git"
    
    [ ! -f "$GIT_FILE" ] && return 0
    
    info "Converting .git to relative path..."
    echo "gitdir: ../.repo/worktrees/$(basename "$WORKTREE_PATH")" > "$GIT_FILE"
    success "Converted .git to relative path"
}

sanitize_branch_name() {
    echo "$1" | sed 's/\//-/g'
}

branch_exists_locally() {
    git show-ref --verify --quiet "refs/heads/$1"
}

branch_exists_remotely() {
    git show-ref --verify --quiet "refs/remotes/${2:-origin}/$1"
}

# ============================================================================
# WORKTREE OPERATIONS (Single Responsibility: Worktree Management)
# ============================================================================

create_worktree_from_existing_branch() {
    local BRANCH_NAME=$1
    local WORKTREE_NAME=$2
    
    info "Using existing local branch"
    git worktree add "../$WORKTREE_NAME" "$BRANCH_NAME"
}

create_worktree_from_remote() {
    local BRANCH_NAME=$1
    local WORKTREE_NAME=$2
    local REMOTE_REF=$3
    
    info "Creating local branch from $REMOTE_REF"
    git worktree add --track -b "$BRANCH_NAME" "../$WORKTREE_NAME" \
        "$REMOTE_REF"
    # Upstream configuration now handled centrally in create_worktree
}

create_new_worktree() {
    local BRANCH_NAME=$1
    local WORKTREE_NAME=$2
    
    info "Creating new branch"
    git worktree add -b "$BRANCH_NAME" "../$WORKTREE_NAME"
}

create_worktree() {
    local BRANCH_NAME=$1
    local WORKTREE_NAME=$2
    local REMOTE_REF=$3
    
    cd "$REPO_DIR"
    
    local WORKTREE_PATH="$PROJECT_ROOT/$WORKTREE_NAME"
    
    # Create the worktree using the appropriate method
    if branch_exists_locally "$BRANCH_NAME"; then
        create_worktree_from_existing_branch "$BRANCH_NAME" \
            "$WORKTREE_NAME"
    elif [ -n "$REMOTE_REF" ] && \
         branch_exists_remotely "$BRANCH_NAME" \
         "$(dirname "$REMOTE_REF")"; then
        create_worktree_from_remote "$BRANCH_NAME" "$WORKTREE_NAME" \
            "$REMOTE_REF"
    elif branch_exists_remotely "$BRANCH_NAME" "origin"; then
        create_worktree_from_remote "$BRANCH_NAME" "$WORKTREE_NAME" \
            "origin/$BRANCH_NAME"
    else
        create_new_worktree "$BRANCH_NAME" "$WORKTREE_NAME"
    fi
    
    # Always ensure upstream is configured after worktree creation
    # set_branch_upstream handles validation internally
    local DESIRED_UPSTREAM="${REMOTE_REF:-origin/$BRANCH_NAME}"
    set_branch_upstream "$BRANCH_NAME" "$WORKTREE_PATH" \
        "$DESIRED_UPSTREAM" || true
    
    convert_git_to_relative "$WORKTREE_PATH"
    success "Worktree created at: $WORKTREE_PATH"
    
    echo "$WORKTREE_PATH"
}

# ============================================================================
# SCRIPT INSTALLATION (Single Responsibility: Script Deployment)
# ============================================================================

install_script_to_project() {
    local TARGET_SCRIPT="$PROJECT_ROOT/$SCRIPT_NAME"
    local SOURCE_SCRIPT="$SCRIPT_PATH"
    
    [ "$SOURCE_SCRIPT" = "$TARGET_SCRIPT" ] && {
        info "Script is already in project root"
        return 0
    }
    
    if [[ "$SOURCE_SCRIPT" == *"/scripts/$SCRIPT_NAME" ]]; then
        cd "$PROJECT_ROOT"
        ln -sf "scripts/$SCRIPT_NAME" "$SCRIPT_NAME" 2>/dev/null || {
            cp "$SOURCE_SCRIPT" "$TARGET_SCRIPT"
            chmod +x "$TARGET_SCRIPT"
        }
    else
        cp "$SOURCE_SCRIPT" "$TARGET_SCRIPT"
        chmod +x "$TARGET_SCRIPT"
    fi
    
    success "Script available at: $TARGET_SCRIPT"
}

# ============================================================================
# CONFIGURATION MANAGEMENT (Single Responsibility: Config Setup)
# ============================================================================

copy_config_file() {
    local SOURCE_FILE=$1
    local TARGET_FILE=$2
    local FILE_NAME=$3
    
    if [ ! -f "$TARGET_FILE" ]; then
        if [ -f "$SOURCE_FILE" ]; then
            info "Creating $FILE_NAME from example..."
            if cp "$SOURCE_FILE" "$TARGET_FILE"; then
                success "Created $FILE_NAME"
                return 0
            else
                warning "Could not create $FILE_NAME"
                return 1
            fi
        else
            warning "$FILE_NAME.example not found in repository"
            return 1
        fi
    else
        info "$FILE_NAME already exists"
        return 2
    fi
}

setup_config_directory() {
    local SOURCE_WORKTREE=$1
    local CONFIG_DIR="$PROJECT_ROOT/config"
    local SOURCE_CONFIG_DIR="$SOURCE_WORKTREE/solaredge2mqtt/config"
    
    mkdir -p "$CONFIG_DIR"
    
    [ ! -d "$SOURCE_CONFIG_DIR" ] && {
        warning "Configuration directory not found: $SOURCE_CONFIG_DIR"
        return 1
    }
    
    info "Setting up configuration files..."
    echo ""
    
    local CREATED_FILES=()
    
    copy_config_file \
        "$SOURCE_CONFIG_DIR/configuration.yml.example" \
        "$CONFIG_DIR/configuration.yml" \
        "configuration.yml" && \
        CREATED_FILES+=("configuration.yml")
    
    copy_config_file \
        "$SOURCE_CONFIG_DIR/secrets.yml.example" \
        "$CONFIG_DIR/secrets.yml" \
        "secrets.yml" && \
        CREATED_FILES+=("secrets.yml")
    
    echo ""
    
    if [ ${#CREATED_FILES[@]} -gt 0 ]; then
        success "Configuration files ready!"
        echo ""
        warning "⚠️  IMPORTANT: Edit these files with your actual settings!"
        echo ""
        printf '  nano config/%s\n' "${CREATED_FILES[@]}"
    else
        success "Configuration files already exist"
    fi
    
    echo ""
}

# ============================================================================
# USER INTERACTION (Single Responsibility: User Prompts)
# ============================================================================

prompt_yes_no() {
    local PROMPT=$1
    local REPLY
    read -p "$PROMPT (y/N): " -n 1 -r REPLY
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

handle_existing_directory() {
    local DIR=$1
    local TYPE=$2
    
    if git worktree list 2>/dev/null | grep -q "$DIR"; then
        info "$TYPE already exists and is registered"
        return 1
    else
        warning "Directory '$DIR' exists but is not a worktree"
        if prompt_yes_no "Remove and recreate?"; then
            # Validate that DIR is within PROJECT_ROOT for safety
            local REAL_DIR
            local REAL_PROJECT_ROOT

            if ! REAL_DIR="$(cd "$DIR" 2>/dev/null && pwd -P)"; then
                error "Safety check failed: Cannot resolve directory '$DIR'"
            fi

            if ! REAL_PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd -P)"; then
                error "Safety check failed: Cannot resolve project root '$PROJECT_ROOT'"
            fi
            
            if [[ "$REAL_DIR" != "$REAL_PROJECT_ROOT"/* ]]; then
                error "Safety check failed: Directory is not within project root"
            fi
            
            rm -rf "$DIR"
            return 0
        else
            warning "Skipping $TYPE creation"
            return 1
        fi
    fi
}

# ============================================================================
# COMMANDS (Interface Segregation: Each command is independent)
# ============================================================================

cmd_setup() {
    local SETUP_DIR=$1
    
    [ -z "$SETUP_DIR" ] && error "Project directory required.\n\nUsage: $SCRIPT_NAME setup <directory>"
    
    export PROJECT_ROOT="$(resolve_absolute_path "$SETUP_DIR")"
    export REPO_DIR="$PROJECT_ROOT/.repo"
    
    if [ -d "$REPO_DIR" ]; then
        warning "Repository already exists at $REPO_DIR"
        echo ""
        prompt_yes_no "Reinitialize? (won't delete worktrees)" || {
            info "Setup cancelled."
            exit 0
        }
    fi
    
    echo "🔧 Setting up bare repository for worktree development..."
    echo "   Location: $PROJECT_ROOT"
    echo ""
    
    mkdir -p "$PROJECT_ROOT" "$REPO_DIR"
    cd "$REPO_DIR"
    
    if [ -d "objects" ]; then
        info "Repository already initialized, updating configuration..."
    else
        info "Cloning repository as bare..."
        git clone --bare "$GITHUB_REPO" .
    fi
    
    info "Configuring repository..."
    configure_bare_repository
    
    info "Fetching all branches..."
    git fetch origin
    
    success "Bare repository setup complete!"
    echo ""
    
    install_script_to_project
    echo ""
    
    info "Creating main worktree..."
    echo ""
    
    local MAIN_WORKTREE="$PROJECT_ROOT/main"
    
    if [ -d "$MAIN_WORKTREE" ]; then
        handle_existing_directory "$MAIN_WORKTREE" "Main worktree" && \
            create_worktree "main" "main" "origin/main"
    else
        create_worktree "main" "main" "origin/main"
    fi
    
    echo ""
    
    [ -d "$MAIN_WORKTREE" ] && setup_config_directory "$MAIN_WORKTREE" || {
        warning "Main worktree not available, skipping configuration setup"
        mkdir -p "$PROJECT_ROOT/config"
        echo ""
    }
    
    success "Setup complete! 🎉"
    echo ""
    info "Your structure:"
    echo "  $PROJECT_ROOT/"
    echo "  ├── .repo/            # Bare repository"
    echo "  ├── config/           # Shared configuration"
    echo "  ├── $SCRIPT_NAME      # This script"
    echo "  └── main/             # Main worktree"
    echo ""
    info "Next: cd $PROJECT_ROOT && code main"
    echo ""
    info "Commands: list, add <branch>, add-pr <number>, fetch, help"
}

cmd_add() {
    local BRANCH_NAME=$1
    local WORKTREE_NAME=$2
    
    [ -z "$BRANCH_NAME" ] && error "Branch name required"
    
    detect_project_root
    check_repo_exists
    configure_bare_repository
    
    [ -z "$WORKTREE_NAME" ] && WORKTREE_NAME=$(sanitize_branch_name "$BRANCH_NAME")
    
    local WORKTREE_PATH="$PROJECT_ROOT/$WORKTREE_NAME"
    [ -d "$WORKTREE_PATH" ] && error "Worktree already exists: $WORKTREE_PATH"
    
    echo "🚀 Creating worktree: $BRANCH_NAME → $WORKTREE_NAME"
    echo ""
    
    WORKTREE_PATH=$(create_worktree "$BRANCH_NAME" "$WORKTREE_NAME" "")
    
    echo ""
    info "Next: code $WORKTREE_PATH"
}

cmd_add_pr() {
    local PR_NUMBER=$1
    local WORKTREE_NAME=${2:-pr-$PR_NUMBER}
    
    [ -z "$PR_NUMBER" ] && error "PR number required"
    
    detect_project_root
    check_repo_exists
    configure_bare_repository
    
    cd "$REPO_DIR"
    
    local WORKTREE_PATH="$PROJECT_ROOT/$WORKTREE_NAME"
    [ -d "$WORKTREE_PATH" ] && error "Worktree already exists"
    
    echo "🚀 Creating worktree for PR #$PR_NUMBER"
    echo ""
    
    info "Fetching PR from GitHub..."
    local BRANCH_NAME="pr-$PR_NUMBER"
    
    # Fetch PR to both local branch and tracking ref in one operation
    git fetch origin \
        "pull/$PR_NUMBER/head:$BRANCH_NAME" \
        "refs/pull/$PR_NUMBER/head:refs/remotes/origin/pr/$PR_NUMBER"
    
    echo ""
    # Set upstream to origin/pr/$PR_NUMBER for git pull support
    WORKTREE_PATH=$(create_worktree "$BRANCH_NAME" "$WORKTREE_NAME" \
        "origin/pr/$PR_NUMBER")
    
    echo ""
    info "Next: code $WORKTREE_PATH"
}

cmd_remove() {
    local WORKTREE_NAME=$1
    
    [ -z "$WORKTREE_NAME" ] && error "Worktree name required"
    
    detect_project_root
    check_repo_exists
    
    cd "$REPO_DIR"
    
    local WORKTREE_PATH="$PROJECT_ROOT/$WORKTREE_NAME"
    
    if [ ! -d "$WORKTREE_PATH" ]; then
        warning "Worktree doesn't exist: $WORKTREE_PATH"
        info "Pruning stale entries..."
        git worktree prune
        exit 0
    fi
    
    echo "🗑️  Removing worktree: $WORKTREE_NAME"
    git worktree remove "../$WORKTREE_NAME"
    success "Worktree removed"
}

cmd_list() {
    detect_project_root
    check_repo_exists
    
    cd "$REPO_DIR"
    echo "📂 Current worktrees:"
    echo ""
    git worktree list || info "No worktrees found"
}

cmd_list_remote() {
    detect_project_root
    check_repo_exists
    configure_bare_repository
    
    cd "$REPO_DIR"
    echo "🌐 Remote branches:"
    echo ""
    
    # Cache worktree list once to avoid repeated calls
    local WORKTREE_LIST=$(git worktree list)
    local STATUS
    
    git branch -r --format='%(refname:short)' | sed 's/origin\///' | while read -r branch; do
        STATUS=""
        echo "$WORKTREE_LIST" | grep -q "\\[$branch\\]" && STATUS=" (checked out)"
        echo "  $branch$STATUS"
    done
}

cmd_fetch() {
    detect_project_root
    check_repo_exists
    configure_bare_repository
    
    cd "$REPO_DIR"
    echo "📥 Fetching updates..."
    git fetch origin --prune
    success "Fetch complete"
    echo ""
    info "Use '$SCRIPT_NAME list-remote' to see branches"
}

cmd_prune() {
    detect_project_root
    check_repo_exists
    
    cd "$REPO_DIR"
    echo "🧹 Pruning stale worktree entries..."
    git worktree prune -v
    success "Prune complete"
}

cmd_help() {
    cat << 'EOF'
Worktree Management Script for solaredge2mqtt

Manage git worktrees in a bare repository setup for parallel branch development.

SETUP:
  curl -O https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/main/scripts/manage-worktrees.sh
  chmod +x manage-worktrees.sh
  ./manage-worktrees.sh setup ~/projects/solaredge2mqtt

COMMANDS:
  setup <dir>              Setup bare repository
  add <branch> [name]      Create worktree from branch
  add-pr <number> [name]   Create worktree from GitHub PR
  remove <name>            Remove worktree
  list                     List all worktrees
  list-remote              List remote branches
  fetch                    Fetch updates
  prune                    Clean up stale entries
  help                     Show this help

STRUCTURE:
  ~/projects/solaredge2mqtt/
  ├── .repo/               # Bare repository
  ├── config/              # Shared configuration
  │   ├── configuration.yml
  │   └── secrets.yml
  ├── manage-worktrees.sh
  ├── main/                # Main branch worktree
  ├── feature-xyz/         # Feature worktree
  └── pr-298/              # PR worktree

BENEFITS:
  ✓ Multiple branches simultaneously
  ✓ No branch switching needed
  ✓ Shared configuration
  ✓ Portable with relative paths
  ✓ Easy PR reviews

See CONTRIBUTING.md for details.
EOF
}

# ============================================================================
# MAIN ROUTER (Dependency Inversion: Commands depend on abstractions)
# ============================================================================

# Route to command (detection happens in commands via detect_project_root)
case "${1:-help}" in
    setup)       cmd_setup "$2" ;;
    add)         cmd_add "$2" "$3" ;;
    add-pr)      cmd_add_pr "$2" "$3" ;;
    remove)      cmd_remove "$2" ;;
    list)        cmd_list ;;
    list-remote) cmd_list_remote ;;
    fetch)       cmd_fetch ;;
    prune)       cmd_prune ;;
    help|--help|-h) cmd_help ;;
    *)
        error "Unknown command: ${1}\n\nRun '$SCRIPT_NAME help' for usage"
        ;;
esac
