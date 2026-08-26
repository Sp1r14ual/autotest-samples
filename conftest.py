import logging

import pytest
import time
from simple_settings import settings

from commands.data_import import data_import
from db import Db
from sources.v2.spark import Spark
from celery_app import app as celery_app, create_queue_for_application_handle
from tests.v2.util import create_token

log = logging.getLogger(__name__)


@pytest.fixture(scope='session', autouse=True)
def setup_data(request):
    if not settings.TEST_CASE:
        raise Exception("Тесты должны проводиться только в тестовой среде, иначе есть риск удаления БД")
    # Import data to database
    data_import()
    setup_spark_okveds()
    app, _ = create_token('test', token=settings.COLLECTION_TOKEN)
    time.sleep(60)
    create_queue_for_application_handle(str(app.id))

    def fin():
        # Cleanup database after test function
        teardown_db()
    request.addfinalizer(fin)


@pytest.fixture(scope='function', autouse=True)
def teardown_checks():
    yield
    celery_app.control.purge()
    celery_app.control.revoke(list(celery_app.tasks.keys()), terminate=True)
    for collection in Db().checks, Db().results, Db().errors, Db().tasks, Db().hashed_data:
        collection.delete_many({})


def teardown_db():
    Db().client.drop_database(settings.MONGO_DATABASE)


def setup_spark_okveds():
    Spark.AVAILABLE_METHODS_MAPPING = {
        **Spark.AVAILABLE_METHODS_MAPPING,
        **{f'okved_{okved_category}': 'check_okved' for okved_category in Db().okved_categories}
    }
