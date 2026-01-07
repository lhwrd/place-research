"""Test data factories for creating test objects."""

from typing import Optional

from faker import Faker
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.custom_location import CustomLocation
from app.models.property import Property
from app.models.saved_property import SavedProperty
from app.models.user import User

fake = Faker()


class UserFactory:
    """Factory for creating test users."""

    @staticmethod
    def create(
        db: Session,
        email: Optional[str] = None,
        password: str = "testpassword123",
        full_name: Optional[str] = None,
        is_active: bool = True,
        is_superuser: bool = False,
    ) -> User:
        """Create a test user."""
        user = User(
            email=email or fake.email(),
            hashed_password=get_password_hash(password),
            full_name=full_name or fake.name(),
            is_active=is_active,
            is_superuser=is_superuser,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def create_batch(db: Session, count: int = 5) -> list[User]:
        """Create multiple test users."""
        return [UserFactory.create(db) for _ in range(count)]


class PropertyFactory:
    """Factory for creating test properties."""

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        address: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        **kwargs,
    ) -> Property:
        """Create a test property."""
        property_data = {
            "user_id": user_id,
            "address": address or fake.street_address(),
            "city": fake.city(),
            "state": fake.state_abbr(),
            "zip_code": fake.zipcode(),
            "county": f"{fake.last_name()} County",
            "latitude": latitude or float(fake.latitude()),
            "longitude": longitude or float(fake.longitude()),
            "bedrooms": fake.random_int(1, 5),
            "bathrooms": fake.random_element([1, 1.5, 2, 2.5, 3, 3.5, 4]),
            "square_feet": fake.random_int(800, 4000),
            "lot_size": fake.random_int(3000, 10000),
            "year_built": fake.random_int(1950, 2023),
            "property_type": fake.random_element(["Single Family", "Condo", "Townhouse"]),
            "estimated_value": fake.random_int(200000, 1500000),
        }
        property_data.update(kwargs)

        property_record = Property(**property_data)
        db.add(property_record)
        db.commit()
        db.refresh(property_record)
        return property_record

    @staticmethod
    def create_batch(db: Session, user_id: int, count: int = 5) -> list[Property]:
        """Create multiple test properties."""
        return [PropertyFactory.create(db, user_id) for _ in range(count)]


class CustomLocationFactory:
    """Factory for creating test custom locations."""

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        name: Optional[str] = None,
        location_type: str = "family",
        **kwargs,
    ) -> CustomLocation:
        """Create a test custom location."""
        location_data = {
            "user_id": user_id,
            "name": name or f"{fake.first_name()}'s House",
            "description": fake.sentence(),
            "address": fake.street_address(),
            "city": fake.city(),
            "state": fake.state_abbr(),
            "zip_code": fake.zipcode(),
            "latitude": float(fake.latitude()),
            "longitude": float(fake.longitude()),
            "location_type": location_type,
            "priority": fake.random_int(0, 100),
            "is_active": True,
        }
        location_data.update(kwargs)

        location = CustomLocation(**location_data)
        db.add(location)
        db.commit()
        db.refresh(location)
        return location

    @staticmethod
    def create_batch(db: Session, user_id: int, count: int = 3) -> list[CustomLocation]:
        """Create multiple test custom locations."""
        return [CustomLocationFactory.create(db, user_id) for _ in range(count)]
