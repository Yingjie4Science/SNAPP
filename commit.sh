#!/usr/bin/env bash
# Stage, commit, and push SNAPP changes to GitHub — safely.
#
# Usage:
#   bash commit.sh "your commit message"      # commit + push to origin/<branch>
#   bash commit.sh "msg" --no-push            # commit only, don't push
#   bash commit.sh                            # uses a dated default message
#
# Safeguards:
#   - refuses to commit .env or anything under data/ (secrets / big files),
#   - clears the stale .git/index.lock that Google Drive sync sometimes leaves,
#   - relies on .gitignore (data/, .env, caches) but double-checks anyway,
#   - no-ops cleanly when there is nothing to commit.

set -euo pipefail
cd "$(dirname "$0")"

MSG="${1:-SNAPP update $(date '+%Y-%m-%d %H:%M')}"
PUSH=1
for a in "$@"; do [ "$a" = "--no-push" ] && PUSH=0; done

# Google Drive occasionally leaves a stale lock; clear it so git can proceed.
[ -f .git/index.lock ] && { echo "Clearing stale .git/index.lock"; rm -f .git/index.lock; }

# Stage everything not excluded by .gitignore.
git add -A

# --- Safety guards -------------------------------------------------------
STAGED=$(git diff --cached --name-only)

if echo "$STAGED" | grep -qE '(^|/)\.env$'; then
    echo "ABORT: .env is staged — that file holds secrets and must not be pushed."
    echo "       Run: git reset  (then check your .gitignore)."
    exit 1
fi
if echo "$STAGED" | grep -qE '^data/'; then
    echo "ABORT: files under data/ are staged — datasets should not go to GitHub."
    echo "       Offending paths:"; echo "$STAGED" | grep -E '^data/' | sed 's/^/         /'
    echo "       Run: git reset  (then confirm data/ is in .gitignore)."
    exit 1
fi

# Nothing to commit?
if git diff --cached --quiet; then
    echo "Nothing to commit — working tree clean."
    exit 0
fi

echo "== Files to be committed =="
git status --short
echo "== Commit message =="
echo "  $MSG"

git commit -m "$MSG"

if [ "$PUSH" -eq 1 ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    echo "Pushing to origin/$BRANCH ..."
    git push origin "$BRANCH"
    echo "Done — pushed to origin/$BRANCH."
else
    echo "Committed locally (--no-push). Run 'git push' when ready."
fi
