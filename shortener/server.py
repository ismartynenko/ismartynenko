import argparse
import logging
from time import sleep
from os import getcwd, listdir
from json import loads
from sys import stdout
from threading import Thread
from functools import partial
from urllib import parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from database import DBClient


class MyHandler(BaseHTTPRequestHandler):
    def __init__(self, db, *args, **kwargs):
        self.db = db
        self.ua = None
        super().__init__(*args, **kwargs)

    # Метод отправки заголовков и определение User-Agent
    def do(self, code=200):
        # Отправляем заголовки
        self.send_response(code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        # Определяем User-agent
        self.ua = self.headers['User-Agent'].split('/')[0]

    # Вывод информации в Web или CMD интерфейс
    def html(self, code: int, link='', slug=''):
        if code == 200:
            info = '<a href="./' + slug + '">' + link + '</a>'
            txt = html['200'].replace('_INFO', info)
            self.wfile.write(txt.encode()) if self.ua != 'curl' else self.wfile.write(("http://"+link).encode())
        elif code == 301:
            txt = html['301'].replace('_INFO', link)
            self.wfile.write(txt.encode()) if self.ua != 'curl' else self.wfile.write(link.encode())
        elif code == 404:
            txt = html['404']
            self.wfile.write(txt.encode()) if self.ua != 'curl' else self.wfile.write('Error 404'.encode())

    # Метод обработки POST-запроса
    def do_POST(self):
        self.do(200)
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        # В зависимости от User-Agent получаем полную ссылку для сокращения
        if self.ua == 'curl':
            path = post_data.decode()
        else:
            r_path = parse.parse_qs(post_data.decode())
            path = r_path['link'][0]
        logger.debug(f"POST request:\n\tUser-Agent: {self.ua}\n\tLink for Shortener: {path}")
        # Получаем короткую ссылку
        with DBClient(self.db) as post:
            slug = post.post(path)
        link = str(cfg['host']) + ':' + str(cfg['port']) + '/' + slug
        # Выводим информацию в Web или CMD интерфейс
        self.html(200, link, slug)
        logger.info(f"Short link created: http://{link} for URL: {path}")

    # Метод обработки GET-запроса
    def do_GET(self):
        # При запросе главной страницы - отображаем её
        if self.path == '/' or self.path == '/favicon.ico':
            self.do(200)
            self.html(200)
        else:
            logger.debug(f"GET request:\n\tPath: {self.path}")
            # Получаем длинную ссылку
            with DBClient(self.db) as get:
                uri = get.get(self.path)
                # Проверка на наличие полного URL в БД
                if uri:
                    # Редирект на длинную ссылку
                    logger.info(f"Return URI: {uri[0]}")
                    self.do(301)
                    self.html(301, uri[0])
                else:
                    # Ссылка не найдена в БД
                    logger.info("Return URI: NOT FOUND")
                    self.do(404)
                    self.html(404)


def parse_arg():
    # Определение пути до файла настроек
    parser = argparse.ArgumentParser(description='JSON config file')
    parser.add_argument('-c', dest="conf")
    # Чтение настроек
    try:
        with open(parser.parse_args().conf) as config:
            conf = loads(config.read())
    except TypeError:
        # Обработка исключения на случай если не указан путь до файла конфигурации (параметр "-с")
        print("Please specify the path to the config JSON-file.\nExample 'server.py -c config.json'")
    return conf


def log():
    # Создаем и настраиваем режим логирования
    log_obj = logging.getLogger(__name__)
    log_obj.setLevel(cfg['debug_mode'])
    # Настраиваем вывод логов в консоль и их формат записи
    handler = logging.StreamHandler(stream=stdout)
    handler.setFormatter(logging.Formatter(fmt='[%(asctime)s: %(levelname)s] %(message)s'))
    log_obj.addHandler(handler)
    log_obj.warning(f"\t\tLogging Mode - {cfg['debug_mode']}:")
    return log_obj


def static():
    pages = {}
    page = getcwd() + r'\static\\'
    # Обход директории и сохранение данных в словарь
    for filename in listdir(page):
        with open(page + filename) as file:
            text = file.read()
            pages[filename.rstrip('.html')] = text
    return pages


def clean_db(db: str, lifetime: int):
    with DBClient(db) as cln:
        while thr_stop_flag is None:
            res = cln.clean(lifetime)
            if res != 0:
                logger.info(f'{res} record(s) deleted')
            else:
                logger.debug(f'{res} record(s) deleted')
            sleep(10)


if __name__ == '__main__':
    # Функция чтения файла настроек
    cfg = parse_arg()
    # Функция создания лог-объекта
    logger = log()
    # Функция получения html страниц для web интерфейса
    html = static()

    # Создаем и запускаем поток проверки и удаления ссылок с истекшим временем жизни
    thr_stop_flag = None
    clean = Thread(target=clean_db, args=(cfg['database'], cfg['lifetime'],))
    logger.warning(f'DB cleaner start: {clean.name}')
    clean.start()

    try:
        # Передаем название базы данных в конструктор класса
        my_handler = partial(MyHandler, cfg['database'])
        # Запуск сервера
        with ThreadingHTTPServer((cfg['host'], cfg['port']), my_handler) as server:
            logger.warning(f'HTTP server start on: {cfg["host"]}:{cfg["port"]}')
            server.serve_forever()
    # Обработка исключения на остановку сервера
    except KeyboardInterrupt:
        logger.warning('Command to stop')
        thr_stop_flag = True
    # Обработка неожиданных исключений
    except Exception as exc:
        logger.exception(f"Unexpected error: {exc}")
    finally:
        clean.join()
        logger.warning('DB cleaner is stopped')
        server.server_close()
        logger.warning('HTTP Server is stopped')
