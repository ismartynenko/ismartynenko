import json
import argparse
import logging
import os
import sys
from functools import partial
from urllib import parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from database import DBClient


class MyHandler(BaseHTTPRequestHandler):
    def __init__(self, db, *args, **kwargs):
        self.db = db
        super().__init__(*args, **kwargs)
        self.ua = None

    # Отправка заголовков
    def do(self, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        # Определяем User-agent
        self.ua = self.headers['User-Agent'].split('/')[0]
        # Проверяем и удаляем ссылки с истекшим временем жизни при каждом POST/GET запросе
        rem = self.db.clean(lifetime)
        # Вывод в лог количества удаленных записей
        if rem == 0:
            logger.debug(f'Removed {rem} old record(s)')
        else:
            logger.info(f'Removed {rem} old record(s)')

    # Вывод информации в WEB - интерфейс
    def html(self, code: int, link='', slug=''):
        if code == 200:
            info = '<a href="./' + slug + '">' + link + '</a>'
            txt = html['200'].replace('_INFO', info)
            self.wfile.write(txt.encode()) if self.ua != 'curl' else self.wfile.write(link.encode())
        elif code == 301:
            txt = html['301'].replace('_INFO', link)
            self.wfile.write(txt.encode()) if self.ua != 'curl' else self.wfile.write(link.encode())
        elif code == 404:
            txt = html['404']
            self.wfile.write(txt.encode()) if self.ua != 'curl' else self.wfile.write('Error 404'.encode())

    # Обработка POST запроса
    def do_POST(self):
        self.do(200)
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        # В зависимости от User-Agent получаем ссылку для сокращения
        if self.ua == 'curl':
            path = post_data.decode()
        else:
            r_path = parse.parse_qs(post_data.decode())
            path = r_path['link'][0]
        logger.debug(f"POST request:\n\tUser-Agent: {self.ua}\n\tLink for Shortener: {path}")
        # Получаем короткую ссылку
        slug = self.db.post(path)
        link = str(host) + ':' + str(port) + '/' + slug
        # Выводим информацию в Web-интерфейс и CMD-интерфейс
        self.html(200, link, slug)
        logger.info(f"Created short link: {link} for URL: {path}")

    # Обработка GET запроса
    def do_GET(self):
        if self.path == '/' or self.path == '/favicon.ico':
            self.do(200)
            self.html(200)
        else:
            logger.debug(f"GET request:\n\tPath: {self.path}")
            # Получаем длинную ссылку
            uri = self.db.get(self.path)
            # Проверка на ее наличие в БД
            if uri:
                # Редирект на длинную ссылку
                logger.info(f"Returned URI: {uri[0]}")
                self.do(301)
                self.html(301, uri[0])
            else:
                # Ссылка не найдена в БД
                logger.info("Returned URI: NOT FOUND")
                self.do(404)
                self.html(404)


# Извлекаем путь до файла конфигурации
def parse_arg():
    parser = argparse.ArgumentParser(description='JSON config file')
    parser.add_argument('-c', dest="conf")
    return parser.parse_args()


if __name__ == '__main__':
    arg = parse_arg()
    try:
        # Чтение настроек
        with open(arg.conf) as config:
            conf = json.loads(config.read())
            host = conf['host']
            port = conf['port']
            dbname = conf['database']
            lifetime = conf['lifetime']
            debug_mode = conf['debug_mode']
    except TypeError:
        # Обработка исключения на случай если не указан параметр "-с" до файла конфигурации
        print("Please specify the path to the config JSON-file.\nExample 'server.py -c config.json'")
        exit()

    # Создаем лог объект
    logger = logging.getLogger(__name__)
    logger.setLevel(debug_mode)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(fmt='[%(asctime)s: %(levelname)s] %(message)s'))
    logger.addHandler(handler)
    logger.warning(f'\t\tLogging Mode - {conf[str(debug_mode)]}:')

    # Получаем html код для web интерфейса
    html = {}
    static = os.getcwd() + r'\static\\'
    for filename in os.listdir(static):
        with open(static + filename) as file:
            code = file.read()
            html[filename.rstrip('.html')] = code

    try:
        # Создаем объект для работы с БД через менеджер контекста
        with DBClient(dbname) as database:
            logger.info(f'Connecting to Database: {dbname}')
            # Передаем название базы данных в конструктор класса
            my_handler = partial(MyHandler, database)
            # Запуск сервера
            with HTTPServer((host, port), my_handler) as server:
                logger.warning(f'Started HTTP server on: {host}:{port}')
                server.serve_forever()
    # Обработка исключения на остановку сервера
    except KeyboardInterrupt:
        logger.warning(f'Stopping HTTP server on: {host}:{port}')
        server.server_close()
    # Обработка неожиданных исключений
    except Exception as exc:
        logger.exception(f"Unexpected error: {exc}")
