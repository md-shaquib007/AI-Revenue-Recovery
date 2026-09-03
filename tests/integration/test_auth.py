import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.auth import require_operator
from apps.api.main import app


@pytest.mark.asyncio
async def test_ops_returns_401_when_auth_required(monkeypatch):
    from apps.api.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "auth_required", True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/ops/cases/missing/decision",
            json={"action": "DISMISS", "operator_notes": "nope"},
        )
        assert resp.status_code == 401
    monkeypatch.setattr(settings, "auth_required", False)


@pytest.mark.asyncio
async def test_login_and_me_roundtrip():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["username"] == "ops"


@pytest.mark.asyncio
async def test_change_password_roundtrip():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Invalid current password
        bad_change = await client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "wrong-password", "new_password": "new-secure-pass-2026"},
            headers=headers,
        )
        assert bad_change.status_code == 400

        # Valid password change
        change = await client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "revive-ops-2026", "new_password": "new-secure-pass-2026"},
            headers=headers,
        )
        assert change.status_code == 200
        assert change.json()["status"] == "SUCCESS"

        # Reset password back
        reset_change = await client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "new-secure-pass-2026", "new_password": "revive-ops-2026"},
            headers=headers,
        )
        assert reset_change.status_code == 200


@pytest.mark.asyncio
async def test_all_five_rbac_roles_login_and_scopes():
    """Validates that all 5 least-privilege enterprise RBAC roles can log in and receive their scopes."""
    roles_to_test = [
        ("ops", "revive-ops-2026", "admin"),
        ("admin", "revive-ops-2026", "admin"),
        ("risk_admin", "revive-risk-2026", "risk_admin"),
        ("operator", "revive-op-2026", "operator"),
        ("auditor", "revive-audit-2026", "auditor"),
        ("viewer", "revive-view-2026", "viewer"),
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for username, password, expected_role in roles_to_test:
            res = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
            assert res.status_code == 200
            data = res.json()
            assert data["username"] == username
            assert data["role"] == expected_role
            assert "access_token" in data

            # Verify /me endpoint returns exact role
            me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
            assert me_res.status_code == 200
            assert me_res.json()["role"] == expected_role
