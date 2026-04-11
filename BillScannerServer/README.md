# Bill Scanner — API server

FastAPI backend for scanning bills (images, PDF, Office files), OCR, parsing, and analytics. Pair this repo with **BillScannerApp** (Expo mobile client).

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python** | 3.10 or 3.11 recommended (PaddlePaddle wheels vary by version). |
| **PostgreSQL** | Running instance and an empty database (e.g. `billdb`). |
| **Git** | To clone the project. |

Optional: **Tesseract** only if you use code paths that call `pytesseract` (primary pipeline uses **PaddleOCR**).

## 1. Clone and virtual environment

```bash
cd BillScannerServer
python -m venv venv
```

**Windows**

```bat
venv\Scripts\activate
```

**macOS / Linux**

```bash
source venv/bin/activate
```

## 2. Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### If `paddlepaddle` fails to install

Paddle wheels are OS- and Python-version specific. Use the official guide and pick **CPU** (or GPU) for your system:

- [PaddlePaddle install (English)](https://www.paddlepaddle.org.cn/documentation/docs/en/install/index_en.html)

Then install the rest (if needed):

```bash
pip install -r requirements.txt
```

On some networks, a mirror helps (example):

```bash
pip install paddlepaddle -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 3. Database

1. Create a PostgreSQL database, for example:

   ```sql
   CREATE DATABASE billdb;
   ```

2. Set the connection string (recommended: environment variable, not committed secrets):

   **Windows (PowerShell)**

   ```powershell
   $env:DATABASE_URL = "postgresql://USER:PASSWORD@localhost:5432/billdb"
   ```

   **macOS / Linux**

   ```bash
   export DATABASE_URL="postgresql://USER:PASSWORD@localhost:5432/billdb"
   ```

   Default in code (if `DATABASE_URL` is unset) is `postgresql://postgres:postgreSQL@localhost/billdb` — **change this** for your machine.

3. Tables are created automatically on first startup (`Base.metadata.create_all`). A default vendor row may be seeded for uploads.

## 4. Run the API

From `BillScannerServer` with the venv activated:

```bash
python main.py
```

Or:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- **API base:** `http://localhost:8000`
- **Versioned routes:** `http://localhost:8000/api/v1/...`
- **OpenAPI docs:** `http://localhost:8000/docs`

### Useful environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SQL_ECHO=1` | Log SQL statements (debug) |
| `EXPO_PUBLIC_API_BASE_URL` | Not used by server; for the mobile app |
| `API_LOG_SKIP_PATHS` | Comma-separated paths to skip in `api_request_logs` (default skips `/docs`, `/redoc`, etc.) |
| `API_LOG_LOG_OPTIONS=1` | Log `OPTIONS` (CORS) requests to DB |
| `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` | Reduces Paddle “model hoster” checks at startup |

## 5. Verify

```bash
curl http://localhost:8000/
```

Expect JSON with `"status": "healthy"`.

## 6. Request logging (debugging)

Successful and failed HTTP requests are written to the **`api_request_logs`** table (method, path, status, duration, client info; failures include a truncated response body and optional server traceback for unhandled errors).

## Project layout (short)

- `main.py` — FastAPI app, CORS, middleware, legacy routes
- `api/` — Routers (`bills`, `analytics`, `auth`, `vendors`)
- `models/` — SQLAlchemy models
- `services/` — OCR, parsing, file text extraction, LLM helpers
- `middleware/` — API request logging
- `uploads/` — Saved uploads (created at runtime)

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| `ModuleNotFoundError: paddle` / OCR errors | Install Paddle per official docs; match Python version. |
| DB connection refused | Start PostgreSQL; check `DATABASE_URL` host/port/user/password. |
| Upload fails with vendor error | Ensure vendor `id=1` exists (app seeds a default on first run). |
| Mobile app cannot reach API | Use machine LAN IP, not `localhost`, on a physical phone; set `EXPO_PUBLIC_API_BASE_URL` in the app. |

## License / course use

Use as needed for coursework; keep credentials out of git (`.env`, database passwords).
