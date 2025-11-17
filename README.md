# lucidlog-api

lucidlog-api is a lightweight Flask-based web service that transforms raw log entries into clear, structured explanations using **Gemini 2.5 Pro**. It converts cryptic logs into human-readable summaries, likely causes, severity, and recommended next steps—delivered in strictly formatted JSON.

---

## Features

- Uses **Gemini Pro** for high-quality reasoning.
- Accepts single log entries plus optional context.
- Returns clean, predictable JSON (no Markdown interpretation required).
- Deployable via Docker, Cloud Run, or any Python environment.
- API keys are injected at runtime—never stored in the repo.

---

## Requirements

- Python 3.12+
- A **Gemini API key**
- `pip` for installing dependencies
- (Optional) Docker for container builds

---

## Getting a Gemini API Key

A Gemini API key is required.

To generate one:

1. Go to **Google AI Studio**: https://aistudio.google.com  
2. Select **API Keys** on the left-hand side.  
3. Click **Create API Key**.  
4. Choose **Developer API**.  
5. Copy your key.

This key is private—**do not commit it to GitHub**.

---

## Setting the API Key

The environment variable `GEMINI_API_KEY` must be set before running the service.

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
gcloud run deploy lucidlog-api   --image gcr.io/PROJECT_ID/lucidlog-api   --region=us-central1   --set-env-vars=GEMINI_API_KEY=your-key-here
```

### Cloud Run (recommended: Secret Manager)

```bash
gcloud secrets create gemini-api-key --data-file=- <<EOF
your-key-here
EOF

gcloud run deploy lucidlog-api   --image gcr.io/PROJECT_ID/lucidlog-api   --region=us-central1   --set-secrets=GEMINI_API_KEY=gemini-api-key:latest
```

---

## Local Installation

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your-real-key"
python app.py
```

The service runs at:

```
http://localhost:8080
```

---

## API Usage

### `POST /explain-log`

#### Example Request

```json
{
  "log": "2025-11-14T01:23:45Z ERROR auth-service Failed login for user bob (401)",
  "context": {
    "host": "node-03",
    "cluster": "prod-gke-1"
  }
}
```

#### Example Response

```json
{
  "status": "OK",
  "result": {
    "summary": "The auth-service rejected a login attempt for the user 'bob' with HTTP 401.",
    "severity": "ERROR",
    "component": "auth-service",
    "probable_causes": [
      "Incorrect credentials",
      "Account lockout",
      "Outdated cached password"
    ],
    "recommended_actions": [
      "Verify the user's password",
      "Check authentication service metrics",
      "Investigate possible brute-force attempts"
    ],
    "raw_log": "2025-11-14T01:23:45Z ERROR auth-service Failed login for user bob (401)"
  }
}
```

---

## Docker Deployment

Build the container:

```bash
docker build -t lucidlog-api .
```

Run the container:

```bash
docker run -e GEMINI_API_KEY="your-real-key" -p 8080:8080 lucidlog-api
```

---

## Project Structure

```
.
├── app.py
├── helpers.py
├── requirements.txt
├── Dockerfile
└── README.md
```
