import socket
import threading
import json
import os
import logging
from typing import Dict, List, Union
import struct

from config import HOST, PORT, LOG_LEVEL


def setup_logger():
    """
    Настраивает систему логирования для сервера.

    Returns:
        logging.Logger: Объект логгера с установленным уровнем INFO и выводом в консоль.
    """
    logger = logging.getLogger('server_logger')
    logger.setLevel(LOG_LEVEL)

    # Создаем форматтер для логов
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Хендлер для вывода в консоль важных сообщений
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


class Server:
    """
    Класс сервера для удаленного управления файловой системой через сокеты.

    Attributes:
        host (str): IP-адрес или имя хоста сервера.
        port (int): Порт для прослушивания подключений.
        socket (socket.socket): Сокет сервера для обработки подключений.
        clients (List[socket.socket]): Список активных клиентских сокетов.
        root_dir (str): Текущая корневая директория сервера.
        logger (logging.Logger): Объект для логирования событий сервера.
    """

    def __init__(self):
        """
        Инициализирует сервер с параметрами из конфигурации и настраивает логирование.
        """
        self.host = HOST
        self.port = PORT
        self.socket = None
        self.clients = []
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.logger = setup_logger()

    def start(self):
        """
        Запускает сервер, начинает прослушивание подключений и обрабатывает клиентов.

        Raises:
            KeyboardInterrupt: При остановке сервера пользователем.
            Exception: При критической ошибке сервера.
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.host, self.port))
            self.logger.info(f"Сервер запущен на порту {self.port}")
            self.logger.debug("Логирование с уровнем DEBUG")
            self.socket.listen()

            while True:
                client_socket, address = self.socket.accept()
                self.logger.info(f"Новое подключение от {address}")
                self.clients.append(client_socket)
                threading.Thread(target=self.handle_client,
                                 args=(client_socket,)).start()

        except KeyboardInterrupt:
            self.logger.warning("Сервер остановлен пользователем")
            self.stop()
        except Exception as e:
            self.logger.error(f"Критическая ошибка сервера: {str(e)}")
            self.stop()

    def handle_client(self, client_socket):
        """
        Обрабатывает запросы от клиента в отдельном потоке.

        Args:
            client_socket (socket.socket): Сокет подключенного клиента.

        Raises:
            ConnectionResetError: Если клиент неожиданно отключился.
            Exception: При ошибке обработки запроса.
        """
        try:
            client_address = client_socket.getpeername()
            self.logger.debug(f"Начало обработки клиента {client_address}")
        except:
            client_address = "Неизвестный"
            self.logger.warning(f"Не удалось получить адрес клиента")

        while True:
            try:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                self.logger.debug(
                    f"Получена команда от {client_address}: {data}")
                command, *arguments = data.split()

                if command == 'ls':
                    directory_path = arguments[0] if arguments else ''
                    self.logger.debug(
                        f"Запрос содержимого директории: {directory_path or self.root_dir}")
                    files_info = self.get_files_info(
                        directory_path or self.root_dir)
                    files_info['current_path'] = self.root_dir
                    response_json = json.dumps(files_info)
                    response_bytes = response_json.encode('utf-8')
                    client_socket.send(struct.pack('!I', len(response_bytes)))
                    client_socket.send(response_bytes)
                    self.logger.debug(
                        f"Отправлен ответ размером {len(response_bytes)} байт")

                elif command == 'cd':
                    new_root = arguments[0]
                    self.logger.debug(
                        f"Запрос на смену директории: {new_root}")
                    if new_root == '..':
                        parent_dir = os.path.dirname(self.root_dir)
                        if os.path.exists(parent_dir) and os.path.isdir(parent_dir):
                            self.root_dir = parent_dir
                            self.logger.info(
                                f"Переход в родительскую директорию: {parent_dir}")
                            response = "ОК".encode('utf-8')
                            client_socket.send(
                                struct.pack('!I', len(response)))
                            client_socket.send(response)
                        else:
                            self.logger.warning(
                                "Попытка выйти за пределы корневой директории")
                            response = "Невозможно перейти выше корневой директории".encode(
                                'utf-8')
                            client_socket.send(
                                struct.pack('!I', len(response)))
                            client_socket.send(response)
                    elif self.validate_new_root(new_root):
                        self.root_dir = os.path.join(self.root_dir, new_root)
                        self.logger.info(
                            f"Смена директории на: {self.root_dir}")
                        response = "ОК".encode('utf-8')
                        client_socket.send(struct.pack('!I', len(response)))
                        client_socket.send(response)
                    else:
                        self.logger.warning(
                            f"Попытка перехода в несуществующую директорию: {new_root}")
                        response = "Неверный путь к директории".encode('utf-8')
                        client_socket.send(struct.pack('!I', len(response)))
                        client_socket.send(response)
                else:
                    self.logger.warning(
                        f"Получена неизвестная команда: {command}")
                    response = "Неизвестная команда".encode('utf-8')
                    client_socket.send(struct.pack('!I', len(response)))
                    client_socket.send(response)

            except ConnectionResetError:
                self.logger.info(f"Клиент {client_address} отключился")
                self.clients.remove(client_socket)
                break
            except Exception as e:
                self.logger.error(
                    f"Ошибка при обработке запроса от {client_address}: {str(e)}")
                try:
                    client_socket.send(
                        "Ошибка при обработке запроса".encode('utf-8'))
                except:
                    self.logger.error(
                        "Не удалось отправить сообщение об ошибке клиенту")
                break

    def validate_new_root(self, new_root: str) -> bool:
        """
        Проверяет, существует ли указанная директория и является ли она директорией.

        Args:
            new_root (str): Относительный путь к новой директории.

        Returns:
            bool: True, если путь существует и является директорией, иначе False.
        """
        full_path = os.path.join(self.root_dir, new_root)
        return os.path.exists(full_path) and os.path.isdir(full_path)

    def get_files_info(self, path: str) -> Dict[str, Union[List[str], List[str]]]:
        """
        Собирает информацию о файлах и подкаталогах в указанном пути.

        Args:
            path (str): Относительный путь от текущей корневой директории.

        Returns:
            Dict[str, Union[List[str], List[str]]]: Словарь с информацией о файлах и директориях.
                Ключи:
                    - <relative_path>: {'dirs': List[str], 'files': List[str], 'warning': str (опционально)}
                    - 'current_path': str
                    - 'warning': str (опционально)
                    - 'error': str (при ошибке)
        """
        try:
            target_path = os.path.join(self.root_dir, path)
            files_info = {}

            if not os.path.exists(target_path):
                return {"error": "Путь не существует"}

            MAX_ITEMS = 100  # Максимальное количество элементов в директории
            MAX_RESPONSE_SIZE = 2048  # Оставляем запас для JSON-форматирования

            for root, dirs, files in os.walk(target_path):
                relative_root = os.path.relpath(root, self.root_dir)

                total_items = len(dirs) + len(files)
                dirs_to_show = dirs[:MAX_ITEMS//2]
                files_to_show = files[:MAX_ITEMS//2]

                test_response = {
                    **files_info,
                    relative_root: {
                        'dirs': dirs_to_show,
                        'files': files_to_show
                    },
                    'current_path': self.root_dir
                }

                adding_allow = True
                while len(json.dumps(test_response).encode('utf-8')) > MAX_RESPONSE_SIZE:
                    if len(dirs_to_show) == 0 and len(files_to_show) == 0:
                        adding_allow = False
                        break
                    else:
                        if len(dirs_to_show) > 0:
                            dirs_to_show = dirs_to_show[:-1]
                        if len(files_to_show) > 0:
                            files_to_show = files_to_show[:-1]

                        test_response = {
                            **files_info,
                            relative_root: {
                                'dirs': dirs_to_show,
                                'files': files_to_show
                            },
                            'current_path': self.root_dir
                        }

                if adding_allow:
                    files_info[relative_root] = {
                        'dirs': dirs_to_show,
                        'files': files_to_show
                    }

                    if total_items > len(dirs_to_show) + len(files_to_show):
                        files_info[relative_root]['warning'] = (
                            f'Показано {len(dirs_to_show)} директорий и {len(files_to_show)} '
                            f'файлов из {len(dirs)} директорий и {len(files)} файлов'
                        )

                if len(json.dumps(files_info).encode('utf-8')) > MAX_RESPONSE_SIZE or not adding_allow:
                    files_info['warning'] = 'Показана только часть структуры каталогов из-за ограничения размера ответа'
                    break

            return files_info
        except Exception as e:
            return {"error": str(e)}

    def stop(self):
        """
        Останавливает сервер и закрывает все активные соединения.
        """
        self.logger.info("Остановка сервера...")
        for client in self.clients:
            try:
                client.close()
            except:
                self.logger.warning(
                    "Ошибка при закрытии соединения с клиентом")
        try:
            self.socket.close()
        except:
            self.logger.error("Ошибка при закрытии серверного сокета")
        self.logger.info("Сервер остановлен")


if __name__ == "__main__":
    server = Server()
    server.start()
