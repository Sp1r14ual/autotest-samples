import json
from pathlib import Path
import shutil


from simple_settings import settings

from db import Db
from utils.session import Session
from bson import ObjectId


def test_session():
    Db().client.drop_database(settings.MONGO_DATABASE)
    source_name = 'common'
    url = settings.INPHOSPHERE_ADDRESS
    db_exchange = Db().db['exchange']
    assert db_exchange.count_documents({}) == 0
    with Session(check_id=str(ObjectId()), source=source_name) as session:
        session.get(url=url)
        log_dir = session.log_dir

    assert db_exchange.count_documents({}) == 1
    source = db_exchange.find_one({"method": 'GET', "url": url})
    request_file_path = Path(source["request_file_path"])
    response_file_path = Path(source["response_file_path"])
    assert log_dir.exists()
    assert request_file_path.exists()
    assert response_file_path.exists()

    json.load(request_file_path.open('r'))  # check is valid json
    json.load(request_file_path.open('r'))  # check is valid json
    assert source["status_code"] is not None

    shutil.rmtree(log_dir)
    assert not log_dir.exists()

