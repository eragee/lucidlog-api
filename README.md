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
│   └── index.html     ← Test UI (React SPA)
└── tests/
    └── test_app.py    ← Unit tests for /explain-log
```

Flask serves both API endpoints and the UI:

- `/` → test UI  
- `/explain-log` → JSON API endpoint  
- `/openapi.json` → OpenAPI description of the API  

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

## Response Schema

All responses from `/explain-log` follow a wrapper structure:

```json
{
  "status": "OK" | "ERROR",
  "result": { ... }
}
```

### Success (`status: "OK"`)

For successful explanations, `result` is an object with the following fields:

```json
{
  "summary": "string",
  "severity": "string",
  "component": "string or null",
  "probable_causes": ["string", "..."],
  "recommended_actions": ["string", "..."],
  "raw_log": "string"
}
```

- `summary`  
  High-level natural language explanation of what the log line represents.

- `severity`  
  Normalized severity inferred from the log, typically one of: `ERROR`, `WARN`, `INFO`.  
  The value is not strictly enforced, so other strings are possible.

- `component`  
  The logical component or service inferred from the log (for example, `auth-service`, `gateway`).  
  May be `null` if no component can be inferred.

- `probable_causes`  
  Array of strings. Each entry describes a plausible cause for the event described by the log.

- `recommended_actions`  
  Array of strings. Each entry describes a concrete step that may help investigate or resolve the issue.

- `raw_log`  
  Echo of the original log line that was sent in the request, or a close approximation when the model response is used directly.

Additional internal fields may appear in some edge cases:

- `_debug` (optional)  
  Present only when the service attaches diagnostic information for empty or blocked model responses.  
  This field is not intended for consumers in production use.

### Error (`status: "ERROR"`)

For error responses (validation errors, upstream failures, etc.), `result` is a human-readable message string:

```json
{
  "status": "ERROR",
  "result": "Gemini API error: Upstream timeout"
}
```

Clients can rely on:

- `status` always being present and equal to `"OK"` or `"ERROR"`.  
- When `status === "OK"`, `result` being a structured explanation object.  
- When `status === "ERROR"`, `result` being an error message.

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
- JSON output formatted into readable sections (summary, severity, component, probable causes, recommended actions, raw log)  

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

### Running tests in PyCharm

1. Open the project in PyCharm.  
2. Ensure the project interpreter has `pytest` installed.  
3. Right-click the `tests/` folder → **Run 'pytest in tests'**.  

Individual tests can be run by clicking the gutter icon next to a test function in `test_app.py`.

---

## OpenAPI Description

An OpenAPI description of the service is exposed at:

```text
/openapi.json
```

This document describes:

- Request schema for `POST /explain-log`
- Wrapper response structure (`status`, `result`)
- Explanation result fields (summary, severity, component, probable_causes, recommended_actions, raw_log)

It can be used with tools such as Swagger UI or Postman to explore the API.

---

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
