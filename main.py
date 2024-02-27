#!/usr/bin/env python3.8
__author__ = 'InfSub'
__contact__ = 'ADmin@TkYD.ru'
__copyright__ = 'Copyright (C) 2024, [LegioNTeaM] InfSub'
__date__ = '2024/02/27'
__deprecated__ = False
__email__ = 'ADmin@TkYD.ru'
__maintainer__ = 'InfSub'
__status__ = 'Production'
__version__ = '1.0.0'


import ftplib
from datetime import datetime
import os
import logging
import shutil
import subprocess
import sys
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загрузка переменных окружения из файла .env
load_dotenv()

# Параметры FTP
ftp_host = os.getenv('FTP_HOST')
ftp_user = os.getenv('FTP_USER')
ftp_password = os.getenv('FTP_PASSWORD')
remote_base_path = os.getenv('REMOTE_BASE_PATH', '')
remote_paths = os.getenv('REMOTE_PATHS').split(';')
local_base_path = os.getenv('LOCAL_BASE_PATH', '')
local_paths = os.getenv('LOCAL_PATHS').split(';')

# Параметры Git
# URL вашего репозитория на GitHub
# REPO_URL = 'https://github.com/username/repo.git'
REPO_URL = 'https://github.com/ADmin-TkYD/SLS-Updater-from-FTP.git'
# Путь к локальной директории, где хранится скрипт
# LOCAL_REPO_DIR = r'C:\path\to\your\script'
LOCAL_REPO_DIR = os.path.dirname(os.path.realpath(__file__))
# Путь к директории виртуального окружения
# VENV_DIR = 'C:\\path\\to\\your\\venv'
VENV_DIR = os.path.join(LOCAL_REPO_DIR, 'venv')


def check_for_updates():
    try:
        subprocess.run(
            ['git', 'fetch'], cwd=LOCAL_REPO_DIR, check=True, capture_output=True, text=True
        )
        status = subprocess.run(
            ['git', 'status', '-uno'], cwd=LOCAL_REPO_DIR, check=True, capture_output=True, text=True
        )
        if 'Your branch is up to date' not in status.stdout:
            print('Обнаружены обновления. Обновляемся...')
            subprocess.run(['git', 'pull'], cwd=LOCAL_REPO_DIR, check=True)
            print('Обновление завершено. Перезапуск...')
            activate_venv_and_restart()
    except subprocess.CalledProcessError as e:
        print(f'Ошибка при проверке обновлений: {e}')
        exit(1)


def activate_venv_and_restart():
    activate_script = os.path.join(VENV_DIR, 'Scripts', 'activate.bat')
    python_exec = os.path.join(VENV_DIR, 'Scripts', 'python.exe')
    command = f'cmd.exe /k "{activate_script} && {python_exec} {" ".join(sys.argv)}"'
    os.system(command)
    exit(0)


def synchronize_files():
    if not all([ftp_host, ftp_user, ftp_password, remote_paths, local_paths]):
        logging.error("Не все переменные окружения заданы.")
        return

    if len(remote_paths) != len(local_paths):
        logging.error("Количество локальных и удаленных путей не совпадает.")
        return

    try:
        ftp = ftplib.FTP(ftp_host, ftp_user, ftp_password)
        logging.info("Успешное подключение к FTP")

        for remote_path, local_path in zip(remote_paths, local_paths):
            remote_path = remote_base_path + remote_path
            local_path = local_base_path + local_path

            # Проверяем, существует ли локальная директория, и создаем ее при необходимости
            local_dir = os.path.dirname(local_path)
            if not os.path.exists(local_dir):
                os.makedirs(local_dir)
                logging.info(f"Создана директория: {local_dir}")

            # Проверяем, существует ли локальный файл
            if not os.path.isfile(local_path):
                logging.info(f"Локальный файл {local_path} не найден. Начинаем копирование с FTP...")
                with open(local_path, 'wb') as local_file:
                    def callback(data):
                        local_file.write(data)

                    ftp.retrbinary(f'RETR {remote_path}', callback)
                logging.info(f"Файл {local_path} успешно скопирован с FTP.")
            else:
                # Если файл существует, сравниваем время модификации
                resp = ftp.sendcmd('MDTM ' + remote_path)
                remote_mtime = datetime.strptime(resp[4:], "%Y%m%d%H%M%S")
                local_mtime = datetime.fromtimestamp(os.path.getmtime(local_path))

                if local_mtime < remote_mtime:
                    current_time = datetime.now().strftime('%Y.%m.%d-%H.%M')
                    file_extension = local_path.split('.')[-1]
                    base_name = local_path.rsplit('.', 1)[0]
                    new_file_name = f"{base_name}_{current_time}.{file_extension}"

                    shutil.copy(local_path, new_file_name)
                    logging.info(f"Бэкап файла '{local_path}' создан с именем '{new_file_name}'.")

                    # Обновляем файл с FTP
                    with open(local_path, 'wb') as local_file:
                        def callback(data):
                            local_file.write(data)

                        ftp.retrbinary(f'RETR {remote_path}', callback)
                    logging.info(f"Файл {local_path} обновлен с FTP.")
                else:
                    logging.info(f"Локальный файл {local_path} новее или файлы одинаковые. Обновление не требуется.")
    except ftplib.all_errors as e:
        logging.error(f"Ошибка FTP: {e}")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка: {e}")
    finally:
        try:
            ftp.quit()
        except:
            pass


def main():
    print('Запуск основной части скрипта...')
    synchronize_files()


if __name__ == '__main__':
    check_for_updates()
    main()
