
# Project Progress Log

_Comprehensive record of the DebGPT vector-service integration workstream._

## 2025-11-08

- **Documentation polish**
  - Added pip/uv installation guidance to `README.md`, stressing use of a virtual environment before invoking `debgpt`.
  - Removed redundant instructions in the README tutorial so the latest context-reader guidance is single-sourced from the MapReduce section.
  - Documented a one-shot Debian installation path that installs the CLI, vector service, and Qdrant via `apt install`.

- **CI migration to Debian 13**
  - Switched `.github/workflows/build-debgpt.yml` to run inside a `debian:trixie` container instead of Ubuntu 24.04.
  - Installed the missing Debian packaging toolchain (`dpkg-dev`, `fakeroot`, etc.) directly in the container to unblock `dpkg-buildpackage`.
  - Noted follow-up: workflow still fails on the post-build artifact step because `/bin/sh` lacks `shopt`; need to replace the bashism.

- **Vector DB bootstrap helper**
  - Added `contrib/vector_service/setup_vectordb.sh` to add the upstream Qdrant APT repo, install the service, align `/etc/debgpt/vector-service.env`, and restart relevant systemd units.
  - Called out the script in the README’s one-shot install section for easier ops hand-off.

- **Manual Debian install validation**
  - Installed the generated `.deb` on a clean Debian 13 environment; CLI (`debgpt --help`) and vector-config TUI launched successfully.
  - Confirms packaging artifacts function end-to-end outside of CI.

- **GitHub Actions artifact follow-up**
  - Need to replace lingering `shopt` usage in `.github/workflows/build-debgpt.yml` so the post-build artifact copy works under POSIX `/bin/sh`.
  - Tracking the rerun once the bashism is removed to confirm the Debian packaging job completes end-to-end.

- **Progress tracking**
  - Updated this log to capture the build workflow change and keep stakeholders informed during the rerun window.

- **Stabilized HTTP retrieval stack**
  - Broadened reader Accept headers and added PDF handling to unblock network-dependent tests (`tests/test_reader.py`).
  - Ensured `pypdf` support so PDF fetches parse correctly during regression test runs.

- **Swapped Google scraping for Custom Search API**
  - Updated `debgpt/reader.py` and related defaults/fixtures to rely on Google Custom Search credentials.
  - Extended tests to mock API responses and validated the new flow with `pytest`.

- **Interactive configuration tooling**
  - Authored `contrib/vector_service/configure_env.py` to build `.env` files via prompts.
  - Ran the script twice (first attempt interrupted, second successful) to produce a working environment file.

- **Vector microservice validation**
  - Launched Qdrant via Docker Compose and uvicorn for the FastAPI app.
  - Executed `contrib/vector_service/test_suite.sh` against live endpoints (`/healthz`, `/message`, `/context`).
  - Captured logs and confirmed persistence into `messages.db`.

- **Runtime smoke tests**
  - Exercised DebGPT CLI and frontend pathways in preparation for full vector-enabled sessions.
  - Inspected `debgpt/cli.py` and `debgpt/frontend.py` to understand vector-client wiring before live runs.

- **Vector service operational scripts**
  - Created `contrib/vector_service/dump_vector_store.py`, a helper to inspect the SQLite-backed chat history (table or JSON output).

- **Lightweight debugging frontend**
  - Introduced `VectorEchoFrontend` (vector-aware echo frontend) in `debgpt/frontend.py`.
  - Updated CLI argument choices to expose `--frontend vectorecho` for local debugging.
  - Verified the new frontend persists messages to the vector service by inspecting `/conversation/<uuid>/history`.

- **Documentation updates**
  - Authored `docs/debugging-frontends.md` summarizing dryrun/echo/vectorecho workflows with typical usage patterns.
  - Linked the new guide from `README.md` for discoverability.

- **Context awareness notes**
  - Measured retrieval prompt footprint (~110–120 tokens per snippet) to guide `--vector_service_top_k` tuning, especially for high-context-window models.

This log captures the sequence of code, tooling, and validation tasks performed to bring DebGPT’s vector-service integration to a fully testable state.

## 2025-07-13

- **README link maintenance**
  - Corrected an internal anchor so navigation within `README.md` doesn’t break after recent section renames (`6a14224`).
  - Fixed backend section hyperlinks to point at the proper anchors and external references, keeping setup guidance accurate (`4a8e0c8`).
