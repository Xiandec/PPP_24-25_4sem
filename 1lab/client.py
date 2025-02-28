import socket
import json
import os
from typing import Dict, List, Union
import struct  

from config import HOST, PORT


class Client:
    def __init__(self):
        self.host = HOST
        self.port = PORT
        self.socket = None
        # Добавляем цветовые коды
        self.BLUE = '\033[94m'
        self.GREEN = '\033[92m'
        self.RESET = '\033[0m'
        self.RED = '\033[91m'
        self.YELLOW = '\033[93m'

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print("Подключение установлено")
        except Exception as e:
            print(f"Ошибка подключения: {e}")

    def run(self):
        os.system('clear || cls')
        print("\nДоступные команды:")
        print("  ls <путь_к_каталогу> - просмотр содержимого директории")
        print("  cd <путь> - сменить директорию")
        print("  cd .. - перейти на уровень выше")
        print("  clear - очистить консоль")
        print("  exit - выход\n")

        while True:
            try:
                command = input("Введите команду: ").strip()
                if command == 'exit':
                    break

                if command.startswith('ls'):
                    parts = command.split(maxsplit=1)
                    directory_path = parts[1].strip() if len(parts) > 1 else ''  # Проверяем наличие аргумента
                    self.request_directory(directory_path)

                elif command.startswith('cd'):
                    parts = command.split(maxsplit=1)
                    if len(parts) == 1 or not parts[-1].strip():  # Проверяем наличие аргумента
                        os.system('clear || cls')
                        print("Укажите новую корневую директорию!")
                        continue
                    new_root = parts[-1].strip()
                    self.change_root(new_root)
                elif command.startswith('clear'):
                    os.system('clear || cls')

                else:
                    os.system('clear || cls')
                    print("Неизвестная команда")
            except KeyboardInterrupt:
                print("Сервер остановлен")
                self.disconnect()
                break
            except Exception as e:
                print(f"Ошибка обработки запроса: {e}")

        self.disconnect()

    def receive_message(self):
        """Получение сообщения с предварительной длиной"""
        # Получаем длину сообщения (4 байта)
        length_bytes = self.socket.recv(4)
        if not length_bytes:
            return None
        message_length = struct.unpack('!I', length_bytes)[0]
        
        # Получаем само сообщение
        chunks = []
        bytes_received = 0
        while bytes_received < message_length:
            chunk = self.socket.recv(min(message_length - bytes_received, 4096))
            if not chunk:
                break
            chunks.append(chunk)
            bytes_received += len(chunk)
        
        return b''.join(chunks).decode('utf-8')

    def request_directory(self, directory_path: str = None):
        message = f"ls {directory_path}".encode('utf-8')
        try:
            os.system('clear || cls')
            self.socket.send(message)
            response = self.receive_message()
            if response:
                try:
                    files_info = json.loads(response)
                    self.print_directory_tree(files_info)
                except json.JSONDecodeError:
                    print(f"{self.RED}Ошибка при разборе ответа от сервера{self.RESET}")
        except Exception as e:
            print(f"{self.RED}Ошибка при получении каталога: {e}{self.RESET}")

    def change_root(self, new_root: str):
        message = f"cd {new_root}".encode('utf-8')
        try:
            os.system('clear || cls')
            self.socket.send(message)
            response = self.receive_message()
            if response == "ОК":
                print(f"Корневая директория успешно изменена на {new_root}")
            else:
                print(response)
        except Exception as e:
            print(f"Ошибка при изменении корневой директории: {e}")

    def print_directory_tree(self, files_info: Dict[str, Union[List[str], List[str]]]):
        if 'error' in files_info:
            print(f"{self.RED}Ошибка: {files_info['error']}{self.RESET}")
            return
        if 'warning' in files_info:
            print(f"{self.YELLOW}{files_info.pop('warning')}{self.RESET}")
            

        # Печатаем текущий путь синим цветом
        current_path = files_info.pop('current_path', '')
        print(f"{self.BLUE}Текущая директория: {current_path}{self.RESET}\n")

        for key, value in files_info.items():
            print(f"{self.GREEN}{key}{self.RESET}")
            for d in value['dirs']:
                print(f"\t📁 {d}")
            for f in value['files']:
                print(f"\t📄 {f}")
            if 'warning' in value:
                print(f"\n{self.YELLOW}{value['warning']}{self.RESET}")

    def disconnect(self):
        self.socket.close()
        print("Отключено")


if __name__ == "__main__":
    client = Client()
    client.connect()
    client.run()