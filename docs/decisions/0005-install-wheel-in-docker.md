# 5. Install the wheel in Docker instead of freezing a version file and copying source

- **Status:** accepted
- **Date:** 2026-08-14

## Context

[0004](0004-drop-armv7-support.md) migrated the Docker build's dependency layer to uv: `uv sync
--frozen --no-install-project --extra forecast` installs everything `uv.lock` pins, reproducibly.
`--no-install-project` is deliberate there — it skips building/installing the project itself,
keeping the dependency layer independent of source changes so it stays cache-friendly across
commits.

That flag has a side effect nothing in 0004 addressed: `pyproject.toml` declares
`[tool.setuptools_scm] version_file = "solaredge2mqtt/_version.py"`, which only fires as part of an
actual build (`uv build`, `uv sync` of the project itself, `pip install .`). Because
`--no-install-project` never builds the project, `solaredge2mqtt/_version.py` never gets written,
and the final Docker stage had nothing to install from — it fell back to copying raw source
straight in (`COPY solaredge2mqtt/ ./solaredge2mqtt/`, `COPY pyproject.toml README.md LICENSE
./`).

`freeze_version.py` existed to paper over the missing version file: it called
`setuptools_scm.get_version(..., version_file=...)` directly, and `build_project.yml`'s
`build-docker` job ran it via `uv run --no-project --with 'setuptools-scm[toml]>=8' python
freeze_version.py` before the Docker build, requiring both a full-history (`fetch-depth: 0`)
checkout and its own `uv` install on the runner just to run one script.

Meanwhile `build-check` already runs `uv build` and uploads the resulting wheel as
`python-artifacts-3.13-${REF_NAME}` — a wheel that already contains a correct, git-resolved
`_version.py`, baked in as an ordinary side effect of a real build. `build-docker` never used it.

The raw source copy also had a quieter problem: `[tool.setuptools]` in `pyproject.toml` declares
`forecast.py`, `migrate_config.py` and `monitoring.py` as top-level `py-modules` backing the
`solaredge2mqtt-monitoring` and `solaredge2mqtt-migrate` console scripts. The `COPY
solaredge2mqtt/ ./solaredge2mqtt/` line never touched those root-level files, so the scripts were
silently broken inside the image — installed as entry points by nothing, since nothing installed
the project at all.

## Decision

Stop skipping the real build. `build-docker` downloads the wheel `build-check` already built and
installs it with `uv pip install --no-deps` on top of the dependencies synced from `uv.lock`, the
same two-layer pattern the sibling `learninghouse` repo's `docker/Dockerfile` already uses:

```dockerfile
COPY dist/*.whl /app/dist/
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv pip install --no-deps /app/dist/*.whl
```

`--no-deps` matters here: dependencies are already synced from `uv.lock` in the layer above, and
letting `uv pip install` resolve them again from the wheel's metadata would both duplicate work and
risk drifting from the lockfile's pins.

The final stage's two source-copy `COPY` lines are removed — the package now comes from the wheel
installed above, already inside `/venv`.

`.dockerignore` gets an explicit `!dist/*.whl` allow rule, ordered after the blanket `dist/` deny
line (Docker ignore-pattern order matters: later patterns override earlier ones), so the downloaded
wheel can reach the build context.

`build_project.yml`'s `build-docker` job replaces its "Generate static
solaredge2mqtt/_version.py" step with a "Download python artifacts" step, pulling
`python-artifacts-3.13-${{ env.REF_NAME }}` into `dist` via `actions/download-artifact` (pinned to
the same SHA already used for the digest download in `merge-manifest`, rather than inventing a new
pin). `build-docker` already depends on `build-check` (`needs: [variables, build-check]`), so the
artifact is guaranteed to exist by the time this step runs.

`freeze_version.py` and `tests/test_freeze_version.py` are deleted, not simplified further — there
is nothing left for them to do. `solaredge2mqtt/__init__.py`'s fallback comment is updated to
reflect that the git-query fallback now only matters for a genuinely unbuilt/uninstalled source
checkout (e.g. running straight from a clone without `uv sync`/`pip install .`); the fallback logic
itself is unchanged, since Docker installing a real wheel means it never hits that branch there.

## Consequence

`build-docker`'s `Checkout` step no longer needs `fetch-depth: 0` — that was only ever needed so
`freeze_version.py` could query git history directly on the runner. With that step gone, nothing
else in the job touches git history: the Dockerfile, `pyproject.toml`, `uv.lock` and
`docker-entrypoint.sh` are all present in an ordinary shallow checkout, and the image tags are
built from `env.VERSION`/`env.REF_NAME`, both computed once in the `variables` job from
`github.ref_name`, not from anything `build-docker` itself derives from git. Checked the rest of
the job's steps (metadata extraction, tag construction, digest export/upload, the
`docker/build-push-action` call) for anything else that might implicitly depend on tags or history
being present — nothing does. The step now defaults to a shallow checkout.

The job's own `astral-sh/setup-uv` "Install uv" step is removed too — it existed solely to run
`freeze_version.py` via `uv run --no-project --with 'setuptools-scm[toml]>=8' ...` on the runner.
Nothing else in `build-docker` invokes `uv` on the runner: the Dockerfile does its own `uv` install
inside the build (`COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv`), entirely
independent of the runner's toolchain.

As a side effect, `solaredge2mqtt-monitoring` and `solaredge2mqtt-migrate` become genuinely present
and installed inside the image for the first time — the wheel `uv build` produces includes
`forecast.py`, `migrate_config.py` and `monitoring.py` (the `py-modules` those console scripts are
built from), where the old source-copy silently omitted all three.
