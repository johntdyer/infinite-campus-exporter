# Infinite Campus Prometheus Exporter

A Prometheus exporter that polls the [Infinite Campus](https://www.infinitecampus.com/) parent portal API and exposes student grades and assignment data as metrics. Includes a pre-built Grafana dashboard that highlights missing assignments at a glance.

---

## Features

- Tracks grades, scores, and assignment counts per student and course
- Flags assignments as **missing**, **late**, **incomplete**, **dropped**, or **turned in**
- One scrape covers all students associated with the parent account
- Configurable scrape interval (default: every 5 minutes)
- Pre-built Grafana dashboard with per-student views and missing assignment alerts

---

## Requirements

- Python 3.11+
- An Infinite Campus parent portal account
- Prometheus
- Grafana (optional, for the dashboard)

---

## Installation

```bash
git clone https://github.com/youruser/ic_campus_exporter.git
cd ic_campus_exporter/infinite-campus-exporter

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

Copy the example env file and fill in your credentials:

```bash
cp infinite-campus-exporter/.env.example infinite-campus-exporter/.env
```

`.env` fields:

| Variable | Required | Default | Description |
|---|---|---|---|
| `IC_BASE_URL` | yes | — | Base URL of your district's Infinite Campus instance (e.g. `https://ic.yourdistrict.edu`) |
| `IC_USERNAME` | yes | — | Parent portal username |
| `IC_PASSWORD` | yes | — | Parent portal password |
| `IC_DISTRICT` | yes | — | District identifier string |
| `IC_PATH` | no | — | Optional URL path prefix |
| `IC_EXPORTER_PORT` | no | `9877` | Port to expose the `/metrics` endpoint on |
| `IC_SCRAPE_INTERVAL` | no | `300` | Seconds between Infinite Campus API polls |

> **Note:** `.env` is listed in `.gitignore` and will not be committed.

---

## Running

### Locally

```bash
cd infinite-campus-exporter
source .venv/bin/activate
python3 exporter.py
```

Metrics are available at `http://localhost:9877/metrics`.

### Docker Compose (recommended)

Spins up the exporter, Prometheus, and Grafana together:

```bash
cp infinite-campus-exporter/.env.example infinite-campus-exporter/.env   # fill in your credentials
make up
```

Available `make` targets:

| Target | Description |
|---|---|
| `make setup` | Create virtualenv and install dependencies |
| `make build` | Build the Docker image |
| `make up` | Start all services |
| `make down` | Stop all services |
| `make restart` | Restart all services |
| `make logs` | Tail logs for all services |
| `make ps` | Show running services |

| Service | URL |
|---|---|
| Exporter metrics | http://localhost:9877/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / admin) |

The Grafana dashboard is provisioned automatically — no manual import needed.

### Docker (exporter only)

```bash
docker build -t ic-campus-exporter ./infinite-campus-exporter
docker run --env-file ./infinite-campus-exporter/.env -p 9877:9877 ic-campus-exporter
```

---

## Metrics Reference

### Assignment scores

| Metric | Labels | Description |
|---|---|---|
| `ic_assignment_score_percentage` | `student_id`, `student_name`, `course_name`, `assignment_name` | Score as a percentage (0–100) |
| `ic_assignment_score_points` | same | Points earned |
| `ic_assignment_total_points` | same | Total possible points |
| `ic_assignments_total` | `student_id`, `student_name`, `course_name` | Assignment count per course |

### Assignment flags

`ic_assignment_flag` — value is `1` (true) or `0` (false).

| `flag` label | Meaning |
|---|---|
| `missing` | Assignment is marked missing |
| `late` | Assignment was submitted late |
| `turnedin` | Assignment has been turned in |
| `incomplete` | Assignment is marked incomplete |
| `dropped` | Assignment has been dropped |

### Exporter health

| Metric | Description |
|---|---|
| `ic_scrape_success` | `1` if the last scrape succeeded, `0` if it failed |
| `ic_scrape_duration_seconds` | How long the last scrape took |
| `ic_last_scrape_timestamp_seconds` | Unix timestamp of the last successful scrape |

---

## Grafana Dashboard

A pre-built dashboard is included at `examples/grafana_dashboard.json`.

**To import:**

1. In Grafana, go to **Dashboards → Import**
2. Click **Upload JSON file** and select `examples/grafana_dashboard.json`
3. Select your Prometheus datasource
4. Use the **Student** dropdown at the top to switch between students

### Dashboard layout

**Alert strip** — four stat panels that immediately highlight problems:
- Missing Assignments (red when > 0)
- Late Assignments (orange when > 0)
- Overall Average Score (color-coded by grade threshold)
- Incomplete Assignments (orange when > 0)

**Average Score by Course** — horizontal bar chart, color-coded red → green by score.

**Missing Assignments Detail** — table showing only missing assignments with red row highlights.

**All Assignments** — full table with score %, points, and status columns. Missing cells display `MISSING` in red; late cells display `LATE` in orange.

---

## Prometheus Configuration

See `examples/prometheus.yml` for a minimal scrape config:

```yaml
scrape_configs:
  - job_name: ic_campus_exporter
    static_configs:
      - targets:
          - localhost:9877
```

## Grafana Alloy Configuration

See `examples/alloy.config` for an Alloy scrape config with remote write, including a commented-out Grafana Cloud variant.

---

## Project Structure

```
ic_campus_exporter/
├── docker-compose.yml
├── .gitignore
├── infinite-campus-exporter/
│   ├── exporter.py          # Main exporter
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example         # Configuration template
└── examples/
    ├── grafana_dashboard.json
    ├── prometheus.yml
    ├── alloy.config
    └── grafana_provisioning/
        ├── datasources/
        │   └── prometheus.yml
        └── dashboards/
            └── dashboard.yml
```

---

## License

MIT
