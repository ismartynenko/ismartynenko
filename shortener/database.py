import hashlib
import sqlite3
from time import time, sleep


class DBClient:
    def __init__(self, dbname: str):
        self._db_name = dbname
        self._conn = None

    def __enter__(self):
        # Создаем базу данных
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_name, check_same_thread=False)
        cur = self._conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS Urls"
                    "   (ID     INTEGER     PRIMARY KEY     AUTOINCREMENT,"
                    "   Uri     TEXT    NOT NULL,"
                    "   Slug    TEXT    NOT NULL,"
                    "   Ctime   TIMESTAMP)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS 'slug_id' ON 'Urls'('Slug');")
        self._conn.commit()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._conn.close()
        self._conn = None

    def post(self, path: str):
        # Генерируем короткую ссылку с помощью модуля hashlib
        hash_object = hashlib.sha512(path.encode())
        slug = hash_object.hexdigest()[0:8]
        cur = self._conn.cursor()
        # Добавляем запись в БД вида - Полный URL | Короткая ссылка | Время создания
        try:
            cur.execute("INSERT INTO Urls (Uri, Slug, Ctime) VALUES (:uri, :slug, :ctime)",
                        {'uri': path, 'slug': slug, 'ctime': time()})
            self._conn.commit()
        # Если ссылка уже имеется в БД, обновляем для нее время создания...
        except sqlite3.IntegrityError:
            cur.execute("UPDATE Urls"
                        " SET Ctime = :ctime"
                        " WHERE Uri = :uri",
                        {'ctime': time(), 'uri': path})
            self._conn.commit()
            # ...и возвращаем короткую ссылку
            cur.execute("SELECT Slug FROM Urls WHERE Uri = :uri",
                        {'uri': path})
            return cur.fetchone()[0]
        # Возвращаем короткую ссылку
        return slug

    def get(self, path: str):
        # Поиск в БД полной ссылки
        cur = self._conn.cursor()
        cur.execute("SELECT Uri FROM Urls WHERE Slug = :path",
                    {'path': path.lstrip('/')})
        # Возвращаем результат поиска
        return cur.fetchone()

    # Проверка и чистка записей с истекшим временем хранения
    def clean(self, lifetime: int):
        while self._conn is not None:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM Urls WHERE Ctime < :time",
                        {'time': time() - lifetime})
            self._conn.commit()
            print(f'Deleted {cur.rowcount} old record(s)')
            sleep(10)
