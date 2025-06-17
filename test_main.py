import unittest
import os
import shutil
import tempfile
from pathlib import Path
from main import (
    find_md_files,
    has_yandex_disk_links,
    has_attachments,
    extract_attachment_names,
    is_archive,
    get_yandex_disk_folder_path,
    extract_yandex_disk_links
)

class TestObsidianMigration(unittest.TestCase):
    def setUp(self):
        """Создаем временную директорию для тестов"""
        self.test_dir = tempfile.mkdtemp()
        print(f"\nВременная директория для тестов: {self.test_dir}")
        self.create_test_files()

    def tearDown(self):
        """Удаляем временную директорию после тестов"""
        shutil.rmtree(self.test_dir)

    def create_test_files(self):
        """Создаем тестовые файлы для проверки"""
        # Создаем тестовые .md файлы
        test_files = {
            'clean_note.md': 'Просто текст без ссылок и вложений',
            'yandex_note.md': 'Ссылка на Яндекс.Диск: https://disk.yandex.ru/d/abc123',
            'attachment_note.md': '![картинка](image.jpg)\n![[document.pdf]]',
            'mixed_note.md': 'Ссылка на Яндекс.Диск: https://disk.yandex.ru/d/xyz789\n![картинка](image.png)',
        }

        for filename, content in test_files.items():
            with open(os.path.join(self.test_dir, filename), 'w', encoding='utf-8') as f:
                f.write(content)

    def test_find_md_files(self):
        """Тест поиска .md файлов"""
        md_files = find_md_files(self.test_dir)
        self.assertEqual(len(md_files), 4)
        self.assertTrue(all(f.endswith('.md') for f in md_files))

    def test_has_yandex_disk_links(self):
        """Тест проверки наличия ссылок на Яндекс.Диск"""
        with open(os.path.join(self.test_dir, 'clean_note.md'), 'r', encoding='utf-8') as f:
            self.assertFalse(has_yandex_disk_links(f.read()))
        
        with open(os.path.join(self.test_dir, 'yandex_note.md'), 'r', encoding='utf-8') as f:
            self.assertTrue(has_yandex_disk_links(f.read()))

    def test_has_attachments(self):
        """Тест проверки наличия вложений"""
        with open(os.path.join(self.test_dir, 'clean_note.md'), 'r', encoding='utf-8') as f:
            self.assertFalse(has_attachments(f.read()))
        
        with open(os.path.join(self.test_dir, 'attachment_note.md'), 'r', encoding='utf-8') as f:
            self.assertTrue(has_attachments(f.read()))

    def test_extract_attachment_names(self):
        """Тест извлечения имен вложений"""
        with open(os.path.join(self.test_dir, 'attachment_note.md'), 'r', encoding='utf-8') as f:
            attachments = extract_attachment_names(f.read())
            self.assertEqual(len(attachments), 2)
            self.assertIn('image.jpg', attachments)
            self.assertIn('document.pdf', attachments)

    def test_is_archive(self):
        """Тест проверки архивов"""
        self.assertTrue(is_archive('file.zip'))
        self.assertTrue(is_archive('file.7z'))
        self.assertTrue(is_archive('file.rar'))
        self.assertFalse(is_archive('file.txt'))
        self.assertFalse(is_archive('file.pdf'))

    def test_get_yandex_disk_folder_path(self):
        """Тест извлечения пути к папке из ссылки Яндекс.Диска"""
        test_cases = [
            ('https://disk.yandex.ru/d/abc123', 'abc123'),
            ('https://disk.yandex.ru/client/disk/folder1', 'folder1'),
            ('https://disk.yandex.ru/folder2', 'folder2'),
            ('https://disk.yandex.ru/d/xyz789?param=value', 'xyz789'),
        ]

        for url, expected in test_cases:
            result = get_yandex_disk_folder_path(url)
            self.assertEqual(result, expected)

    def test_extract_yandex_disk_links(self):
        """Тест извлечения ссылок на Яндекс.Диск"""
        test_content = """
        Ссылка 1: https://disk.yandex.ru/d/abc123
        Ссылка 2: https://disk.yandex.ru/client/disk/folder1
        Обычный текст
        Ссылка 3: https://disk.yandex.ru/folder2
        """
        
        links = extract_yandex_disk_links(test_content)
        self.assertEqual(len(links), 3)
        self.assertIn('https://disk.yandex.ru/d/abc123', links)
        self.assertIn('https://disk.yandex.ru/client/disk/folder1', links)
        self.assertIn('https://disk.yandex.ru/folder2', links)

if __name__ == '__main__':
    unittest.main() 