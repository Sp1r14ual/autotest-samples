import contextlib
import hashlib

import psycopg2
import pytest
from db.postgres import Postgres
from db.query import Query
from simple_settings import settings


@pytest.fixture
def sandbox():
    DB_NAME = f'{settings.CFT_POSTGRES_DATABASE}_sandbox'

    connection = psycopg2.connect(
        host=settings.CFT_POSTGRES_HOST,
        dbname='template1',
        user=settings.CFT_POSTGRES_USER,
        password=settings.CFT_POSTGRES_PASSWORD,
    )
    connection.autocommit = True
    with contextlib.closing(connection):
        connection.cursor().execute(f'CREATE DATABASE {DB_NAME}')

    sandbox_connection = psycopg2.connect(
        host=settings.CFT_POSTGRES_HOST,
        dbname=DB_NAME,
        user=settings.CFT_POSTGRES_USER,
        password=settings.CFT_POSTGRES_PASSWORD,
    )
    sandbox_connection.autocommit = True
    with contextlib.closing(sandbox_connection):
        sandbox_connection.cursor().execute("""
            CREATE TABLE users (
              id INT NOT NULL,
              email VARCHAR(45) NULL,
              password VARCHAR(45) NULL,
              PRIMARY KEY (id));

            insert into users (id, email,password) values (1, 'user@example.com', md5('abc'));
            insert into users (id, email,password) values (2, 'admin@example.org', md5('xyz'));
        """)

    db = Postgres(database=DB_NAME)

    try:
        with contextlib.closing(db._conn):
            yield db

    finally:
        connection = psycopg2.connect(
            host=settings.CFT_POSTGRES_HOST,
            dbname='template1',
            user=settings.CFT_POSTGRES_USER,
            password=settings.CFT_POSTGRES_PASSWORD,
        )
        connection.autocommit = True
        with contextlib.closing(connection):
            connection.cursor().execute(f'DROP DATABASE {DB_NAME}')


@pytest.mark.skip('Failed on prod db')
def test_sql_injection(sandbox):
    query = Query()
    query.eaxct(email="user@example.com'); TRUNCATE users; COMMIT; --", password=hashlib.md5('asdsad'.encode('utf-8')).hexdigest())
    sandbox.search_in(table='users', query=query)

    sandbox.search_in(table='users', query=Query())
    rows = sandbox.cur.fetchall()
    assert rows, 'SQL injection truncate table with email field from Query()'
