"""Flask app initialization."""

import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/test.db"
db = SQLAlchemy(app)

app.config["GOOGLE_MAPS_API_KEY"] = os.getenv("GOOGLE_MAPS_API_KEY")
app.config["GOOGLE_MAPS_MAP_ID"] = os.getenv("GOOGLE_MAPS_MAP_ID")

# Configure app.logger
if not app.logger.handlers:
    app.logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)

with app.app_context():
    # pylint: disable=wrong-import-position
    from . import routes  # noqa: F401, E402
