#!/bin/sh
# Dependency-acquisition phase: network IS available here. Runs inside the
# sandbox image but *before* the no-network build step -- this container
# invocation is separate from build_and_audit.sh precisely so the network
# can be torn down (via --network none) for everything after this point.
set -eu

repo="$1"
commit="$2"

case "$repo" in
  https://*) ;;
  *) echo "refusing non-https repo URL: $repo" >&2; exit 1 ;;
esac

mkdir -p /workspace/src
cd /workspace/src
git init -q
git remote add origin "$repo"
git fetch --depth 1 origin "$commit"
git checkout -q FETCH_HEAD

if [ -f lean-toolchain ]; then
  # elan reads this file itself on `lake build`/`lean`, but resolving it
  # explicitly here, while network is still available, means the actual
  # build step never needs to reach out for a toolchain it doesn't already
  # have cached.
  elan toolchain install "$(cat lean-toolchain)" || true
fi

if [ -f lakefile.lean ] || [ -f lakefile.toml ]; then
  lake update || true
fi
