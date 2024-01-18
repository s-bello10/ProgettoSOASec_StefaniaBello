import os
from flask import Flask, session, render_template, jsonify, request
from flask_session import Session
import requests
import redis

import google_drive

api = Flask(__name__)
api.secret_key = os.getenv("FLASK_SECRET_KEY")
api.register_blueprint(google_drive.app)

api.config['SESSION_TYPE'] = 'redis'
api.config['SESSION_PERMANENT'] = True
api.config['SESSION_USE_SIGNER'] = False

# Use JSON serialization
api.config['SESSION_KEY_PREFIX'] = 'soasec:'
api.config['SESSION_REDIS'] = redis.Redis(host='redis', port=6379, db=0)


Session(api)

@api.route('/', methods=["GET"])
def index():
    if "item_id" in request.args:
        items = google_drive.getFoldersAndFiles(request.args["item_id"])
    else:
        items = google_drive.getFoldersAndFiles()

    tokens = session['tokens'] if 'tokens' in session else session['tokens_drive']
    response_info = requests.post(GOOGLE_AUTH_URL + "/getUserInfo", json=tokens)
    if response_info.status_code == 200:
        response_info_json = response_info.json()

        return render_template('index.html', items=items, user_info=response_info_json, base_uri=BASE_URI)
    return jsonify({"message": "Error: no user info"}), 500


if __name__ == "__main__":
    GOOGLE_AUTH_URL = os.getenv("GOOGLE_AUTH_URL")
    BASE_URI = os.getenv("BASE_URI")
    api.run("0.0.0.0", debug=True)
