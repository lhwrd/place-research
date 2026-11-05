"""Address-related exceptions."""

from typing import Optional

from app.exceptions.base import ValidationError


class InvalidAddressError(ValidationError):
    """Raised when address format is invalid or cannot be geocoded."""

    def __init__(self, address: str, reason: Optional[str] = None):
        message = f"Invalid address:  {address}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, details={"address": address, "reason": reason})
