""" Forms for the app. """

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired


class SearchForm(FlaskForm):
    """Search form."""

    address = StringField("Address", validators=[DataRequired()])
    submit = SubmitField("Search")
