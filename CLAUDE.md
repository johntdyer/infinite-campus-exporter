# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands assume the virtualenv is active. The Python app lives in `infinite-campus-exporter/`.

```bash
# Set up virtualenv (from project root)
make setup

# Run the exporter directly
cd infinite-campus-exporter && source .venv/bin/activate && python3 exporter.py

# Docker Compose (from project root)
make build   # build image
make up      # start all services
make logs    # tail logs
make down    # stop all services
```

## Architecture

This is a single-file Prometheus exporter (`infinite-campus-exporter/exporter.py`) that polls the Infinite Campus parent portal API on a fixed interval and exposes metrics via `prometheus_client`.

**Data flow:**
1. `main()` reads config from environment (loaded from `.env` via `python-dotenv`), starts the HTTP metrics server, then calls `asyncio.run(run_loop(...))`.
2. `run_loop()` calls `collect_metrics()` on every interval (default 300s).
3. `collect_metrics()` opens an `aiohttp` session, authenticates via `InfiniteCampus.authenticate()`, then fetches all students and their assignments. Metrics are updated in-place on the module-level `Gauge` objects.

**Key dependency — `ic-parent-api`:**
- `InfiniteCampus` (from `ic_parent_api.infinitecampus`) is the high-level client. It wraps `InfiniteCampusApiClient`.
- Model properties are **all lowercase** (e.g. `student.personid`, `student.firstname`, `assignment.coursename`, `assignment.scorepercentage`). The underlying Pydantic models use camelCase but the wrapper classes expose lowercase properties.
- `ic.assignments(student.personid)` returns `Assignment` objects with flag attributes: `late`, `missing`, `turnedin`, `incomplete`, `dropped`.

**Metrics are module-level globals** — all `Gauge` objects are instantiated at import time. Labels used: `student_id`, `student_name`, `course_name`, `assignment_name`, and `flag` (for `ic_assignment_flag`).

## Configuration

Credentials and settings live in `infinite-campus-exporter/.env` (see `.env.example` in the same folder). Required: `IC_BASE_URL`, `IC_USERNAME`, `IC_PASSWORD`, `IC_DISTRICT`. Optional: `IC_PATH`, `IC_EXPORTER_PORT` (default `9877`), `IC_SCRAPE_INTERVAL` (default `300`).

## Examples

`examples/` contains ready-to-use configs:
- `grafana_dashboard.json` — auto-provisioned by Docker Compose via `examples/grafana_provisioning/`
- `prometheus.yml` — scrape config for standalone Prometheus
- `alloy.config` — Grafana Alloy scrape + remote write config
