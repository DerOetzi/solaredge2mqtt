# 4. Migrate the Docker build to uv, and drop `arm/v7` support

- **Status:** accepted
- **Date:** 2026-08-12

## Context

The Docker build installs dependencies with pip from a generated
`requirements.txt` (`generate_requirements.py` flattens `pyproject.toml`'s
`dependencies` + `forecast` extra into it at CI time). This has two problems:

- **No transitive pinning.** `requirements.txt` only pins the top-level
  packages `pyproject.toml` names — everything transitive (`pydantic-core`,
  `aiohappyeyeballs`, scikit-learn's own dependency tree, and so on) resolves
  fresh on every build. The image is not actually reproducible, despite the
  Docker layer cache making it *look* stable build to build.
- **A second source of truth.** The project already maintains `uv.lock` (full
  transitive pins, used by dev tooling) alongside the hand-parsed
  `requirements.txt` the Docker image actually installs from.
  `generate_requirements.py` exists only to bridge that gap — it re-derives a
  subset of what `uv.lock` already knows, less precisely.

The fix is to point the Docker build at `uv.lock` directly — `uv sync
--frozen` — and delete `generate_requirements.py`/`requirements.txt` entirely.

That was blocked by `arm/v7`. uv ships official Docker images
(`ghcr.io/astral-sh/uv`) for `amd64`/`arm64` only, and `uv.lock` resolves
against plain PyPI wheels project-wide — there is no piwheels fallback path
for the one package (`aiocsv`) that has only ever had an `arm/v7` wheel on
piwheels, not PyPI. A uv-native Docker build and continued `arm/v7` support
are mutually exclusive as things stand. So the uv migration is the actual
goal of this decision; dropping `arm/v7` is what makes it possible.

## Why dropping `arm/v7` is also the right call on its own terms

`arm/v7` (32-bit ARM, `armhf`) has been a second-class platform for a while
already: the forecast service was excluded from it back in
[`2f66d73`](https://github.com/DerOetzi/solaredge2mqtt/commit/2f66d73)
(2025-07-29) because pvlearn's dependencies (scikit-learn, scipy) don't ship
usable `arm/v7` wheels, and `README.md` carried a note about it ever since.

- **Home Assistant dropped 32-bit entirely** with the 2025.12 release
  (announced [2025-05-22](https://www.home-assistant.io/blog/2025/05/22/deprecating-core-and-supervised-installation-methods-and-32-bit-systems/),
  citing under 1% adoption). This project's companion is a Home Assistant
  integration; a user still on 32-bit cannot run a current Home Assistant
  next to it either way.
- **`arm/v7` hardware mostly isn't 32-bit anymore.** Raspberry Pi 3 and up
  are ARMv8 boards; Raspberry Pi OS has installed the 64-bit (`arm64`)
  userland by default since Bookworm. The realistic remaining audience is Pi
  2 boards and old images on newer Pi hardware that were never reinstalled —
  not the hardware itself running out of options.
- **The dependency problem has gotten worse, not better.** Checked while
  updating pvlearn to 0.4.0: resolving `arm/v7` wheel-only against PyPI alone
  fails on a single package now — `aiocsv`. The `piwheels` extra index this
  repo has carried for years exists at this point to serve that one package.
- **No usage signal exists to weigh against this.** Docker Hub's API returns
  no pull counts per tag, and `last_pulled` timestamps update on every
  registry mirror/scanner hit regardless of real usage — even `2.3.1-armv7`
  from February shows a pull from last night. There is no way to tell real
  `arm/v7` deployments from index noise, so a deprecation cycle would not
  produce better information than deciding now.
- **It is a third of the build matrix and the slowest third.** `build-docker`
  ran `amd64`/`arm64`/`arm/v7` under QEMU emulation on `amd64` GitHub
  runners; `arm/v7` was consistently among the slower legs.

## Decision

**Hard drop `arm/v7`.** No deprecation release, no warning period. Releases
publish `amd64` and `arm64` images only; the multi-arch manifest (`latest`,
`:version`) stops including an `armv7` variant. Existing `*-armv7` tags on
Docker Hub and GHCR are not deleted — they remain pullable as a last
known-good snapshot, they simply stop receiving new versions.

**Migrate the Docker build to uv.** The build stage installs from `uv.lock`
directly via `uv sync --frozen --no-install-project --extra forecast`,
replacing `pip install -r requirements.txt`. `generate_requirements.py` and
`requirements.txt` generation are deleted, not merely simplified.

The alternative to the hard drop — a deprecation cycle with a warning release
— was rejected because there is no telemetry to time it against (see above),
and because the project has already signalled this for a year: the
forecast-service note has been in `README.md` since July 2025.

**Users still on `arm/v7` who need a newer version than the last published
`*-armv7` tag can build the image themselves.** The rest of this document is
that recipe: the exact Dockerfile, requirements split and CI logic this
project used for `arm/v7`, as of the last commit that had it —
[`f11e56d`](https://github.com/DerOetzi/solaredge2mqtt/commit/f11e56d) on the
`storedge` branch — preserved here so it survives independently of git
history or of anyone still remembering how the pieces fit together.

## Self-build recipe for `arm/v7`

This assumes building **natively on the target device** (a Raspberry Pi
running a 32-bit OS, or equivalent). That sidesteps the one part of the CI
setup that doesn't matter for a single local build: QEMU emulation and
multi-platform `buildx`. `docker build` on the device itself already produces
a native `arm/v7` image.

### 1. Get the source

```bash
git clone https://github.com/DerOetzi/solaredge2mqtt.git
cd solaredge2mqtt
git checkout <the tag or commit you want to build>
```

Newer commits have dropped `requirements-armv7.txt` generation, the
`Dockerfile`'s `TARGETARCH` branch, and eventually `requirements.txt`/
`generate_requirements.py` altogether (that is what this ADR documents the
removal of). If building past that point, recreate the files below from this
document before proceeding, or start from a commit that still has them.

### 2. `generate_requirements.py`, as it stood before removal

Regenerates `requirements.txt` (all dependencies plus the `forecast` extra)
and `requirements-armv7.txt` (base dependencies only — no `forecast`, since
pvlearn's ML dependencies don't build on this platform) from
`pyproject.toml`:

```python
#!/usr/bin/env python3
from pathlib import Path

import tomli


def main() -> None:
    pyproject = Path("pyproject.toml")
    with pyproject.open("rb") as f:
        data = tomli.load(f)

    project = data.get("project", {})
    dependencies = project.get("dependencies", [])
    optional = project.get("optional-dependencies", {})

    # requirements.txt: alle deps + forecast
    requirements_all = sorted(set(dependencies + optional.get("forecast", [])))

    # requirements-armv7.txt: nur deps
    requirements_arm = sorted(set(dependencies))

    Path("requirements.txt").write_text("\n".join(requirements_all) + "\n")
    Path("requirements-armv7.txt").write_text("\n".join(requirements_arm) + "\n")

    print("✅ requirements.txt und requirements-armv7.txt wurden generiert.")


if __name__ == "__main__":
    main()
```

Run it once before building:

```bash
pip install tomli
python3 generate_requirements.py
```

This produces `requirements-armv7.txt` — the base runtime dependencies,
**without** the forecast/ML stack. That absence is not a bug to work around:
scikit-learn and scipy do not have usable `arm/v7` wheels, and building them
from source under emulation is what made this platform expensive to support
in the first place. A self-built `arm/v7` image has no forecast service, same
as every `arm/v7` image this project ever published.

### 3. The `Dockerfile`, as it stood before removal

```dockerfile
FROM python:3.13-slim AS buildimage

ARG TARGETARCH

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

COPY requirements*.txt .

RUN set -eux && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m venv /venv && \
    . /venv/bin/activate && \
    pip install --upgrade pip && \
    if [ "$TARGETARCH" = "arm" ]; then \
    pip install \
    --prefer-binary \
    --no-cache-dir \
    --extra-index-url https://www.piwheels.org/simple \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements-armv7.txt; \
    else  \
    pip install \
    --prefer-binary \
    --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt; \
    fi 

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app

RUN set -eux && \
    apt-get update && \
    apt-get install -y --no-install-recommends gosu && \
    rm -rf /var/lib/apt/lists/* && \
    adduser --uid 1000 --disabled-password --gecos '' solaredge2mqtt && \
    mkdir -p /app/config /app/cache && \
    chown solaredge2mqtt:solaredge2mqtt /app/config /app/cache && \
    chmod 755 /app/config && \
    chmod 700 /app/cache

COPY --chown=root:solaredge2mqtt --chmod=755 --from=buildimage /venv /venv
COPY --chown=root:solaredge2mqtt --chmod=755 \
    solaredge2mqtt/ ./solaredge2mqtt/
COPY --chown=root:solaredge2mqtt --chmod=755 \
    pyproject.toml README.md LICENSE ./
COPY --chown=root:root --chmod=755 docker-entrypoint.sh /usr/local/bin/

VOLUME ["/app/config"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python3", "-m", "solaredge2mqtt"]
```

`TARGETARCH` is normally supplied by `buildx` during a multi-platform build.
Building natively with plain `docker build`, set it explicitly instead —
that's what selects the `requirements-armv7.txt` / `piwheels` branch:

```bash
docker build --build-arg TARGETARCH=arm -t solaredge2mqtt:armv7-self .
```

### 4. Run it

Same as any other image — see [DOCKER.md](../../DOCKER.md):

```bash
mkdir -p config
docker run -d --name solaredge2mqtt \
    -v $(pwd)/config:/app/config \
    -e "TZ=Europe/Berlin" \
    --restart unless-stopped \
    solaredge2mqtt:armv7-self
```

### 5. What CI did that a local build doesn't need

For completeness, `.github/workflows/build_project.yml`'s `build-docker` job
built `arm/v7` as one leg of a matrix (`arch: [amd64, arm64, arm/v7]`) on an
`amd64` GitHub runner, using QEMU emulation and `buildx` for the cross-build:

```yaml
- name: Set up QEMU
  uses: docker/setup-qemu-action@...
  with:
    platforms: linux/amd64,linux/arm64,linux/arm/v7

- name: Build and push Docker image
  uses: docker/build-push-action@...
  with:
    platforms: linux/${{ matrix.arch }}
    # ...
```

and `merge-manifest` stitched the three single-arch images
(`*-amd64`, `*-arm64`, `*-armv7`) into one multi-arch manifest with
`docker buildx imagetools create`. None of that is needed for a one-off local
build on real `arm/v7` hardware — `TARGETARCH=arm` on a plain `docker build`
reproduces the same image content without emulation or a matrix.

## Consequence

The `Dockerfile`'s build stage is rewritten around uv: `# syntax=docker/
dockerfile:1` at the top, the `uv` binary copied in from
`ghcr.io/astral-sh/uv:0.12.3` (`amd64`/`arm64` only — exactly what's left),
`COPY pyproject.toml uv.lock` as an early, cache-friendly layer, and `RUN
--mount=type=cache,target=/root/.cache/uv,sharing=locked uv sync --frozen
--no-install-project --extra forecast` in place of the old `pip install`.
`build-essential`/`gcc` are dropped entirely — every package in the resolved
dependency closure ships a `manylinux` wheel for both `x86_64` and `aarch64`
on cp313, so nothing ever needs to compile. The dead `--extra-index-url
https://download.pytorch.org/whl/cpu` (present since the `arm/v7` split was
introduced, never actually needed by anything in the dependency tree) is
dropped too. Stage 2, the final runtime image, is untouched — it never
depended on `requirements.txt` or pip, only on the `/venv` produced by stage
1.

On caching: the `--mount=type=cache` on `uv sync` speeds up local iterative
`docker build` runs, but GitHub Actions' `type=gha` layer cache (already
configured on `build-docker`, kept as-is) is what actually delivers "skip
reinstall when unrelated source files change" in CI — the same mechanism
`requirements.txt` relied on before, just keyed off `uv.lock` now via layer
ordering (dependencies installed before source is copied in). BuildKit
cache-mounts and GHA's layer cache are two different mechanisms; the former
isn't exported by `type=gha` without extra tooling
(`buildkit-cache-dance`), which isn't worth adding for a dependency closure
this size.

`generate_requirements.py` and `tests/test_generate_requirements.py` are
deleted, not simplified further — there is nothing left for them to do.
`.gitignore`'s `requirements.txt`/`requirements-armv7.txt` lines and
`MANIFEST.in`'s `include requirements.txt` are removed as dead weight.
`build_project.yml`'s `build-docker` job drops its "install tomli" and
"generate requirements" steps (keeping the `setuptools-scm` install, still
needed by `freeze_version.py`). `build-check`/`build-compat`'s pip cache key
— previously `hashFiles('**/requirements.txt')`, always empty since that file
never existed in those jobs — is fixed to `hashFiles('uv.lock')`, a real file
that changes exactly when dependencies do.

The result is a Docker image that is, for the first time, actually
reproducible: every transitive dependency comes from the same lock file the
project's own dev tooling is pinned against, not a fresh resolve on every
build.
