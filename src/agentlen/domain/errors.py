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


class AgentMaxIterationsError(DomainError):
    """Raised when the agent loop reaches the maximum number of iterations."""

    def __init__(self, max_iterations: int) -> None:
        self.max_iterations = max_iterations
        super().__init__(
            f"Agent did not converge after {max_iterations} iterations."
        )
