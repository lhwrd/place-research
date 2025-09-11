import logging
import os

from dataclasses import dataclass
import requests

from place_research.interfaces import DisplayableResult, ProviderNameMixin


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

    def fetch_place_data(self, place):
        if place.walk_score and place.walk_description:
            self.logger.debug(
                "Walk/Bike score data already fetched for place ID %s", place.id
            )
            return

        coords = place.geolocation.split(";")
        if len(coords) != 2:
            self.logger.error("Invalid geolocation format.")
            return

        url = "https://api.walkscore.com/score"
        params = {
            "format": "json",
            "address": place.address,
            "lat": coords[0],
            "lon": coords[1],
            "wsapikey": self.api_key,
            "bike": 1,
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            place.walk_score = data.get("walkscore")
            place.walk_description = data.get("description")
            place.bike_score = data.get("bike", {}).get("score")
            place.bike_description = data.get("bike", {}).get("description")
