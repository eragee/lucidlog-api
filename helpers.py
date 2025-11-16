from flask import jsonify

def rest_response(obj):
    return jsonify({
        "status": "OK",
        "result": obj
    })

def rest_error(message: str):
    return jsonify({
        "status": "ERROR",
        "result": message
    }), 400
