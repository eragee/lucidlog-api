import os
import json

from flask import Flask, request
from helpers import rest_response, rest_error

from google import genai
from google.genai import types

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Gemini client (Developer API using API key from env)
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

LOG_EXPLAINER_INSTRUCTIONS = """
You are a senior SRE helping a developer understand log entries.

Given:
- A single log line (possibly JSON or plain text)
- Optional context metadata

You must:
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
If you truly cannot interpret the log, say so in "summary" and leave the rest minimal.
"""

log_explainer_schema = types.Schema(
    type=types.Type.OBJECT,
    required=["summary", "severity", "raw_log"],
    properties={
        "summary": types.Schema(
            type=types.Type.STRING,
            description="1–3 sentence human explanation of the log entry."
        ),
        "severity": types.Schema(
            type=types.Type.STRING,
            description="Log severity level (e.g. DEBUG, INFO, WARN, ERROR, FATAL)."
        ),
        "component": types.Schema(
            type=types.Type.STRING,
            description="Service or component emitting the log.",
        ),
        "probable_causes": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
            description="List of likely causes."
        ),
        "recommended_actions": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
            description="Suggested next steps."
        ),
        "raw_log": types.Schema(
            type=types.Type.STRING,
            description="The original log entry."
        ),
    },
)

def build_prompt(log_entry: str, context: dict | None) -> str:
    prompt = "Explain this log entry for an engineer.\n\n"
    prompt += "LOG ENTRY:\n"
    prompt += log_entry
    prompt += "\n\n"
    if context:
        prompt += "ADDITIONAL CONTEXT (JSON):\n"
        prompt += json.dumps(context, indent=2)
        prompt += "\n\n"
    prompt += "Remember to respond ONLY with JSON as specified."
    return prompt

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
                response_mime_type="application/json",
                response_schema=log_explainer_schema,
            ),
            system_instruction=LOG_EXPLAINER_INSTRUCTIONS,
        )

        text = response.text or ""
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {
                "summary": text.strip() or "Model returned an empty response.",
                "severity": "INFO",
                "component": None,
                "probable_causes": [],
                "recommended_actions": [],
                "raw_log": log_entry,
            }

        return rest_response(parsed)

    except Exception as e:
        return rest_error(f"Gemini API error: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
