class SkrybeException(Exception):
    """Base exception for Skrybe SDK errors."""
    pass

class ValidationException(SkrybeException):
    """Exception for validation errors in Skrybe SDK."""
    pass
