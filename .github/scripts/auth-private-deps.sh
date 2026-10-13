#!/usr/bin/env bash
# Give CI read access to this project's private git dependencies.
#
# Usage: auth-private-deps.sh <repo-name> [<repo-name> ...]
#
# Each named repository must have a matching Actions secret holding a
# read-only deploy key, named DEPLOY_KEY_<REPO_NAME_UPPER_SNAKE>, e.g.
# hypercubian-qa-platinum-standards -> DEPLOY_KEY_HYPERCUBIAN_QA_PLATINUM_STANDARDS.
#
# Why a key per dependency rather than one key for everything: a GitHub
# deploy key can only ever be attached to a single repository, so a
# project depending on two private repos genuinely needs two keys. ssh
# cannot pick between them by URL alone, so each gets a Host alias and
# the https URL is rewritten to that alias.
set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "::error::No dependency repositories given."
    exit 1
fi

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"
ssh-keyscan -t ed25519,rsa github.com >> "${HOME}/.ssh/known_hosts" 2>/dev/null || true

for repo in "$@"; do
    var="DEPLOY_KEY_$(printf '%s' "$repo" | tr 'a-z-' 'A-Z_')"
    key="${!var:-}"

    if [ -z "$key" ]; then
        echo "::error::${var} is not set, but ${repo} is a required dependency."
        echo "::error::Add the deploy key secret to this repository's Actions secrets."
        exit 1
    fi

    key_path="${HOME}/.ssh/dep_${repo}"
    printf '%s\n' "$key" > "$key_path"
    chmod 600 "$key_path"

    # A Host alias per dependency is what lets ssh choose the right key:
    # every URL is github.com, so only the alias distinguishes them.
    alias_host="${repo}.github.invalid"
    {
        printf 'Host %s\n' "$alias_host"
        printf '  HostName github.com\n'
        printf '  User git\n'
        printf '  IdentityFile %s\n' "$key_path"
        printf '  IdentitiesOnly yes\n'
        printf '  StrictHostKeyChecking accept-new\n'
    } >> "${HOME}/.ssh/config"

    git config --global \
        "url.git@${alias_host}:hypercubian/${repo}.git.insteadOf" \
        "https://github.com/hypercubian/${repo}.git"

    echo "Configured read-only access to ${repo}."
done

chmod 600 "${HOME}/.ssh/config"

# Poetry clones git dependencies with dulwich, a pure-Python git client
# that honours neither insteadOf nor ssh config. Without this it retries
# the original https URL anonymously and dies with a dulwich
# HangupException naming no cause. system-git-client makes Poetry shell
# out to the real git binary, which respects both.
echo 'POETRY_SYSTEM_GIT_CLIENT=true' >> "${GITHUB_ENV}"
echo "Poetry will use the system git client so the rewrites apply."
