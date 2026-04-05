"""Custom exceptions for authentication."""


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    def __init__(self, message: str, mfa_required: bool = False):
        self.message = message
        self.mfa_required = mfa_required
        super().__init__(message)
