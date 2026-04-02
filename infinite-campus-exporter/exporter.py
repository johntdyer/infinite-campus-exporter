"""Prometheus exporter for Infinite Campus Parent API."""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import aiohttp
from dotenv import load_dotenv
from ic_parent_api.infinitecampus import InfiniteCampus
from prometheus_client import Gauge, start_http_server

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_LOGGER = logging.getLogger(__name__)

# Remove default collectors to keep metrics clean (optional)
# REGISTRY.unregister(GC_COLLECTOR)
# REGISTRY.unregister(PLATFORM_COLLECTOR)
# REGISTRY.unregister(PROCESS_COLLECTOR)

# --- Metrics ---

assignment_score_percentage = Gauge(
    "ic_assignment_score_percentage",
    "Assignment score as a percentage",
    ["student_id", "student_name", "course_name", "assignment_name"],
)

assignment_score_points = Gauge(
    "ic_assignment_score_points",
    "Assignment score points earned",
    ["student_id", "student_name", "course_name", "assignment_name"],
)

assignment_total_points = Gauge(
    "ic_assignment_total_points",
    "Assignment total possible points",
    ["student_id", "student_name", "course_name", "assignment_name"],
)

assignment_flags = Gauge(
    "ic_assignment_flag",
    "Assignment status flags (late, missing, turned_in, incomplete, dropped)",
    ["student_id", "student_name", "course_name", "assignment_name", "flag"],
)

assignment_due_date_timestamp = Gauge(
    "ic_assignment_due_date_timestamp",
    "Assignment due date as a Unix timestamp",
    ["student_id", "student_name", "course_name", "assignment_name"],
)

assignment_count = Gauge(
    "ic_assignments_total",
    "Total number of assignments per student per course",
    ["student_id", "student_name", "course_name"],
)

scrape_duration = Gauge(
    "ic_scrape_duration_seconds",
    "Time taken to scrape Infinite Campus API",
)

scrape_success = Gauge(
    "ic_scrape_success",
    "Whether the last scrape succeeded (1) or failed (0)",
)

last_scrape_timestamp = Gauge(
    "ic_last_scrape_timestamp_seconds",
    "Unix timestamp of the last successful scrape",
)


async def collect_metrics(ic: InfiniteCampus) -> None:
    """Fetch data from Infinite Campus and update Prometheus metrics."""
    start = time.monotonic()
    try:
        async with aiohttp.ClientSession() as session:
            authenticated = await ic.authenticate(session)
            if not authenticated:
                _LOGGER.error("Authentication failed")
                scrape_success.set(0)
                return

            students = await ic.students()
            _LOGGER.info("Found %d student(s)", len(students))

            for student in students:
                student_id = str(student.personid)
                student_name = f"{student.firstname} {student.lastname}"

                assignments = await ic.assignments(student.personid)
                _LOGGER.info(
                    "Student %s: %d assignment(s)", student_name, len(assignments)
                )

                # Track per-course assignment counts
                course_counts: dict[str, int] = {}

                for a in assignments:
                    labels = {
                        "student_id": student_id,
                        "student_name": student_name,
                        "course_name": a.coursename,
                        "assignment_name": a.assignmentname,
                    }

                    if a.scorepercentage is not None:
                        try:
                            assignment_score_percentage.labels(**labels).set(
                                float(a.scorepercentage)
                            )
                        except ValueError:
                            pass

                    if a.scorepoints is not None:
                        try:
                            assignment_score_points.labels(**labels).set(
                                float(a.scorepoints)
                            )
                        except ValueError:
                            pass

                    if a.totalpoints is not None:
                        assignment_total_points.labels(**labels).set(a.totalpoints)

                    for flag in ("late", "missing", "turnedin", "incomplete", "dropped"):
                        val = getattr(a, flag, None)
                        if val is not None:
                            assignment_flags.labels(
                                **{**labels, "flag": flag}
                            ).set(1 if val else 0)

                    if a.duedate:
                        due_ts = None
                        try:
                            due_ts = datetime.fromisoformat(a.duedate).replace(
                                tzinfo=timezone.utc
                            ).timestamp()
                        except ValueError:
                            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
                                try:
                                    due_ts = datetime.strptime(a.duedate, fmt).replace(
                                        tzinfo=timezone.utc
                                    ).timestamp()
                                    break
                                except ValueError:
                                    continue
                        if due_ts is not None:
                            assignment_due_date_timestamp.labels(**labels).set(due_ts)
                        else:
                            _LOGGER.warning(
                                "Unrecognized due date format for %r: %r",
                                a.assignmentname,
                                a.duedate,
                            )

                    course_counts[a.coursename] = course_counts.get(a.coursename, 0) + 1

                for course_name, count in course_counts.items():
                    assignment_count.labels(
                        student_id=student_id,
                        student_name=student_name,
                        course_name=course_name,
                    ).set(count)

        scrape_success.set(1)
        last_scrape_timestamp.set(time.time())

    except Exception as exc:
        _LOGGER.exception("Error collecting metrics: %s", exc)
        scrape_success.set(0)
    finally:
        scrape_duration.set(time.monotonic() - start)


async def run_loop(ic: InfiniteCampus, interval: int) -> None:
    """Continuously collect metrics on a fixed interval."""
    while True:
        _LOGGER.info("Collecting metrics...")
        await collect_metrics(ic)
        _LOGGER.info("Sleeping %ds until next scrape", interval)
        await asyncio.sleep(interval)


def main() -> None:
    """Read configuration from environment and start the exporter."""
    base_url = os.environ["IC_BASE_URL"]
    username = os.environ["IC_USERNAME"]
    password = os.environ["IC_PASSWORD"]
    district = os.environ["IC_DISTRICT"]
    path = os.environ.get("IC_PATH")
    port = int(os.environ.get("IC_EXPORTER_PORT", "9877"))
    interval = int(os.environ.get("IC_SCRAPE_INTERVAL", "300"))

    ic = InfiniteCampus(
        base_url=base_url,
        username=username,
        secret=password,
        district=district,
        path=path,
    )

    _LOGGER.info("Starting Infinite Campus exporter on port %d", port)
    start_http_server(port)

    asyncio.run(run_loop(ic, interval))


if __name__ == "__main__":
    main()
