class DomainError(Exception):
    """Base class for all domain errors."""


class ValidationError(DomainError):
    """Raised when a mapping document fails validation."""

    def __init__(self, code: str, field_path: str, message: str) -> None:
        self.code = code
        self.field_path = field_path
        self.message = message
        super().__init__(f"[{code}] {field_path}: {message}")


class UnsupportedOperatorError(ValidationError):
    """Raised when a mapping uses an operator outside the whitelist."""

    def __init__(self, operator: str, field_path: str) -> None:
        super().__init__(
            code="MAPPING_UNKNOWN_OPERATOR",
            field_path=field_path,
            message=f"Operator '{operator}' is not in the allowed whitelist.",
        )


class UnknownTargetFieldError(ValidationError):
    """Raised when a mapping targets a field that doesn't exist in the schema."""

    def __init__(self, target: str, field_path: str) -> None:
        super().__init__(
            code="MAPPING_UNKNOWN_TARGET",
            field_path=field_path,
            message=f"Target field '{target}' does not exist in the schema.",
        )


class MissingNaturalKeyError(ValidationError):
    """Raised when an entity declares no natural_key (MAPPING_CONTRACT.md §4:
    structural check — deduplication has nothing to key off)."""

    def __init__(self, target: str, field_path: str) -> None:
        super().__init__(
            code="MAPPING_MISSING_NATURAL_KEY",
            field_path=field_path,
            message=f"Entity '{target}' declares no natural_key.",
        )


class InvalidNaturalKeyFieldError(ValidationError):
    """A natural key must name a value the transformation engine produces."""

    def __init__(self, target: str, key: str, field_path: str) -> None:
        super().__init__(
            code="MAPPING_INVALID_NATURAL_KEY",
            field_path=field_path,
            message=f"Natural key field '{key}' is not produced for entity '{target}'.",
        )


class MissingSequenceIndexError(ValidationError):
    """A non-iterated call needs an explicit stable index across source records."""

    def __init__(self, target: str, field_path: str) -> None:
        super().__init__(
            code="MAPPING_MISSING_SEQUENCE_INDEX",
            field_path=field_path,
            message=(
                f"Non-iterated entity '{target}' must map 'sequence_index' explicitly; "
                "the per-record fallback would always be zero."
            ),
        )


class UnsupportedPathError(ValidationError):
    """Raised when a path is outside the notation of domain/services/json_path.py.
    The parser leaves `field_path` empty; the validator fills in the location."""

    def __init__(self, path: str, reason: str, field_path: str = "") -> None:
        self.path = path
        self.reason = reason
        super().__init__(
            code="MAPPING_UNSUPPORTED_PATH",
            field_path=field_path,
            message=f"Path '{path}' is not supported: {reason}.",
        )


class InvalidOperatorParamError(ValidationError):
    """Raised when an operator's parameters are malformed (e.g. an uncompilable regex)."""

    def __init__(self, field_path: str, message: str) -> None:
        super().__init__(code="INVALID_OPERATOR_PARAM", field_path=field_path, message=message)


class InvalidEmailError(ValidationError):
    """Raised when a user-supplied e-mail address fails the format check."""

    def __init__(self, email: str) -> None:
        super().__init__(
            code="INVALID_EMAIL",
            field_path="email",
            message=f"'{email}' n'est pas une adresse e-mail valide.",
        )


class WeakPasswordError(ValidationError):
    """Raised when a password fails the minimum-strength policy."""

    def __init__(self, message: str) -> None:
        super().__init__(code="WEAK_PASSWORD", field_path="password", message=message)


class OperatorFailedError(DomainError):
    """Raised by an operator on a data-level failure, carrying a stable ImportIssue code.

    Distinct from InvalidOperatorParamError: this is about the *data* being
    unprocessable (e.g. an unparsable date), not the operator's own params
    being malformed.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class AgentMaxIterationsError(DomainError):
    """Raised when the agent loop reaches the maximum number of iterations."""

    def __init__(self, max_iterations: int) -> None:
        self.max_iterations = max_iterations
        super().__init__(f"Agent did not converge after {max_iterations} iterations.")
