"""Routes for the application."""

from flask import render_template, request
from flask import current_app as app

# from app.models import RVPark
from app.api.client import get_client
from app.api.places import get_lat_lng, search_multiple_places
from app.api.routes import chunked_distance_matrix
from app.api.utils import meters_to_miles, seconds_to_human_readable


@app.route("/")
def index():
    """Return the homepage."""
    return render_template(
        "index.html", GOOGLE_MAPS_API_KEY=app.config["GOOGLE_MAPS_API_KEY"]
    )


@app.route("/research-around-park", methods=["POST"])
def search_nearby_park():
    """Search for nearby RV parks."""
    # Get the address from the form
    address = request.form["address"]

    # Get the Google Maps API client
    gmaps = get_client()

    search_terms = [
        {"keyword": "Walmart Supercenter"},
        {"type": "grocery_or_supermarket"},
        {"type": "gas_station"},
        # {"type": "laundry"},
        {"type": "post_office"},
        # {"type": "pet_store"},
        # {"type": "veterinary_care"},
        # {"type": "hospital"},
        # {"type": "restaurant"},
        # {"type": "shopping_mall"},
        # {"type": "museum"},
        # {"type": "park"},
    ]

    places = search_multiple_places(
        gmaps,
        address,
        search_terms=search_terms,
    )
    app.logger.debug("Found %s places", len(places))
    app.logger.debug(places)

    center = get_lat_lng(gmaps, address)

    # Get distance and duration from the address to each place
    distances = chunked_distance_matrix(
        gmaps, center, [place["geometry"]["location"] for place in places]
    )

    # Add the distance and duration to each place
    for i, place in enumerate(places):
        place["distance"] = meters_to_miles(distances[i]["distance"])
        place["duration"] = seconds_to_human_readable(distances[i]["duration"])

    # Return back to the homepage with the search results
    return render_template(
        "index.html",
        GOOGLE_MAPS_API_KEY=app.config["GOOGLE_MAPS_API_KEY"],
        center=center,
        results=places,
    )
