#!/bin/bash

# Exit immediately if any command fails
set -e

# Default version bump to patch
version_bump="patch"
echo "Defaulting to patch version bump"
# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --username) PYPI_USERNAME="$2"; shift ;;
        --password) PYPI_TOKEN="$2"; shift ;;
        --major) version_bump="major" ;;
        --minor) version_bump="minor" ;;
    esac
    shift
done

echo "Username: $PYPI_USERNAME"
echo "Password: $PYPI_TOKEN"

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
echo "Bumped version to $new_version"

# Build and publish
uv build
echo "Building with version $new_version"
uv publish --username $PYPI_USERNAME --password $PYPI_TOKEN

# Clean up dist directory
rm -rf dist
echo "Cleaned up dist directory"

echo "Build and publish process completed successfully with version $new_version"



