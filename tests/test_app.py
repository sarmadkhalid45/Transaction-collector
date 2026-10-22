import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import create_app


class TransactionCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(db_path=Path(self.temp.name) / "test.sqlite3", admin_email="admin@example.test", admin_password="Admin-test-password-2026!")
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def register(self, email="person@example.test", password="Valid-test-password-2026!"):
        return self.client.post("/api/register", json={"email": email, "password": password, "consent": True})

    def auth(self, method, path, payload=None, extra_headers=None):
        token = self.client.get("/api/me").json()["csrf_token"]
        headers = {"X-CSRF-Token": token, **(extra_headers or {})}
        if method.upper() == "POST" and path == "/api/transactions":
            headers.setdefault("Idempotency-Key", str(uuid.uuid4()))
        return self.client.request(method.upper(), path, json=payload, headers=headers)

    def test_registration_requires_explicit_sheet_sharing_consent(self):
        response = self.client.post("/api/register", json={"email": "no@example.test", "password": "Valid-test-password-2026!", "consent": False})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/me").json()["authenticated"], False)

    def test_repeated_create_with_same_idempotency_key_returns_one_transaction(self):
        self.register()
        payload = {
            "transaction_date": "2026-10-21", "transaction_type": "income", "category": "Sales",
            "amount": "19.00", "currency": "USD", "payment_method": "Cash", "description": "Duplicate request fixture"
        }
        first = self.auth("post", "/api/transactions", payload, {"Idempotency-Key": "attempt-12345678"})
        second = self.auth("post", "/api/transactions", payload, {"Idempotency-Key": "attempt-12345678"})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(len(self.client.get("/api/transactions").json()["items"]), 1)

    def test_reusing_idempotency_key_with_different_data_is_rejected(self):
        self.register()
        payload = {
            "transaction_date": "2026-10-21", "transaction_type": "income", "category": "Sales",
            "amount": "19.00", "currency": "USD", "payment_method": "Cash", "description": "Original"
        }
        key = {"Idempotency-Key": "attempt-different-123"}
        self.auth("post", "/api/transactions", payload, key)
        payload["description"] = "Changed payload"
        response = self.auth("post", "/api/transactions", payload, key)
        self.assertEqual(response.status_code, 409)

    def test_user_can_create_and_only_see_own_transactions(self):
        self.assertEqual(self.register().status_code, 201)
        created = self.auth("post", "/api/transactions", {
            "transaction_date": "2026-10-21", "transaction_type": "income", "category": "Sales",
            "amount": "125.50", "currency": "USD", "payment_method": "Cash",
            "description": "Fictional test receipt", "reference_number": "REF-1"
        })
        self.assertEqual(created.status_code, 201, created.text)
        transaction_id = created.json()["id"]
        self.assertEqual(self.client.get("/api/transactions").json()["items"][0]["id"], transaction_id)
        self.auth("post", "/api/logout")
        self.register("second@example.test")
        self.assertEqual(self.client.get("/api/transactions").json()["items"], [])

    def test_admin_endpoints_are_role_protected_and_can_review_records(self):
        self.register()
        self.auth("post", "/api/transactions", {
            "transaction_date": "2026-10-21", "transaction_type": "expense", "category": "Travel",
            "amount": "20", "currency": "USD", "payment_method": "Card", "description": "Test only"
        })
        self.assertEqual(self.client.get("/api/admin/summary").status_code, 403)
        self.auth("post", "/api/logout")
        self.assertEqual(self.client.get("/api/admin/summary").status_code, 401)
        logged_in = self.client.post("/api/login", json={"email": "admin@example.test", "password": "Admin-test-password-2026!"})
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(self.client.get("/api/admin/summary").status_code, 200)
        self.assertEqual(len(self.client.get("/api/admin/transactions").json()["items"]), 1)

    def test_invalid_amount_and_cross_user_mutation_are_rejected(self):
        self.register()
        bad = self.auth("post", "/api/transactions", {
            "transaction_date": "2026-10-21", "transaction_type": "expense", "category": "Food",
            "amount": "-5", "currency": "USD", "payment_method": "Cash", "description": "Invalid"
        })
        self.assertEqual(bad.status_code, 422)
        self.auth("post", "/api/transactions", {
            "transaction_date": "2026-10-21", "transaction_type": "expense", "category": "Food",
            "amount": "5", "currency": "USD", "payment_method": "Cash", "description": "Own"
        })
        owner_id = self.client.get("/api/transactions").json()["items"][0]["id"]
        self.auth("post", "/api/logout")
        self.register("other@example.test")
        self.assertEqual(self.auth("put", f"/api/transactions/{owner_id}", {
            "transaction_date": "2026-10-21", "transaction_type": "expense", "category": "Food",
            "amount": "5", "currency": "USD", "payment_method": "Cash", "description": "stolen"
        }).status_code, 404)
        self.assertEqual(self.auth("delete", f"/api/transactions/{owner_id}").status_code, 404)

    def test_user_can_export_only_own_transaction_data(self):
        self.register()
        self.auth("post", "/api/transactions", {
            "transaction_date": "2026-10-21", "transaction_type": "income", "category": "Sales",
            "amount": "12.30", "currency": "USD", "payment_method": "Cash", "description": "User export fixture"
        })
        response = self.client.get("/api/transactions/export.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("User export fixture", response.text)
        self.assertNotIn("admin@example.test", response.text)

    def test_sheet_upsert_does_not_append_duplicate_transaction_ids(self):
        from app import upsert_sheet_row
        class Result:
            def __init__(self, value=None, callback=None):
                self.value, self.callback = value, callback
            def execute(self):
                return self.callback() if self.callback else self.value
        class Values:
            def __init__(self):
                self.rows = [["Transaction ID"]]
                self.append_count = 0
                self.update_count = 0
            def get(self, **kwargs):
                return Result({"values": [[row[0]] for row in self.rows]})
            def append(self, **kwargs):
                def commit():
                    self.rows.append(kwargs["body"]["values"][0])
                    self.append_count += 1
                return Result(callback=commit)
            def update(self, **kwargs):
                def commit():
                    row_number = int(kwargs["range"].split("A")[1].split(":")[0])
                    self.rows[row_number - 1] = kwargs["body"]["values"][0]
                    self.update_count += 1
                return Result(callback=commit)
        api = Values()
        tx = {"id": "tx-1", "user_id": "user-1", "transaction_date": "2026-10-21", "transaction_type": "income", "category": "Sales", "amount": "4.00", "currency": "USD", "payment_method": "Cash", "description": "Fake", "reference_number": "", "submitted_at": "now", "updated_at": "now", "sync_status": "pending"}
        self.assertEqual(upsert_sheet_row(api, "sheet-id", "Transactions", tx), "synced")
        self.assertEqual(upsert_sheet_row(api, "sheet-id", "Transactions", tx), "synced")
        self.assertEqual(api.append_count, 1)
        self.assertEqual(api.update_count, 1)
        self.assertEqual(len(api.rows), 2)

    def test_sheet_sync_retries_temporary_failures_before_giving_up(self):
        from app import retry_sheet_sync
        attempts = []
        def flaky_operation():
            attempts.append(1)
            if len(attempts) < 3:
                raise TimeoutError("temporary")
            return "synced"
        self.assertEqual(retry_sheet_sync(flaky_operation, sleeper=lambda _: None), "synced")
        self.assertEqual(len(attempts), 3)

    def test_sync_failure_is_recorded_without_exposing_exception_message(self):
        self.register()
        payload = {
            "transaction_date": "2026-10-21", "transaction_type": "expense", "category": "Test",
            "amount": "3.50", "currency": "USD", "payment_method": "Cash", "description": "Failure fixture"
        }
        with patch("app.sync_transaction", side_effect=RuntimeError("private-token-value")):
            response = self.auth("post", "/api/transactions", payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["sync_status"], "failed")
        self.assertNotIn("private-token-value", response.json()["sync_error"])

    def test_edit_and_delete_update_only_own_visible_history(self):
        self.register()
        payload = {
            "transaction_date": "2026-10-21", "transaction_type": "expense", "category": "Food",
            "amount": "5.00", "currency": "USD", "payment_method": "Cash", "description": "Before edit"
        }
        tx = self.auth("post", "/api/transactions", payload).json()
        payload["description"] = "After edit"
        updated = self.auth("put", f"/api/transactions/{tx['id']}", payload)
        self.assertEqual(updated.json()["description"], "After edit")
        self.assertEqual(self.auth("delete", f"/api/transactions/{tx['id']}").status_code, 200)
        self.assertEqual(self.client.get("/api/transactions").json()["items"], [])

    def test_admin_can_suspend_and_restore_user_access(self):
        self.register()
        user_id = self.client.get("/api/me").json()["user"]["id"]
        self.auth("post", "/api/logout")
        self.client.post("/api/login", json={"email": "admin@example.test", "password": "Admin-test-password-2026!"})
        self.assertEqual(self.auth("post", f"/api/admin/users/{user_id}/suspend").status_code, 200)
        self.assertFalse(next(u for u in self.client.get("/api/admin/users").json()["items"] if u["id"] == user_id)["active"])
        self.auth("post", "/api/logout")
        denied = self.client.post("/api/login", json={"email": "person@example.test", "password": "Valid-test-password-2026!"})
        self.assertEqual(denied.status_code, 401)
        self.client.post("/api/login", json={"email": "admin@example.test", "password": "Admin-test-password-2026!"})
        self.assertEqual(self.auth("post", f"/api/admin/users/{user_id}/reactivate").status_code, 200)

    def test_admin_summary_keeps_currencies_separate(self):
        self.register()
        for currency, amount in (("USD", "10"), ("EUR", "7")):
            self.auth("post", "/api/transactions", {
                "transaction_date": "2026-10-21", "transaction_type": "income", "category": "Sales",
                "amount": amount, "currency": currency, "payment_method": "Cash", "description": "Currency fixture"
            })
        self.auth("post", "/api/logout")
        self.client.post("/api/login", json={"email": "admin@example.test", "password": "Admin-test-password-2026!"})
        totals = self.client.get("/api/admin/summary").json()["by_currency"]
        self.assertEqual(set(totals), {"USD", "EUR"})
        self.assertEqual(totals["USD"]["income"], "10.00")
        self.assertEqual(totals["EUR"]["income"], "7.00")

    def test_sheet_retry_uses_upsert_by_transaction_id(self):
        self.register()
        row = self.auth("post", "/api/transactions", {
            "transaction_date": "2026-10-21", "transaction_type": "income", "category": "Sales",
            "amount": "9.99", "currency": "USD", "payment_method": "Cash", "description": "Retry test"
        }).json()
        with patch("app.sync_transaction", return_value="synced") as sync:
            result = self.auth("post", f"/api/transactions/{row['id']}/retry-sync")
            self.assertEqual(result.status_code, 200)
            sync.assert_called_once()


if __name__ == "__main__":
    unittest.main()
