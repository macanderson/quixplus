#!/bin/bash

# Exit immediately if any command fails
set -e

# Default version bump to patch
version_bump="patch"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --username) username="$2"; shift ;;
        --password) password="$2"; shift ;;
        --major) version_bump="major" ;;
        --minor) version_bump="minor" ;;
    esac
    shift
done

# Check if username and password were provided
if [[ -z "$username" || -z "$password" ]]; then
    echo "Error: --username and --password are required."
    exit 1
fi

# Function to bump version in pyproject.toml
bump_version() {
    current_version=$(grep -Eo 'version = "[0-9]+\.[0-9]+\.[0-9]+"' pyproject.toml | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+')
    IFS='.' read -r major minor patch <<< "$current_version"

    case $version_bump in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
    esac

    new_version="${major}.${minor}.${patch}"
    echo "Bumping version to $new_version"
    sed -i.bak -E "s/version = \"[0-9]+\.[0-9]+\.[0-9]+\"/version = \"$new_version\"/" pyproject.toml
    rm pyproject.toml.bak
}

# Bump the version
bump_version

# Build and publish
uv build
uv publish --username "$username" --password "$password"

# Clean up dist directory
rm -rf dist

echo "Build and publish process completed successfully with version $new_version"