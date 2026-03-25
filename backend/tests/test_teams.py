"""Integration tests for the teams API.

Tests team CRUD, membership management, and admin-only operations.
"""

import pytest
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
TEAMS_URL = "/api/v1/teams"

USER_A = {"email": "alice@example.com", "password": "secret123"}
USER_B = {"email": "bob@example.com", "password": "secret123"}
USER_C = {"email": "carol@example.com", "password": "secret123"}


@pytest.fixture
def headers_a(client: TestClient):
    res = client.post(REGISTER_URL, json=USER_A)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers_b(client: TestClient):
    res = client.post(REGISTER_URL, json=USER_B)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers_c(client: TestClient):
    res = client.post(REGISTER_URL, json=USER_C)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_b_id(client: TestClient, headers_b):
    """Register user B and return their UUID."""
    res = client.post(REGISTER_URL, json=USER_B)
    # Already registered via headers_b fixture — fetch via token decode
    # Simpler: create a goal and inspect scope_id, or just store from register response
    data = client.post(REGISTER_URL, json={"email": "bob2@example.com", "password": "x"})
    # Use headers_b to hit an endpoint that returns current user id
    # We'll extract it from the teams membership after creation
    return None  # resolved indirectly in tests


@pytest.fixture
def team(client: TestClient, headers_a):
    res = client.post(TEAMS_URL, json={"name": "Alpha Squad"}, headers=headers_a)
    assert res.status_code == 201
    return res.json()


# ─────────────────────────────────────────────────────────────────────────────
# Team CRUD
# ─────────────────────────────────────────────────────────────────────────────

def test_create_team(client: TestClient, headers_a):
    res = client.post(TEAMS_URL, json={"name": "Alpha Squad"}, headers=headers_a)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Alpha Squad"
    assert "id" in data


def test_create_team_creator_is_admin(client: TestClient, headers_a, team):
    members_res = client.get(f"{TEAMS_URL}/{team['id']}/members", headers=headers_a)
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) == 1
    assert members[0]["is_admin"] is True


def test_get_team(client: TestClient, headers_a, team):
    res = client.get(f"{TEAMS_URL}/{team['id']}", headers=headers_a)
    assert res.status_code == 200
    assert res.json()["name"] == "Alpha Squad"


def test_get_team_non_member_returns_404(client: TestClient, headers_b, team):
    res = client.get(f"{TEAMS_URL}/{team['id']}", headers=headers_b)
    assert res.status_code == 404


def test_list_user_teams_excludes_others_teams(client: TestClient, headers_a, headers_b, team):
    # B creates their own team
    client.post(TEAMS_URL, json={"name": "Beta Team"}, headers=headers_b)
    # A should only see Alpha Squad
    res = client.get(TEAMS_URL, headers=headers_a)
    assert res.status_code == 200
    names = [t["name"] for t in res.json()]
    assert "Alpha Squad" in names
    assert "Beta Team" not in names


def test_update_team_admin_only(client: TestClient, headers_a, headers_b, team):
    team_id = team["id"]
    # B is not a member — should get 404
    res = client.patch(f"{TEAMS_URL}/{team_id}", json={"name": "New Name"}, headers=headers_b)
    assert res.status_code == 404

    # A (admin) can update
    res = client.patch(f"{TEAMS_URL}/{team_id}", json={"name": "New Name"}, headers=headers_a)
    assert res.status_code == 200
    assert res.json()["name"] == "New Name"


def test_delete_team_admin_only(client: TestClient, headers_a, headers_b, team):
    team_id = team["id"]
    # B cannot delete
    res = client.delete(f"{TEAMS_URL}/{team_id}", headers=headers_b)
    assert res.status_code == 404

    # A (admin) can delete
    res = client.delete(f"{TEAMS_URL}/{team_id}", headers=headers_a)
    assert res.status_code == 204


# ─────────────────────────────────────────────────────────────────────────────
# Membership management
# ─────────────────────────────────────────────────────────────────────────────

def _get_user_id(client, headers):
    """Helper: get the current user's ID by creating and inspecting a goal."""
    goal_res = client.post("/api/v1/goals", json={"title": "_id_probe"}, headers=headers)
    return goal_res.json()["scope_id"]


def test_add_member(client: TestClient, headers_a, headers_b, team):
    b_id = _get_user_id(client, headers_b)
    team_id = team["id"]

    res = client.post(
        f"{TEAMS_URL}/{team_id}/members",
        json={"user_id": b_id, "is_admin": False},
        headers=headers_a,
    )
    assert res.status_code == 201
    assert res.json()["is_admin"] is False

    members = client.get(f"{TEAMS_URL}/{team_id}/members", headers=headers_a).json()
    user_ids = [m["user_id"] for m in members]
    assert b_id in user_ids


def test_add_member_non_admin_forbidden(client: TestClient, headers_a, headers_b, headers_c, team):
    # Add B as regular member first
    b_id = _get_user_id(client, headers_b)
    client.post(
        f"{TEAMS_URL}/{team['id']}/members",
        json={"user_id": b_id},
        headers=headers_a,
    )

    # B tries to add C — should be 403
    c_id = _get_user_id(client, headers_c)
    res = client.post(
        f"{TEAMS_URL}/{team['id']}/members",
        json={"user_id": c_id},
        headers=headers_b,
    )
    assert res.status_code == 403


def test_cannot_remove_last_admin(client: TestClient, headers_a, team):
    team_id = team["id"]
    # Get A's id
    a_id = _get_user_id(client, headers_a)

    res = client.delete(f"{TEAMS_URL}/{team_id}/members/{a_id}", headers=headers_a)
    assert res.status_code == 400


def test_remove_member(client: TestClient, headers_a, headers_b, team):
    b_id = _get_user_id(client, headers_b)
    team_id = team["id"]

    # Add B
    client.post(
        f"{TEAMS_URL}/{team_id}/members",
        json={"user_id": b_id},
        headers=headers_a,
    )

    # Remove B
    res = client.delete(f"{TEAMS_URL}/{team_id}/members/{b_id}", headers=headers_a)
    assert res.status_code == 204

    # B can no longer access the team
    res = client.get(f"{TEAMS_URL}/{team_id}", headers=headers_b)
    assert res.status_code == 404
