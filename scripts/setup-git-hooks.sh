#!/usr/bin/env bash

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

git config core.hooksPath .githooks

echo "Check ruff"
ruff check

echo "Check pyright"
pyright

echo "Git hooks configured to use .githooks"
