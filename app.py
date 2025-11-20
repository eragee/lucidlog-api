import os
import json

from flask import Flask, request
from helpers import rest_response, rest_error

from google import genai

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Client for Gemini Developer API.
# GEMINI_API_KEY is expected in the environment.
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

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
        log_entry,
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

    # Strip ```json ... ``` or ``` ... ``` fences if present
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
        # Attach debug only when present and not already in the object.
        obj.setdefault("_debug", debug_meta)

    return obj


@app.route("/explain-log", methods=["POST"])
def explain_log():
    body = request.get_json(silent=True) or {}
    log_entry = body.get("log")
    context = body.get("context")

    if not log_entry:
        return rest_error("Missing 'log' field in JSON body")

    try:
        prompt = build_prompt(log_entry, context)

        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
        )

        raw_text = extract_text_from_response(response)

        # Optional debug information when there is no text.
        debug_meta = None
        if not raw_text:
            debug_meta = {
                "has_candidates": bool(getattr(response, "candidates", None)),
                "prompt_feedback": getattr(response, "prompt_feedback", None),
            }

        parsed = parse_json_from_response(raw_text, log_entry, debug_meta=debug_meta)

        return rest_response(parsed)

    except Exception as e:
        return rest_error(f"Gemini API error: {e}")

@app.route("/")
def root():
    return app.send_static_file("index.html")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
