#!/usr/bin/env bash
# Nightly snapshot of the vault: commits whatever changed under vault/
# under an automated message, then pushes. Meant to be run on a timer
# (see systemd/vault-autocommit.{service,timer}, or a cron entry — see
# the README in that folder for both). Safe to run with nothing to
# commit (no-ops).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

git add vault/

if git diff --cached --quiet; then
    echo "vault-autocommit: nothing changed, skipping."
    exit 0
fi

git commit --quiet -m "chore(vault): auto-commit $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push --quiet
echo "vault-autocommit: committed and pushed."
