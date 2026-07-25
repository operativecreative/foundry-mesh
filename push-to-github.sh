#!/bin/bash
# Push Foundry Mesh to GitHub
# Run this from the project root

set -e

echo "Foundry Mesh — GitHub Push Helper"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: Run this script from the foundry-mesh project root"
    exit 1
fi

# Configure git if not already done
git config user.email "foundry@mesh.local" 2>/dev/null || true
git config user.name "Foundry Mesh" 2>/dev/null || true

# Set remote (using token from environment)
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: Set GITHUB_TOKEN environment variable"
    echo "  export GITHUB_TOKEN=ghp_..."
    exit 1
fi

git remote remove origin 2>/dev/null || true
git remote add origin "https://${GITHUB_TOKEN}@github.com/operativecreative/foundry-mesh.git"

# Ensure we're on main
git branch -m main 2>/dev/null || true

# Push
echo "Pushing to GitHub..."
git push -u origin main --force

# Clean remote URL (remove token)
git remote set-url origin "https://github.com/operativecreative/foundry-mesh.git"

echo ""
echo "✅ Pushed to https://github.com/operativecreative/foundry-mesh"
echo ""
echo "Next steps:"
echo "  1. Set up SSH keys for future pushes:"
echo "     ssh-keygen -t ed25519 -C 'your@email.com'"
echo "     cat ~/.ssh/id_ed25519.pub | pbcopy  # paste into GitHub Settings > SSH Keys"
echo "  2. Switch remote to SSH:"
echo "     git remote set-url origin git@github.com:operativecreative/foundry-mesh.git"
