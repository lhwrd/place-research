# Run flask app in debug
# Usage: make run
run:
	FLASK_APP=app.py FLASK_ENV=development flask run

debug:
	FLASK_APP=app.py FLASK_ENV=development FLASK_DEBUG=1 flask run
