import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive']
MAIN_FOLDER_ID = '1vLsC-rXBkGUerIgU27KTybCd3pfs44sp'

def authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def main():
    try:
        service = authenticate()
        print("OK, підключено.\n")

        query = f"'{MAIN_FOLDER_ID}' in parents and trashed=false"
        all_files = []
        page_token = None
        while True:
            results = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=100,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            all_files.extend(results.get('files', []))
            page_token = results.get('nextPageToken')
            if not page_token:
                break

        folders = [f for f in all_files if f['mimeType'] == 'application/vnd.google-apps.folder']
        files = [f for f in all_files if f['mimeType'] != 'application/vnd.google-apps.folder']

        if folders:
            print(f"=== ПАПКИ ({len(folders)}): ===")
            for i, f in enumerate(sorted(folders, key=lambda x: x['name']), 1):
                print(f"  {i}. {f['name']}")

        print(f"\n=== ФАЙЛИ ({len(files)}): ===")
        for i, f in enumerate(sorted(files, key=lambda x: x['name']), 1):
            print(f"  {i}. {f['name']}")

    except HttpError as error:
        print(f"Помилка API: {error}")

if __name__ == '__main__':
    main()
