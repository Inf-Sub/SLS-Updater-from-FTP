#!/usr/bin/env python3.8
__author__ = 'InfSub'
__contact__ = 'ADmin@TkYD.ru'
__copyright__ = 'Copyright (C) 2024, [LegioNTeaM] InfSub'
__date__ = '2024/08/27'
__deprecated__ = False
__email__ = 'ADmin@TkYD.ru'
__maintainer__ = 'InfSub'
__status__ = 'Production'
__version__ = '2.0.1'

import sys
import os
import subprocess
from pathlib import Path
import logging
from ftplib import FTP, all_errors
from datetime import datetime
import shutil
import winreg


# Настройка логирования
logging.basicConfig(level=logging.INFO)


# Параметры Git
# Путь к локальной директории, где хранится скрипт
LOCAL_REPO_DIR = os.path.dirname(os.path.realpath(__file__))
# Путь к директории виртуального окружения
VENV_DIR = os.path.join(LOCAL_REPO_DIR, 'venv')
# Реестр
REGISTRY_PATH = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
REGISTRY_KEY = 'SLS-Updater-from-FTP'


def is_venv():
    return (hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))


def create_venv():
    venv_dir = Path("venv")
    print("Creating virtual environment...")
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    print(type(venv_dir))
    return venv_dir


def install_requirements(venv_python):
    print("Installing requirements...")
    subprocess.check_call([venv_python, "-m", "pip", "install", "-r", "requirements.txt"])


def ln(num: int = 30) -> str:
    return f'\n{"=" * num}'


def check_for_updates() -> None:
    try:
        subprocess.run(
            ['git', 'fetch'], cwd=LOCAL_REPO_DIR, check=True, capture_output=True, text=True
        )
        status = subprocess.run(
            ['git', 'status', '-uno'], cwd=LOCAL_REPO_DIR, check=True, capture_output=True, text=True
        )
        if 'Your branch is up to date' not in status.stdout:
            print('Обнаружены обновления. Обновляемся...')
            subprocess.run(['git', 'pull'], cwd=LOCAL_REPO_DIR, check=True, capture_output=True, text=True)
            print('Обновление завершено. Перезапуск...')
            activate_venv_and_restart()
        else:
            print('Ветка уже обновлена.')

        print(f'{ln()}')

    except subprocess.CalledProcessError as e:
        print(f'Ошибка при проверке обновлений: {e}{ln()}Вывод: {e.output.decode()}{ln()}')
        exit(1)


def activate_venv_and_restart() -> None:
    activate_script = os.path.join(VENV_DIR, 'Scripts', 'activate.bat')
    python_exec = os.path.join(VENV_DIR, 'Scripts', 'pythonw.exe')
    command = f'cmd.exe /k ""{activate_script}" && "{python_exec}" "{" ".join(sys.argv)}""'
    os.system(command)
    exit(0)


def add_to_registry() -> None:
    python_path = os.path.abspath(sys.executable)

    # hide mode
    python_path = python_path.replace('python.exe', 'pythonw.exe')

    print(f'Python path: {python_path}')
    print(f'Script path: {LOCAL_REPO_DIR}{ln()}')

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        REGISTRY_PATH,
        0,
        winreg.KEY_SET_VALUE)
    winreg.SetValueEx(
        key,
        REGISTRY_KEY,
        0,
        winreg.REG_SZ,
        f'{python_path} "{LOCAL_REPO_DIR}'
        r'\main.py"'
    )
    key.Close()


def copy_file_from_ftp(ftp, remote_path, local_path) -> None:
    with open(local_path, 'wb') as local_file:
        """
        Открываем локальный файл в режиме записи байтов (binary write mode). Если файл с указанным local_path уже 
        существует, он будет перезаписан. Если файла нет, он будет создан.
        """
        def callback(data):
            """
            Внутри блока with определяется функция callback, которая принимает один параметр data. Эта функция будет
            использоваться для записи данных, полученных от FTP-сервера, в локальный файл. Всякий раз, когда FTP-сервер
            отправляет очередной блок данных, callback вызывается и записывает эти данные в local_file.
            """
            local_file.write(data)

    if check_file_exists_on_ftp(ftp, remote_path):
        ftp.retrbinary(f'RETR {remote_path}', callback)


def check_exist_dir(local_dir) -> None:
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
        print(f"Создана директория: {local_dir}")


def check_file_exists_on_ftp(ftp, filepath) -> bool:
    """
    Check if the given file exists on the FTP server.

    :param ftp: FTP connection object
    :param filepath: Path to the file to check
    :return: True if the file exists, False otherwise
    """
    file_found = False

    def file_check_callback(line):
        nonlocal file_found
        parts = line.split()
        file_name = parts[-1]
        if file_name == filepath:
            file_found = True

    try:
        ftp.retrlines('LIST', file_check_callback)
    except Exception as e:
        logging.error(f'Ошибка при получении списка файлов: {e}')
        return False

    if file_found:
        msg = f'Файл: {filepath} - найден на FTP.'
        print(msg)
        return True
    else:
        msg = f'Файл: {filepath} - не найден на FTP.'
        logging.error(msg)
        print(msg)
        return False


def synchronize_files(params: dict) -> None:
    if not all([
        params['ftp_host'], params['ftp_user'], params['ftp_password'], params['remote_paths'], params['local_paths']
    ]):
        logging.error("Не все переменные окружения заданы.")
        return

    if len(params['remote_paths']) != len(params['local_paths']):
        logging.error("Количество локальных и удаленных путей не совпадает.")
        return

    try:
        with FTP(params['ftp_host'], params['ftp_user'], params['ftp_password']) as ftp:
            print("Успешное подключение к FTP")
    
            for remote_path, local_path in zip(params['remote_paths'], params['local_paths']):
                remote_path = params['remote_base_path'] + remote_path
                local_path = params['local_base_path'] + local_path
    
                # Проверяем, существует ли локальная директория, и создаем ее при необходимости
                local_dir = os.path.dirname(local_path)
                check_exist_dir(local_dir)

                # Проверяем, существует ли локальная директория для бэкапа, и создаем ее при необходимости
                local_backup_path = os.path.join(local_dir, params['backup_path'])
                local_backup_dir = os.path.dirname(local_backup_path)
                check_exist_dir(local_backup_dir)
    
                # Проверяем, существует ли локальный файл
                if not os.path.isfile(local_path):
                    print(f"Локальный файл {local_path} не найден. Начинаем копирование с FTP...")
                    copy_file_from_ftp(ftp, remote_path, local_path)
                    print(f"Файл {local_path} успешно скопирован с FTP.")
                else:
                    # Если файл существует, сравниваем время модификации
                    resp = ftp.sendcmd('MDTM ' + remote_path)
                    remote_time = datetime.strptime(resp[4:], "%Y%m%d%H%M%S")
                    local_time = datetime.fromtimestamp(os.path.getmtime(local_path))
    
                    if local_time < remote_time:
                        current_time = datetime.now().strftime('%Y.%m.%d-%H.%M')
                        file_extension = local_path.split('.')[-1]
                        base_name = local_path.rsplit('.', 1)[0]
                        new_file_name = f"{base_name}_{current_time}.{file_extension}"
    
                        shutil.copy(local_path, os.path.join(local_backup_dir, new_file_name))
                        print(f"Бэкап файла '{local_path}' создан с именем '{new_file_name}'.")
    
                        # Обновляем файл с FTP
                        copy_file_from_ftp(ftp, remote_path, local_path)
                        print(f"Файл {local_path} обновлен с FTP.")
                    else:
                        print(f"Локальный файл {local_path} новее или файлы одинаковые. Обновление не требуется.")
    except all_errors as e:
        logging.error(f"Ошибка FTP: {e}")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка: {e}")
    # finally:
    #     try:
    #         ftp.quit()
    #     except:
    #         pass


def run() -> None:
    params = {}
    if not is_venv():
        print("Not running in a virtual environment.")
        venv_dir = Path("venv")

        if not venv_dir.is_dir():
            venv_dir = create_venv()

        venv_python = venv_dir / "Scripts" / "python.exe"

        install_requirements(venv_python)

        print(f"Restarting script using virtual environment: {venv_python}")
        subprocess.check_call([str(venv_python), __file__])
        sys.exit()
    else:
        print("Running in a virtual environment.")
        try:
            import dotenv
        except ImportError:
            install_requirements(sys.executable)
            subprocess.check_call([sys.executable, __file__])
            sys.exit()

    # Начало вашего основного скрипта
    from dotenv import load_dotenv

    # Здесь идет основной код вашей программы
    print("Все необходимые библиотеки установлены и скрипт выполнен в виртуальном окружении.")

    # Загрузка переменных окружения из файла .env
    load_dotenv()

    # Параметры FTP
    params['ftp_host'] = os.getenv('FTP_HOST')
    params['ftp_user'] = os.getenv('FTP_USER')
    params['ftp_password'] = os.getenv('FTP_PASSWORD')
    params['remote_base_path'] = os.getenv('REMOTE_BASE_PATH', '')
    params['remote_paths'] = os.getenv('REMOTE_PATHS').split(';')
    params['local_base_path'] = os.getenv('LOCAL_BASE_PATH', '')
    params['local_paths'] = os.getenv('LOCAL_PATHS').split(';')
    params['backup_path'] = os.getenv('BACKUP_PATH', '')

    check_for_updates()
    # adding to autostart at user login
    add_to_registry()
    print(f'Adding to autostart at user login.{ln()}')
    print('Запуск основной части скрипта...')
    synchronize_files(params)


if __name__ == '__main__':
    run()
