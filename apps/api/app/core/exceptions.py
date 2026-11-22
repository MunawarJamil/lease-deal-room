class LeaseDealRoomError(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        code: str = "internal_error",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class NotFoundError(LeaseDealRoomError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404, code="not_found")


class ValidationError(LeaseDealRoomError):
    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message, status_code=422, code="validation_error")


class ParsingError(LeaseDealRoomError):
    def __init__(self, message: str = "Failed to parse document") -> None:
        super().__init__(message, status_code=422, code="parsing_error")


class VectorStoreError(LeaseDealRoomError):
    def __init__(self, message: str = "Vector store operation failed") -> None:
        super().__init__(message, status_code=502, code="vectorstore_error")


class LLMError(LeaseDealRoomError):
    def __init__(self, message: str = "LLM call failed") -> None:
        super().__init__(message, status_code=502, code="llm_error")


class AuditError(LeaseDealRoomError):
    def __init__(self, message: str = "Rent roll audit failed") -> None:
        super().__init__(message, status_code=500, code="audit_error")