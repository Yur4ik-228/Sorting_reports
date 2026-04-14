import os
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']

MAIN_FOLDER_ID = '1vLsC-rXBkGUerIgU27KTybCd3pfs44sp'
DRY_RUN = False  # Змініть на False, щоб скрипт реально переміщував та перейменовував файли

def authenticate_google_drive():
    """Аутентифікація та створення сервісу Google Drive API."""
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

def parse_filename(old_name, folder_name):
    """
    Аналізує стару назву файлу та генерує нову у форматі 'Лаб {number} {Surname} {Name}'.
    Використовує назву папки для отримання прізвища та імені, якщо вони є.
    """
    # Жорстко задані перейменування на основі логу:
    manual_renames = {
        'Лаб. Роб. N2': 'Лаб 2 Дамян Максим',
        'Лабораторна робота N1': 'Лаб 1 Яримчук Дмитро',
        'ЛР2 Бацала Юрій.docx': 'Лаб 2 Бацала Юрій',
        'ЛР1 Бацала Юрій.docx': 'Лаб 1 Бацала Юрій',
        'Лабораторнаробота2,Звіт.docx': 'Лаб 2 Голбан Крістіна',
        'Лабораторна робота1Звіт.docx': 'Лаб 1 Голбан Крістіна',
        'Оп лабораторна 1': 'Лаб 1 Яровий Олександр',
        'Лаб роб 2(Основи програм).docx': 'Лаб 2 Радомський Максим',
        'Основи Програмування Звіт_Лабораторна_робота_№1.docx': 'Лаб 1 Радомський Максим',
        'Крутой Олешка': 'Лаб X Волошин Іван', # Невідомий номер лаби
        'Лаба 1': 'Лаб 1 Волошин Іван',
        'Фефчак Ангеліна ЛР1.docx': 'Лаб 1 Фефчак Ангеліна'
    }

    if old_name in manual_renames:
        return manual_renames[old_name]

    # ... fall back logic ...
    base_name = re.sub(r'\.[a-zA-Z0-9]+$', '', old_name)

    # Замінюємо підкреслення на пробіли
    base_name = base_name.replace('_', ' ')
    
    # Шукаємо цифру (номер лабораторної)
    num_match = re.search(r'\d+', base_name)
    lab_num = str(int(num_match.group())) if num_match else "X"
    
    # Слова для ігнорування
    stop_words = {'лаб', 'лабораторна', 'робота', 'лро', 'звіт', 'приклад', 'docx', 'pdf', 'роб'}
    
    # Знаходимо всі слова, що складаються з кириличних літер
    words = re.findall(r'[А-ЯІЇЄҐа-яіїєґ]+', base_name)
    
    # Фільтруємо імена/прізвища (слова з великої літери, які не є стоп-словами)
    names = []
    for w in words:
        if w.lower() not in stop_words and len(w) > 1 and w[0].isupper():
            names.append(w)
    
    if not names:
        return None  # Не вдалося знайти прізвище та ім'я
        
    surname = names[-2] if len(names) >= 2 else names[0]
    name = names[-1] if len(names) >= 2 else ""
    
    new_name = f"Лаб {lab_num} {surname} {name}".strip()
    return new_name

def main():
    try:
        service = authenticate_google_drive()
        print("успішно підключено до Google Drive API.")
        
        if DRY_RUN:
            print("--- УВІМКНЕНО REGIME DRY_RUN: Реальнi змiни не будуть застосованi ---")

        # --- ОЧИЩЕННЯ ДУБЛІКАТІВ ТА ОТРИМАННЯ ІСНУЮЧИХ ФАЙЛІВ ---
        print("\n--- Перевірка та очищення дублікатів у головній папці ---")
        query_root = f"'{MAIN_FOLDER_ID}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
        res_root = service.files().list(q=query_root, fields="files(id, name)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        root_files = res_root.get('files', [])
        
        existing_root_names = set()
        for f in root_files:
            name = f['name']
            if name in existing_root_names:
                if not DRY_RUN:
                    try:
                        service.files().delete(fileId=f['id'], supportsAllDrives=True).execute()
                        print(f"  [Видалено дублікат] '{name}'")
                    except HttpError:
                        pass
                else:
                    print(f"  [DRY RUN] Would delete duplicate: '{name}'")
            else:
                existing_root_names.add(name)

        # 1. Знаходимо всі підпапки в MAIN_FOLDER_ID
        query_folders = f"'{MAIN_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results_folders = service.files().list(
            q=query_folders, 
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        folders = results_folders.get('files', [])

        if not folders:
            print("Підпапок не знайдено.")
            return

        for folder in folders:
            folder_id = folder['id']
            folder_name = folder['name']
            print(f"\nОбробка папки: {folder_name} ({folder_id})")

            # 2. Отримуємо файли всередині підпапки
            query_files = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
            results_files = service.files().list(
                q=query_files, 
                fields="files(id, name, parents)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            files = results_files.get('files', [])

            for file in files:
                file_id = file['id']
                old_name = file['name']
                
                new_name = parse_filename(old_name, folder_name)
                
                # ПЕРЕВІРКА: чи ми вже скопіювали цей файл раніше?
                check_name = new_name if new_name else old_name
                if check_name in existing_root_names:
                    print(f"  [ℹ️] Файл з назвою '{check_name}' вже є в головній папці. Пропускаємо копіювання.")
                    continue
                
                if DRY_RUN:
                    print(f"  [DRY RUN] Would move: '{old_name}' from '{folder_name}' to MAIN_FOLDER")
                    if new_name:
                        print(f"  [DRY RUN] Would rename: '{old_name}' -> '{new_name}'")
                    else:
                        print(f"  [DRY RUN] Could not parse format for renaming: '{old_name}'")
                else:
                    try:
                        # Створення тіла запиту для перейменування (якщо нове ім'я згенеровано)
                        file_metadata = {}
                        if new_name:
                            file_metadata['name'] = new_name
                            
                        # Переміщення файлу (оновлення 'parents')
                        previous_parents = ",".join(file.get('parents', []))
                        
                        try:
                            # Спроба 1: звичайне переміщення
                            updated_file = service.files().update(
                                fileId=file_id,
                                addParents=MAIN_FOLDER_ID,
                                removeParents=previous_parents,
                                body=file_metadata if file_metadata else None,
                                fields='id, parents, name',
                                supportsAllDrives=True
                            ).execute()
                            existing_root_names.add(new_name if new_name else old_name)
                            print(f"  [OK] Файл '{old_name}' успішно переміщено" + (f" та перейменовано на '{new_name}'" if new_name else "."))
                        except HttpError as update_error:
                            if "Increasing the number of parents" in str(update_error) or "insufficientFilePermissions" in str(update_error):
                                # Спроба 2: копіювання, якщо немає прав на переміщення (часто буває з чужими файлами)
                                print(f"  [ℹ️] Звичайне переміщення заборонено (спільний доступ). Роблю копію файлу...")
                                copy_metadata = {'parents': [MAIN_FOLDER_ID]}
                                if new_name:
                                    copy_metadata['name'] = new_name
                                else:
                                    copy_metadata['name'] = old_name
                                
                                service.files().copy(
                                    fileId=file_id,
                                    body=copy_metadata,
                                    supportsAllDrives=True
                                ).execute()
                                existing_root_names.add(new_name if new_name else old_name)
                                print(f"  [OK] Файл '{old_name}' скопійовано у головну папку" + (f" з новою назвою '{new_name}'" if new_name else "."))
                                # Опціонально можна спробувати видалити оригінал, але якщо немає прав — ігноруємо
                                try:
                                    service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
                                except HttpError:
                                    pass
                            else:
                                raise update_error
                                
                    except HttpError as error:
                        print(f"  [ПОМИЛКА] Під час переміщення/перейменування '{old_name}': {error}")

            # 3. Видалення порожньої папки
            if DRY_RUN:
                print(f"[DRY RUN] Would delete empty folder: '{folder_name}'")
            else:
                try:
                    # Перевіряємо, чи лишились ще якісь файли в папці перед її видаленням
                    check_empty = service.files().list(
                        q=f"'{folder_id}' in parents and trashed=false", 
                        fields="files(id)",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True
                    ).execute()
                    
                    if not check_empty.get('files'):
                        service.files().delete(fileId=folder_id, supportsAllDrives=True).execute()
                        print(f"[OK] Порожню папку '{folder_name}' успішно видалено.")
                    else:
                        print(f"[УВАГА] Папка '{folder_name}' не порожня, пропуск видалення.")
                except HttpError as error:
                    # Якщо немає прав на видалення чужої папки - просто повідомляємо про це спокійно
                    if "insufficientFilePermissions" in str(error):
                        print(f"[ℹ️] Папку '{folder_name}' не видалено: ви не є її власником (недостатньо прав).")
                    else:
                        print(f"[ПОМИЛКА] Під час видалення папки '{folder_name}': {error}")
                        
        # 4. Перевірка та перейменування файлів, які вже лежать БЕЗПОСЕРЕДНЬО в MAIN_FOLDER_ID
        print(f"\n--- Перевірка файлів вже в головній папці ---")
        query_root_files = f"'{MAIN_FOLDER_ID}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
        results_root_files = service.files().list(
            q=query_root_files, 
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        root_files = results_root_files.get('files', [])
        for file in root_files:
            file_id = file['id']
            old_name = file['name']
            
            new_name = parse_filename(old_name, "Root Folder")
            
            # Якщо згенеровано нове ім'я і воно відрізняється від старого
            if new_name and new_name != old_name:
                if new_name in existing_root_names:
                    print(f"  [ℹ️] Перейменований файл '{new_name}' вже існує. Пропускаємо перейменування для '{old_name}'.")
                    continue
                    
                if DRY_RUN:
                    print(f"  [DRY RUN] Would rename root file: '{old_name}' -> '{new_name}'")
                else:
                    try:
                        service.files().update(
                            fileId=file_id,
                            body={'name': new_name},
                            fields='id, name',
                            supportsAllDrives=True
                        ).execute()
                        print(f"  [OK] Файл у корені '{old_name}' перейменовано на '{new_name}'")
                    except HttpError as error:
                        print(f"  [ПОМИЛКА] Не вдалося перейменувати '{old_name}' у корені (можливо, немає прав): {error}")

    except HttpError as error:
        print(f"Сталася помилка API: {error}")

if __name__ == '__main__':
    main()
