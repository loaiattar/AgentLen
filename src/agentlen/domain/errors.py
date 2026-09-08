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
            code="UNSUPPORTED_OPERATOR",
            field_path=field_path,
            message=f"Operator '{operator}' is not in the allowed whitelist.",
        )


class UnknownTargetFieldError(ValidationError):
    """Raised when a mapping targets a field that doesn't exist in the schema."""

    def __init__(self, target: str, field_path: str) -> None:
        super().__init__(
            code="UNKNOWN_TARGET_FIELD",
            field_path=field_path,
            message=f"Target field '{target}' does not exist in the schema.",
        )


class InvalidOperatorParamError(ValidationError):
    """Raised when an operator's parameters are malformed (e.g. an uncompilable regex)."""

    def __init__(self, field_path: str, message: str) -> None:
        super().__init__(code="INVALID_OPERATOR_PARAM", field_path=field_path, message=message)


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
        super().__init__(
            f"Agent did not converge after {max_iterations} iterations."
        )
