"""
Скрипт для миграции заметок из Obsidian с обработкой вложений и ссылок на Яндекс.Диск.
Писалось для себя, но вдруг кому-то пригодится.

Глобальные переменные для настройки:
- OBSIDIAN_PATH: путь к папке с заметками Obsidian
- ATTACHMENT_PATH: путь к папке с вложениями Obsidian
- OUTPUT_PATH: путь, куда будут сохранены обработанные файлы
- ARCHIVE_PASSWORD: пароль для распаковки архивов (если требуется)
- YANDEX_DISK_TOKEN: токен для доступа к API Яндекс.Диска

Как работает скрипт:

1. Обработка заметок:
   - Скрипт рекурсивно находит все .md файлы в указанной директории
   - Файлы разделяются на три категории:
     * Чистые заметки (без вложений и ссылок)
     * Заметки с вложениями
     * Заметки со ссылками на Яндекс.Диск

2. Работа с вложениями:
   - Поддерживаются два формата вложений:
     * Стандартный markdown: ![текст](путь)
     * Obsidian wiki-links: ![[имя_файла]]
   - Вложения копируются в отдельные папки для каждой заметки
   - Поддерживается распаковка архивов (.zip, .7z, .rar)
   - Архивы распаковываются в подпапку [имя_архива]_extracted

3. Работа с Яндекс.Диском:
   - Скрипт ищет ссылки на Яндекс.Диск в формате:
     * https://disk.yandex.ru/d/...
     * https://disk.yandex.ru/client/disk/...
     * https://disk.yandex.ru/...
   - Для каждой найденной ссылки:
     * Создается отдельная папка
     * Скачивается содержимое папки с Яндекс.Диска
     * Файлы сохраняются в подпапке yandex_disk_contents

4. Структура выходных данных:
   - just_notes/ - чистые заметки без вложений и ссылок
   - attachment_notes/[имя_заметки]/ - заметки с вложениями
     * [имя_заметки].md - сама заметка
     * [вложения] - копии вложений
     * [имя_архива]_extracted/ - распакованные архивы
   - link_notes/[имя_заметки]/ - заметки со ссылками
     * [имя_заметки].md - сама заметка
     * yandex_disk_contents/ - скачанное содержимое с Яндекс.Диска

Требования:
- Python 3.x
- Библиотеки: py7zr, rarfile, requests, yadisk
- Доступ к API Яндекс.Диска (токен)
- Достаточно места на диске для копирования файлов

Примечания:
- Перед запуском убедитесь, что все пути в глобальных переменных корректны
- Для работы с архивами может потребоваться установленный 7-Zip (если нет архивов, то не нужно)
- Токен Яндекс.Диска должен иметь права на чтение файлов (если нет ссылок на Яндекс.Диск, то не нужно)
"""

import os
import re
import shutil
import zipfile
import py7zr
import rarfile
import requests
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from yadisk import YaDisk

# Глобальные переменные
OBSIDIAN_PATH = r"P:\obsi_data\data"
ATTACHMENT_PATH = r"P:\obsi_data\data\files"
OUTPUT_PATH = r"C:\Users\starr\Documents\migrate from obsidian\output"
ARCHIVE_PASSWORD = "7281"  # Замените на реальный пароль
# Токен Яндекс.Диска
YANDEX_DISK_TOKEN = "ТУТ_ВАШ_ТОКЕН" #замените на реальный токен если хотите использовать Яндекс.Диск

# Инициализация клиента Яндекс.Диска
yadisk = YaDisk(token=YANDEX_DISK_TOKEN)

def find_md_files(directory):
    """Рекурсивно находит все .md файлы в указанной директории"""
    md_files = []
    try:
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.md'):
                    md_files.append(os.path.join(root, file))
    except Exception as e:
        print(f"Ошибка при поиске файлов: {e}")
    return md_files

def has_yandex_disk_links(content):
    """Проверяет наличие ссылок на Яндекс.Диск в тексте"""
    pattern = r'https?://disk\.yandex\.ru/'
    return bool(re.search(pattern, content))

def has_attachments(content):
    """Проверяет наличие вложений в тексте (обоих форматов)"""
    # Стандартный markdown формат
    markdown_pattern = r'!\[.*?\]\(.*?\)'
    # Obsidian wiki-links формат
    obsidian_pattern = r'!\[\[.*?\]\]'
    return bool(re.search(markdown_pattern, content) or re.search(obsidian_pattern, content))

def extract_attachment_names(content):
    """Извлекает имена вложений из текста"""
    attachments = []
    
    # Стандартный markdown формат: ![текст](путь)
    markdown_pattern = r'!\[.*?\]\((.*?)\)'
    markdown_matches = re.findall(markdown_pattern, content)
    attachments.extend(markdown_matches)
    
    # Obsidian wiki-links формат: ![[имя_файла]]
    obsidian_pattern = r'!\[\[(.*?)\]\]'
    obsidian_matches = re.findall(obsidian_pattern, content)
    attachments.extend(obsidian_matches)
    
    return attachments

def is_archive(filename):
    """Проверяет, является ли файл архивом"""
    archive_extensions = ('.zip', '.7z', '.rar')
    return filename.lower().endswith(archive_extensions)

def extract_archive(archive_path, extract_path, password=None):
    """Распаковывает архив в указанную директорию"""
    try:
        if archive_path.lower().endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                if password:
                    zip_ref.extractall(extract_path, pwd=password.encode())
                else:
                    zip_ref.extractall(extract_path)
        elif archive_path.lower().endswith('.7z'):
            with py7zr.SevenZipFile(archive_path, 'r', password=password) as sz:
                sz.extractall(extract_path)
        elif archive_path.lower().endswith('.rar'):
            with rarfile.RarFile(archive_path, 'r') as rar:
                if password:
                    rar.extractall(extract_path, pwd=password.encode())
                else:
                    rar.extractall(extract_path)
        return True
    except Exception as e:
        print(f"Ошибка при распаковке архива {archive_path}: {e}")
        return False

def copy_clean_notes(md_files, output_dir):
    """Копирует файлы без ссылок на Яндекс.Диск и без вложений"""
    just_notes_dir = os.path.join(output_dir, 'just_notes')
    os.makedirs(just_notes_dir, exist_ok=True)
    
    copied_count = 0
    skipped_count = 0
    
    for file_path in md_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if not has_yandex_disk_links(content) and not has_attachments(content):
                file_name = os.path.basename(file_path)
                dest_path = os.path.join(just_notes_dir, file_name)
                shutil.copy2(file_path, dest_path)
                print(f"Скопирован файл: {file_name}")
                copied_count += 1
            else:
                print(f"Пропущен файл (содержит ссылки на Яндекс.Диск или вложения): {os.path.basename(file_path)}")
                skipped_count += 1
                
        except Exception as e:
            print(f"Ошибка при обработке файла {file_path}: {e}")
            skipped_count += 1
    
    return copied_count, skipped_count

def copy_yandex_disk_notes(md_files, output_dir):
    """Копирует файлы с ссылками на Яндекс.Диск в отдельную папку."""
    yandex_dir = os.path.join(output_dir, "link_notes")
    os.makedirs(yandex_dir, exist_ok=True)
    
    copied = 0
    skipped = 0
    
    for file_path in md_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if has_yandex_disk_links(content):
                # Создаем подпапку для заметки
                note_name = os.path.splitext(os.path.basename(file_path))[0]
                note_dir = os.path.join(yandex_dir, note_name)
                os.makedirs(note_dir, exist_ok=True)
                
                # Копируем файл в подпапку
                shutil.copy2(file_path, note_dir)
                print(f"Скопирован файл с Яндекс.Диск ссылками: {os.path.basename(file_path)}")
                copied += 1
            else:
                skipped += 1
                
        except Exception as e:
            print(f"Ошибка при обработке файла {file_path}: {str(e)}")
            skipped += 1
            
    return copied, skipped

def copy_attachment_notes(md_files, output_dir):
    """Копирует файлы с вложениями и сами вложения в отдельные подпапки"""
    attachment_notes_dir = os.path.join(output_dir, 'attachment_notes')
    os.makedirs(attachment_notes_dir, exist_ok=True)
    
    copied_count = 0
    skipped_count = 0
    attachments_copied = 0
    archives_extracted = 0
    
    for file_path in md_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if has_attachments(content):
                # Создаем подпапку для заметки
                file_name = os.path.basename(file_path)
                note_name = os.path.splitext(file_name)[0]
                note_dir = os.path.join(attachment_notes_dir, note_name)
                os.makedirs(note_dir, exist_ok=True)
                
                # Копируем сам файл
                dest_path = os.path.join(note_dir, file_name)
                shutil.copy2(file_path, dest_path)
                print(f"Скопирован файл с вложениями: {file_name}")
                copied_count += 1
                
                # Копируем вложения
                attachment_names = extract_attachment_names(content)
                for attachment_name in attachment_names:
                    # Пробуем найти вложение в ATTACHMENT_PATH
                    attachment_path = os.path.join(ATTACHMENT_PATH, attachment_name)
                    if os.path.exists(attachment_path):
                        dest_attachment_path = os.path.join(note_dir, attachment_name)
                        shutil.copy2(attachment_path, dest_attachment_path)
                        print(f"  Скопировано вложение: {attachment_name}")
                        attachments_copied += 1
                        
                        # Если вложение - архив, распаковываем его
                        if is_archive(attachment_name):
                            archive_extract_path = os.path.join(note_dir, f"{os.path.splitext(attachment_name)[0]}_extracted")
                            os.makedirs(archive_extract_path, exist_ok=True)
                            if extract_archive(dest_attachment_path, archive_extract_path, ARCHIVE_PASSWORD):
                                print(f"  Распакован архив: {attachment_name}")
                                archives_extracted += 1
                    else:
                        print(f"  Вложение не найдено: {attachment_name}")
            else:
                skipped_count += 1
                
        except Exception as e:
            print(f"Ошибка при обработке файла {file_path}: {e}")
            skipped_count += 1
    
    return copied_count, skipped_count, attachments_copied, archives_extracted

def creat_output_dir(directory):
    """Создает выходную директорию, если она не существует"""
    if not os.path.exists(directory):
        os.makedirs(directory)

def get_yandex_disk_folder_path(url: str) -> str | None:
    """Извлекает путь к папке из ссылки Яндекс.Диска."""
    try:
        # Декодируем URL
        decoded_url = unquote(url)
        print(f"Декодированный URL: {decoded_url}")
        
        # Извлекаем путь к папке
        if 'disk.yandex.ru/d/' in decoded_url:
            # Для публичных ссылок
            path = decoded_url.split('disk.yandex.ru/d/')[1].split('?')[0]
        elif 'disk.yandex.ru/client/disk/' in decoded_url:
            # Для ссылок на папки в клиенте
            path = decoded_url.split('disk.yandex.ru/client/disk/')[1].split('?')[0]
        else:
            # Для обычных ссылок
            path = decoded_url.split('disk.yandex.ru/')[1].split('?')[0]
        
        print(f"Извлеченный путь к папке: {path}")
        return path
    except Exception as e:
        print(f"Ошибка при извлечении пути из URL {url}: {str(e)}")
        return None

def download_yandex_disk_folder(folder_path: str | None, local_path: str) -> None:
    """Скачивает содержимое папки с Яндекс.Диска"""
    if folder_path is None:
        print("Не удалось получить путь к папке")
        return
        
    try:
        # Получаем список файлов в папке
        items = yadisk.listdir(folder_path)
        
        for item in items:
            if item.type == 'file' and item.path is not None and item.name is not None:
                # Создаем локальный путь для файла
                local_file_path = os.path.join(local_path, item.name)
                
                # Скачиваем файл
                yadisk.download(item.path, local_file_path)
                print(f"  Скачан файл: {item.name}")
                
    except Exception as e:
        print(f"  Ошибка при скачивании папки {folder_path}: {str(e)}")

def extract_yandex_disk_links(content):
    """Извлекает ссылки на Яндекс.Диск из текста"""
    # Паттерн для поиска ссылок на Яндекс.Диск
    pattern = r'https?://disk\.yandex\.ru/[^\s<>"\']+'
    return re.findall(pattern, content)

def download_yandex_disk_contents():
    """Скачивает содержимое папок Яндекс.Диска для всех файлов с ссылками"""
    print("\nСкачивание содержимого папок Яндекс.Диска...")
    
    # Создаем папку для содержимого Яндекс.Диска
    yandex_disk_dir = os.path.join(OUTPUT_PATH, "link_notes")
    if not os.path.exists(yandex_disk_dir):
        os.makedirs(yandex_disk_dir)
    
    # Перебираем все файлы с ссылками
    for root, dirs, files in os.walk(yandex_disk_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                
                # Читаем содержимое файла
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Извлекаем ссылки
                links = extract_yandex_disk_links(content)
                
                if links:
                    # Создаем папку для содержимого
                    note_name = os.path.splitext(file)[0]
                    yandex_contents_dir = os.path.join(root, "yandex_disk_contents")
                    if not os.path.exists(yandex_contents_dir):
                        os.makedirs(yandex_contents_dir)
                    
                    # Скачиваем содержимое каждой папки
                    for link in links:
                        folder_path = get_yandex_disk_folder_path(link)
                        print(f"\nСкачивание содержимого папки для файла {file}:")
                        download_yandex_disk_folder(folder_path, yandex_contents_dir)

def main():
    """Основная функция скрипта."""
    print("Проверка выходной директории...")
    creat_output_dir(OUTPUT_PATH)
    
    print("\nПоиск .md файлов...")
    md_files = find_md_files(OBSIDIAN_PATH)
    print(f"Найдено .md файлов: {len(md_files)}")
    
    print("\nКопирование файлов без ссылок на Яндекс.Диск и без вложений...")
    clean_copied, clean_skipped = copy_clean_notes(md_files, OUTPUT_PATH)
    
    print("\nКопирование файлов с ссылками на Яндекс.Диск...")
    yandex_copied, yandex_skipped = copy_yandex_disk_notes(md_files, OUTPUT_PATH)
    
    print("\nКопирование файлов с вложениями и самих вложений...")
    attachment_copied, attachment_skipped, attachments_copied, archives_extracted = copy_attachment_notes(md_files, OUTPUT_PATH)
    
    print("\nСкачивание содержимого папок Яндекс.Диска...")
    download_yandex_disk_contents()
    
    print(f"\nИтого:")
    print(f"Скопировано чистых файлов: {clean_copied}")
    print(f"Скопировано файлов с Яндекс.Диск ссылками: {yandex_copied}")
    print(f"Скопировано файлов с вложениями: {attachment_copied}")
    print(f"Скопировано вложений: {attachments_copied}")
    print(f"Распаковано архивов: {archives_extracted}")
    print(f"Пропущено файлов: {clean_skipped + yandex_skipped + attachment_skipped}")
    
    print("\nГотово! Файлы сохранены в папках:")
    print("- 'just_notes' - чистые файлы")
    print("- 'link_notes/[имя_заметки]' - файлы с Яндекс.Диск ссылками")
    print("- 'attachment_notes/[имя_заметки]' - файлы с вложениями и их вложения")
    print("  (архивы автоматически распаковываются в подпапку [имя_архива]_extracted)")
    print("- 'link_notes/[имя_заметки]/yandex_disk_contents' - скачанное содержимое папок Яндекс.Диска")

if __name__ == "__main__":
    main()


