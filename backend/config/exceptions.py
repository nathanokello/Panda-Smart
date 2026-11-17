"""Consistent error envelope for every non-2xx API response.

See architecture.md Section 4 for the agreed error shape.
"""
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

from core.errors import ConflictError


def _fields(detail):
    if isinstance(detail, dict):
        result = {}
        for key, value in detail.items():
            if isinstance(value, (list, tuple)):
                result[str(key)] = [str(item) for item in value]
            else:
                result[str(key)] = [str(value)]
        return result
    if isinstance(detail, (list, tuple)):
        return {"non_field_errors": [str(item) for item in detail]}
    return {}


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    code = "error"
    if isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
    elif isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        code = "unauthenticated"
        response.status_code = 401
    elif isinstance(exc, exceptions.PermissionDenied):
        code = "forbidden"
    elif isinstance(exc, exceptions.NotFound):
        code = "not_found"
    elif isinstance(exc, exceptions.Throttled):
        code = "rate_limited"
    elif isinstance(exc, ConflictError):
        code = "conflict"

    detail = response.data
    fields = _fields(detail)
    if isinstance(detail, dict) and set(detail) == {"detail"}:
        message = str(detail["detail"])
    elif fields:
        message = next(iter(fields.values()))[0]
    else:
        message = "Request could not be completed."

    response.data = {"error": {"code": code, "message": message, "fields": fields}}
    return response
