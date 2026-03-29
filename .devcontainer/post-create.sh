#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ "${1:-}" == "--fix-worktree" ]]; then
    .devcontainer/worktree/fix-worktree.sh
fi

python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev,forecast]

hook_choice="${SE2MQTT_SETUP_GIT_HOOKS:-ask}"

if [[ "$hook_choice" == "ask" ]]; then
    if [[ -r /dev/tty ]]; then
        printf "Configure recommended git pre-commit hooks now? [y/N] " > /dev/tty
        if read -r reply < /dev/tty; then
            case "$reply" in
                [Yy]|[Yy][Ee][Ss])
                    hook_choice="yes"
                    ;;
                *)
                    hook_choice="no"
                    ;;
            esac
        else
            hook_choice="no"
        fi
    else
        echo "Skipping optional git hook setup because no interactive terminal is available."
        echo "Run ./scripts/setup-git-hooks.sh later if you want to enable it."
        hook_choice="no"
    fi
fi

if [[ "$hook_choice" == "yes" ]]; then
    ./scripts/setup-git-hooks.sh
fi