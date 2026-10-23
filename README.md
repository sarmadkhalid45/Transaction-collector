# LedgerBridge — Central Transaction Collector

A responsive, installable web app for multi-user manual transaction entry, private user histories, administrator reporting, CSV export, and optional server-side Google Sheets synchronization. The database is authoritative; Sheets is the administrator's reporting destination.

## Stage 1 architecture decision

The simplest suitable first release is a single FastAPI application with a same-origin HTML/JavaScript frontend, SQLite storage, signed server-side session cookies, and an optional Google Sheets service account. SQLite keeps local setup inexpensive; run one application instance against a persistent disk. If you need multiple application instances or high write concurrency, move the database to PostgreSQL before scaling out.

**Defaults chosen:** transactions are entered manually; account IDs and transaction IDs are UUIDs; currencies are ISO 4217 three-letter codes; income and expenses are summarized separately by currency; no conversion between currencies is performed; deleted user transactions are hidden locally, but already-synced Sheet rows are not deleted automatically. Google credentials are read only on the server from a file path. Transaction creation requires an `Idempotency-Key`; the browser keeps the key for a retry and the database returns the original transaction for repeated requests.

## Included

- Account registration with explicit disclosure/consent, sign-in/out, role checks, and account deletion.
- Administrator account bootstrapping from environment settings; user/admin separation is enforced by the API.
- Scrypt password hashing, signed 12-hour session cookies, CSRF checks on authenticated writes, input validation, and a basic in-memory login rate limit.
- Per-user transaction history, create/edit/soft-delete, date/type filters, user-only CSV export, and summaries grouped by currency.
- Admin reports, search/filtering, direct editing of any submitted transaction, users list with suspend/reactivate controls, CSV export, and failed/pending synchronization visibility.
- Required per-submission idempotency keys backed by a user-scoped unique database index; Google Sheets append/update by transaction ID, three bounded retry attempts for an ambiguous/transient operation, and a process-local sync lock. The sheet is never cleared.
- Responsive interface and PWA shell. API data is not cached offline.
- SQLite schema bootstrap and a matching initial SQL schema file.

## Project structure

```text
app.py                         FastAPI API, database setup, sessions, Sheets integration
static/index.html              Responsive user and admin interface
static/manifest.webmanifest    PWA install metadata
static/sw.js                    Static shell cache; never caches API records
static/icon.svg                 PWA icon
migrations/001_initial.sql      Initial SQLite schema
sheet-template.csv              Central Sheet header row
.env.example                    Safe configuration template
.env                            Local-only settings; ignored by Git
requirements.txt                Runtime and test dependencies
run_windows.bat                 Windows install-and-run helper
Dockerfile                      Single-container deployment artifact
tests/test_app.py               Automated API/security tests
```

## Local setup (Windows)

1. Install Python 3.11 or newer.
2. In this folder, edit `.env` (or copy `.env.example` first). Set `ADMIN_EMAIL` and a unique `ADMIN_PASSWORD` of at least 12 characters. Set `SECRET_KEY` to a locally generated random value; generate one with:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Do not send the resulting secret or administrator password in chat or commit `.env`.
3. Install and run:

   ```bash
   python -m venv .venv
   .venv\\Scripts\\python.exe -m pip install -r requirements.txt
   .venv\\Scripts\\python.exe app.py
   ```

   Or double-click `run_windows.bat`. Open <http://127.0.0.1:8000>.
4. The first startup creates the database at `data/transactions.sqlite3` and creates the admin account if `ADMIN_EMAIL`/`ADMIN_PASSWORD` are set. Configure them **before the first run**. Changing those environment variables later does not reset an existing password; production startup checks that the configured credentials still match the existing administrator, so keep them in your secret manager until a password-rotation flow is added.
5. Register a fictional test user, sign in, and create a fictional transaction. Do not put real financial data in a test deployment.

On non-Windows systems, use `python3 -m venv .venv`, activate `.venv`, install `requirements.txt`, and run `python app.py`.

## Google Sheets administrator setup

The integration is optional. Without credentials, accepted transactions remain saved in SQLite with `pending` sync status. The live Google API path has **not** been exercised for this delivery because no administrator-owned Sheet or service-account credentials were supplied.

1. Create a Google Cloud project, enable the Google Sheets API, and create a service account with access limited to this application.
2. Create a JSON key for that service account and store it locally outside source control (for example, `secrets/google-service-account.json`). Never put this key in the frontend, a public repository, an archive, or application logs.
3. Create a Google spreadsheet. Add a tab named `Transactions` and put the exact header row from `sheet-template.csv` in row 1. Share the spreadsheet with the service account's `client_email` as an Editor. The Sheet remains controlled by the administrator.
4. Set these values in `.env`, then restart the service:

   ```env
   GOOGLE_SHEET_ID=the-spreadsheet-id-from-its-url
   GOOGLE_SHEET_TAB=Transactions
   GOOGLE_SERVICE_ACCOUNT_FILE=secrets/google-service-account.json
   ```

   In Docker, mount the JSON key read-only into the container and set the path to its **container** location.
5. Submit a fictional transaction and inspect its unique ID in column A. Retry the same transaction from the user history or admin dashboard; the integration searches column A and updates that ID instead of adding another row. Existing Sheet rows are preserved.
6. Check the administrator dashboard for pending/failed syncs. API failures are recorded with a sanitized error class, not request/credential details. Fix credentials, API access, or the tab name and use **Retry**.

Columns are: `Transaction ID | User ID | User Reference | Transaction Date | Transaction Type | Category | Amount | Currency | Payment Method | Description | Reference Number | Submitted At | Last Updated At | Sync Status`. The user reference is a shortened opaque reference; email is not sent to the Sheet. The internal user UUID is included as requested. Google sync writes values as `RAW`.

## Data sharing and privacy

Before registration, users see the disclosure and must consent. Each transaction is stored by the application and, when configured, sent to the administrator-controlled Sheet. Collected fields are the date, type, category, amount, currency, payment method, description, optional reference number, internal user ID/reference, transaction ID, and timestamps. The application does not collect bank logins, card security codes, screen contents, or data from other apps.

Users can review/edit their own records and request deletion through **Delete my account and records**. Local account and transaction records are deleted; this app does not remove rows already copied to the administrator's Sheet. The administrator must apply the retention/deletion policy to those copies. Transaction delete in the history is a local soft-delete. Admin actions are recorded in the local `audit_log`; transaction edits/deletes and user suspension/reactivation/retry actions are logged without storing transaction descriptions in the audit log.

**Do not deploy for real financial information until you have reviewed applicable privacy, retention, access, and backup obligations.** Anyone with access to the Google Sheet can see the submitted rows. Keep the Sheet restricted to authorized administrators.

## Administrator guide

- Sign in with the configured admin account to view transaction totals, active-user count, failures, and the records table.
- Filter by user, date range, category, transaction type, currency, or search text; export the matching rows using **Export CSV**.
- Totals are shown separately for each currency. Transfers/other types are counted but are not treated as income or expenses. No currency conversion is performed.
- Use **Edit** beside any submitted transaction to correct its date, type, category, amount, currency, payment method, description, or reference. Saving records an admin audit event and updates the matching Google Sheet row when sync is configured.
- Suspend or reactivate user accounts in **User access**. A suspended account is denied on its next API request.
- Sheet connectivity is configured through server environment variables, not through the browser. Restart after changing settings.
- Back up the SQLite database regularly. Use SQLite's online backup command, not a raw copy of a database file while it is being written:

  ```bash
  sqlite3 data/transactions.sqlite3 ".backup 'backup/transactions-YYYY-MM-DD.sqlite3'"
  ```

  Store backups encrypted and separately from the running host; periodically test a restore.

## Tests

Run from the project directory:

```bash
python -m unittest discover -s . -p 'test*.py' -v
```

The automated suite uses temporary SQLite databases and fictional values. It checks explicit consent, registration, user isolation, validation, role protection, admin review, Sheets retry invocation, and retry-after-temporary-failure behavior. Google API writes are not live-tested without credentials; browser-based visual testing on physical mobile devices and production HTTPS deployment are not part of the automated suite.

## Deployment and cost

The included Dockerfile creates a non-root, single-process container. For a small deployment, use a VPS or container host with **persistent storage**, HTTPS termination (for example, Caddy or a managed reverse proxy), and regular backups. Set `APP_ENV=production`, a random `SECRET_KEY` of 32+ characters, `ADMIN_EMAIL`, and a strong `ADMIN_PASSWORD`; production startup fails if the secret/admin bootstrap values are missing. The session cookie is marked Secure in production, so serve the site over HTTPS.

Example Docker deployment (from a host with Docker):

```bash
docker build -t ledgerbridge .
docker volume create ledgerbridge-data
docker run --name ledgerbridge --restart unless-stopped \
  --env-file .env -p 8000:8000 \
  -e DATABASE_PATH=/data/transactions.sqlite3 \
  -v ledgerbridge-data:/data \
  ledgerbridge
```

To enable Sheets in Docker, set `GOOGLE_SERVICE_ACCOUNT_FILE=/run/secrets/google-service-account.json` and add a read-only bind mount for the local JSON key, for example `-v /absolute/host/path/google-service-account.json:/run/secrets/google-service-account.json:ro`. Restrict host file permissions. Terminate TLS at a reverse proxy; do not expose an unencrypted production service directly to the internet.

A current example budget is a DigitalOcean Basic Droplet with 1 GiB RAM, listed at **$6/month** (25 GiB SSD and 1,000 GiB transfer included); backups, a domain, taxes, and any chosen managed services can add cost.[1] This is a price example, not an all-in quote or guarantee. Check the provider's current pricing and sizing before deployment. Google account/API quotas and any other provider charges are separate; this project does not promise indefinite free operation.

## Known limitations / not yet implemented

- Google Sheets credentials, sheet ownership, and live synchronization were not configured or verified in this environment.
- SQLite and a process-local rate limiter/sync lock are intended for a single application instance; do not scale to several workers/hosts without moving to a shared database and distributed sync coordination.
- No email verification, password reset, MFA, admin password-rotation UI, scheduled background retry worker, CSV import, bank integration, or offline transaction submission.
- The initial schema is created at startup, but there is no general migration runner for future schema versions.
- Logs and sync errors are sanitized, but production operations still need centralized monitoring, encrypted backup storage, restore drills, and an explicit retention schedule.
- This is a starter application, not a certified accounting, banking, or regulated financial platform. Review the code and threat model before collecting real financial data.

## Sources

[1] https://www.digitalocean.com/pricing/droplets — DigitalOcean Droplet Pricing
