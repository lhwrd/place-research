"""Address parsing utilities."""

import logging
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AddressParser:
    """
    Parse and validate address components.

    Useful for extracting structured data from unstructured address strings.
    """

    # US state abbreviations
    US_STATES = {
        "AL": "Alabama",
        "AK": "Alaska",
        "AZ": "Arizona",
        "AR": "Arkansas",
        "CA": "California",
        "CO": "Colorado",
        "CT": "Connecticut",
        "DE": "Delaware",
        "FL": "Florida",
        "GA": "Georgia",
        "HI": "Hawaii",
        "ID": "Idaho",
        "IL": "Illinois",
        "IN": "Indiana",
        "IA": "Iowa",
        "KS": "Kansas",
        "KY": "Kentucky",
        "LA": "Louisiana",
        "ME": "Maine",
        "MD": "Maryland",
        "MA": "Massachusetts",
        "MI": "Michigan",
        "MN": "Minnesota",
        "MS": "Mississippi",
        "MO": "Missouri",
        "MT": "Montana",
        "NE": "Nebraska",
        "NV": "Nevada",
        "NH": "New Hampshire",
        "NJ": "New Jersey",
        "NM": "New Mexico",
        "NY": "New York",
        "NC": "North Carolina",
        "ND": "North Dakota",
        "OH": "Ohio",
        "OK": "Oklahoma",
        "OR": "Oregon",
        "PA": "Pennsylvania",
        "RI": "Rhode Island",
        "SC": "South Carolina",
        "SD": "South Dakota",
        "TN": "Tennessee",
        "TX": "Texas",
        "UT": "Utah",
        "VT": "Vermont",
        "VA": "Virginia",
        "WA": "Washington",
        "WV": "West Virginia",
        "WI": "Wisconsin",
        "WY": "Wyoming",
        "DC": "District of Columbia",
    }

    @classmethod
    def parse(cls, address: str) -> Dict[str, Optional[str]]:
        """
        Parse an address string into components.

        Args:
            address: Address string to parse

        Returns:
            Dictionary with extracted components:
            {
                "street_number": str,
                "street_name": str,
                "unit": str,
                "city":  str,
                "state": str,
                "zip_code":  str
            }
        """
        components = {
            "street_number": None,
            "street_name": None,
            "unit": None,
            "city": None,
            "state": None,
            "zip_code": None,
        }

        # Extract ZIP code (5 or 9 digits)
        zip_match = re.search(r"\b(\d{5})(? :-(\d{4}))?\b", address)
        if zip_match:
            components["zip_code"] = zip_match.group(0)
            address = address.replace(zip_match.group(0), "").strip()

        # Extract state (2-letter code)
        state_match = re.search(r"\b([A-Z]{2})\b", address)
        if state_match and state_match.group(1) in cls.US_STATES:
            components["state"] = state_match.group(1)
            address = address.replace(state_match.group(0), "").strip()

        # Split remaining by comma
        parts = [p.strip() for p in address.split(",")]

        if len(parts) >= 1:
            # First part is usually street address
            street_part = parts[0]

            # Extract street number
            number_match = re.match(r"^(\d+[A-Za-z]? )\s+(. +)$", street_part)
            if number_match:
                components["street_number"] = number_match.group(1)
                components["street_name"] = number_match.group(2)
            else:
                components["street_name"] = street_part

            # Extract unit/apartment
            unit_match = re.search(
                r"(? :apt|apartment|unit|suite|ste|#)\s*([A-Za-z0-9-]+)",
                components["street_name"],
                re.IGNORECASE,
            )
            if unit_match:
                components["unit"] = unit_match.group(1)
                # Remove unit from street name
                components["street_name"] = components["street_name"][: unit_match.start()].strip()

        if len(parts) >= 2:
            # Second part is usually city
            components["city"] = parts[1].strip()

        return components

    @classmethod
    def validate_zip_code(cls, zip_code: str) -> bool:
        """Validate US ZIP code format."""
        return bool(re.match(r"^\d{5}(? :-\d{4})?$", zip_code))

    @classmethod
    def validate_state(cls, state: str) -> bool:
        """Validate US state code."""
        return state.upper() in cls.US_STATES

    @classmethod
    def format_address(cls, components: Dict[str, Optional[str]]) -> str:
        """
        Format address components into a standard string.

        Args:
            components: Dictionary of address components

        Returns:
            Formatted address string
        """
        parts = []

        # Street address
        street_parts = []
        if components.get("street_number"):
            street_parts.append(components["street_number"])
        if components.get("street_name"):
            street_parts.append(components["street_name"])
        if components.get("unit"):
            street_parts.append(f"Unit {components['unit']}")

        if street_parts:
            parts.append(" ".join(street_parts))

        # City
        if components.get("city"):
            parts.append(components["city"])

        # State and ZIP
        state_zip = []
        if components.get("state"):
            state_zip.append(components["state"])
        if components.get("zip_code"):
            state_zip.append(components["zip_code"])

        if state_zip:
            parts.append(" ".join(state_zip))

        return ", ".join(parts)
