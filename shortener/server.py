import json
import argparse
import logging
import sys
from urllib import parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from database import Sql


class MyHandler(BaseHTTPRequestHandler):
    # Отправка заголовков
    def do(self, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        # Проверяем и удаляем ссылки с истекшим временем жизни при каждом POST/GET запросе
        rem = db.clean(lifetime)
        # Вывод в лог количества удаленных записей
        if rem == 0:
            logger.debug(f'Removed {rem} old record(s)')
        else:
            logger.info(f'Removed {rem} old record(s)')

    # Вывод информации в WEB - интерфейс
    def html(self, code: int, info=''):
        if code == 200:
            txt = html['200'].replace('_INFO', info)
            self.wfile.write(txt.encode())
        elif code == 301:
            txt = html['301'].replace('_INFO', info)
            self.wfile.write(txt.encode())
        elif code == 404:
            txt = html['404']
            self.wfile.write(txt.encode())

    # Обработка POST запроса
    def do_POST(self):
        self.do(200)
        # Определяем User-Agent
        ua = self.headers['User-Agent']
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        # В зависимости от User-Agent получаем ссылку для сокращения
        if ua.find('curl') != -1:
            path = post_data.decode()
        else:
            r_path = parse.parse_qs(post_data.decode())
            path = r_path['link'][0]
        logger.debug(f"POST request:\n\tUser-Agent: {ua}\n\tLink for Shortener: {path}")
        # Получаем короткую ссылку
        slug = db.post(path)
        link = str(host) + ':' + str(port) + '/' + slug
        # Выводим информацию в Web-интерфейс
        self.html(200, '<a href="./' + slug + '">' + link + '</a>')
        logger.info(f"Created short link: {link} for URL: {path}")

    # Обработка GET запроса
    def do_GET(self):
        if self.path == '/' or self.path == '/favicon.ico':
            self.do(200)
            self.html(200)
        else:
            logger.debug(f"GET request:\n\tPath: {self.path}")
            # Получаем длинную ссылку
            uri = db.get(self.path)
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
    with open('message.txt') as msg:
        logger.info(f'Reading HTML-message file: {msg.name}')
        for line in msg:
            key, value = line.split(':')
            html[key] = value

    try:
        # Создаем объект для работы с БД через менеджер контекста
        with Sql(dbname) as sql:
            logger.info(f'Connecting to Database: {dbname}')
            db = sql
            # Запуск сервера
            with HTTPServer((host, port), MyHandler) as server:
                logger.warning(f'Started HTTP server on: {host}:{port}')
                server.serve_forever()
    # Обработка исключения на остановку сервера
    except KeyboardInterrupt:
        logger.warning(f'Stopping HTTP server on: {host}:{port}')
        server.server_close()
    # Обработка неожиданных исключений
    except Exception as exc:
        logger.exception("Unexpected error: {}".format(exc))
