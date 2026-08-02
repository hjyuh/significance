# Sandbox image for the Lean evidence adapter's untrusted-build workflow.
#
# This image itself is only ever used with `docker run --network none` for
# the actual build+audit step (see lean-adapter-untrusted-build.yml); the
# network access this Dockerfile needs (apt, elan installer, Lean/Mathlib
# toolchain download) all happens at *image build time* / in the separate
# fetch step, before the no-network build step runs.
#
# KNOWN LIMITATION (see SECURITY.md): the base image below is pinned by
# tag, not by content digest, because this repository's automation does
# not currently have a mechanism to re-resolve and update a hardcoded
# digest pin over time. The workflow itself records the *resulting* image
# id/digest into the receipt after build (see the "Resolve and record the
# sandbox image digest" step), so what actually ran is always captured
# and auditable -- but the base layer is not reproducible byte-for-byte
# across rebuilds the way a digest pin would guarantee. Tightening this
# (e.g. with a periodic pin-refresh job) is future work.
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 \
    && rm -rf /var/lib/apt/lists/*

# elan is Lean's toolchain manager; it reads each project's own
# `lean-toolchain` file to resolve the exact Lean version to install, so
# we do not hardcode a Lean version here -- the submission pins its own
# toolchain, and elan enforces that pin.
RUN curl -fsSL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
      -o /tmp/elan-init.sh \
    && sh /tmp/elan-init.sh -y --default-toolchain none \
    && rm /tmp/elan-init.sh
ENV PATH="/root/.elan/bin:${PATH}"

# This alternate Elan home is populated during the networked acquisition
# phase and mounted read-only into the later no-network build container.
# It carries both the installed toolchain and Elan's settings; persisting
# only `toolchains/` makes Elan try to create settings under the read-only
# `/root`. The proxy binaries remain in /root/.elan/bin via PATH.
RUN mkdir -p /elan-home

COPY fetch.sh build_and_audit.sh /adapter/
RUN chmod +x /adapter/fetch.sh /adapter/build_and_audit.sh
