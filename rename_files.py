import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive']
MAIN_FOLDER_ID = '1vLsC-rXBkGUerIgU27KTybCd3pfs44sp'

# Мапа перейменувань: "стара назва" -> "нова назва"
RENAME_MAP = {
    'Лаб 1 Кожелянко Єви': 'Лаб 1 Кожелянко Єва',
    'Лаб 2 Кожелянко Єви': 'Лаб 2 Кожелянко Єва',
    'Лаб 3 Кожелянко Єви': 'Лаб 3 Кожелянко Єва',
    'Лаб 2 Черкашин Костнянтин.docx': 'Лаб 2 Черкашин Костянтин.docx',
    'Лаб 2 Яримчука Дмитра': 'Лаб 2 Яримчук Дмитро',
    'Лаб №3 Яримчука Дмитра ': 'Лаб 3 Яримчук Дмитро',
    'Лаба 2 Волошин': 'Лаб 2 Волошин Іван',
    'Лабораторна 3 яровий олександр': 'Лаб 3 Яровий Олександр',
    'Лаб роб 4 Радомський Максим.docx': 'Лаб 4 Радомський Максим.docx',
    'Радомський Максим ЛабР 3.docx': 'Лаб 3 Радомський Максим.docx',
    'Лаб№2 Кушнір Богдан .docx': 'Лаб 2 Кушнір Богдан.docx',
    '№3 Кушнір Богдан.docx': 'Лаб 3 Кушнір Богдан.docx',
}

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

        # Отримуємо всі файли з головної папки
        query = f"'{MAIN_FOLDER_ID}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
        all_files = []
        page_token = None
        while True:
            results = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name)",
                pageSize=100,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            all_files.extend(results.get('files', []))
            page_token = results.get('nextPageToken')
            if not page_token:
                break

        renamed = 0
        skipped = 0
        errors = 0

        for file in all_files:
            old_name = file['name']
            if old_name in RENAME_MAP:
                new_name = RENAME_MAP[old_name]
                try:
                    service.files().update(
                        fileId=file['id'],
                        body={'name': new_name},
                        fields='id, name',
                        supportsAllDrives=True
                    ).execute()
                    print(f"  [OK] '{old_name}' → '{new_name}'")
                    renamed += 1
                except HttpError as error:
                    print(f"  [ПОМИЛКА] '{old_name}': {error}")
                    errors += 1
            else:
                skipped += 1

        print(f"\nГотово! Перейменовано: {renamed}, пропущено: {skipped}, помилок: {errors}")

    except HttpError as error:
        print(f"Помилка API: {error}")

if __name__ == '__main__':
    main()
