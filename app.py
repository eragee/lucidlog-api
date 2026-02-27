import os
import json
import time
import uuid
import logging

from flask import Flask, request, Response
from helpers import rest_response, rest_error
from google import genai

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logger = logging.getLogger("lucidlog")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    # Formatter prints only the message, which in this case is JSON
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
MODEL_NAME = "gemini-2.5-pro"
MAX_LOG_CHARS = 4000

LOG_EXPLAINER_INSTRUCTIONS = """
You are a senior SRE helping a developer understand log entries.

Given:
- A single log line (possibly JSON or plain text)
- Optional context metadata

Goals:
- Parse or infer: timestamp, severity, component/service, and main event
- Explain in plain English what happened
- Infer likely causes and recommended next troubleshooting steps

Output ONLY JSON with the following schema:
{
  "summary": string,
  "severity": string,
  "component": string | null,
  "probable_causes": string[],
  "recommended_actions": string[],
  "raw_log": string
}
Do not add any extra fields.
If the log cannot be interpreted, state that in "summary" and keep other fields minimal.
"""


def build_prompt(log_entry: str, context: dict | None) -> str:
    parts = [
        LOG_EXPLAINER_INSTRUCTIONS.strip(),
        "",
        "LOG ENTRY:",
        str(log_entry),
    ]

    if context:
        parts.extend(
            [
                "",
                "ADDITIONAL CONTEXT (JSON):",
                json.dumps(context, indent=2),
            ]
        )

    parts.extend(
        [
            "",
            "Return ONLY JSON as specified above.",
        ]
    )

    return "\n".join(parts)


def extract_text_from_response(response) -> str:
    """
    Extracts text from the response object.
    Uses response.text first, then candidate parts as a fallback.
    """
    if getattr(response, "text", None):
        return response.text.strip()

    texts = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                texts.append(part_text)

    return "\n".join(texts).strip()


def parse_json_from_response(text: str, log_entry: str, debug_meta: dict | None = None) -> dict:
    """
    Attempts to parse a JSON object from model output.
    Handles responses wrapped in ```json code fences.
    If parsing fails, returns a fallback structure with the raw text in the summary.
    """
    if not text:
        result = {
            "summary": "Model returned an empty response.",
            "severity": "INFO",
            "component": None,
            "probable_causes": [],
            "recommended_actions": [],
            "raw_log": log_entry,
        }
        if debug_meta:
            result["_debug"] = debug_meta
        return result

    cleaned = text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        obj = {
            "summary": cleaned,
            "severity": "INFO",
            "component": None,
            "probable_causes": [],
            "recommended_actions": [],
            "raw_log": log_entry,
        }

    obj.setdefault("raw_log", log_entry)

    if debug_meta is not None:
        obj.setdefault("_debug", debug_meta)

    return obj


def validate_request_payload(body: dict) -> tuple[str | None, dict | None, str | None]:
    """Validates request JSON and returns (log_entry, context, error_message)."""
    log_entry = body.get("log")
    context = body.get("context")

    if log_entry is None:
        return None, None, "Missing 'log' field in JSON body"

    if not isinstance(log_entry, str) or not log_entry.strip():
        return None, None, "'log' must be a non-empty string"

    if len(log_entry) > MAX_LOG_CHARS:
        return None, None, f"'log' must be <= {MAX_LOG_CHARS} characters"

    if context is not None and not isinstance(context, dict):
        return None, None, "'context' must be a JSON object when provided"

    return log_entry.strip(), context, None


def normalize_result_shape(obj: dict, log_entry: str) -> dict:
    """Ensures model output always matches the public response schema types."""
    summary = obj.get("summary")
    severity = obj.get("severity")
    component = obj.get("component")
    probable_causes = obj.get("probable_causes")
    recommended_actions = obj.get("recommended_actions")

    normalized = {
        "summary": summary if isinstance(summary, str) and summary else "No summary provided.",
        "severity": severity if isinstance(severity, str) and severity else "INFO",
        "component": component if isinstance(component, str) or component is None else None,
        "probable_causes": probable_causes if isinstance(probable_causes, list) else [],
        "recommended_actions": recommended_actions if isinstance(recommended_actions, list) else [],
        "raw_log": log_entry,
    }

    if "_debug" in obj:
        normalized["_debug"] = obj["_debug"]

    return normalized


@app.route("/explain-log", methods=["POST"])
def explain_log():
    request_id = str(uuid.uuid4())
    start_time = time.time()
    status_label = "OK"
    error_message = None

    body = request.get_json(silent=True) or {}
    log_entry, context, validation_error = validate_request_payload(body)

    try:
        if validation_error:
            status_label = "ERROR"
            return rest_error(validation_error)

        if not client:
            status_label = "ERROR"
            return rest_error("Server missing GEMINI_API_KEY configuration")

        prompt = build_prompt(log_entry, context)

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )

        raw_text = extract_text_from_response(response)

        debug_meta = None
        if not raw_text:
            debug_meta = {
                "has_candidates": bool(getattr(response, "candidates", None)),
                "prompt_feedback": getattr(response, "prompt_feedback", None),
            }

        parsed = parse_json_from_response(raw_text, log_entry, debug_meta=debug_meta)
        parsed = normalize_result_shape(parsed, log_entry)

        return rest_response(parsed)

    except Exception as e:
        status_label = "ERROR"
        error_message = str(e)
        return rest_error(f"Gemini API error: {e}")

    finally:
        latency_ms = (time.time() - start_time) * 1000.0
        log_record = {
            "request_id": request_id,
            "path": request.path,
            "method": request.method,
            "status": status_label,
            "model": MODEL_NAME,
            "latency_ms": round(latency_ms, 2),
        }
        if error_message:
            log_record["error"] = error_message

        logger.info(json.dumps(log_record))


@app.route("/")
def root():
    return app.send_static_file("index.html")


@app.route("/healthz", methods=["GET"])
def healthz():
    return rest_response({
        "service": "lucidlog-api",
        "status": "healthy",
        "gemini_configured": bool(GEMINI_API_KEY),
        "model": MODEL_NAME,
    })


openapi_spec = {
    "openapi": "3.1.0",
    "info": {
        "title": "lucidlog-api",
        "version": "1.0.0",
        "description": "LLM-powered log explanation service backed by Gemini Pro."
    },
    "paths": {
        "/healthz": {
            "get": {
                "summary": "Service health check",
                "operationId": "healthz",
                "responses": {
                    "200": {
                        "description": "Service health status"
                    }
                }
            }
        },
        "/explain-log": {
            "post": {
                "summary": "Explain a single log entry",
                "operationId": "explainLog",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ExplainLogRequest"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Successful explanation",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ExplainLogResponse"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid input or upstream error",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ExplainLogResponse"
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "ExplainLogRequest": {
                "type": "object",
                "required": ["log"],
                "properties": {
                    "log": {
                        "type": "string",
                        "maxLength": MAX_LOG_CHARS,
                        "description": "Single log line to explain."
                    },
                    "context": {
                        "type": "object",
                        "description": "Optional contextual metadata (host, pod, cluster, trace ID, etc.). Must be a JSON object.",
                        "additionalProperties": True
                    }
                }
            },
            "ExplainLogResult": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "severity": {"type": "string"},
                    "component": {
                        "type": ["string", "null"]
                    },
                    "probable_causes": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "recommended_actions": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "raw_log": {"type": "string"},
                    "_debug": {
                        "type": "object",
                        "description": "Optional diagnostic information for debugging model responses.",
                        "additionalProperties": True
                    }
                },
                "required": ["summary", "severity", "component", "probable_causes", "recommended_actions", "raw_log"]
            },
            "ExplainLogResponse": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["OK", "ERROR"]
                    },
                    "result": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/ExplainLogResult"},
                            {"type": "string"}
                        ]
                    }
                },
                "required": ["status", "result"]
            }
        }
    }
}


@app.route("/openapi.json", methods=["GET"])
def openapi_json():
    return Response(
        json.dumps(openapi_spec),
        mimetype="application/json"
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
