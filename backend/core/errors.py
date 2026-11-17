from rest_framework.exceptions import APIException


class ConflictError(APIException):
    status_code = 409
    default_detail = "The request conflicts with the current state."
    default_code = "conflict"
