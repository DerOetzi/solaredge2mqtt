#!/usr/bin/env bash

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

git config core.hooksPath .githooks
npm install

echo "Git hooks configured to use .githooks"
echo "Node dependencies installed"