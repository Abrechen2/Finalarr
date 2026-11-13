"""Shared helpers for the JSON API blueprints."""

from __future__ import annotations

from flask import Flask, current_app, request
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ValidationError

from finalarr.crypto import SecretBox
from finalarr.db.session import Database
from finalarr.errors import api_error


class ApiProblem(Exception):
    """Raise to answer with ``{"error": {...}}``; caught by the app-wide handler."""

    def __init__(
        self, status: int, code: str, message: str, fields: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.fields = status, code, message, fields


def database() -> Database:
    db: Database = current_app.extensions["finalarr.db"]
    return db


def secrets() -> SecretBox:
    box: SecretBox = current_app.extensions["finalarr.secrets"]
    return box


def parse_body[M: BaseModel](model: type[M]) -> M:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiProblem(400, "bad_request", "Expected a JSON object")
    try:
        return model.model_validate(body)
    except ValidationError as error:
        fields = {
            ".".join(str(p) for p in issue["loc"]): issue["msg"].removeprefix("Value error, ")
            for issue in error.errors(include_input=False)
        }
        raise ApiProblem(400, "validation", "Invalid input", fields) from None


def not_found(what: str) -> ApiProblem:
    return ApiProblem(404, "not_found", f"{what} not found")


def register_error_handler(app: Flask) -> None:
    @app.errorhandler(ApiProblem)
    def _problem(problem: ApiProblem) -> ResponseReturnValue:
        response, status = api_error(problem.status, problem.code, problem.message)
        if problem.fields:
            body = response.get_json()
            body["error"]["fields"] = problem.fields
            response.set_data(current_app.json.dumps(body))
        return response, status
