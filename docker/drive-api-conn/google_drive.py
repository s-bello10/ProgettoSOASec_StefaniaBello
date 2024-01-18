import io
import os
import tempfile
from flask import Blueprint, session, request, redirect, send_file, jsonify
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import googleapiclient.discovery
from werkzeug.utils import secure_filename
from google.oauth2.credentials import Credentials

BASE_URI = os.getenv("BASE_URI")

app = Blueprint('google_drive', __name__)


def buildCredentials():
    tokens = session['tokens'] if 'tokens' in session else session['tokens_drive']

    client_secret = os.getenv("CLIENT_SECRET")
    client_id = os.getenv("CLIENT_ID")

    if client_secret and client_id:
        creds = Credentials(
            tokens['access_token'],
            refresh_token=tokens['refresh_token'],
            client_id=client_id,
            client_secret=client_secret,
            scopes=os.getenv("AUTH_SCOPES_DRIVE"),
            token_uri=os.getenv("TOKEN_URI"))
        client_secret = None
        client_id = None

        return creds


def buildDriveApiV3():
    credentials = buildCredentials()
    return googleapiclient.discovery.build('drive', 'v3', credentials=credentials).files()


def saveImage(file_name, mime_type, file_data):
    drive_api = buildDriveApiV3()

    generate_ids_result = drive_api.generateIds(count=1).execute()
    file_id = generate_ids_result['ids'][0]

    body = {
        'id': file_id,
        'name': file_name,
        'mimeType': mime_type,
    }

    media_body = MediaIoBaseUpload(file_data,
                                   mimetype=mime_type,
                                   resumable=True)

    drive_api.create(body=body,
                     media_body=media_body,
                     fields='id,name,mimeType,createdTime,modifiedTime').execute()

    return file_id


def getFoldersAndFiles(item_id=None):
    drive_fields = "files(id,name,mimeType,createdTime,modifiedTime,shared,webContentLink)"
    query_folder = "trashed=false and mimeType='application/vnd.google-apps.folder'"
    query_files = "trashed=false and mimeType!='application/vnd.google-apps.folder'"
    drive_api = buildDriveApiV3()

    if item_id:
        query_folder += "and parents in '" + item_id + "'"
    folders = drive_api.list(
        pageSize=20, orderBy="name", q=query_folder,
        fields=drive_fields
    ).execute()['files']

    if item_id:
        query_files += "and parents in '" + item_id + "'"
    else:
        for folder in folders:
            query_files += " and not parents in '" + folder['id'] + "'"

    files = drive_api.list(
        pageSize=20, orderBy="name", q=query_files,
        fields=drive_fields
    ).execute()['files']

    return folders + files


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(BASE_URI)

    file = request.files['file']
    if (not file):
        return redirect(BASE_URI)

    filename = secure_filename(file.filename)

    fp = tempfile.TemporaryFile()
    ch = file.read()
    fp.write(ch)
    fp.seek(0)

    mime_type = request.headers['Content-Type']
    saveImage(filename, mime_type, fp)

    return redirect(BASE_URI + "/driveApi")


@app.route('/view/<item_id>', methods=['GET'])
def view_file(item_id: str):
    drive_api = buildDriveApiV3()

    metadata = drive_api.get(fields="name,mimeType", fileId=item_id).execute()

    request_ = drive_api.get_media(fileId=item_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request_)

    done = False
    while done is False:
        status, done = downloader.next_chunk()

    fh.seek(0)

    return send_file(
        fh,
        download_name=metadata['name'],
        mimetype=metadata['mimeType']
    )
