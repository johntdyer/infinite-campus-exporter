"""Tests for the Infinite Campus Prometheus exporter."""

import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# Ensure the exporter module is importable from the tests directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import exporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_student(personid=1, firstname="Jane", lastname="Doe"):
    s = MagicMock()
    s.personid = personid
    s.firstname = firstname
    s.lastname = lastname
    return s


def make_assignment(
    coursename="Math",
    assignmentname="Homework 1",
    scorepercentage="95.0",
    scorepoints="19.0",
    totalpoints=20.0,
    late=False,
    missing=False,
    turnedin=True,
    incomplete=False,
    dropped=False,
):
    a = MagicMock()
    a.coursename = coursename
    a.assignmentname = assignmentname
    a.scorepercentage = scorepercentage
    a.scorepoints = scorepoints
    a.totalpoints = totalpoints
    a.late = late
    a.missing = missing
    a.turnedin = turnedin
    a.incomplete = incomplete
    a.dropped = dropped
    return a


def make_ic(authenticated=True, students=None, assignments=None):
    ic = MagicMock()
    ic.authenticate = AsyncMock(return_value=authenticated)
    ic.students = AsyncMock(return_value=students or [])
    ic.assignments = AsyncMock(return_value=assignments or [])
    return ic


def mock_session_ctx():
    """Return a mock aiohttp.ClientSession usable as an async context manager."""
    session = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_failure_sets_scrape_success_zero():
    ic = make_ic(authenticated=False)
    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set") as mock_set, \
         patch.object(exporter.scrape_duration, "set"):
        await exporter.collect_metrics(ic)
    mock_set.assert_called_with(0)


@pytest.mark.asyncio
async def test_auth_success_sets_scrape_success_one():
    ic = make_ic(authenticated=True, students=[make_student()])
    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set") as mock_set, \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"):
        await exporter.collect_metrics(ic)
    mock_set.assert_called_with(1)


# ---------------------------------------------------------------------------
# Score metrics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_percentage_is_set():
    student = make_student()
    assignment = make_assignment(scorepercentage="88.5")
    ic = make_ic(students=[student], assignments=[assignment])

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"), \
         patch.object(exporter.assignment_score_percentage, "labels") as mock_labels:
        mock_gauge = MagicMock()
        mock_labels.return_value = mock_gauge
        await exporter.collect_metrics(ic)

    mock_gauge.set.assert_called_once_with(88.5)


@pytest.mark.asyncio
async def test_score_points_is_set():
    student = make_student()
    assignment = make_assignment(scorepoints="17.0", totalpoints=20.0)
    ic = make_ic(students=[student], assignments=[assignment])

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"), \
         patch.object(exporter.assignment_score_points, "labels") as mock_labels:
        mock_gauge = MagicMock()
        mock_labels.return_value = mock_gauge
        await exporter.collect_metrics(ic)

    mock_gauge.set.assert_called_once_with(17.0)


@pytest.mark.asyncio
async def test_total_points_is_set():
    student = make_student()
    assignment = make_assignment(totalpoints=25.0)
    ic = make_ic(students=[student], assignments=[assignment])

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"), \
         patch.object(exporter.assignment_total_points, "labels") as mock_labels:
        mock_gauge = MagicMock()
        mock_labels.return_value = mock_gauge
        await exporter.collect_metrics(ic)

    mock_gauge.set.assert_called_once_with(25.0)


@pytest.mark.asyncio
async def test_non_numeric_score_does_not_raise():
    student = make_student()
    assignment = make_assignment(scorepercentage="N/A", scorepoints="—")
    ic = make_ic(students=[student], assignments=[assignment])

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"):
        # Should not raise
        await exporter.collect_metrics(ic)


@pytest.mark.asyncio
async def test_none_scores_are_skipped():
    student = make_student()
    assignment = make_assignment(scorepercentage=None, scorepoints=None, totalpoints=None)
    ic = make_ic(students=[student], assignments=[assignment])

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"), \
         patch.object(exporter.assignment_score_percentage, "labels") as mock_pct, \
         patch.object(exporter.assignment_score_points, "labels") as mock_pts, \
         patch.object(exporter.assignment_total_points, "labels") as mock_total:
        await exporter.collect_metrics(ic)

    mock_pct.assert_not_called()
    mock_pts.assert_not_called()
    mock_total.assert_not_called()


# ---------------------------------------------------------------------------
# Assignment flags
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_flag_is_set_to_one():
    student = make_student()
    assignment = make_assignment(missing=True, turnedin=False)
    ic = make_ic(students=[student], assignments=[assignment])

    flag_calls = {}

    def capture_labels(**kwargs):
        g = MagicMock()
        g.set = MagicMock(side_effect=lambda v: flag_calls.__setitem__(kwargs["flag"], v))
        return g

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"), \
         patch.object(exporter.assignment_flags, "labels", side_effect=capture_labels):
        await exporter.collect_metrics(ic)

    assert flag_calls.get("missing") == 1


@pytest.mark.asyncio
async def test_missing_flag_is_zero_when_not_missing():
    student = make_student()
    assignment = make_assignment(missing=False)
    ic = make_ic(students=[student], assignments=[assignment])

    flag_calls = {}

    def capture_labels(**kwargs):
        g = MagicMock()
        g.set = MagicMock(side_effect=lambda v: flag_calls.__setitem__(kwargs["flag"], v))
        return g

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"), \
         patch.object(exporter.assignment_flags, "labels", side_effect=capture_labels):
        await exporter.collect_metrics(ic)

    assert flag_calls.get("missing") == 0


@pytest.mark.asyncio
async def test_all_flags_are_recorded():
    student = make_student()
    assignment = make_assignment(late=True, missing=True, turnedin=False, incomplete=True, dropped=False)
    ic = make_ic(students=[student], assignments=[assignment])

    recorded_flags = set()

    def capture_labels(**kwargs):
        recorded_flags.add(kwargs["flag"])
        return MagicMock()

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"), \
         patch.object(exporter.assignment_flags, "labels", side_effect=capture_labels):
        await exporter.collect_metrics(ic)

    assert recorded_flags == {"late", "missing", "turnedin", "incomplete", "dropped"}


# ---------------------------------------------------------------------------
# Assignment count per course
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assignment_count_per_course():
    student = make_student()
    assignments = [
        make_assignment(coursename="Math", assignmentname="HW1"),
        make_assignment(coursename="Math", assignmentname="HW2"),
        make_assignment(coursename="English", assignmentname="Essay"),
    ]
    ic = make_ic(students=[student], assignments=assignments)

    counts = {}

    def capture_labels(**kwargs):
        g = MagicMock()
        g.set = MagicMock(side_effect=lambda v: counts.__setitem__(kwargs["course_name"], v))
        return g

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"), \
         patch.object(exporter.assignment_count, "labels", side_effect=capture_labels):
        await exporter.collect_metrics(ic)

    assert counts["Math"] == 2
    assert counts["English"] == 1


# ---------------------------------------------------------------------------
# Multiple students
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_students_are_scraped():
    students = [make_student(1, "Jane", "Doe"), make_student(2, "John", "Smith")]
    ic = MagicMock()
    ic.authenticate = AsyncMock(return_value=True)
    ic.students = AsyncMock(return_value=students)
    ic.assignments = AsyncMock(return_value=[])

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set"), \
         patch.object(exporter.last_scrape_timestamp, "set"):
        await exporter.collect_metrics(ic)

    assert ic.assignments.call_count == 2
    ic.assignments.assert_any_call(1)
    ic.assignments.assert_any_call(2)


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exception_sets_scrape_success_zero():
    ic = MagicMock()
    ic.authenticate = AsyncMock(side_effect=RuntimeError("network error"))

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set") as mock_set, \
         patch.object(exporter.scrape_duration, "set"):
        await exporter.collect_metrics(ic)

    mock_set.assert_called_with(0)


@pytest.mark.asyncio
async def test_scrape_duration_always_set():
    ic = make_ic(authenticated=False)

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx()), \
         patch.object(exporter.scrape_success, "set"), \
         patch.object(exporter.scrape_duration, "set") as mock_duration:
        await exporter.collect_metrics(ic)

    mock_duration.assert_called_once()
    assert mock_duration.call_args[0][0] >= 0
