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

---

## Project Structure

```text
.
├── app.py
├── helpers.py
├── requirements.txt
├── Dockerfile
├── static/
│   └── index.html     ← Test UI (React SPA)
└── tests/
    └── test_app.py    ← Unit tests for /explain-log
```

Flask serves both API endpoints and the UI:

- `/` → test UI  
- `/explain-log` → JSON API endpoint  

---

## Getting a Gemini API Key

A Gemini API key is required.

1. Go to **Google AI Studio**: https://aistudio.google.com  
2. Select **API Keys**  
3. Choose **Create API Key → Developer API**  
4. Copy the key

Do not store this key in version control.

---

## Setting the API Key

Set the environment variable `GEMINI_API_KEY` before running the service.

### macOS / Linux

```bash
export GEMINI_API_KEY="your-key-here"
```

### Windows (PowerShell)

```powershell
setx GEMINI_API_KEY "your-key-here"
```

### Docker

```bash
docker run -e GEMINI_API_KEY="your-key" -p 8080:8080 lucidlog-api
```

### Cloud Run (simple env var)

```bash
gcloud run deploy lucidlog-api   --image gcr.io/PROJECT_ID/lucidlog-api   --region us-west1   --set-env-vars GEMINI_API_KEY=your-key-here
```

### Cloud Run (recommended: Secret Manager)

```bash
gcloud secrets create gemini-api-key --data-file=- <<EOF
your-key-here
EOF

gcloud run deploy lucidlog-api   --image gcr.io/PROJECT_ID/lucidlog-api   --region us-west1   --set-secrets=GEMINI_API_KEY=gemini-api-key:latest
```

---

## Local Installation

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your-real-key"
python app.py
```

Open the built-in UI at:

```text
http://localhost:8080
```

---

## API Usage

### POST /explain-log

The payload must include:

- `log`: A single log line in plain text

The payload may optionally include:

- `context`: A JSON object with metadata such as host, pod, cluster, region, or trace ID

Example without context:

```json
{
  "log": "2025-11-14T03:21:15Z ERROR auth-service Failed login for user alice (401)"
}
```

Example with context:

```json
{
  "log": "2025-11-14T03:21:15Z ERROR auth-service Failed login for user alice (401)",
  "context": {
    "host": "node-03",
    "cluster": "prod-gke-1",
    "pod": "auth-7d4f9c6d8b-xyz"
  }
}
```

---

## Understanding the `context` Field

The `context` field is optional.  
When present, it provides additional signals that help Gemini generate more accurate and environment-aware explanations.

Useful context fields may include:

- Host or node name  
- Kubernetes pod  
- Cluster / namespace  
- Region  
- Request ID / trace ID  
- Deployment version  

Example:

```json
{
  "context": {
    "host": "node-17",
    "cluster": "prod-gke-1",
    "trace_id": "df102abf34"
  }
}
```

If omitted, the model relies solely on the log line.

---

## Example Response

```json
{
  "status": "OK",
  "result": {
    "summary": "The 'auth-service' rejected a login attempt from user 'alice' because the provided credentials were unauthorized (HTTP 401).",
    "severity": "ERROR",
    "component": "auth-service",
    "probable_causes": [
      "Incorrect credentials",
      "Locked or disabled account",
      "Malformed or expired token"
    ],
    "recommended_actions": [
      "Verify credentials",
      "Check account status",
      "Inspect authentication tokens"
    ],
    "raw_log": "2025-11-14T03:21:15Z ERROR auth-service Failed login for user alice (401)"
  }
}
```

---

## Built-In Test UI

The test UI is a small React page served from the `/` route via Flask.  
It provides fields for:

- Log entry  
- Optional context  
- JSON output display in a structured HTML layout  

It requires no separate deployment and runs inside the same container as the API.

Open it locally or on Cloud Run:

```text
https://<cloud-run-service-url>/
```

---

## Running Unit Tests

Unit tests are written using `pytest` and live in the `tests/` directory.  
The Gemini API client is mocked so no real network calls are made.

### Install test dependencies

If `pytest` is listed in `requirements.txt`, install as usual:

```bash
pip install -r requirements.txt
```

Otherwise, install directly:

```bash
pip install pytest
```

### Run all tests from the command line

From the project root:

```bash
pytest
```

or explicitly via Python:

```bash
python -m pytest
```

## Docker Deployment

Build:

```bash
docker build -t lucidlog-api .
```

Run locally:

```bash
docker run -e GEMINI_API_KEY="your-key" -p 8080:8080 lucidlog-api
```

Deploy to Cloud Run:

```bash
gcloud run deploy lucidlog-api   --image gcr.io/PROJECT_ID/lucidlog-api   --region us-west1   --allow-unauthenticated
```
