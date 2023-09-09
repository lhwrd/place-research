from dataclasses import dataclass
import requests

@dataclass
class WalkScore:
    score: float
    description: str


@dataclass
class BikeScore(WalkScore):
    ...


def get_walk_score(
    formatted_address: str, latitude: float, longitude: float, wsapikey: str
):
    # Define the API endpoint and parameters.
    url = "https://api.walkscore.com/score"
    params = {
        "address": formatted_address,
        "lat": str(round(latitude, 2)),
        "lon": str(round(longitude, 2)),
        "format": "json",
        "bike": "1",
        "wsapikey": wsapikey,
    }

    # Make the API request and get the response.
    response = requests.get(url, params=params)

    # Check if the request was successful.
    if response.status_code == 200:
        # Parse the response JSON and extract the walk score.
        data = response.json()
        if data["status"] != 1:
            errors = {
                2: "Score is being calculated and is not currently available",
                40: "Your WSAPIKEY is invalid",
                41: "Your daily API quta has been exceeded",
            }

            print(
                f"Error: {response.status_code} - {data['status']}: {errors[data['status']]}"
            )
            return None

        return (
            WalkScore(score=data["walkscore"], description=data["description"]),
            BikeScore(
                score=data["bike"]["score"], description=data["bike"]["description"]
            ),
        )
    else:
        # If the request was not successful, print the error message and return None.
        print(f"Error: {response.status_code} - {response.json()}")
        return None
