"""Tests for Calendar API endpoints."""

import pytest
from datetime import datetime, time
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
CONFIG_URL = "/api/v1/calendar/config"
EVENTS_URL = "/api/v1/calendar/events"
AVAILABILITY_URL = "/api/v1/calendar/availability"

USER = {"email": "calendar_user@example.com", "password": "secret123"}


@pytest.fixture
def auth_headers(client: TestClient):
    res = client.post(REGISTER_URL, json=USER)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestScheduleConfig:
    def test_create_config(self, client: TestClient, auth_headers):
        payload = {
            "timezone": "America/New_York",
            "work_days": [0, 1, 2, 3, 4],
            "work_start_time": "09:00:00",
            "work_end_time": "17:00:00",
        }
        res = client.post(CONFIG_URL, json=payload, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["timezone"] == "America/New_York"
        assert data["work_days"] == [0, 1, 2, 3, 4]

    def test_get_config(self, client: TestClient, auth_headers):
        # First create
        payload = {"timezone": "UTC", "work_days": [0, 1, 2, 3, 4]}
        client.post(CONFIG_URL, json=payload, headers=auth_headers)

        res = client.get(CONFIG_URL, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["timezone"] == "UTC"

    def test_get_config_not_found(self, client: TestClient, auth_headers):
        res = client.get(CONFIG_URL, headers=auth_headers)
        assert res.status_code == 404

    def test_update_config(self, client: TestClient, auth_headers):
        # Create first
        client.post(
            CONFIG_URL,
            json={"timezone": "UTC", "work_days": [0, 1, 2, 3, 4]},
            headers=auth_headers,
        )

        # Update
        res = client.put(
            CONFIG_URL,
            json={"timezone": "America/Los_Angeles"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.json()["timezone"] == "America/Los_Angeles"

    def test_create_config_duplicate(self, client: TestClient, auth_headers):
        payload = {"timezone": "UTC", "work_days": [0, 1, 2, 3, 4]}
        client.post(CONFIG_URL, json=payload, headers=auth_headers)

        res = client.post(CONFIG_URL, json=payload, headers=auth_headers)
        assert res.status_code == 400

    def test_config_with_day_overrides(self, client: TestClient, auth_headers):
        payload = {
            "timezone": "UTC",
            "work_days": [0, 1, 2, 3, 4],
            "day_overrides": {"0": {"start": "08:00", "end": "16:00"}},
        }
        res = client.post(CONFIG_URL, json=payload, headers=auth_headers)
        assert res.status_code == 201
        assert res.json()["day_overrides"]["0"]["start"] == "08:00"


class TestCalendarEvents:
    def test_create_event(self, client: TestClient, auth_headers):
        payload = {
            "schedule_type": "blocked",
            "title": "Team Meeting",
            "start_datetime": "2026-03-12T10:00:00",
            "end_datetime": "2026-03-12T11:00:00",
            "timezone": "UTC",
        }
        res = client.post(EVENTS_URL, json=payload, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["title"] == "Team Meeting"
        assert data["schedule_type"] == "blocked"
        assert data["is_recurring"] is False

    def test_create_recurring_event(self, client: TestClient, auth_headers):
        payload = {
            "schedule_type": "blocked",
            "title": "Standup",
            "start_datetime": "2026-03-12T09:00:00",
            "end_datetime": "2026-03-12T09:30:00",
            "timezone": "America/New_York",
            "rrule": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
        }
        res = client.post(EVENTS_URL, json=payload, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["is_recurring"] is True
        assert data["rrule"] == "FREQ=WEEKLY;BYDAY=MO,WE,FR"

    def test_create_event_invalid_rrule(self, client: TestClient, auth_headers):
        payload = {
            "schedule_type": "blocked",
            "title": "Bad Event",
            "start_datetime": "2026-03-12T10:00:00",
            "end_datetime": "2026-03-12T11:00:00",
            "rrule": "INVALID=RRULE",
        }
        res = client.post(EVENTS_URL, json=payload, headers=auth_headers)
        assert res.status_code == 400

    def test_list_events(self, client: TestClient, auth_headers):
        # Create some events
        for i in range(3):
            client.post(
                EVENTS_URL,
                json={
                    "schedule_type": "personal",
                    "title": f"Event {i}",
                    "start_datetime": f"2026-03-{12+i}T10:00:00",
                    "end_datetime": f"2026-03-{12+i}T11:00:00",
                },
                headers=auth_headers,
            )

        res = client.get(
            EVENTS_URL,
            params={"start_date": "2026-03-01", "end_date": "2026-03-31"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert len(res.json()) == 3

    def test_list_events_invalid_range(self, client: TestClient, auth_headers):
        res = client.get(
            EVENTS_URL,
            params={"start_date": "2026-03-31", "end_date": "2026-03-01"},
            headers=auth_headers,
        )
        assert res.status_code == 400

    def test_get_event(self, client: TestClient, auth_headers):
        # Create event
        create_res = client.post(
            EVENTS_URL,
            json={
                "schedule_type": "blocked",
                "title": "Test Event",
                "start_datetime": "2026-03-12T10:00:00",
                "end_datetime": "2026-03-12T11:00:00",
            },
            headers=auth_headers,
        )
        event_id = create_res.json()["id"]

        res = client.get(f"{EVENTS_URL}/{event_id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["title"] == "Test Event"

    def test_update_event(self, client: TestClient, auth_headers):
        # Create event
        create_res = client.post(
            EVENTS_URL,
            json={
                "schedule_type": "blocked",
                "title": "Original Title",
                "start_datetime": "2026-03-12T10:00:00",
                "end_datetime": "2026-03-12T11:00:00",
            },
            headers=auth_headers,
        )
        event_id = create_res.json()["id"]

        res = client.put(
            f"{EVENTS_URL}/{event_id}",
            json={"title": "Updated Title"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.json()["title"] == "Updated Title"

    def test_delete_event(self, client: TestClient, auth_headers):
        # Create event
        create_res = client.post(
            EVENTS_URL,
            json={
                "schedule_type": "blocked",
                "title": "To Delete",
                "start_datetime": "2026-03-12T10:00:00",
                "end_datetime": "2026-03-12T11:00:00",
            },
            headers=auth_headers,
        )
        event_id = create_res.json()["id"]

        res = client.delete(f"{EVENTS_URL}/{event_id}", headers=auth_headers)
        assert res.status_code == 204

        # Verify deleted
        get_res = client.get(f"{EVENTS_URL}/{event_id}", headers=auth_headers)
        assert get_res.status_code == 404

    def test_skip_occurrence(self, client: TestClient, auth_headers):
        # Create recurring event
        create_res = client.post(
            EVENTS_URL,
            json={
                "schedule_type": "blocked",
                "title": "Recurring",
                "start_datetime": "2026-03-12T09:00:00",
                "end_datetime": "2026-03-12T09:30:00",
                "rrule": "FREQ=DAILY",
            },
            headers=auth_headers,
        )
        event_id = create_res.json()["id"]

        res = client.post(
            f"{EVENTS_URL}/{event_id}/skip/2026-03-15",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert "2026-03-15" in res.json()["exdates"]

    def test_skip_non_recurring_event(self, client: TestClient, auth_headers):
        # Create non-recurring event
        create_res = client.post(
            EVENTS_URL,
            json={
                "schedule_type": "blocked",
                "title": "One-time",
                "start_datetime": "2026-03-12T09:00:00",
                "end_datetime": "2026-03-12T09:30:00",
            },
            headers=auth_headers,
        )
        event_id = create_res.json()["id"]

        res = client.post(
            f"{EVENTS_URL}/{event_id}/skip/2026-03-15",
            headers=auth_headers,
        )
        assert res.status_code == 400


class TestAvailability:
    @pytest.fixture
    def setup_config(self, client: TestClient, auth_headers):
        client.post(
            CONFIG_URL,
            json={
                "timezone": "UTC",
                "work_days": [0, 1, 2, 3, 4],
                "work_start_time": "09:00:00",
                "work_end_time": "17:00:00",
            },
            headers=auth_headers,
        )

    def test_get_availability(self, client: TestClient, auth_headers, setup_config):
        res = client.get(
            AVAILABILITY_URL,
            params={"start_date": "2026-03-09", "end_date": "2026-03-13"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert "days" in data
        assert "summary" in data
        # 5 days from Mon-Fri
        assert len(data["days"]) == 5

    def test_get_availability_with_blocked_event(
        self, client: TestClient, auth_headers, setup_config
    ):
        # Create blocked event
        client.post(
            EVENTS_URL,
            json={
                "schedule_type": "blocked",
                "title": "Meeting",
                "start_datetime": "2026-03-09T10:00:00",
                "end_datetime": "2026-03-09T11:00:00",
            },
            headers=auth_headers,
        )

        res = client.get(
            AVAILABILITY_URL,
            params={"start_date": "2026-03-09", "end_date": "2026-03-09"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        day = res.json()["days"][0]
        assert len(day["busy_slots"]) == 1
        assert len(day["free_slots"]) == 2  # Before and after meeting

    def test_get_availability_summary(
        self, client: TestClient, auth_headers, setup_config
    ):
        res = client.get(
            f"{AVAILABILITY_URL}/summary",
            params={"start_date": "2026-03-09", "end_date": "2026-03-13"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert "work_days" in data
        assert "total_work_hours" in data
        assert "total_free_hours" in data
        assert data["work_days"] == 5
        # 8 hours * 5 days = 40 hours
        assert data["total_work_hours"] == 40.0

    def test_availability_invalid_range(self, client: TestClient, auth_headers):
        res = client.get(
            AVAILABILITY_URL,
            params={"start_date": "2026-03-31", "end_date": "2026-03-01"},
            headers=auth_headers,
        )
        assert res.status_code == 400


class TestUnauthenticated:
    def test_config_unauthenticated(self, client: TestClient):
        res = client.get(CONFIG_URL)
        assert res.status_code == 401

    def test_events_unauthenticated(self, client: TestClient):
        res = client.get(EVENTS_URL, params={"start_date": "2026-03-01", "end_date": "2026-03-31"})
        assert res.status_code == 401

    def test_availability_unauthenticated(self, client: TestClient):
        res = client.get(
            AVAILABILITY_URL,
            params={"start_date": "2026-03-01", "end_date": "2026-03-31"},
        )
        assert res.status_code == 401
