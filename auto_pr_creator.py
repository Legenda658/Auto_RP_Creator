import sys
import os
import json
import subprocess
import webbrowser
import shutil
import requests
import time
import tempfile
import random
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QMessageBox, QProgressBar, QTextEdit, QStackedWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QIntValidator, QPixmap
class PRWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    error_signal = pyqtSignal(str)
    def __init__(self, username, email, pr_count, token, repo_url):
        super().__init__()
        self.username = username
        self.email = email
        self.pr_count = pr_count
        self.token = token
        self.repo_url = repo_url
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.temp_dir = None
    def run_git_command(self, command, check=True):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=check)
            if check and result.returncode != 0:
                error_message = f"Git команда не удалась: {' '.join(command)}\nОшибка: {result.stderr}"
                self.error_signal.emit(error_message)
                raise Exception(error_message)
            return result
        except subprocess.CalledProcessError as e:
            error_message = f"Git команда не удалась: {' '.join(command)}\nОшибка: {e.stderr}"
            self.error_signal.emit(error_message)
            raise Exception(error_message)
        except FileNotFoundError:
            error_message = "Git не найден. Убедитесь, что Git установлен и добавлен в PATH."
            self.error_signal.emit(error_message)
            raise Exception(error_message)
    def check_git_status(self):
        status = self.run_git_command(["git", "status", "--porcelain"])
        return status.stdout.strip()
    def initialize_repository(self):
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)
        self.run_git_command(["git", "init"])
        self.run_git_command(["git", "config", "user.name", self.username])
        self.run_git_command(["git", "config", "user.email", self.email])
        with open("README.md", "w", encoding='utf-8') as f:
            f.write(f"# {os.path.basename(self.repo_url.split('/')[-1].replace('.git', ''))}\n\n")
            f.write("Репозиторий для автоматического создания Pull Requests.\n")
        self.run_git_command(["git", "add", "README.md"])
        status = self.check_git_status()
        if not status:
            raise Exception("Нет изменений для коммита в README.md. Статус Git пуст.")
        self.run_git_command(["git", "commit", "-m", "Initial commit"])
        repo_url_with_token = self.repo_url.replace('https://', f'https://oauth2:{self.token}@') 
        try:
            self.run_git_command(["git", "remote", "add", "origin", repo_url_with_token])
        except Exception as e:
            if "already exists" in str(e):
                self.run_git_command(["git", "remote", "set-url", "origin", repo_url_with_token])
            else:
                raise
        self.run_git_command(["git", "branch", "-M", "main"])
        self.run_git_command(["git", "push", "-u", "origin", "main", "--force"])
    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                os.chdir(os.path.expanduser("~"))
                git_dir = os.path.join(self.temp_dir, '.git')
                if os.path.exists(git_dir):
                    try:
                        objects_dir = os.path.join(git_dir, 'objects')
                        if os.path.exists(objects_dir):
                            for root, dirs, files in os.walk(objects_dir, topdown=False):
                                for name in files:
                                    try:
                                        os.remove(os.path.join(root, name))
                                    except:
                                        pass
                                for name in dirs:
                                    try:
                                        os.rmdir(os.path.join(root, name))
                                    except:
                                        pass
                        for root, dirs, files in os.walk(git_dir, topdown=False):
                            for name in files:
                                try:
                                    os.remove(os.path.join(root, name))
                                except:
                                    pass
                            for name in dirs:
                                try:
                                    os.rmdir(os.path.join(root, name))
                                except:
                                    pass
                        try:
                            os.rmdir(git_dir)
                        except:
                            pass
                    except:
                        pass
                for root, dirs, files in os.walk(self.temp_dir, topdown=False):
                    for name in files:
                        try:
                            os.remove(os.path.join(root, name))
                        except:
                            pass
                    for name in dirs:
                        try:
                            os.rmdir(os.path.join(root, name))
                        except:
                            pass
                try:
                    os.rmdir(self.temp_dir)
                except:
                    pass
            except Exception as e:
                self.error_signal.emit(f"Ошибка при удалении временной директории {self.temp_dir}: {str(e)}")
                pass
    def run(self):
        try:
            self.initialize_repository()
            for i in range(self.pr_count):
                if i > 0:
                    delay = random.randint(30, 60)
                    time.sleep(delay)
                branch_name = f"feature-{i+1}"
                self.run_git_command(["git", "checkout", "-b", branch_name])
                files = [
                    (f"src/feature_{i+1}.py", f"""
def calculate_feature_{i+1}(data):
    \"\"\"
    Функция для обработки данных.
    Args:
        data: Входные данные для обработки
    Returns:
        Обработанные данные
    \"\"\"
    result = []
    for item in data:
        processed = item * 2
        result.append(processed)
    return result
def validate_feature_{i+1}(data):
    \"\"\"
    Валидация входных данных.
    Args:
        data: Данные для валидации
    Returns:
        bool: True если данные валидны
    \"\"\"
    return all(isinstance(x, (int, float)) for x in data)
"""),
                    (f"tests/test_feature_{i+1}.py", f"""
import unittest
from src.feature_{i+1} import calculate_feature_{i+1}, validate_feature_{i+1}
class TestFeature{i+1}(unittest.TestCase):
    def test_calculation(self):
        data = [1, 2, 3, 4, 5]
        result = calculate_feature_{i+1}(data)
        self.assertEqual(result, [2, 4, 6, 8, 10])
    def test_validation(self):
        valid_data = [1, 2, 3]
        invalid_data = [1, '2', 3]
        self.assertTrue(validate_feature_{i+1}(valid_data))
        self.assertFalse(validate_feature_{i+1}(invalid_data))
if __name__ == '__main__':
    unittest.main()
"""),
                    (f"docs/feature_{i+1}.md", f"""
# Feature {i+1}
## Описание
Этот модуль предоставляет функциональность для обработки данных.
## Использование
```python
from src.feature_{i+1} import calculate_feature_{i+1}
data = [1, 2, 3]
result = calculate_feature_{i+1}(data)
print(result)  # [2, 4, 6]
```
## Требования
- Python 3.6+
- numpy
- pandas
## Установка
```bash
pip install -r requirements.txt
```
""")
                ]
                for dir_path in ['src', 'tests', 'docs']:
                    os.makedirs(dir_path, exist_ok=True)
                for file_path, content in files:
                    with open(file_path, "w", encoding='utf-8') as f:
                        f.write(content.strip())
                    if not os.path.exists(file_path):
                        raise Exception(f"Не удалось создать файл: {file_path}")
                requirements_path = "requirements.txt"
                with open(requirements_path, "w", encoding='utf-8') as f:
                    f.write("numpy>=1.19.0\npandas>=1.1.0\npytest>=6.0.0\n")
                if not os.path.exists(requirements_path):
                    raise Exception("Не удалось создать файл requirements.txt")
                self.run_git_command(["git", "add", "."])
                status = self.check_git_status()
                if not status:
                    raise Exception("Нет изменений для коммита. Статус Git пуст.")
                self.run_git_command(["git", "commit", "-m", f"Добавлен новый функционал #{i+1}"])
                time.sleep(random.randint(2, 5))
                self.run_git_command(["git", "push", "-u", "origin", branch_name, "--force"])
                repo_name = self.repo_url.split('/')[-1].replace('.git', '')
                pr_url = f'https://api.github.com/repos/{self.username}/{repo_name}/pulls'
                pr_data = {
                    'title': f'Добавлен новый функционал #{i+1}',
                    'body': f"""## Описание изменений
Добавлен новый функционал для обработки данных.
### Что сделано:
- Добавлен модуль `feature_{i+1}.py` с функциями обработки данных
- Добавлены unit-тесты
- Добавлена документация
- Обновлены зависимости
### Технические детали:
- Реализована функция `calculate_feature_{i+1}` для обработки данных
- Добавлена валидация входных данных
- Написаны тесты с использованием unittest
- Добавлена документация в формате Markdown
### Зависимости:
- numpy>=1.19.0
- pandas>=1.1.0
- pytest>=6.0.0""",
                    'head': branch_name,
                    'base': 'main'
                }
                pr_response = requests.post(pr_url, headers=self.headers, json=pr_data)
                if pr_response.status_code != 201:
                    raise Exception(f"Ошибка создания PR: {pr_response.json().get('message', 'Неизвестная ошибка')}")
                pr_number = pr_response.json()['number']
                time.sleep(random.randint(10, 20))
                merge_url = f'https://api.github.com/repos/{self.username}/{repo_name}/pulls/{pr_number}/merge'
                merge_data = {
                    'merge_method': 'merge',
                    'commit_title': f'Merge: Добавлен новый функционал #{i+1}',
                    'commit_message': f"""Объединение PR #{i+1}
Добавлен новый функционал для обработки данных:
- Новый модуль с функциями обработки
- Unit-тесты
- Документация
- Обновлены зависимости"""
                }
                merge_response = requests.put(merge_url, headers=self.headers, json=merge_data)
                if merge_response.status_code != 200:
                    raise Exception(f"Ошибка мержа PR: {merge_response.json().get('message', 'Неизвестная ошибка')}")
                self.run_git_command(["git", "checkout", "main"])
                self.run_git_command(["git", "pull", "origin", "main"])
                self.progress.emit(int((i + 1) / self.pr_count * 100))
            self.finished.emit(True, f"Успешно создано и замержено {self.pr_count} Pull Requests!")
        except Exception as e:
            self.finished.emit(False, f"Ошибка: {str(e)}")
        finally:
            self.cleanup()
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GitHub PR Creator")
        self.setMinimumSize(800, 600)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Auto_RP_Creator.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e; /* Темный фон */
            }
            QLabel {
                color: #ffffff; /* Белый текст */
                font-size: 16px;
            }
            QLineEdit {
                background-color: #2d2d2d; /* Темно-серый фон поля ввода */
                color: #ffffff; /* Белый текст ввода */
                border: 2px solid #3d3d3d;
                border-radius: 5px;
                padding: 10px;
                font-size: 16px;
            }
            QPushButton {
                background-color: #007acc; /* Синяя кнопка */
                color: white;
                border: none;
                border-radius: 5px;
                padding: 12px 25px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005f99;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
            QProgressBar {
                border: 2px solid #007acc;
                border-radius: 5px;
                text-align: center;
                background-color: #2d2d2d;
                color: white; /* Белый текст прогресса */
                font-size: 14px;
            }
            QProgressBar::chunk {
                background-color: #007acc;
            }
            QTextEdit {
                background-color: #2d2d2d; /* Темно-серый фон текстового поля */
                color: #ffffff; /* Белый текст */
                border: 2px solid #3d3d3d;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 40, 40, 40)
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        step1_widget = QWidget()
        step1_layout = QVBoxLayout(step1_widget)
        step1_layout.setSpacing(20)
        title1 = QLabel("Шаг 1: Введите данные GitHub")
        title1.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step1_layout.addWidget(title1)
        instructions1 = QLabel("""
        Для работы программы вам потребуется:
        1. Никнейм GitHub - ваш логин на GitHub
        2. Email GitHub - email, привязанный к вашему аккаунту GitHub
           (должен быть публичным в настройках GitHub)
        """)
        instructions1.setWordWrap(True)
        step1_layout.addWidget(instructions1)
        self.username_input = self.create_input_field(step1_layout, "Никнейм GitHub:", "Введите ваш никнейм GitHub")
        self.email_input = self.create_input_field(step1_layout, "Email GitHub:", "Введите email, привязанный к GitHub")
        step1_layout.addStretch(1)
        next_btn1 = QPushButton("Далее")
        next_btn1.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        step1_layout.addWidget(next_btn1)
        self.stacked_widget.addWidget(step1_widget)
        step2_widget = QWidget()
        step2_layout = QVBoxLayout(step2_widget)
        step2_layout.setSpacing(20)
        title2 = QLabel("Шаг 2: Получение токена GitHub")
        title2.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step2_layout.addWidget(title2)
        token_instructions = QLabel("""
        Для получения токена (с правами 'repo'):
        1. Нажмите 'Создать токен'
        2. Введите название токена (например: 'AutoPR')
        3. Выберите срок действия (рекомендуется 30 дней)
        4. В разделе 'Select scopes' выберите 'repo' и 'workflow'
        5. Нажмите 'Generate token'
        6. Скопируйте токен и вставьте его в поле ниже
        """)
        token_instructions.setWordWrap(True)
        step2_layout.addWidget(token_instructions)
        token_btn_layout = QHBoxLayout()
        token_btn = QPushButton("Создать токен GitHub")
        token_btn.clicked.connect(lambda: webbrowser.open("https://github.com/settings/tokens/new"))
        token_btn_layout.addWidget(token_btn)
        video_btn = QPushButton("Видео инструкция")
        video_btn.clicked.connect(lambda: webbrowser.open("receiving_a_token.mp4"))
        token_btn_layout.addWidget(video_btn)
        step2_layout.addLayout(token_btn_layout)
        self.token_input = self.create_input_field(step2_layout, "GitHub Token:", "Вставьте ваш токен сюда")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        step2_layout.addStretch(1)
        nav_layout2 = QHBoxLayout()
        back_btn2 = QPushButton("Назад")
        back_btn2.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        nav_layout2.addWidget(back_btn2)
        next_btn2 = QPushButton("Далее")
        next_btn2.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        nav_layout2.addWidget(next_btn2)
        step2_layout.addLayout(nav_layout2)
        self.stacked_widget.addWidget(step2_widget)
        step3_widget = QWidget()
        step3_layout = QVBoxLayout(step3_widget)
        step3_layout.setSpacing(20)
        title3 = QLabel("Шаг 3: URL репозитория")
        title3.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step3_layout.addWidget(title3)
        instructions3 = QLabel("""
        Для работы программы вам нужен репозиторий на GitHub:
        1. Если у вас еще нет репозитория:
           - Нажмите кнопку "Создать репозиторий"
           - Введите название репозитория
           - Выберите "Public" (публичный)
           - Нажмите "Create repository"
           - Скопируйте URL репозитория (кнопка "Code")
        URL должен быть в формате: https://github.com/username/repo.git
        """)
        instructions3.setWordWrap(True)
        step3_layout.addWidget(instructions3)
        create_repo_btn = QPushButton("Создать репозиторий")
        create_repo_btn.clicked.connect(lambda: webbrowser.open("https://github.com/new"))
        step3_layout.addWidget(create_repo_btn)
        self.repo_url_input = self.create_input_field(step3_layout, "URL репозитория:", "https://github.com/username/repo.git")
        step3_layout.addStretch(1)
        nav_layout3 = QHBoxLayout()
        back_btn3 = QPushButton("Назад")
        back_btn3.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        nav_layout3.addWidget(back_btn3)
        next_btn3 = QPushButton("Далее")
        next_btn3.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(3))
        nav_layout3.addWidget(next_btn3)
        step3_layout.addLayout(nav_layout3)
        self.stacked_widget.addWidget(step3_widget)
        step4_widget = QWidget()
        step4_layout = QVBoxLayout(step4_widget)
        step4_layout.setSpacing(20)
        title4 = QLabel("Шаг 4: Количество Pull Requests")
        title4.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title4.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step4_layout.addWidget(title4)
        self.pr_count_input = self.create_input_field(step4_layout, "Количество PR:", "Введите количество PR (1-1000)")
        self.pr_count_input.setValidator(QIntValidator(1, 1000))
        step4_layout.addStretch(1)
        self.create_button = QPushButton("Создать Pull Requests")
        self.create_button.clicked.connect(self.create_prs)
        step4_layout.addWidget(self.create_button)
        nav_layout4 = QHBoxLayout()
        back_btn4 = QPushButton("Назад")
        back_btn4.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        nav_layout4.addWidget(back_btn4)
        step4_layout.addLayout(nav_layout4)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        step4_layout.addWidget(self.progress_bar)
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        step4_layout.addWidget(self.status_text)
        self.stacked_widget.addWidget(step4_widget)
        self.load_saved_data()
    def create_input_field(self, target_layout, label_text, placeholder_text=""):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setMinimumWidth(150)
        layout.addWidget(label)
        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder_text)
        layout.addWidget(input_field)
        target_layout.addWidget(container)
        return input_field
    def create_prs(self):
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()
        token = self.token_input.text().strip()
        repo_url = self.repo_url_input.text().strip()
        try:
            pr_count = int(self.pr_count_input.text().strip())
        except ValueError:
            self.status_text.setText("Ошибка: Введите корректное число PR")
            return
        if not all([username, email, token, repo_url, pr_count]):
            self.status_text.setText("Ошибка: Пожалуйста, заполните все поля")
            return
        self.save_data(username, email, token, repo_url)
        self.worker = PRWorker(username, email, pr_count, token, repo_url)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.handle_finished)
        self.worker.error_signal.connect(self.status_text.setText) 
        self.create_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_text.setText("Создание Pull Requests...")
        self.worker.start()
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    def handle_finished(self, success, message):
        self.create_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_text.setText(message)
    def save_data(self, username, email, token, repo_url):
        data = {
            'username': username,
            'email': email,
            'token': token,
            'repo_url': repo_url
        }
        with open('pr_creator_data.json', 'w') as f:
            json.dump(data, f)
    def load_saved_data(self):
        try:
            with open('pr_creator_data.json', 'r') as f:
                data = json.load(f)
                self.username_input.setText(data.get('username', ''))
                self.email_input.setText(data.get('email', ''))
                self.token_input.setText(data.get('token', ''))
                self.repo_url_input.setText(data.get('repo_url', ''))
        except:
            pass
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 