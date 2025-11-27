import json
from types import SimpleNamespace
from unittest import mock

from app import app


def make_dummy_gemini_response(payload: dict) -> object:
    """
    Creates a minimal object with a .text attribute that matches the
    structure expected by extract_text_from_response and parse_json_from_response.
    """
    return SimpleNamespace(text=json.dumps(payload))


@mock.patch("app.client.models.generate_content")
def test_explain_log_happy_path_log_only(mock_generate):
    # Mock Gemini returning a valid JSON object as text.
    mock_generate.return_value = make_dummy_gemini_response(
        {
            "summary": "Mock summary for test.",
            "severity": "ERROR",
            "component": "auth-service",
            "probable_causes": ["Mock cause 1", "Mock cause 2"],
            "recommended_actions": ["Mock action 1"],
            "raw_log": "test-log-line",
        }
    )

    client = app.test_client()
    resp = client.post(
        "/explain-log",
        json={"log": "2025-11-14T03:21:15Z ERROR auth-service Failed login"},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "OK"

    result = data["result"]
    assert result["summary"] == "Mock summary for test."
    assert result["severity"] == "ERROR"
    assert result["component"] == "auth-service"
    assert result["raw_log"] == "test-log-line"
    assert isinstance(result["probable_causes"], list)
    assert isinstance(result["recommended_actions"], list)

    # Ensure Gemini was called once.
    mock_generate.assert_called_once()


@mock.patch("app.client.models.generate_content")
def test_explain_log_happy_path_with_context(mock_generate):
    mock_generate.return_value = make_dummy_gemini_response(
        {
            "summary": "Summary with context.",
            "severity": "WARN",
            "component": "gateway",
            "probable_causes": ["Context-aware cause"],
            "recommended_actions": ["Context-aware action"],
            "raw_log": "test-log-line-with-context",
        }
    )

    client = app.test_client()
    resp = client.post(
        "/explain-log",
        json={
            "log": "2025-11-14T03:21:15Z WARN gateway Upstream 503",
            "context": {
                "host": "node-03",
                "cluster": "prod-gke-1",
            },
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "OK"

    result = data["result"]
    assert result["summary"] == "Summary with context."
    assert result["severity"] == "WARN"
    assert result["component"] == "gateway"
    assert result["raw_log"] == "test-log-line-with-context"

    mock_generate.assert_called_once()
    # Assert that context was included in the prompt indirectly by checking the call.
    args, kwargs = mock_generate.call_args
    contents = kwargs.get("contents") or (args[1] if len(args) > 1 else "")
    assert "prod-gke-1" in contents
    assert "node-03" in contents


def test_explain_log_invalid_payload_missing_log():
    client = app.test_client()
    resp = client.post("/explain-log", json={"foo": "bar"})

    # Missing 'log' should be treated as a client error.
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["status"] == "ERROR"
    assert "Missing 'log' field" in data["result"]


def test_explain_log_invalid_payload_wrong_type():
    client = app.test_client()
    # log is not a string; build_prompt will fail when concatenating.
    resp = client.post("/explain-log", json={"log": 123})

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["status"] == "ERROR"
    # Message is generic "Gemini API error: ..." with TypeError inside.
    assert "Gemini API error" in data["result"]


@mock.patch("app.client.models.generate_content")
def test_explain_log_upstream_failure(mock_generate):
    # Simulate upstream failure (timeout, network error, etc.).
    mock_generate.side_effect = TimeoutError("Upstream timeout")

    client = app.test_client()
    resp = client.post(
        "/explain-log",
        json={"log": "2025-11-14T01:00:00Z ERROR service Something bad"},
    )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["status"] == "ERROR"
    assert "Gemini API error" in data["result"]
    assert "Upstream timeout" in data["result"]
