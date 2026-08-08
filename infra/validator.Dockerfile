# syntax=docker/dockerfile:1.7

# Local Solana validator.
#
# Anza publishes Linux binaries for x86_64 only, so on an arm64 machine this
# image runs under QEMU emulation (see `platform:` in docker-compose.yml). It
# works, but a validator is CPU-bound and emulation costs real speed. If block
# production feels sluggish, run the validator natively instead — see
# "Running the validator natively" in the README.
FROM --platform=linux/amd64 debian:bookworm-slim

# Pinned to 2.3.x on purpose, even though the host runs Agave 3.1.5.
#
# Agave 3.x asserts io_uring_supported() at startup, and io_uring is not
# available inside Docker Desktop's VM when the binary runs under x86_64
# emulation — it panics with `assertion failed: io_uring_supported()` before the
# RPC comes up. 2.3.x has no such requirement and is still comfortably within
# what Anchor 1.x supports, so it is the newest version that actually runs here.
#
# If you switch the validator to run natively on the host (no emulation), 3.x
# works fine — that is what `pnpm chain:validator` uses.
ARG AGAVE_VERSION=v2.3.13

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl bzip2 libssl3 \
 && rm -rf /var/lib/apt/lists/*

RUN curl -sSfL \
      "https://github.com/anza-xyz/agave/releases/download/${AGAVE_VERSION}/solana-release-x86_64-unknown-linux-gnu.tar.bz2" \
    | tar -xj -C /opt \
 && /opt/solana-release/bin/solana --version

ENV PATH="/opt/solana-release/bin:${PATH}"

# The ledger lives on a named volume so a restart does not force a full replay.
WORKDIR /ledger

EXPOSE 8899 8900

COPY validator-entrypoint.sh /usr/local/bin/validator-entrypoint.sh
RUN chmod +x /usr/local/bin/validator-entrypoint.sh

HEALTHCHECK --interval=10s --timeout=5s --start-period=90s --retries=10 \
    CMD solana --url http://127.0.0.1:8899 cluster-version || exit 1

ENTRYPOINT ["/usr/local/bin/validator-entrypoint.sh"]
