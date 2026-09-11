"""Application-layer errors.

The domain owns rule violations (`domain/errors.py`). These three describe
situations the *application* runs into while orchestrating: something asked for
does not exist, something conflicts with what is already stored, or an outbound
adapter misbehaved.

They carry a stable machine-readable `code` because the API contract promises
one on every error (API.md §1). Keeping them here rather than in
`interfaces/http/` means a CLI or a worker reports the same codes as the API.
"""

from __future__ import annotations

from typing import Any


class ApplicationError(Exception):
    """Base class for application-layer failures."""

    code = "APPLICATION_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details: dict[str, Any] = details or {}
        super().__init__(message)


class NotFoundError(ApplicationError):
    """A requested resource does not exist. -> 404"""

    code = "NOT_FOUND"

    def __init__(self, resource: str, identifier: object) -> None:
        super().__init__(
            f"{resource} '{identifier}' does not exist.",
            details={"resource": resource, "id": str(identifier)},
        )


class ConflictError(ApplicationError):
    """The request conflicts with stored state. -> 409"""

    code = "CONFLICT"


class MappingInvalidError(ApplicationError):
    """A mapping document failed validation. -> 422

    Carries **every** error, not the first one. A user correcting a mapping one
    error per round trip is a user who gives up; MAPPING_CONTRACT.md §4 requires
    the full list, each with its code and the path of the offending field.
    """

    code = "MAPPING_INVALID"

    def __init__(self, errors: list[dict[str, str | None]]) -> None:
        super().__init__(
            f"Le mapping comporte {len(errors)} erreur(s) de validation.",
            details={"errors": errors},
        )
        self.errors = errors


class ImportInterruptedError(ApplicationError):
    """An import stopped on an unexpected failure, at a known place in the file.

    Carries positions only — `first_line` to `last_line`, or from `first_line`
    on when the end is unknown — never the failure's text, which can hold trace
    content (#153). The worker writes these numbers into `error_summary`.
    """

    code = "IMPORT_INTERRUPTED"

    def __init__(self, *, first_line: int, last_line: int | None = None) -> None:
        self.first_line = first_line
        self.last_line = last_line
        super().__init__(f"Import interrompu : {describe_lines(first_line, last_line)}.")


def describe_lines(first_line: int, last_line: int | None) -> str:
    if last_line is None:
        return f"à partir de la ligne {first_line}"
    if last_line == first_line:
        return f"ligne {first_line}"
    return f"lignes {first_line} à {last_line}"


class AnalyzerError(ApplicationError):
    """The AI provider failed or returned a non-conforming response. -> 502

    Deliberately distinct from a 500: the fault is upstream, not ours, and the
    front is expected to offer a retry rather than report a bug.
    """

    code = "ANALYZER_FAILED"


class InvalidCredentialsError(ApplicationError):
    """Login failed. -> 401

    Raised identically whether the e-mail is unknown or the password is
    wrong — the two cases must not be distinguishable from the response, or
    the endpoint becomes an oracle for which e-mails have an account.
    """

    code = "INVALID_CREDENTIALS"

    def __init__(self) -> None:
        super().__init__("Adresse e-mail ou mot de passe incorrect.")


class UnauthenticatedError(ApplicationError):
    """No valid session on a route that requires one. -> 401

    Distinct from the app-wide `X-API-Key` gate (interfaces/http/auth.py):
    that key authenticates the front-end application, this authenticates the
    person using it.
    """

    code = "UNAUTHENTICATED"

    def __init__(self) -> None:
        super().__init__("Authentification requise.")
