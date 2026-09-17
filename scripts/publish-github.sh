#!/bin/sh
set -e
cd /Users/red/ai/z/mymind
git add README.md memory.md .gitignore
git status --porcelain
git commit -m "Initial MyMind project memory and README."
gh repo create mymind --private --source=. --remote=origin --push
git remote -v
gh repo view --web --json url -q .url
