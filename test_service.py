from db import Db
from app import app
from commands.createuser import createuser

import pytest


@pytest.fixture(autouse=False, scope="module")
def add_test_settings():
    settings = Db().settings
    settings.insert({"CHECK": 50, "DELETE": 150})
    admin = ("a", "a")
    createuser(admin[0], admin[1], ["admin"])
    user = ("q", "q")
    createuser(user[0], user[1], ["support"])
    yield admin, user


def test_auth(add_test_settings):
    admin, user = add_test_settings

    with app.test_client() as client:
        response = client.get('service/timeout', follow_redirects=True, auth=(user[0], user[1]))
        assert response.status_code == 403
        response = client.post('service/timeout/update', data={"source": 'source', "timeout": 22},
                               follow_redirects=True, auth=(user[0], user[1]))
        assert response.status_code == 403
        response = client.post('service/timeout/delete', data={"delete_source": "source"},
                               follow_redirects=True, auth=(user[0], user[1]))
        assert response.status_code == 403


def test_get_timeouts(add_test_settings):
    admin, user = add_test_settings

    with app.test_client() as client:
        response = client.get('service/timeout', auth=(admin[0], admin[1]), follow_redirects=True)
        assert response.status_code == 200


def test_update_timeout(add_test_settings):
    admin, user = add_test_settings

    with app.test_client() as client:
        # test update timeouts
        timeouts = Db().settings.find_one()
        timeouts.pop("_id")
        add_timeout_source = "NEW"
        timeouts[
            add_timeout_source] = 10  # мы добавляем в ручную значение в словарь, которого нет в БД, а потом проверяем что в БД он появился
        for name, val in timeouts.items():
            new_timeout = 1
            response = client.post('service/timeout/update', data={"source": name, "timeout": new_timeout},
                                   auth=(admin[0], admin[1]), follow_redirects=True)
            assert response.status_code == 200
            update_timeouts = Db().settings.find_one()
            assert new_timeout != val
            assert update_timeouts[name] == new_timeout


def test_delete_timeouts(add_test_settings):
    admin, user = add_test_settings

    with app.test_client() as client:
        client.auth = (admin[0], admin[1])
        client.follow_redirects = True
        timeouts = Db().settings.find_one()
        del_timeout_source = "CHECK"
        delete_timeout = timeouts.get(del_timeout_source)
        assert delete_timeout is not None
        response = client.post('service/timeout/delete', data={"delete_source": del_timeout_source},
                               auth=(admin[0], admin[1]), follow_redirects=True)
        assert response.status_code == 200
        timeouts = Db().settings.find_one()
        assert timeouts.get(del_timeout_source) is None


