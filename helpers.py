import json
from flask import Response


def rest_response(obj):
    """
    Generates a standard success response with a fixed key order.
    Output format:
    {
        "status": "OK",
        "result": <object>
    }
    """
    payload = {
        "status": "OK",
        "result": obj
    }

    return Response(
        json.dumps(payload, ensure_ascii=False),
        mimetype="application/json"
    )


def rest_error(message: str):
    """
    Generates a standard error response with a fixed key order.
    Output format:
    {
        "status": "ERROR",
        "result": <message>
    }
    """
    payload = {
        "status": "ERROR",
        "result": message
    }

    return Response(
        json.dumps(payload, ensure_ascii=False),
        mimetype="application/json",
        status=400
    )
