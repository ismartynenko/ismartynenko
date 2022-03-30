import hashlib
import sqlite3
from time import time


class Sql:
    def __init__(self, dbname: str):
        self.db_name = dbname

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS Urls"
                    "   (ID     INTEGER     PRIMARY KEY     AUTOINCREMENT,"
                    "   Uri     TEXT    NOT NULL,"
                    "   Slug    TEXT    NOT NULL,"
                    "   Ctime   TIMESTAMP)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS 'slug_id' ON 'Urls'('Slug');")
        self.conn.commit()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

    def post(self, path: str):
        hash_object = hashlib.sha512(path.encode())
        slug = hash_object.hexdigest()[0:8]
        cur = self.conn.cursor()
        try:
            cur.execute("INSERT INTO Urls (Uri, Slug, Ctime) VALUES (:uri, :slug, :ctime)",
                        {'uri': path, 'slug': slug, 'ctime': time()})
        except sqlite3.IntegrityError:
            cur.execute("SELECT Slug FROM Urls WHERE Uri = :uri",
                        {'uri': path})
            return cur.fetchone()[0]
        self.conn.commit()
        return slug

    def get(self, path: str):
        cur = self.conn.cursor()
        cur.execute("SELECT Uri FROM Urls WHERE Slug = :path",
                    {'path': path.lstrip('/')})
        return cur.fetchone()

    def clean(self, lifetime: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM Urls WHERE Ctime < :time",
                    {'time': time() - lifetime})
        self.conn.commit()
        return cur.rowcount
