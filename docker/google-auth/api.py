from google.oauth2.credentials import Credentials
import googleapiclient.discovery
import google_auth_oauthlib.flow
from flask import Flask, jsonify, request, session, redirect
from flask_session import Session
import os
import requests
import redis


def credentialsToDict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}


def buildCredentials(tokens):
    client_secret = os.getenv("CLIENT_SECRET")
    client_id = os.getenv("CLIENT_ID")

    if client_secret and client_id:
        creds = Credentials(
            tokens['access_token'],
            refresh_token=tokens['refresh_token'],
            client_id=client_id,
            client_secret=client_secret,
            token_uri=TOKEN_URI)
        client_secret = None
        client_id = None

        return creds


def getUserData(tokens):
    credentials = buildCredentials(tokens)

    if not credentials:
        return credentials

    oauth2_client = googleapiclient.discovery.build(
        'oauth2', 'v2',
        credentials=credentials)

    return oauth2_client.userinfo().get().execute()

def storeTokensInSession(credentials, api_type):
    if INCREMENTAL_AUTH == "true":
        if 'tokens' in session:
            apis = session['tokens']['apis'].copy()
            apis.append(api_type)
            session['tokens'] = {"access_token": credentials['token'],
                                 "refresh_token": credentials['refresh_token'],
                                 "apis": apis
                                 }
        else:
            session['tokens'] = {"access_token": credentials['token'],
                                 "refresh_token": credentials['refresh_token'],
                                 "apis": [api_type]}
    else:
        session['tokens_' + api_type] = {"access_token": credentials['token'],
                                         "refresh_token": credentials['refresh_token']}


# ----------------------------------------------------------------------------------------------------------------------

api = Flask(__name__)
api.secret_key = os.getenv("FLASK_SECRET_KEY")

api.config['SESSION_TYPE'] = 'redis'
api.config['SESSION_PERMANENT'] = True
api.config['SESSION_USE_SIGNER'] = False

# Use JSON serialization
api.config['SESSION_KEY_PREFIX'] = 'soasec:'
api.config['SESSION_REDIS'] = redis.Redis(host='redis', port=6379, db=0)

Session(api)


@api.route('/<path:undefined_route>', methods=['GET'])
def default_route(undefined_route):
    return redirect(BASE_URI)


@api.route('/getUserInfo', methods=["POST"])
def getUserInfo():
    data = request.get_json()
    return jsonify(getUserData(data)), 200


@api.route('/<api_type>/login', methods=["GET"])
def startLogin(api_type: str):
    api_type = api_type.lower()
    if api_type in ALLOWED_APIS:
        AUTH_SCOPES = os.getenv("AUTH_SCOPES_" + api_type.upper()).split(",")
    else:
        return redirect(BASE_URI)

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'secrets/client_secret.json',
        scopes=AUTH_SCOPES)

    flow.redirect_uri = BASE_URI + "/googleAuth/" + api_type + "/auth"

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt="consent",
        include_granted_scopes=INCREMENTAL_AUTH
    )

    session['state'] = state

    return redirect(authorization_url, code=302)


@api.route('/<api_type>/auth')
def oAuth2Callback(api_type: str):
    state = session['state']

    api_type = api_type.lower()
    if api_type in ALLOWED_APIS:
        AUTH_SCOPES = os.getenv("AUTH_SCOPES_" + api_type.upper()).split(",")
    else:
        return redirect(BASE_URI)

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'secrets/client_secret.json',
        scopes=AUTH_SCOPES, state=state)

    flow.redirect_uri = BASE_URI + "/googleAuth/" + api_type + "/auth"

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = request.url

    flow.fetch_token(authorization_response=authorization_response)

    credentials = credentialsToDict(flow.credentials)
    storeTokensInSession(credentials, api_type)
    del session['state']

    return redirect(BASE_URI + "/" + api_type + "Api")


@api.route("/logout", methods=["GET"])
def logout():
    if 'tokens' in session:
        del session['tokens']
    else:
        for api_name in ALLOWED_APIS:
            if 'tokens_' + api_name in session:
                del session['tokens_' + api_name]

    return redirect(BASE_URI)

@api.route("/revoke", methods=["GET"])
def revoke():
    if 'tokens' in session:
        requests.post('https://oauth2.googleapis.com/revoke',
                      params={'token': session['tokens']['access_token']},
                      headers={'content-type': 'application/x-www-form-urlencoded'})
        del session['tokens']
    else:
        for api_name in ALLOWED_APIS:
            if 'tokens_' + api_name in session:
                requests.post('https://oauth2.googleapis.com/revoke',
                              params={'token': session['tokens_' + api_name]['access_token']},
                              headers={'content-type': 'application/x-www-form-urlencoded'})
                del session['tokens_' + api_name]
    return redirect(BASE_URI)



if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

    TOKEN_URI = os.getenv("TOKEN_URI")
    AUTH_URL = os.getenv("AUTH_URL")
    BASE_URI = os.getenv("BASE_URI")
    ALLOWED_APIS = os.getenv("ALLOWED_APIS").split(",")
    INCREMENTAL_AUTH = os.getenv("INCREMENTAL_AUTH")

    api.run('0.0.0.0', debug=True)
