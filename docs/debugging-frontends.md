# Debugging Frontends

This guide summarizes the lightweight frontends available for local debugging and testing without relying on external LLM services.

## Overview

- **dryrun**
  - No network calls.
  - Prints the constructed prompt so you can copy it into another interface.
  - Vector service integration is disabled.
- **echo**
  - Mirrors the most recent user message back to the terminal.
  - Skips `AbstractFrontend.__init__()`, so vector-service hooks remain inactive.
  - Useful when you need deterministic output for quick CLI plumbing checks.
- **vectorecho**
  - Mirrors user input like `echo`, but it subclasses `AbstractFrontend` properly, enabling vector-service telemetry.
  - Every user and assistant message is persisted via `VectorServiceClient`, so `/message`, `/context`, and `/conversation/<id>/history` behave as they do with real LLM frontends.
  - Perfect for verifying retrieval prompts, Qdrant connectivity, or scripts such as `contrib/vector_service/dump_vector_store.py` without engaging a live model.

## Typical Workflows

1. **Smoke test the vector microservice**
   ```bash
   # ensure Qdrant and the FastAPI service are up first
   .venv/bin/python -m debgpt.cli \
     --frontend vectorecho \
     --vector_service_enabled \
     --vector_service_url http://127.0.0.1:8000 \
     --vector_service_top_k 3 \
     --quit \
     --ask "Vector echo sanity check."
   ```
   Afterwards inspect the stored messages:
   ```bash
   python3 contrib/vector_service/dump_vector_store.py --json
   ```

2. **Compare dry-run vs. vector-aware output**
   ```bash
   .venv/bin/python -m debgpt.cli --frontend dryrun --ask "Review this patch."
   .venv/bin/python -m debgpt.cli --frontend vectorecho --vector_service_enabled --ask "Review this patch."
   ```
   The first prints the prompt only; the second also records the interaction for retrieval experiments.

3. **Load-test retrieval prompts**
   ```bash
   for i in $(seq 1 10); do
     .venv/bin/python -m debgpt.cli \
       --frontend vectorecho \
       --vector_service_enabled \
       --vector_service_url http://127.0.0.1:8000 \
       --vector_service_top_k 5 \
       --quit \
       --ask "Iteration $i"
   done
   python3 contrib/vector_service/dump_vector_store.py --limit 20
   ```
   This verifies batching and retrieval quality without waiting on an LLM response.

## Tips

- Vector-aware frontends inherit the default system prompt and session UUID handling. Use `--vector_service_conversation_id` to align multiple runs with the same history.
- If you only need to inspect prompts without touching the vector service, prefer `dryrun` to keep the timeline clean.
- Combine `vectorecho` with `--vector_service_top_k` and logs from `/tmp/vector_service.log` to tune retrieval formatting before switching to a production frontend.
