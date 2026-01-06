"""Property search and management specific exceptions."""

from typing import Optional

from app.exceptions.base import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


class PropertyNotFoundError(NotFoundError):
    """Raised when property is not found."""

    def __init__(self, property_id: Optional[int] = None, address: Optional[str] = None):
        if property_id:
            message = f"Property with ID {property_id} not found"
            details = {"property_id": property_id}
        elif address:
            message = f"Property not found for address: {address}"
            details = {"address": address}
        else:
            message = "Property not found"
            details = {}

        super().__init__(message, details=details)


class InvalidAddressError(ValidationError):
    """Raised when address format is invalid or cannot be geocoded."""

    def __init__(self, address: str, reason: Optional[str] = None):
        message = f"Invalid address:  {address}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, details={"address": address, "reason": reason})


class PropertyAccessDeniedError(ForbiddenError):
    """Raised when user tries to access another user's property."""

    def __init__(self, property_id: int):
        super().__init__(
            f"Access denied to property {property_id}",
            details={"property_id": property_id},
        )


class DuplicatePropertyError(ConflictError):
    """Raised when attempting to save a property that's already saved."""

    def __init__(self, property_id: int):
        super().__init__(
            f"Property {property_id} is already in your saved properties",
            details={"property_id": property_id},
        )
