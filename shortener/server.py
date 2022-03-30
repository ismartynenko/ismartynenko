import json
import argparse
import logging
import sys
from urllib import parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from database import Sql


class MyHandler(BaseHTTPRequestHandler):
    def do(self, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        logger.info(f'Removed {db.clean(lifetime)} old record(s)')

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

    def do_POST(self):
        self.do(200)
        ua = self.headers['User-Agent']
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        if ua.find('curl') != -1:
            path = post_data.decode()
        else:
            r_path = parse.parse_qs(post_data.decode())
            path = r_path['link'][0]
        logger.debug(f"POST request:\n\tUser-Agent: {ua}\n\tLink for Shortener: {path}")

        slug = db.post(path)
        link = str(host) + ':' + str(port) + '/' + slug
        self.html(200, '<a href="./' + slug + '">' + link + '</a>')
        logger.info(f"Created short link: {link} for URL: {path}")

    def do_GET(self):
        if self.path == '/' or self.path == '/favicon.ico':
            self.do(200)
            self.html(200)
        else:
            logger.debug(f"GET request:\n\tPath: {self.path}")
            uri = db.get(self.path)
            if uri:
                logger.info(f"Returned URI: {uri[0]}")
                self.do(301)
                self.html(301, uri[0])
            else:
                logger.info("Returned URI: NOT FOUND")
                self.do(404)
                self.html(404)


def parse_arg():
    parser = argparse.ArgumentParser(description='JSON config file')
    parser.add_argument('-c', dest="conf")
    return parser.parse_args()


if __name__ == '__main__':
    arg = parse_arg()
    with open(arg.conf) as config:
        conf = json.loads(config.read())
        host = conf['host']
        port = conf['port']
        dbname = conf['database']
        lifetime = conf['lifetime']
        debug_mode = conf['debug_mode']

    logger = logging.getLogger(__name__)
    logger.setLevel(debug_mode)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(fmt='[%(asctime)s: %(levelname)s] %(message)s'))
    logger.addHandler(handler)
    logger.warning(f'\t\tLogging Mode - {conf[str(debug_mode)]}:')

    html = {}
    with open('message.txt') as msg:
        logger.info(f'Reading HTML-message file: {msg.name}')
        for line in msg:
            key, value = line.split(':')
            html[key] = value

    try:
        with Sql(dbname) as sql:
            logger.info(f'Connecting to Database: {dbname}')
            db = sql
            with HTTPServer((host, port), MyHandler) as server:
                logger.warning(f'Started HTTP server on: {host}:{port}')
                server.serve_forever()
    except KeyboardInterrupt:
        logger.warning(f'Stopping HTTP server on: {host}:{port}')
        server.server_close()
    except Exception as exc:
        logger.exception("Unexpected error: {}".format(exc))
