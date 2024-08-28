#!/usr/bin/env python3.8
__author__ = 'InfSub'
__contact__ = 'ADmin@TkYD.ru'
__copyright__ = 'Copyright (C) 2024, [LegioNTeaM] InfSub'
__date__ = '2024/08/28'
__deprecated__ = False
__email__ = 'ADmin@TkYD.ru'
__maintainer__ = 'InfSub'
__status__ = 'Production'
__version__ = '2.2.0'


import sys
import os
import subprocess
from pathlib import Path
from ftplib import FTP, all_errors
import shutil
import winreg
import posixpath
from dotenv import load_dotenv

import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime


def is_venv():
    return (hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))


def create_venv():
    venv_dir = Path("venv")
    logger.info("Creating virtual environment...")
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    return venv_dir


def install_requirements(venv_python):
    logger.info("Installing requirements...")
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
            logger.info('Обнаружены обновления. Обновляемся...')
            subprocess.run(['git', 'pull'], cwd=LOCAL_REPO_DIR, check=True, capture_output=True, text=True)
            logger.info(f'Обновление завершено. Перезапуск...{ln()}')
            activate_venv_and_restart()
        else:
            logger.info(f'Ветка уже обновлена.{ln()}')

    except subprocess.CalledProcessError as e:
        logger.critical(f'Ошибка при проверке обновлений: {e}')
        logger.critical(f'Вывод: {e.output.decode()}{ln()}')
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

    logger.debug(f'Python path: {python_path}')
    logger.debug(f'Script path: {LOCAL_REPO_DIR}')

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
    logger.info(f'Adding to autostart at user login.{ln()}')


def check_exist_dir(directory: str) -> None:
    """Проверяет наличие каталога и создает его при необходимости."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        if 'logger' in globals() and logger is not None:
            logger.info(f'Создана директория: {directory}')


def copy_file_from_ftp(ftp: FTP, remote_path: str, local_path: str) -> None:
    """Копирует файл с FTP-сервера на локальную машину."""
    if check_file_exists_on_ftp(ftp, remote_path):
        with open(local_path, 'wb') as local_file:
            def callback(data):
                local_file.write(data)
            ftp.retrbinary(f'RETR {remote_path}', callback)
        logger.info(f'Файл: {local_path} - скопирован с FTP.{ln()}')
    else:
        logger.info(f'Файл: {remote_path} - не существует на FTP-сервере.{ln()}')


def check_file_exists_on_ftp(ftp, filepath) -> bool:
    """
    Check if the given file exists on the FTP server.

    :param ftp: FTP connection object
    :param filepath: Path to the file to check
    :return: True if the file exists, False otherwise
    """
    try:
        ftp.encoding = 'latin-1'  # Устанавливаем кодировку latin-1 для FTP соединения
        if filepath in ftp.nlst():
            return True
        else:
            return False
    except Exception as e:
        logger.error(f'Ошибка при получении списка файлов: {e}')
        return False


def synchronize_files(params: dict) -> None:
    required_keys = ['ftp_host', 'ftp_user', 'ftp_password', 'remote_paths', 'local_paths', 'remote_base_path',
                     'local_base_path', 'backup_path']
    if not all(params.get(key) for key in required_keys):
        logger.critical('Error: Не все необходимые параметры переданы.')
        return

    if len(params['remote_paths']) != len(params['local_paths']):
        logger.critical('Error: Количество локальных и удаленных путей не совпадает.')
        return

    try:
        with (FTP(params['ftp_host'], params['ftp_user'], params['ftp_password']) as ftp):
            logger.info(f'Успешное подключение к FTP{ln()}')

            for remote_path, local_path in zip(params['remote_paths'], params['local_paths']):
                # Функция os.path.join в Python автоматически использует символ пути, соответствующий операционной
                # системе, на которой выполняется скрипт. В Windows это обратный слеш (\), а в Unix-подобных системах
                # (например, Linux) это прямой слеш (/).
                # Если вам требуется получать путь с использованием прямых слешей, то можно воспользоваться модулем
                # posixpath, который предназначен для работы с путями в Unix-подобных системах.
                remote_path = f'{posixpath.join(params["remote_base_path"], remote_path)}'
                local_path = f'{os.path.join(params["local_base_path"], local_path)}'
                local_dir = f'{os.path.dirname(local_path)}'
                local_backup_dir = f'{os.path.join(local_dir, params["backup_path"])}'

                check_exist_dir(local_dir)
                check_exist_dir(local_backup_dir)

                is_copy = False

                # Проверяем, существует ли локальный файл
                if not os.path.isfile(local_path):
                    logger.info(f'Локальный файл {local_path} не найден.')
                    is_copy = True
                else:
                    resp = ftp.sendcmd(f'MDTM {remote_path}')
                    remote_time = datetime.strptime(resp[4:], "%Y%m%d%H%M%S")
                    local_time = datetime.fromtimestamp(os.path.getmtime(local_path)).replace(microsecond=0)

                    if local_time < remote_time:
                        current_time = datetime.now().strftime('%Y.%m.%d-%H.%M')
                        base_name, file_extension = os.path.splitext(local_path)
                        new_file_name = f"{base_name}_{current_time}{file_extension}"

                        shutil.copy(local_path, os.path.join(local_backup_dir, new_file_name))
                        logger.info(f"Бэкап файла '{local_path}' создан с именем '{new_file_name}'.")
                        is_copy = True
                    else:
                        logger.info(f'Обновление для файла: {local_path} - не требуется.')

                if is_copy:
                    logger.info('Проверяем наличие файла на FTP:')
                    copy_file_from_ftp(ftp, remote_path, local_path)

    except all_errors as e:
        logger.error(f'Ошибка FTP: {e}')
    except Exception as e:
        logger.error(f'Непредвиденная ошибка: {e}')


def run() -> None:
    logger.info(f'The script version: {__version__} - is being executed.{ln()}')
    params = {}
    if not is_venv():
        logger.warning('Not running in a virtual environment.')
        venv_dir = Path('venv')

        if not venv_dir.is_dir():
            venv_dir = create_venv()

        venv_python = venv_dir / "Scripts" / "python.exe"

        install_requirements(venv_python)

        logger.info(f'Restarting script using virtual environment: {venv_python}')
        subprocess.check_call([str(venv_python), __file__])
        sys.exit()
    else:
        logger.info('Running in a virtual environment.')
        try:
            import dotenv
        except ImportError:
            install_requirements(sys.executable)
            subprocess.check_call([sys.executable, __file__])
            sys.exit()

    # Здесь идет основной код вашей программы
    logger.info('Все необходимые библиотеки установлены и скрипт выполнен в виртуальном окружении.')

    # Загрузка переменных окружения из файла .env
    load_dotenv()

    # Параметры FTP
    params['ftp_host'] = os.getenv('FTP_HOST')
    params['ftp_user'] = os.getenv('FTP_USER')
    params['ftp_password'] = os.getenv('FTP_PASSWORD')
    params['remote_base_path'] = os.getenv('REMOTE_BASE_PATH', '')
    params['remote_paths'] = os.getenv('REMOTE_PATHS')
    params['local_base_path'] = os.getenv('LOCAL_BASE_PATH', '')
    params['local_paths'] = os.getenv('LOCAL_PATHS')
    params['backup_path'] = os.getenv('BACKUP_PATH', '')

    if params['remote_paths'] is not None:
        params['remote_paths'] = params['remote_paths'].split(';')
    if params['local_paths'] is not None:
        params['local_paths'] = params['local_paths'].split(';')

    check_for_updates()
    # adding to autostart at user login
    add_to_registry()
    synchronize_files(params)


if __name__ == '__main__':
    # Параметры Git
    # Путь к локальной директории, где хранится скрипт
    LOCAL_REPO_DIR = os.path.dirname(os.path.realpath(__file__))
    # Путь к директории виртуального окружения
    VENV_DIR = os.path.join(LOCAL_REPO_DIR, 'venv')
    # Реестр
    REGISTRY_PATH = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
    REGISTRY_KEY = 'SLS-Updater-from-FTP'
    # Logs
    log_dir = 'logs'
    log_path = os.path.join(LOCAL_REPO_DIR, log_dir)

    check_exist_dir(log_dir)

    # Создание форматировщика
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Настройка файлового обработчика
    filename = datetime.now().strftime('logfile_%Y%m%d_%H%M%S.log')
    file_handler = logging.FileHandler(os.path.join(log_path, filename))
    file_handler.setFormatter(log_formatter)

    # Настройка консольного обработчика
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    # Настройка логгера
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Устанавливаем уровень логирования

    # Добавление обработчиков к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    run()
