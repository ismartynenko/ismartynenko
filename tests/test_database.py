from time import sleep
from database import DBClient
from os import remove
import unittest

test_db = 'test.db'
testmodules = ['test_post', 'test_get', 'test_clean']


class TestDBClient(unittest.TestCase):
    def test_post(self):
        with DBClient(test_db) as db:
            result1 = db.post('https://ya.ru')
            result2 = db.post('https://ya.ru')
            result3 = db.post('https://yandex.ru')

        assert result1 == result2
        assert result2 != result3

    def test_get(self):
        lnk = 'https://gmail.com'
        with DBClient(test_db) as db:
            result1 = db.get('/r4rkr4j5')
            result2 = db.get('/' + db.post(lnk))

        assert result1 is None
        assert result2[0] == lnk

    def test_clean(self):
        with DBClient(test_db) as db:
            slug = db.post('https://google.com')
            sleep(5)
            result1 = db.clean(1)
            result2 = db.get(slug)

        assert result1 == 1
        assert result2 is None

    def tearDown(self):
        remove(test_db)


if __name__ == '__main__':
    # unittest.main()
    suite = unittest.TestSuite()
    for tm in testmodules:
        suite.addTest(unittest.defaultTestLoader.loadTestsFromName(tm))
    unittest.TextTestRunner().run(suite)
