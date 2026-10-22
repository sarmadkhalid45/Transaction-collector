from __future__ import annotations

import csv
import hashlib
import hmac
from contextlib import contextmanager
import io
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from dotenv import load_dotenv

load_dotenv()
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.sessions import SessionMiddleware


log = logging.getLogger("transaction_collector")
COLUMNS = ["Transaction ID", "User ID", "User Reference", "Transaction Date", "Transaction Type", "Category", "Amount", "Currency", "Payment Method", "Description", "Reference Number", "Submitted At", "Last Updated At", "Sync Status"]
TX_TYPES = {"income", "expense", "transfer", "other"}
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = encoded.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


@contextmanager
def open_db(path: Path):
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open_db(path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','user')),
            active INTEGER NOT NULL DEFAULT 1, consent_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            transaction_date TEXT NOT NULL, transaction_type TEXT NOT NULL,
            category TEXT NOT NULL, amount TEXT NOT NULL, currency TEXT NOT NULL,
            payment_method TEXT NOT NULL, description TEXT NOT NULL,
            reference_number TEXT NOT NULL DEFAULT '', submitted_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, sync_status TEXT NOT NULL DEFAULT 'pending',
            sync_error TEXT NOT NULL DEFAULT '', deleted_at TEXT, idempotency_key TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tx_user_date ON transactions(user_id, transaction_date DESC);
        CREATE INDEX IF NOT EXISTS idx_tx_sync ON transactions(sync_status);
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT NOT NULL,
            action TEXT NOT NULL, subject_id TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """)
        tx_columns = {row["name"] for row in conn.execute("PRAGMA table_info(transactions)")}
        if "idempotency_key" not in tx_columns:
            conn.execute("ALTER TABLE transactions ADD COLUMN idempotency_key TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_user_idempotency ON transactions(user_id,idempotency_key) WHERE idempotency_key IS NOT NULL AND deleted_at IS NULL")


def sheet_values(tx: dict[str, Any]) -> list[str]:
    return [tx["id"], tx["user_id"], "user-" + tx["user_id"].replace("-", "")[:8], tx["transaction_date"], tx["transaction_type"], tx["category"], tx["amount"], tx["currency"], tx["payment_method"], tx["description"], tx["reference_number"], tx["submitted_at"], tx["updated_at"], tx["sync_status"]]


def retry_sheet_sync(operation, sleeper=time.sleep, attempts: int = 3):
    """Retry idempotent Sheets operations with bounded exponential backoff."""
    for attempt in range(attempts):
        try:
            return operation()
        except Exception:
            if attempt == attempts - 1:
                raise
            sleeper(0.5 * (2 ** attempt))


def upsert_sheet_row(api, spreadsheet_id: str, tab: str, tx: dict[str, Any]) -> str:
    """Insert once per transaction ID, then update the same row on later attempts."""
    col_a = api.get(spreadsheetId=spreadsheet_id, range=f"'{tab}'!A:A").execute().get("values", [])
    row_num = next((i + 1 for i, row in enumerate(col_a) if row and row[0] == tx["id"]), None)
    tx["sync_status"] = "synced"
    row = sheet_values(tx)
    if row_num:
        api.update(spreadsheetId=spreadsheet_id, range=f"'{tab}'!A{row_num}:N{row_num}", valueInputOption="RAW", body={"values": [row]}).execute()
    else:
        api.append(spreadsheetId=spreadsheet_id, range=f"'{tab}'!A:N", valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": [row]}).execute()
    return "synced"


_SHEET_SYNC_LOCK = threading.Lock()


def sync_transaction(tx: dict[str, Any]) -> str:
    """Idempotently insert or update a row; never clears the administrator's sheet."""
    spreadsheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    credentials_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if not spreadsheet_id or not credentials_file:
        return "pending"
    tab = os.getenv("GOOGLE_SHEET_TAB", "Transactions").strip() or "Transactions"
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials.from_service_account_file(credentials_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    api = service.spreadsheets().values()

    # A retry after an ambiguous append outcome re-reads column A and updates the existing ID.
    with _SHEET_SYNC_LOCK:
        return retry_sheet_sync(lambda: upsert_sheet_row(api, spreadsheet_id, tab, tx))


class RegisterInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    consent: bool

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class LoginInput(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TransactionInput(BaseModel):
    transaction_date: date
    transaction_type: str
    category: str = Field(min_length=1, max_length=80)
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    payment_method: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    reference_number: str = Field(default="", max_length=120)

    @field_validator("transaction_type")
    @classmethod
    def check_type(cls, value: str) -> str:
        if value not in TX_TYPES:
            raise ValueError("Unsupported transaction type")
        return value

    @field_validator("amount")
    @classmethod
    def check_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > Decimal("999999999999.99"):
            raise ValueError("Amount must be positive and within the supported limit")
        if value.as_tuple().exponent < -2:
            raise ValueError("Amount supports at most two decimal places")
        return value.quantize(Decimal("0.01"))

    @field_validator("currency")
    @classmethod
    def check_currency(cls, value: str) -> str:
        value = value.upper()
        if not CURRENCY_RE.fullmatch(value):
            raise ValueError("Currency must be a 3-letter ISO code")
        return value

    @field_validator("category", "payment_method", "description", "reference_number")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()


def create_app(db_path: str | Path | None = None, admin_email: str | None = None, admin_password: str | None = None) -> FastAPI:
    path = Path(db_path or os.getenv("DATABASE_PATH", "data/transactions.sqlite3")).resolve()
    initialize_db(path)
    bootstrap_email = (admin_email if admin_email is not None else os.getenv("ADMIN_EMAIL", "")).strip().lower()
    bootstrap_password = admin_password if admin_password is not None else os.getenv("ADMIN_PASSWORD", "")
    secret_key = os.getenv("SECRET_KEY") or "local-development-only-change-me"
    if os.getenv("APP_ENV") == "production" and (len(secret_key) < 32 or secret_key == "local-development-only-change-me"):
        raise RuntimeError("Production requires a random SECRET_KEY of at least 32 characters")
    if os.getenv("APP_ENV") == "production" and (not bootstrap_email or not bootstrap_password):
        raise RuntimeError("Production requires ADMIN_EMAIL and ADMIN_PASSWORD")
    if bootstrap_email and bootstrap_password and len(bootstrap_password) < 12:
        raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters")
    app = FastAPI(title="Central Transaction Collector", docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=secret_key, session_cookie="tx_session", same_site="lax", https_only=os.getenv("APP_ENV") == "production", max_age=60 * 60 * 12)
    app.add_middleware(CORSMiddleware, allow_origins=[], allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token"])
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    app.state.db_path = path
    app.state.login_attempts = {}
    app.state.registration_attempts = {}

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def rate_limit(store: dict[str, list[float]], key: str, limit: int, window: int) -> bool:
        now = datetime.now(timezone.utc).timestamp()
        recent = [stamp for stamp in store.get(key, []) if now - stamp < window]
        if len(recent) >= limit:
            store[key] = recent
            return False
        recent.append(now)
        store[key] = recent
        return True

    def request_ip(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    if os.getenv("APP_ENV") == "production":
        with open_db(path) as conn:
            stored_admin = conn.execute("SELECT email,password_hash,active FROM users WHERE role='admin' LIMIT 1").fetchone()
        if stored_admin:
            if stored_admin["email"].lower() != bootstrap_email or not stored_admin["active"]:
                raise RuntimeError("Configured ADMIN_EMAIL must match an active administrator account")
            if not verify_password(bootstrap_password, stored_admin["password_hash"]):
                raise RuntimeError("ADMIN_PASSWORD does not match the existing administrator; password changes do not update an existing account")


    if bootstrap_email and bootstrap_password:
        with open_db(path) as conn:
            exists = conn.execute("SELECT id FROM users WHERE email=?", (bootstrap_email,)).fetchone()
            if not exists:
                conn.execute("INSERT INTO users(id,email,password_hash,role,active,consent_at,created_at) VALUES(?,?,?,?,1,?,?)", (str(uuid.uuid4()), bootstrap_email, hash_password(bootstrap_password), "admin", utcnow(), utcnow()))

    def current_user(request: Request, admin: bool = False) -> dict[str, Any]:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(401, "Sign in required")
        with open_db(path) as conn:
            user = conn.execute("SELECT id,email,role,active,created_at FROM users WHERE id=?", (user_id,)).fetchone()
        if not user or not user["active"]:
            request.session.clear()
            raise HTTPException(401, "Account is unavailable")
        result = dict(user)
        if admin and result["role"] != "admin":
            raise HTTPException(403, "Administrator access required")
        return result

    def require_csrf(request: Request) -> None:
        expected = request.session.get("csrf_token", "")
        supplied = request.headers.get("x-csrf-token", "")
        if not expected or not hmac.compare_digest(expected, supplied):
            raise HTTPException(403, "CSRF validation failed")

    def audit(actor_id: str, action: str, subject_id: str) -> None:
        with open_db(path) as conn:
            conn.execute("INSERT INTO audit_log(actor_id,action,subject_id,created_at) VALUES(?,?,?,?)", (actor_id, action, subject_id, utcnow()))

    def load_tx(txid: str) -> dict[str, Any] | None:
        with open_db(path) as conn:
            row = conn.execute("SELECT * FROM transactions WHERE id=? AND deleted_at IS NULL", (txid,)).fetchone()
        return dict(row) if row else None

    def store_sync(txid: str, status: str, error: str = "") -> None:
        with open_db(path) as conn:
            conn.execute("UPDATE transactions SET sync_status=?,sync_error=? WHERE id=?", (status, error[:160], txid))

    def perform_sync(txid: str) -> str:
        tx = load_tx(txid)
        if not tx:
            return "pending"
        try:
            result = sync_transaction(tx)
            store_sync(txid, result, "")
            return result
        except Exception as exc:
            # Avoid putting exception text, request bodies, or credentials in logs/database.
            error = f"Google Sheets sync failed ({type(exc).__name__}). Check server configuration and API access."
            store_sync(txid, "failed", error)
            log.warning("Sheets sync failed for transaction %s: %s", txid, type(exc).__name__)
            return "failed"

    @app.get("/")
    def home():
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/manifest.webmanifest")
    def manifest():
        return FileResponse(Path(__file__).parent / "static" / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/sw.js")
    def service_worker():
        return FileResponse(Path(__file__).parent / "static" / "sw.js", media_type="application/javascript")
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "google_sheets_configured": bool(
            os.getenv("GOOGLE_SHEET_ID")
            and os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        ),
    }


@app.get("/api/me")
def me(request: Request):
    user_id = request.session.get("user_id")

    if user_id:
        try:
            user = current_user(request)
            csrf_token = request.session.get("csrf_token")

            if not csrf_token:
                csrf_token = secrets.token_urlsafe(32)
                request.session["csrf_token"] = csrf_token

            return {
                "authenticated": True,
                "csrf_token": csrf_token,
                "user": user,
            }
        except HTTPException:
            request.session.clear()

    csrf_token = secrets.token_urlsafe(32)
    request.session["csrf_token"] = csrf_token

    return {
        "authenticated": False,
        "csrf_token": csrf_token,
    }
                "user": user,
            }
        except HTTPException:
            request.session.clear()

    csrf_token = secrets.token_urlsafe(32)
    request.session["csrf_token"] = csrf_token

    return {
        "authenticated": False,
        "csrf_token": csrf_token,
    }

    @app.post("/api/register", status_code=201)
    def register(payload: RegisterInput, request: Request):
        if not rate_limit(app.state.registration_attempts, request_ip(request), 10, 3600):
            raise HTTPException(429, "Too many registration attempts. Try again later.")
        if not payload.consent:
            raise HTTPException(400, "Consent to central administrator sharing is required to create an account")
        if len(payload.password) < 12:
            raise HTTPException(400, "Password must be at least 12 characters")
        user_id = str(uuid.uuid4())
        try:
            with open_db(path) as conn:
                conn.execute("INSERT INTO users(id,email,password_hash,role,active,consent_at,created_at) VALUES(?,?,?,?,1,?,?)", (user_id, payload.email, hash_password(payload.password), "user", utcnow(), utcnow()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An account with that email already exists")
        request.session.clear()
        request.session.update({"user_id": user_id, "csrf_token": secrets.token_urlsafe(32)})
        return {"id": user_id, "email": payload.email, "role": "user"}

    @app.post("/api/login")
    def login(payload: LoginInput, request: Request):
        now = datetime.now(timezone.utc).timestamp()
        key = request.client.host if request.client else "unknown"
        attempts = [(t, n) for t, n in app.state.login_attempts.get(key, []) if now - t < 900]
        if sum(n for _, n in attempts) >= 20:
            raise HTTPException(429, "Too many login attempts. Try again later.")
        with open_db(path) as conn:
            row = conn.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", (payload.email.strip(),)).fetchone()
        if not row or not row["active"] or not verify_password(payload.password, row["password_hash"]):
            attempts.append((now, 1))
            app.state.login_attempts[key] = attempts
            raise HTTPException(401, "Invalid email or password")
        app.state.login_attempts.pop(key, None)
        request.session.clear()
        request.session.update({"user_id": row["id"], "csrf_token": secrets.token_urlsafe(32)})
        return {"id": row["id"], "email": row["email"], "role": row["role"]}

    @app.post("/api/logout")
    def logout(request: Request):
        require_csrf(request)
        request.session.clear()
        return {"ok": True}

    @app.get("/api/transactions")
    def my_transactions(request: Request, start: date | None = None, end: date | None = None, category: str | None = None, transaction_type: str | None = None, currency: str | None = None):
        user = current_user(request)
        clauses = ["user_id=?", "deleted_at IS NULL"]
        args: list[Any] = [user["id"]]
        for field, value, op in (("transaction_date", start, ">="), ("transaction_date", end, "<="), ("category", category, "="), ("transaction_type", transaction_type, "="), ("currency", currency.upper() if currency else None, "=")):
            if value:
                clauses.append(f"{field}{op}?")
                args.append(value.isoformat() if isinstance(value, date) else value)
        with open_db(path) as conn:
            rows = [dict(row) for row in conn.execute(f"SELECT * FROM transactions WHERE {' AND '.join(clauses)} ORDER BY transaction_date DESC,submitted_at DESC", args)]
        return {"items": rows, "summary": summarize(rows)}

    @app.post("/api/transactions", status_code=201)
    def create_transaction(payload: TransactionInput, request: Request, idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128)):
        user = current_user(request)
        require_csrf(request)
        if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
            raise HTTPException(422, "Idempotency-Key contains unsupported characters")
        fields = payload.model_dump()
        fields["transaction_date"] = fields["transaction_date"].isoformat()
        fields["amount"] = format(fields["amount"], ".2f")
        def same_submission(row) -> bool:
            return all(row[key] == fields[key] for key in ("transaction_date", "transaction_type", "category", "amount", "currency", "payment_method", "description", "reference_number"))
        with open_db(path) as conn:
            existing = conn.execute("SELECT * FROM transactions WHERE user_id=? AND idempotency_key=? AND deleted_at IS NULL", (user["id"], idempotency_key)).fetchone()
        if existing:
            if not same_submission(existing):
                raise HTTPException(409, "Idempotency-Key was already used with different transaction data")
            perform_sync(existing["id"])
            return load_tx(existing["id"])
        txid, now = str(uuid.uuid4()), utcnow()
        try:
            with open_db(path) as conn:
                conn.execute("INSERT INTO transactions(id,user_id,transaction_date,transaction_type,category,amount,currency,payment_method,description,reference_number,submitted_at,updated_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (txid, user["id"], fields["transaction_date"], fields["transaction_type"], fields["category"], fields["amount"], fields["currency"], fields["payment_method"], fields["description"], fields["reference_number"], now, now, idempotency_key))
        except sqlite3.IntegrityError:
            with open_db(path) as conn:
                existing = conn.execute("SELECT * FROM transactions WHERE user_id=? AND idempotency_key=? AND deleted_at IS NULL", (user["id"], idempotency_key)).fetchone()
            if not existing:
                raise HTTPException(409, "Transaction could not be created")
            if not same_submission(existing):
                raise HTTPException(409, "Idempotency-Key was already used with different transaction data")
            txid = existing["id"]
        perform_sync(txid)
        return load_tx(txid)

    @app.get("/api/transactions/export.csv")
    def export_my_transactions(request: Request):
        user = current_user(request)
        with open_db(path) as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM transactions WHERE user_id=? AND deleted_at IS NULL ORDER BY transaction_date DESC", (user["id"],))]
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(COLUMNS)
        for tx in rows:
            values = sheet_values(tx)
            writer.writerow([("'" + str(value)) if str(value).startswith(("=", "+", "-", "@")) else value for value in values])
        return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=my-transactions.csv"})

    @app.put("/api/transactions/{txid}")
    def update_transaction(txid: str, payload: TransactionInput, request: Request):
        user = current_user(request)
        require_csrf(request)
        with open_db(path) as conn:
            row = conn.execute("SELECT id FROM transactions WHERE id=? AND user_id=? AND deleted_at IS NULL", (txid, user["id"])).fetchone()
            if not row:
                raise HTTPException(404, "Transaction not found")
            fields = payload.model_dump()
            fields["transaction_date"] = fields["transaction_date"].isoformat()
            fields["amount"] = format(fields["amount"], ".2f")
            now = utcnow()
            conn.execute("UPDATE transactions SET transaction_date=?,transaction_type=?,category=?,amount=?,currency=?,payment_method=?,description=?,reference_number=?,updated_at=?,sync_status='pending',sync_error='' WHERE id=?", (fields["transaction_date"], fields["transaction_type"], fields["category"], fields["amount"], fields["currency"], fields["payment_method"], fields["description"], fields["reference_number"], now, txid))
        audit(user["id"], "transaction_updated", txid)
        perform_sync(txid)
        return load_tx(txid)

    @app.delete("/api/transactions/{txid}")
    def delete_transaction(txid: str, request: Request):
        user = current_user(request)
        require_csrf(request)
        now = utcnow()
        with open_db(path) as conn:
            result = conn.execute("UPDATE transactions SET deleted_at=?,updated_at=?,sync_status='pending' WHERE id=? AND user_id=? AND deleted_at IS NULL", (now, now, txid, user["id"]))
            if not result.rowcount:
                raise HTTPException(404, "Transaction not found")
        audit(user["id"], "transaction_deleted", txid)
        return {"ok": True, "note": "Hidden from app history. Previously synced spreadsheet rows are not automatically removed."}

    @app.post("/api/transactions/{txid}/retry-sync")
    def retry_sync(txid: str, request: Request):
        user = current_user(request)
        require_csrf(request)
        tx = load_tx(txid)
        if not tx or (user["role"] != "admin" and tx["user_id"] != user["id"]):
            raise HTTPException(404, "Transaction not found")
        return {"id": txid, "sync_status": perform_sync(txid)}

    @app.get("/api/admin/summary")
    def admin_summary(request: Request, start: date | None = None, end: date | None = None, user_id: str | None = None, category: str | None = None, transaction_type: str | None = None, currency: str | None = None, search: str | None = None):
        current_user(request, admin=True)
        rows = admin_rows(path, start, end, user_id, category, transaction_type, currency, search)
        with open_db(path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM transactions WHERE deleted_at IS NULL").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM transactions WHERE sync_status='failed' AND deleted_at IS NULL").fetchone()[0]
            users = conn.execute("SELECT COUNT(*) FROM users WHERE role='user' AND active=1").fetchone()[0]
        return {"transaction_count": total, "active_users": users, "failed_syncs": failed, "by_currency": summarize(rows)}

    @app.get("/api/admin/transactions")
    def admin_transactions(request: Request, start: date | None = None, end: date | None = None, user_id: str | None = None, category: str | None = None, transaction_type: str | None = None, currency: str | None = None, search: str | None = None):
        current_user(request, admin=True)
        rows = admin_rows(path, start, end, user_id, category, transaction_type, currency, search)
        return {"items": rows, "summary": summarize(rows)}

    @app.get("/api/admin/export.csv")
    def export_csv(request: Request, start: date | None = None, end: date | None = None, user_id: str | None = None, category: str | None = None, transaction_type: str | None = None, currency: str | None = None, search: str | None = None):
        current_user(request, admin=True)
        rows = admin_rows(path, start, end, user_id, category, transaction_type, currency, search)
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Transaction ID", "User ID", "User Email", *COLUMNS[3:]])
        for tx in rows:
            values = [tx["id"], tx["user_id"], tx["email"], *sheet_values(tx)[3:]]
            writer.writerow([("'" + str(value)) if str(value).startswith(("=", "+", "-", "@")) else value for value in values])
        return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=transactions.csv"})

    @app.get("/api/admin/users")
    def admin_users(request: Request):
        current_user(request, admin=True)
        with open_db(path) as conn:
            rows = [dict(row) for row in conn.execute("SELECT id,email,active,created_at FROM users WHERE role='user' ORDER BY created_at DESC")]
        return {"items": rows}

    @app.post("/api/admin/users/{user_id}/suspend")
    def suspend_user(user_id: str, request: Request):
        actor = current_user(request, admin=True)
        require_csrf(request)
        with open_db(path) as conn:
            row = conn.execute("SELECT id FROM users WHERE id=? AND role='user'", (user_id,)).fetchone()
            if not row:
                raise HTTPException(404, "User not found")
            conn.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
        audit(actor["id"], "user_suspended", user_id)
        return {"ok": True}

    @app.post("/api/admin/users/{user_id}/reactivate")
    def reactivate_user(user_id: str, request: Request):
        actor = current_user(request, admin=True)
        require_csrf(request)
        with open_db(path) as conn:
            row = conn.execute("SELECT id FROM users WHERE id=? AND role='user'", (user_id,)).fetchone()
            if not row:
                raise HTTPException(404, "User not found")
            conn.execute("UPDATE users SET active=1 WHERE id=?", (user_id,))
        audit(actor["id"], "user_reactivated", user_id)
        return {"ok": True}

    @app.post("/api/admin/retry-sync/{txid}")
    def admin_retry_sync(txid: str, request: Request):
        actor = current_user(request, admin=True)
        require_csrf(request)
        if not load_tx(txid):
            raise HTTPException(404, "Transaction not found")
        status = perform_sync(txid)
        audit(actor["id"], "sync_retry", txid)
        return {"id": txid, "sync_status": status}

    @app.get("/api/admin/sync-failures")
    def sync_failures(request: Request):
        current_user(request, admin=True)
        with open_db(path) as conn:
            rows = [dict(row) for row in conn.execute("SELECT id,user_id,transaction_date,amount,currency,sync_status,sync_error,updated_at FROM transactions WHERE sync_status='failed' AND deleted_at IS NULL ORDER BY updated_at")]
        return {"items": rows}

    @app.post("/api/account/delete")
    def delete_account(request: Request):
        user = current_user(request)
        require_csrf(request)
        if user["role"] == "admin":
            raise HTTPException(403, "The administrator account cannot be self-deleted")
        audit(user["id"], "account_deleted", user["id"])
        with open_db(path) as conn:
            conn.execute("DELETE FROM transactions WHERE user_id=?", (user["id"],))
            conn.execute("DELETE FROM users WHERE id=?", (user["id"],))
        request.session.clear()
        return {"ok": True, "note": "Your local account and transaction records were deleted. Copies already synchronized to the administrator's spreadsheet must be handled under its retention policy."}

    return app


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, dict[str, str | int]] = {}
    for row in rows:
        currency = row["currency"]
        totals.setdefault(currency, {"income": "0.00", "expenses": "0.00", "net": "0.00", "count": 0})
        current = totals[currency]
        amount = Decimal(str(row["amount"]))
        if row["transaction_type"] == "income":
            current["income"] = format(Decimal(str(current["income"])) + amount, ".2f")
        elif row["transaction_type"] == "expense":
            current["expenses"] = format(Decimal(str(current["expenses"])) + amount, ".2f")
        current["net"] = format(Decimal(str(current["income"])) - Decimal(str(current["expenses"])), ".2f")
        current["count"] = int(current["count"]) + 1
    return totals


def admin_rows(path: Path, start: date | None, end: date | None, user_id: str | None, category: str | None, transaction_type: str | None, currency: str | None, search: str | None = None) -> list[dict[str, Any]]:
    clauses = ["t.deleted_at IS NULL"]
    args: list[Any] = []
    if search and search.strip():
        clauses.append("(t.description LIKE ? OR t.reference_number LIKE ? OR t.category LIKE ? OR u.email LIKE ?)")
        args.extend([f"%{search.strip()[:100]}%"] * 4)
    for field, value, op in (("t.transaction_date", start, ">="), ("t.transaction_date", end, "<="), ("t.user_id", user_id, "="), ("t.category", category, "="), ("t.transaction_type", transaction_type, "="), ("t.currency", currency.upper() if currency else None, "=")):
        if value:
            clauses.append(f"{field}{op}?")
            args.append(value.isoformat() if isinstance(value, date) else value)
    with open_db(path) as conn:
        return [dict(row) for row in conn.execute(f"SELECT t.*,u.email FROM transactions t JOIN users u ON u.id=t.user_id WHERE {' AND '.join(clauses)} ORDER BY t.transaction_date DESC,t.submitted_at DESC", args)]


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
