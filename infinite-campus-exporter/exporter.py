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

assignment_assigned_date_timestamp = Gauge(
    "ic_assignment_assigned_date_timestamp_seconds",
    "Assignment assigned date as a Unix timestamp",
    ["student_id", "student_name", "course_name", "assignment_name"],
)

assignment_multiplier = Gauge(
    "ic_assignment_multiplier",
    "Assignment weight multiplier",
    ["student_id", "student_name", "course_name", "assignment_name"],
)

enrollment_info = Gauge(
    "ic_enrollment_info",
    "Student enrollment information (info metric, value is always 1)",
    ["student_id", "student_name", "grade", "school_name", "calendar_name", "service_type", "enrollment_type"],
)

school_year_start_timestamp = Gauge(
    "ic_school_year_start_timestamp_seconds",
    "School calendar year start date as a Unix timestamp",
    ["student_id", "student_name", "school_name", "calendar_name"],
)

school_year_end_timestamp = Gauge(
    "ic_school_year_end_timestamp_seconds",
    "School calendar year end date as a Unix timestamp",
    ["student_id", "student_name", "school_name", "calendar_name"],
)

course_info = Gauge(
    "ic_course_info",
    "Course information (info metric, value is always 1)",
    ["student_id", "student_name", "course_name", "course_number", "teacher", "room", "school_name"],
)

course_placement_info = Gauge(
    "ic_course_placement_info",
    "Course placement/schedule info per period and term (info metric, value is always 1)",
    ["student_id", "student_name", "course_name", "period_name", "term_name", "teacher", "room", "start_time", "end_time"],
)

term_start_timestamp = Gauge(
    "ic_term_start_timestamp_seconds",
    "Term start date as a Unix timestamp",
    ["term_name", "term_schedule_name", "is_primary"],
)

term_end_timestamp = Gauge(
    "ic_term_end_timestamp_seconds",
    "Term end date as a Unix timestamp",
    ["term_name", "term_schedule_name", "is_primary"],
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


def _parse_date_to_timestamp(date_str: str) -> float | None:
    """Parse a date string to a Unix timestamp, returning None on failure."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                continue
    return None


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

            terms = await ic.terms()
            _LOGGER.info("Found %d term(s)", len(terms))
            for term in terms:
                t_labels = {
                    "term_name": term.termname,
                    "term_schedule_name": term.termschedulename,
                    "is_primary": str(term.isprimary).lower(),
                }
                start_ts = _parse_date_to_timestamp(term.startdate)
                end_ts = _parse_date_to_timestamp(term.enddate)
                if start_ts is not None:
                    term_start_timestamp.labels(**t_labels).set(start_ts)
                if end_ts is not None:
                    term_end_timestamp.labels(**t_labels).set(end_ts)

            for student in students:
                student_id = str(student.personid)
                student_name = f"{student.firstname} {student.lastname}"

                for enrollment in student.enrollments:
                    enrollment_info.labels(
                        student_id=student_id,
                        student_name=student_name,
                        grade=enrollment.grade,
                        school_name=enrollment.schoolname,
                        calendar_name=enrollment.calendarname,
                        service_type=enrollment.servicetype,
                        enrollment_type="current",
                    ).set(1)
                    yr_labels = {
                        "student_id": student_id,
                        "student_name": student_name,
                        "school_name": enrollment.schoolname,
                        "calendar_name": enrollment.calendarname,
                    }
                    start_ts = _parse_date_to_timestamp(enrollment.calendarstartdate)
                    end_ts = _parse_date_to_timestamp(enrollment.calendarenddate)
                    if start_ts is not None:
                        school_year_start_timestamp.labels(**yr_labels).set(start_ts)
                    if end_ts is not None:
                        school_year_end_timestamp.labels(**yr_labels).set(end_ts)

                for enrollment in student.futureenrollments:
                    enrollment_info.labels(
                        student_id=student_id,
                        student_name=student_name,
                        grade=enrollment.grade,
                        school_name=enrollment.schoolname,
                        calendar_name=enrollment.calendarname,
                        service_type=enrollment.servicetype,
                        enrollment_type="future",
                    ).set(1)

                courses = await ic.courses(student.personid)
                _LOGGER.info("Student %s: %d course(s)", student_name, len(courses))
                for course in courses:
                    course_info.labels(
                        student_id=student_id,
                        student_name=student_name,
                        course_name=course.coursename,
                        course_number=course.coursenumber,
                        teacher=course.teacherdisplay or "",
                        room=course.roomname or "",
                        school_name=course.schoolname,
                    ).set(1)
                    for placement in course.sectionplacements:
                        course_placement_info.labels(
                            student_id=student_id,
                            student_name=student_name,
                            course_name=course.coursename,
                            period_name=placement.periodname,
                            term_name=placement.termname,
                            teacher=placement.teacherdisplay or "",
                            room=placement.roomname or "",
                            start_time=placement.starttime or "",
                            end_time=placement.endtime or "",
                        ).set(1)

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

                    if a.assigneddate:
                        assigned_ts = _parse_date_to_timestamp(a.assigneddate)
                        if assigned_ts is not None:
                            assignment_assigned_date_timestamp.labels(**labels).set(assigned_ts)

                    if a.multiplier is not None:
                        assignment_multiplier.labels(**labels).set(a.multiplier)

                    if a.duedate:
                        due_ts = _parse_date_to_timestamp(a.duedate)
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
