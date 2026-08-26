from psycopg2 import DatabaseError
from pymysql import OperationalError
from pymongo.errors import ServerSelectionTimeoutError
from requests import Session
from simple_settings import settings
from zeep import Transport, Client
from db import Db
from db.mysql import MySQL
from db.postgres import Postgres
from sources.v2.inphosphere import Inphosphere
from utils.base import get_proxies


def test_spark_connection():
    session = Session()
    session.proxies = get_proxies()
    transport = Transport(session=session)
    client = Client(settings.SPARK_ADDRESS, transport=transport)
    is_auth = client.service.Authmethod(Login=settings.SPARK_LOGIN, Password=settings.SPARK_PASSWORD)
    assert bool(is_auth) is True


def test_ctf_postgres_connection():
    try:
        Postgres()
        assert True
    except DatabaseError:
        assert False


def test_gulliver_connection():
    try:
        MySQL()
        assert True
    except OperationalError:
        assert False


# def test_inphosphere_connection():
#     inphosphere = Inphosphere()
#     response = inphosphere._api_request()
#     assert response is not None


def test_mongo_connection():
    client = Db().client
    try:
        client.server_info()
        assert True
    except ServerSelectionTimeoutError:
        assert False
