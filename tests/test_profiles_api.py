"""Tests for /api/profiles CRUD endpoints."""

import unittest

from fastapi.testclient import TestClient


class ProfilesApiTests(unittest.TestCase):
    def setUp(self):
        from api.auth import get_current_user
        from api.main import app
        from api.services.profiles_store import get_profiles_store

        class StubProfilesStore:
            def __init__(self) -> None:
                self.records = {}
                self.counter = 0

            def create_profile(self, *, user_id, name, input_payload, is_meli=False):
                self.counter += 1
                profile_id = f"profile-{self.counter}"
                record = {
                    "profile_id": profile_id,
                    "name": name,
                    "input": input_payload,
                    "is_meli": is_meli,
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "user_id": user_id,
                }
                self.records[profile_id] = record
                return record.copy()

            def update_profile(self, *, profile_id, user_id, name=None, input_payload=None, is_meli=None):
                record = self.records.get(profile_id)
                if not record or record["user_id"] != user_id:
                    raise KeyError(profile_id)
                if name is not None:
                    record["name"] = name
                if input_payload is not None:
                    record["input"] = input_payload
                if is_meli is not None:
                    record["is_meli"] = is_meli
                record["updated_at"] = "2025-01-02T00:00:00Z"
                return record.copy()

            def delete_profile(self, *, profile_id, user_id):
                record = self.records.get(profile_id)
                if not record or record["user_id"] != user_id:
                    raise KeyError(profile_id)
                del self.records[profile_id]

            def get_profile(self, *, profile_id, user_id):
                record = self.records.get(profile_id)
                if not record or record["user_id"] != user_id:
                    raise KeyError(profile_id)
                return record.copy()

            def list_profiles(self, *, user_id):
                builtin = {
                    "profile_id": "meli-default",
                    "name": "MELI Default",
                    "input": {"subtitle_mode": "auto", "edit_preset": "standard_vertical"},
                    "is_meli": True,
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "user_id": user_id,
                }
                user_profiles = [
                    r.copy()
                    for r in self.records.values()
                    if r["user_id"] == user_id
                ]
                return [builtin] + user_profiles

            def get_meli_default(self):
                return {
                    "profile_id": "meli-default",
                    "name": "MELI Default",
                    "input": {"subtitle_mode": "auto", "edit_preset": "standard_vertical"},
                    "is_meli": True,
                }

        self.profiles_store = StubProfilesStore()
        app.dependency_overrides[get_current_user] = lambda: {
            "user_id": "user-123",
            "email": "profiles@test.local",
        }
        app.dependency_overrides[get_profiles_store] = lambda: self.profiles_store
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def test_list_profiles_includes_meli_default(self):
        response = self.client.get("/api/profiles")
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertGreaterEqual(len(items), 1)
        meli = next((p for p in items if p["profile_id"] == "meli-default"), None)
        self.assertIsNotNone(meli)
        self.assertTrue(meli["is_meli"])
        self.assertEqual(meli["name"], "MELI Default")

    def test_get_meli_default_profile(self):
        response = self.client.get("/api/profiles/meli-default")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["profile_id"], "meli-default")
        self.assertIn("input", body)

    def test_create_profile_returns_201(self):
        response = self.client.post(
            "/api/profiles",
            json={
                "name": "My Custom Profile",
                "input": {"geo": "MLB", "subtitle_mode": "auto"},
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], "My Custom Profile")
        self.assertEqual(body["input"]["geo"], "MLB")
        self.assertIn("profile_id", body)

    def test_create_profile_rejects_missing_name(self):
        response = self.client.post(
            "/api/profiles",
            json={"input": {"geo": "MLB"}},
        )
        self.assertEqual(response.status_code, 400)

    def test_update_profile(self):
        create_resp = self.client.post(
            "/api/profiles",
            json={"name": "Original", "input": {"geo": "MLA"}},
        )
        profile_id = create_resp.json()["profile_id"]

        response = self.client.put(
            f"/api/profiles/{profile_id}",
            json={"name": "Updated", "input": {"geo": "MLB"}},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], "Updated")
        self.assertEqual(body["input"]["geo"], "MLB")

    def test_update_meli_default_rejected(self):
        response = self.client.put(
            "/api/profiles/meli-default",
            json={"name": "Hacked"},
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_profile(self):
        create_resp = self.client.post(
            "/api/profiles",
            json={"name": "To Delete", "input": {}},
        )
        profile_id = create_resp.json()["profile_id"]

        response = self.client.delete(f"/api/profiles/{profile_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"], profile_id)

        get_resp = self.client.get(f"/api/profiles/{profile_id}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_meli_default_rejected(self):
        response = self.client.delete("/api/profiles/meli-default")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
