import redis
from flask import Flask, session, make_response, request
from flask_session import Session
import os


auth = Flask(__name__)
auth.secret_key = os.getenv("FLASK_SECRET_KEY")

auth.config['SESSION_TYPE'] = 'redis'
auth.config['SESSION_PERMANENT'] = True
auth.config['SESSION_USE_SIGNER'] = False

# Use JSON serialization
auth.config['SESSION_KEY_PREFIX'] = 'soasec:'
auth.config['SESSION_REDIS'] = redis.Redis(host='redis', port=6379, db=0)


Session(auth)

@auth.route("/to_login", methods=["GET"])
def toLogin():
    request_uri = request.headers.get("X-Original-URI")
    response = make_response("Auth response")
    split_uri = request_uri.split("/")
    service = split_uri[split_uri.index("googleAuth") + 1]

    if 'tokens' in session:
        if "logout" in request_uri:
            response.status_code = 200
        else:
            if service in session['tokens']['apis']:
                response.status_code = 401
            else:
                response.status_code = 200
    elif 'tokens_' + service in session:
        if "logout" in request_uri:
            response.status_code = 200
        else:
            response.status_code = 401
    else:
        response.status_code = 200

    return response


@auth.route("/to_service/<service>", methods=["GET"])
def toService(service: str):
    service = service.lower()
    response = make_response("Auth response")

    if 'tokens' in session:
        if service in session['tokens']['apis']:
            response.status_code = 200
        else:
            response.status_code = 401
    elif 'tokens_' + service in session:
        response.status_code = 200
    else:
        response.status_code = 401

    return response


if __name__ == "__main__":
    auth.run("0.0.0.0", debug=True)
