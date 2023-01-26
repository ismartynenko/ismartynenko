import server
import unittest
import mock
from os import remove
from io import BytesIO


test_db = 'test.db'


class TestMyHandler(unittest.TestCase):
    server.html = {'404': '404', '301': '301', '200': '200'}
    server.cfg = {'host': "127.0.0.1", 'port': 8080}

    def test_do_GET(self):
        test_slug = '/f50de615'

        # Мокаем зависимости для создания хэндлера
        server.logger = mock.Mock()
        request = mock.Mock()
        # Мокаем зависимости для обращения к БД за короткой ссылкой
        server.DBClient.get = mock.Mock(return_value=test_slug)
        # Мокаем метод отправки ответа
        server.MyHandler.send_response = mock.Mock()

        print('\n')
        request.makefile.return_value = BytesIO(('GET ' + test_slug + ' HTTP/1.1\r\nHost: 127.0.0.1:8080\r\n').encode())

        # Создаем хэндлер GET-запроса
        test_get = server.MyHandler(test_db, request=request, client_address='0.0.0.0',
                                    server=(server.cfg['host'], server.cfg['port']))

        # Тестируем
        test_get.send_response.assert_called_with(301)
        test_get.wfile._sock.sendall.assert_called_with(b'301')
        assert server.DBClient.get.call_count == 1
        assert server.DBClient.get.call_args.args[0] == test_slug

    def test_do_POST(self):
        test_slug = 'https://google.com'

        # Мокаем зависимости для создания хэндлера
        server.logger = mock.Mock()
        request = mock.Mock()
        # Мокаем зависимости для обращения к БД за короткой ссылкой
        server.DBClient.post = mock.Mock(return_value=test_slug)
        # Мокаем метод отправки ответа
        server.MyHandler.send_response = mock.Mock()

        print('\n')
        request.makefile.return_value = BytesIO(b'POST / HTTP/1.1\r\nHost: 127.0.0.1:8080\r\nUser-Agent: '
                                                b'Mozilla/5.0\r\nContent-Length: 23\r\n\r\nlink=https://google.com')

        # Создаем хэндлер POST-запроса
        test_post = server.MyHandler(test_db, request=request, client_address='0.0.0.0',
                                     server=(server.cfg['host'], server.cfg['port']))

        # Тестируем
        test_post.send_response.assert_called_with(200)
        test_post.wfile._sock.sendall.assert_called_with(b'200')
        assert server.DBClient.post.call_count == 1
        assert server.DBClient.post.call_args.args[0] == 'https://google.com'

    def test_clean_db(self):
        lifetime = 10
        server.thr_stop_flag = None

        server.logger = mock.Mock()
        server.DBClient.clean = mock.Mock()
        server.DBClient.clean.side_effect = [3, 0, StopIteration]

        try:
            server.clean_db(test_db, lifetime)
        except StopIteration:
            server.thr_stop_flag = True

        assert server.logger.info.call_count == 1
        assert server.logger.debug.call_count == 1

    def tearDown(self):
        remove(test_db)


if __name__ == '__main__':
    unittest.main()
