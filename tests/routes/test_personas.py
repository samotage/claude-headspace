"""Route tests for persona registration API endpoint."""

import pytest

from claude_headspace.database import db


@pytest.fixture
def db_session(app):
    """Provide a database session with rollback isolation."""
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        db.drop_all()


class TestApiRegisterPersona:
    """Test POST /api/personas/register."""

    def test_success_returns_201(self, client, db_session):
        """Successful registration returns 201 with slug, id, path."""
        response = client.post(
            "/api/personas/register",
            json={"name": "Con", "role": "developer"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert "slug" in data
        assert "id" in data
        assert "path" in data
        assert data["slug"] == "developer-con-1"

    def test_with_description(self, client, db_session):
        """Registration with description succeeds."""
        response = client.post(
            "/api/personas/register",
            json={
                "name": "Con",
                "role": "developer",
                "description": "Backend Python developer",
            },
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["slug"] == "developer-con-1"

    def test_missing_name_returns_400(self, client, db_session):
        """Missing name returns 400 with error message."""
        response = client.post(
            "/api/personas/register",
            json={"role": "developer"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_empty_name_returns_400(self, client, db_session):
        """Empty name returns 400."""
        response = client.post(
            "/api/personas/register",
            json={"name": "", "role": "developer"},
        )

        assert response.status_code == 400

    def test_missing_role_returns_400(self, client, db_session):
        """Missing role returns 400."""
        response = client.post(
            "/api/personas/register",
            json={"name": "Con"},
        )

        assert response.status_code == 400

    def test_empty_body_returns_400(self, client, db_session):
        """Empty JSON body returns 400."""
        response = client.post(
            "/api/personas/register",
            json={},
        )

        assert response.status_code == 400

    def test_duplicate_creates_unique(self, client, db_session):
        """Calling twice with same data creates two personas with different slugs."""
        r1 = client.post(
            "/api/personas/register",
            json={"name": "Con", "role": "developer"},
        )
        r2 = client.post(
            "/api/personas/register",
            json={"name": "Con", "role": "developer"},
        )

        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.get_json()["slug"] != r2.get_json()["slug"]

    def test_json_response_format(self, client, db_session):
        """Response JSON has exactly the expected keys."""
        response = client.post(
            "/api/personas/register",
            json={"name": "Con", "role": "developer"},
        )

        data = response.get_json()
        assert set(data.keys()) == {"slug", "id", "path"}
        assert isinstance(data["slug"], str)
        assert isinstance(data["id"], int)
        assert isinstance(data["path"], str)
