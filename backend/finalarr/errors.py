"""Uniform API error bodies: ``{"error": {"code", "message"}}``."""

from flask import Response, jsonify


def api_error(status: int, code: str, message: str) -> tuple[Response, int]:
    return jsonify(error={"code": code, "message": message}), status
