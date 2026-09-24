"""Errors raised by services, mapped to the API error shape (ARCHITECTURE.md section 11)."""

from typing import Any


class KatibError(Exception):
    """Base class. `code` is stable and machine-readable; `message` is safe to show a person."""

    code = "error"
    status = 400

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details


class NotFound(KatibError):
    code = "not_found"
    status = 404


class InvalidInput(KatibError):
    code = "invalid_input"
    status = 422


class ClassNameTaken(KatibError):
    code = "class_name_taken"
    status = 409


class ProjectNameTaken(KatibError):
    code = "project_name_taken"
    status = 409


class VersionConflict(KatibError):
    code = "version_conflict"
    status = 409


class ImportNotAllowed(KatibError):
    code = "import_not_allowed"
    status = 403
