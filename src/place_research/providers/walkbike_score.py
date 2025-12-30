import logging
import os

from dataclasses import dataclass
import requests

from place_research.interfaces import DisplayableResult, ProviderNameMixin
from place_research.models.results import WalkBikeScoreResult


@dataclass
class Score:
    score: int | None
    description: str | None

    def to_dict(self):
        return {
            "score": self.score,
            "description": self.description,
        }


@dataclass
class WalkBikeScore(DisplayableResult):
    walk_score: Score
    bike_score: Score

    def display(self):
        return f"Walk Score: {self.walk_score}, Bike Score: {self.bike_score}\n"

    def to_dict(self):
        return {
            "walk_score": self.walk_score.to_dict(),
            "bike_score": self.bike_score.to_dict(),
        }


class WalkBikeScoreProvider(ProviderNameMixin):
    def __init__(self, api_key: str | None = None):
        api_key = api_key or os.getenv("WALKSCORE_API_KEY")
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def fetch_place_data(self, place) -> WalkBikeScoreResult:
        url = "https://api.walkscore.com/score"
        params = {
            "format": "json",
            "address": place.address,
            "lat": place.latitude,
            "lon": place.longitude,
            "wsapikey": self.api_key,
            "bike": 1,
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()

            return WalkBikeScoreResult(
                walk_score=data.get("walkscore"),
                walk_description=data.get("description"),
                bike_score=data.get("bike", {}).get("score"),
                bike_description=data.get("bike", {}).get("description"),
            )

        self.logger.error(
            "Walk/Bike Score API error %s: %s", response.status_code, response.text
        )
        raise requests.RequestException(
            f"Walk/Bike Score API error {response.status_code}: {response.text}"
        )
