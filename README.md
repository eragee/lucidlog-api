# lucidlog-api

lucidlog-api is a lightweight Flask-based web service that converts raw log entries into structured, human-readable explanations using **Gemini 2.5 Pro**.  
A simple in-browser UI is included and served directly by Flask from the `static/` directory.

---

## Features

- Explains single log lines using Gemini Pro
- Optional contextual metadata to improve explanation accuracy
- Predictable JSON output (no Markdown)
- Included test UI served from the same Cloud Run service
- Single-container deployment (Flask + static UI)
- API key stored securely via Cloud Run or Secret Manager
- Automated tests using `pytest` with mocked Gemini calls
- OpenAPI description exposed at `/openapi.json`

---

## Project Structure

```text
.
├── app.py
├── helpers.py
├── requirements.txt
├── Dockerfile
├── static/
│   └── index.html
└── tests/
    └── test_app.py
```

Flask serves both API endpoints and the UI:

- `/` → test UI  
- `/explain-log` → JSON API endpoint  
- `/openapi.json` → OpenAPI description  

---

## Getting Started as a Developer

### Install dependencies

```bash
pip install -r requirements.txt
```

Set the API key:

```bash
export GEMINI_API_KEY="your-api-key"
```

### Run in development mode (hot reload)

#### macOS / Linux

```bash
export FLASK_ENV=development
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=8080
```

#### Windows (PowerShell)

```powershell
setx FLASK_ENV "development"
setx FLASK_APP "app.py"
flask run --host=0.0.0.0 --port=8080
```

Development mode enables:

- Live reload  
- Interactive debugger  
- Verbose logs  

Run without hot-reload:

```bash
python app.py
```

### Local logging for debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or:

```bash
export FLASK_DEBUG=1
```

---

## Getting a Gemini API Key

1. Open: https://aistudio.google.com  
2. Select **API Keys**  
3. Create a **Developer API** key  
4. Save securely  

---

## Setting the API Key

### macOS / Linux

```bash
export GEMINI_API_KEY="your-key"
```

### Windows

```powershell
setx GEMINI_API_KEY "your-key"
```

### Docker

```bash
docker run -e GEMINI_API_KEY="your-key" -p 8080:8080 lucidlog-api
```

### Cloud Run

```bash
gcloud run deploy lucidlog-api   --image gcr.io/PROJECT_ID/lucidlog-api   --region us-west1   --set-env-vars GEMINI_API_KEY=your-key
```

### Cloud Run with Secret Manager

```bash
gcloud secrets create gemini-api-key --data-file=- <<EOF
your-key
EOF

gcloud run deploy lucidlog-api   --image gcr.io/PROJECT_ID/lucidlog-api   --region us-west1   --set-secrets=GEMINI_API_KEY=gemini-api-key:latest
```

---

## Running Unit Tests

Tests use `pytest` and mock Gemini API calls.

### Run all tests

```bash
pytest
```

Or:

```bash
python -m pytest
```

### PyCharm

Right‑click the `tests/` folder → **Run 'pytest in tests'**.

---

## API Usage

### POST /explain-log

Example input:

```json
{ "log": "2025-11-14T03:21:15Z ERROR auth-service Failed login" }
```

Optional `context`:

```json
{
  "log": "...",
  "context": { "host": "node-03", "cluster": "prod-gke-1" }
}
```

---

## Response Schema

Every response has:

```json
{
  "status": "OK" | "ERROR",
  "result": { ... }
}
```

### Success

```json
{
  "summary": "string",
  "severity": "string",
  "component": "string or null",
  "probable_causes": ["string"],
  "recommended_actions": ["string"],
  "raw_log": "string"
}
```

### Error

```json
{
  "status": "ERROR",
  "result": "Error message string"
}
```

Optional development-only:

- `_debug`: diagnostic metadata

---

## Example Response

```json
{
  "status": "OK",
  "result": {
    "summary": "The 'auth-service' rejected a login attempt...",
    "severity": "ERROR",
    "component": "auth-service",
    "probable_causes": ["Incorrect credentials"],
    "recommended_actions": ["Check account status"],
    "raw_log": "..."
  }
}
```

---

## Built-In Test UI

Served from:

```text
/
```

Includes fields for:

- Log entry  
- Optional context  
- Pretty‑formatted explanation output  

---

## OpenAPI Description

Available at:

```text
/openapi.json
```

Contains:

- Request schema  
- Response schema  
- Error schema  

Works with Swagger UI, Postman, etc.

---

## Docker Deployment

### Build

```bash
docker build -t lucidlog-api .
```

### Run locally

```bash
docker run -e GEMINI_API_KEY="your-key" -p 8080:8080 lucidlog-api
```

### Deploy to Cloud Run

```bash
gcloud run deploy lucidlog-api   --image gcr.io/PROJECT_ID/lucidlog-api   --region us-west1   --allow-unauthenticated
```
