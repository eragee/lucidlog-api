import json
from types import SimpleNamespace
from unittest import mock

import app as app_module
from app import app


def make_dummy_gemini_response(payload: dict) -> object:
    return SimpleNamespace(text=json.dumps(payload))


def with_mock_client(return_value=None, side_effect=None):
    generate_content = mock.Mock(return_value=return_value, side_effect=side_effect)
    dummy_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    return mock.patch.object(app_module, "client", dummy_client), generate_content


def test_explain_log_happy_path_log_only():
    patcher, generate_content = with_mock_client(
        return_value=make_dummy_gemini_response(
            {
                "summary": "Mock summary for test.",
                "severity": "ERROR",
                "component": "auth-service",
                "probable_causes": ["Mock cause 1", "Mock cause 2"],
                "recommended_actions": ["Mock action 1"],
                "raw_log": "test-log-line",
            }
        )
    )

    with patcher:
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
    assert result["raw_log"] == "2025-11-14T03:21:15Z ERROR auth-service Failed login"
    assert isinstance(result["probable_causes"], list)
    assert isinstance(result["recommended_actions"], list)

    generate_content.assert_called_once()


def test_explain_log_happy_path_with_context():
    patcher, generate_content = with_mock_client(
        return_value=make_dummy_gemini_response(
            {
                "summary": "Summary with context.",
                "severity": "WARN",
                "component": "gateway",
                "probable_causes": ["Context-aware cause"],
                "recommended_actions": ["Context-aware action"],
                "raw_log": "test-log-line-with-context",
            }
        )
    )

    with patcher:
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

    generate_content.assert_called_once()
    _, kwargs = generate_content.call_args
    contents = kwargs.get("contents", "")
    assert "prod-gke-1" in contents
    assert "node-03" in contents


def test_explain_log_invalid_payload_missing_log():
    client = app.test_client()
    resp = client.post("/explain-log", json={"foo": "bar"})

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["status"] == "ERROR"
    assert "Missing 'log' field" in data["result"]


def test_explain_log_invalid_payload_wrong_log_type():
    client = app.test_client()
    resp = client.post("/explain-log", json={"log": 123})

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["status"] == "ERROR"
    assert "non-empty string" in data["result"]


def test_explain_log_invalid_payload_wrong_context_type():
    client = app.test_client()
    resp = client.post("/explain-log", json={"log": "msg", "context": "bad"})

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["status"] == "ERROR"
    assert "'context' must be a JSON object" in data["result"]


def test_explain_log_normalizes_result_shape():
    patcher, _ = with_mock_client(
        return_value=make_dummy_gemini_response(
            {
                "summary": "",
                "severity": 999,
                "component": ["bad"],
                "probable_causes": "oops",
                "recommended_actions": None,
            }
        )
    )

    with patcher:
        client = app.test_client()
        resp = client.post("/explain-log", json={"log": "sample"})

    assert resp.status_code == 200
    result = resp.get_json()["result"]
    assert result["summary"] == "No summary provided."
    assert result["severity"] == "INFO"
    assert result["component"] is None
    assert result["probable_causes"] == []
    assert result["recommended_actions"] == []


def test_explain_log_upstream_failure():
    patcher, _ = with_mock_client(side_effect=TimeoutError("Upstream timeout"))

    with patcher:
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


def test_healthz_endpoint():
    client = app.test_client()
    resp = client.get("/healthz")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "OK"
    assert data["result"]["service"] == "lucidlog-api"
    assert data["result"]["status"] == "healthy"
    assert data["result"]["gemini_configured"] == bool(app_module.GEMINI_API_KEY)
