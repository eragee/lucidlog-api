import os
import json

from flask import Flask, request
from helpers import rest_response, rest_error

from google import genai
from google.genai import types

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False  # Keep "status" before "result"

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
    prompt = "Explain this log entry for an engineer.\n\n"
    prompt += "LOG ENTRY:\n"
    prompt += log_entry
    prompt += "\n\n"
    if context:
        prompt += "ADDITIONAL CONTEXT (JSON):\n"
        prompt += json.dumps(context, indent=2)
        prompt += "\n\n"
    prompt += "Return ONLY JSON as specified."
    return prompt


def extract_text_from_response(response) -> str:
    """
    Extracts concatenated text from all text parts in all candidates.
    Avoids using response.text directly to work around SDK issues.
    """
    texts = []
    try:
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    texts.append(part_text)
    except Exception:
        return ""
    return "\n".join(texts).strip()


def parse_json_from_response(text: str, log_entry: str) -> dict:
    """
    Attempts to parse a JSON object from model output.
    Handles responses wrapped in ```json code fences.
    """
    if not text:
        return {
            "summary": "Model returned an empty response.",
            "severity": "INFO",
            "component": None,
            "probable_causes": [],
            "recommended_actions": [],
            "raw_log": log_entry,
        }

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
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=512,
                system_instruction=LOG_EXPLAINER_INSTRUCTIONS,
            ),
        )

        raw_text = extract_text_from_response(response)
        parsed = parse_json_from_response(raw_text, log_entry)

        return rest_response(parsed)

    except Exception as e:
        return rest_error(f"Gemini API error: {e}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
