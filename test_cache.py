import datetime
import logging
from unittest import mock

import pytest

from bson import ObjectId
from collection_api.enums import EntityType, MethodStatus, ErrorCode, ErrorMessage
from app import app
from simple_settings import settings
from simple_settings.utils import settings_stub

from db import Db
from sources.check import Check
from tests.fake.source import TestSource
from tests.v2.util import create_check
from utils.base import get_dict_hash

log = logging.getLogger(__name__)


@pytest.mark.parametrize('first_data,second_data,value', [
    # save diff name_last, name_middle with replaced char(Й, Ё), case intensive, star-end spaces and entity_type
    [
        {'name_last': 'Игорь', 'name_first': 'Дудкин', 'name_middle': 'ЁлКОВИЧ', 'entity_type': 'individual'},
        {'name_last': '   ЙГОРЬ   ', 'name_first': 'ДУДКЙН', 'name_middle': 'елкович', 'entity_type': 'entrepreneur'},
        True
    ],
    # add dob, dob is not required in test_source.test_required_keys
    [
        {'name_last': 'Игорь', 'name_first': 'Дудкин', 'name_middle': 'ЁлКОВИЧ', 'entity_type': 'individual'},
        {'name_last': 'Игорь', 'name_first': 'Дудкин', 'name_middle': 'ЁлКОВИЧ', 'dob': '12.12.1998',
         'entity_type': 'individual'},
        True
    ],
    # diff name_last
    [
        {'name_last': 'Игорь', 'name_first': 'Дудкин', 'name_middle': 'ЁлКОВИЧ', 'entity_type': 'individual'},
        {'name_last': 'Не Игорь', 'name_first': 'Дудкин', 'name_middle': 'ЁлКОВИЧ', 'entity_type': 'individual'},
        False
    ],
    # save diff name with replaced char(Й, Ё), case intensive, star-end spaces
    [
        {'name': 'РогА И КОПЫТА ЕДИНЫ', 'inn': '1234567890', 'entity_type': 'corporate'},
        {'name': '   рога Й копыта Ёдины  ', 'inn': '1234567890', 'entity_type': 'corporate'},
        True
    ],
    # add ownership_type, ownership_type is not required in test_source.test_required_keys
    [
        {'name': 'РогА И КОПЫТА ЕДИНЫ', 'inn': '1234567890', 'entity_type': 'corporate'},
        {'name': '   рога Й копыта Ёдины  ', 'inn': '1234567890', 'ownership_type': 'АО', 'entity_type': 'corporate'},
        True
    ],
    # diff inn
    [
        {'name': 'РогА И КОПЫТА ЕДИНЫ', 'inn': '1234567890', 'entity_type': 'corporate'},
        {'name': '   рога Й копыта Ёдины  ', 'inn': '1111111111', 'entity_type': 'corporate'},
        False
    ],
    # diff name
    [
        {'name': 'РогА И КОПЫТА ЕДИНЫ', 'inn': '1234567890', 'entity_type': 'corporate'},
        {'name': 'рога и копыта коровы', 'inn': '1234567890', 'entity_type': 'corporate'},
        False
    ],

])
def test_hashing_data(first_data, second_data, value):
    source_name, method_name = 'test_source', 'test_required_keys'
    first_check = create_check(first_data, check_methods={source_name: [method_name]})
    second_check = create_check(second_data, check_methods={source_name: [method_name]})
    first_hashes, _ = Check(first_check).get_data_hashes(source_name, method_name)
    second_hashes, _ = Check(second_check).get_data_hashes(source_name, method_name)
    assert first_hashes and second_hashes
    assert (set(first_hashes) == set(second_hashes)) is value


def test_get_cached_result_from_db():
    source_name, method_name = 'test_source', 'test_required_keys'
    result_created_at = datetime.datetime.utcnow() - datetime.timedelta(days=5)
    check_id = ObjectId()
    found_result_id = Db().results.insert_one(
        {
            "check_id": check_id,
            "key": f"{source_name}.{method_name}",
            "created_at": result_created_at,
            "result": {
                "status": "OK",
                "risk_exists": False,
                "text": "text"
            }
        }
    ).inserted_id
    hashed_data = get_dict_hash({'cache': True})
    entity_type = 'corporate'
    Db().hashed_data.insert_one(
        {
            "hashed_data": [
                hashed_data
            ],
            "entity_type": entity_type,
            "created_at": datetime.datetime.utcnow(),
            "check_id": check_id
        }
    )
    result = Db().get_cached_result(entity_type=EntityType(entity_type),
                                    cache_at=result_created_at - datetime.timedelta(days=1),
                                    data_hashes=[hashed_data,
                                                 get_dict_hash({'random_cache': 'value'})],
                                    source_name=source_name, method_name=method_name)
    assert result is not None
    assert result['_id'] == found_result_id

    # search with diff data_hashes
    result = Db().get_cached_result(entity_type=EntityType(entity_type),
                                    cache_at=result_created_at - datetime.timedelta(days=1),
                                    data_hashes=[get_dict_hash({'random_cache': 'value'})],
                                    source_name=source_name, method_name=method_name)
    assert result is None

    # search with diff entity_type
    result = Db().get_cached_result(entity_type=EntityType('individual'),
                                    cache_at=result_created_at - datetime.timedelta(days=1),
                                    data_hashes=[hashed_data,
                                                 get_dict_hash({'random_cache': 'value'})],
                                    source_name=source_name, method_name=method_name)
    assert result is None

    # search with old cache_at
    cache_at = result_created_at + datetime.timedelta(days=1)
    result = Db().get_cached_result(entity_type=EntityType(entity_type),
                                    cache_at=cache_at,
                                    data_hashes=[hashed_data,
                                                 get_dict_hash({'random_cache': 'value'})],
                                    source_name=source_name, method_name=method_name)
    assert result is None, f'{result["created_at"]}, {result_created_at}, {cache_at}'

    # search with diff method name
    result = Db().get_cached_result(entity_type=EntityType(entity_type),
                                    cache_at=result_created_at - datetime.timedelta(days=1),
                                    data_hashes=[hashed_data,
                                                 get_dict_hash({'random_cache': 'value'})],
                                    source_name=source_name, method_name='diff_method_name')
    assert result is None

    new_check_id = ObjectId()
    new_found_result_id = Db().results.insert_one(
        {
            "check_id": new_check_id,
            "key": f"{source_name}.{method_name}",
            "created_at": result_created_at + datetime.timedelta(minutes=1),
            "result": {
                "status": "OK",
                "risk_exists": False,
                "text": "text"
            }
        }
    ).inserted_id
    Db().hashed_data.insert_one(
        {
            "hashed_data": [
                hashed_data
            ],
            "entity_type": entity_type,
            "created_at": datetime.datetime.utcnow(),
            "check_id": new_check_id
        }
    )
    result = Db().get_cached_result(entity_type=EntityType(entity_type),
                                    cache_at=result_created_at - datetime.timedelta(days=1),
                                    data_hashes=[hashed_data,
                                                 get_dict_hash({'random_cache': 'value'})],
                                    source_name=source_name, method_name=method_name)
    assert result is not None
    assert result['_id'] == new_found_result_id

    new_check_id = ObjectId()
    Db().results.insert_one(
        {
            "check_id": new_check_id,
            "key": f"{source_name}.{method_name}",
            "created_at": result_created_at + datetime.timedelta(days=3),
            "result": {
                "status": MethodStatus.ERROR,
                "error_code": ErrorCode.SOURCE,
                "error": ErrorMessage.SOURCE
            }
        }
    )
    Db().hashed_data.insert_one(
        {
            "hashed_data": [
                hashed_data
            ],
            "entity_type": entity_type,
            "created_at": datetime.datetime.utcnow(),
            "check_id": new_check_id
        }
    )
    assert result is not None
    assert result['_id'] == new_found_result_id


@settings_stub(CELERY_TASK_ALWAYS_EAGER=True)
def test_get_cached_result_without_args_from_api():
    assert settings.CELERY_TASK_ALWAYS_EAGER is True
    source_name, method_name_without_args, method_name_with_args = 'test_source', 'test_required_keys', \
                                                                   'test_required_keys_with_args'
    success_result = {
        'status': MethodStatus.OK,
        'risk_exists': False,
        'text': 'text'
    }
    # mock в данных тестах используется лишь для подсчет количества вызовов
    # данная конфигурация позволяет подрожать оригинальной функции
    mock_config = {
        method_name_without_args: {
            'return_value': success_result,
            'entity_types': getattr(TestSource, method_name_without_args).entity_types,
            'required_keys': getattr(TestSource, method_name_without_args).required_keys,
        },
        method_name_with_args: {
            'return_value': success_result,
            'entity_types': getattr(TestSource, method_name_with_args).entity_types,
            'required_keys': getattr(TestSource, method_name_with_args).required_keys,
            'args_schema': getattr(TestSource, method_name_with_args).args_schema,
        }
    }
    entity_type = 'individual'
    payload = {'name_last': 'Игорь', 'name_first': 'Дудкин', 'name_middle': 'ЁлКОВИЧ'}
    headers = {'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'}
    cache_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    with app.test_client() as c:
        with mock.patch.object(TestSource, method_name_without_args) as mock_method:
            mock_method.configure_mock(**mock_config[method_name_without_args])
            # первая проверка, где функция проверки будет вызвана
            response = c.post('/v2.1/check/create', headers=headers,
                              json={
                                  "application_id": "test",
                                  "entity_type": EntityType(entity_type),
                                  'cache_at': cache_at.strftime(settings.DATETIME_FORMAT),
                                  "payload": payload,
                                  "check_methods": {
                                      source_name: [method_name_without_args]
                                  }
                              })
            assert response.status_code == 201, response.get_json()
            assert mock_method.call_count == 1
            data = response.get_json()
            response = c.get(f'/v2.1/check/{data["payload"]["id"]}/results', headers=headers)
            assert response.status_code == 200, response.get_json()
            data = response.get_json()
            assert 'cache_from' not in data['payload'][source_name][method_name_without_args]

            # вторая проверка, где функция проверки не будет вызвана, поскольку результат подтянется из кэша
            response = c.post('/v2.1/check/create', headers=headers,
                              json={
                                  "application_id": "test2",
                                  "entity_type": EntityType(entity_type),
                                  'cache_at': cache_at.strftime(settings.DATETIME_FORMAT),
                                  "payload": payload,
                                  "check_methods": {
                                      source_name: [method_name_without_args]
                                  }
                              })
            assert response.status_code == 201, response.get_json()
            assert mock_method.call_count == 1
            data = response.get_json()
            response = c.get(f'/v2.1/check/{data["payload"]["id"]}/results', headers=headers)
            assert response.status_code == 200, response.get_json()
            data = response.get_json()
            assert 'cache_from' in data['payload'][source_name][method_name_without_args]
            cached_from = data['payload'][source_name][method_name_without_args]['cache_from']

            # третья проверка, где функция проверки не будет вызвана, поскольку результат подтянется из
            # кэша(первой проверки)
            response = c.post('/v2.1/check/create', headers=headers,
                              json={
                                  "application_id": "test2",
                                  "entity_type": EntityType(entity_type),
                                  'cache_at': cache_at.strftime(settings.DATETIME_FORMAT),
                                  "payload": payload,
                                  "check_methods": {
                                      source_name: [method_name_without_args]
                                  }
                              })
            assert response.status_code == 201, response.get_json()
            assert mock_method.call_count == 1
            data = response.get_json()
            response = c.get(f'/v2.1/check/{data["payload"]["id"]}/results', headers=headers)
            assert response.status_code == 200, response.get_json()
            data = response.get_json()
            assert 'cache_from' in data['payload'][source_name][method_name_without_args]
            # проверка, что результат вернулся из кэша первой проверки
            assert data['payload'][source_name][method_name_without_args]['cache_from'] == cached_from

            # четвертая проверка, где функция проверки будет вызвана, поскольку не передали аругмент cache_at
            response = c.post('/v2.1/check/create', headers=headers,
                              json={
                                  "application_id": "test2",
                                  "entity_type": EntityType(entity_type),
                                  "payload": payload,
                                  "check_methods": {
                                      source_name: [method_name_without_args]
                                  }
                              })
            assert response.status_code == 201, response.get_json()
            assert mock_method.call_count == 2
            data = response.get_json()
            response = c.get(f'/v2.1/check/{data["payload"]["id"]}/results', headers=headers)
            assert response.status_code == 200, response.get_json()
            data = response.get_json()
            assert 'cache_from' not in data


@settings_stub(CELERY_TASK_ALWAYS_EAGER=True)
def test_get_cached_result_with_args_from_api():
    assert settings.CELERY_TASK_ALWAYS_EAGER is True
    source_name, method_name_without_args, method_name_with_args = 'test_source', 'test_required_keys', \
                                                                   'test_required_keys_with_args'
    success_result = {
        'status': MethodStatus.OK,
        'risk_exists': False,
        'text': 'text'
    }
    # mock в данных тестах используется лишь для подсчет количества вызовов
    # данная конфигурация позволяет подрожать оригинальной функции
    mock_config = {
        method_name_without_args: {
            'return_value': success_result,
            'entity_types': getattr(TestSource, method_name_without_args).entity_types,
            'required_keys': getattr(TestSource, method_name_without_args).required_keys,
        },
        method_name_with_args: {
            'return_value': success_result,
            'entity_types': getattr(TestSource, method_name_with_args).entity_types,
            'required_keys': getattr(TestSource, method_name_with_args).required_keys,
            'args_schema': getattr(TestSource, method_name_with_args).args_schema,
        }
    }
    entity_type = 'individual'
    payload = {'name_last': 'Игорь', 'name_first': 'Дудкин', 'name_middle': 'ЁлКОВИЧ'}
    headers = {'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'}
    cache_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    with app.test_client() as c:
        with mock.patch.object(TestSource, method_name_without_args) as mock_method_without_args:
            with mock.patch.object(TestSource, method_name_with_args) as mock_method_with_args:
                mock_method_without_args.configure_mock(**mock_config[method_name_without_args])
                mock_method_with_args.configure_mock(**mock_config[method_name_with_args])
                # первая проверка, где функция проверок будет вызвана
                response = c.post('/v2.1/check/create', headers=headers,
                                  json={
                                      "application_id": "test",
                                      "entity_type": EntityType(entity_type),
                                      'cache_at': cache_at.strftime(settings.DATETIME_FORMAT),
                                      "payload": payload,
                                      "check_methods": {
                                          source_name: [method_name_without_args, method_name_with_args]
                                      }
                                  })
                assert response.status_code == 201, response.get_json()
                assert mock_method_without_args.call_count == 1
                assert mock_method_with_args.call_count == 1
                data = response.get_json()
                response = c.get(f'/v2.1/check/{data["payload"]["id"]}/results', headers=headers)
                assert response.status_code == 200, response.get_json()
                data = response.get_json()
                assert 'cache_from' not in data['payload'][source_name][method_name_without_args]
                assert 'cache_from' not in data['payload'][source_name][method_name_with_args]

                # вторая проверка, где функция проверки для "mock_method_with_args" не будет вызвана,
                # а функция "method_name_with_args" будет вызвана, поскольку добавляются аргументы
                response = c.post('/v2.1/check/create', headers=headers,
                                  json={
                                      "application_id": "test2",
                                      "entity_type": EntityType(entity_type),
                                      'cache_at': cache_at.strftime(settings.DATETIME_FORMAT),
                                      "payload": payload,
                                      "check_methods": {
                                          source_name: [method_name_without_args,
                                                        {method_name_with_args: {'value': '123'}}]
                                      }
                                  })
                assert response.status_code == 201, response.get_json()
                assert mock_method_without_args.call_count == 1
                assert mock_method_with_args.call_count == 2
                data = response.get_json()
                response = c.get(f'/v2.1/check/{data["payload"]["id"]}/results', headers=headers)
                assert response.status_code == 200, response.get_json()
                data = response.get_json()
                assert 'cache_from' in data['payload'][source_name][method_name_without_args]
                assert 'cache_from' not in data['payload'][source_name][method_name_with_args]

                # третья проверка, где функция проверки для "mock_method_with_args" не будет вызвана,
                # а функция "method_name_with_args" будет вызвана, поскольку добавляются аргументы отличные от первой
                # проверки
                response = c.post('/v2.1/check/create', headers=headers,
                                  json={
                                      "application_id": "test2",
                                      "entity_type": EntityType(entity_type),
                                      'cache_at': cache_at.strftime(settings.DATETIME_FORMAT),
                                      "payload": payload,
                                      "check_methods": {
                                          source_name: [method_name_without_args,
                                                        {method_name_with_args: {'value': '456'}}]
                                      }
                                  })
                assert response.status_code == 201, response.get_json()
                assert mock_method_without_args.call_count == 1
                assert mock_method_with_args.call_count == 3
                data = response.get_json()
                response = c.get(f'/v2.1/check/{data["payload"]["id"]}/results', headers=headers)
                assert response.status_code == 200, response.get_json()
                data = response.get_json()
                assert 'cache_from' in data['payload'][source_name][method_name_without_args]
                assert 'cache_from' not in data['payload'][source_name][method_name_with_args]

                # четвертая проверка, где функции проверки не будут вызваны, поскольку есть данные с такими же
                # аргументами
                response = c.post('/v2.1/check/create', headers=headers,
                                  json={
                                      "application_id": "test2",
                                      "entity_type": EntityType(entity_type),
                                      'cache_at': cache_at.strftime(settings.DATETIME_FORMAT),
                                      "payload": payload,
                                      "check_methods": {
                                          source_name: [method_name_without_args,
                                                        {method_name_with_args: {'value': '123'}}]
                                      }
                                  })
                assert response.status_code == 201, response.get_json()
                assert mock_method_without_args.call_count == 1
                assert mock_method_with_args.call_count == 3
                data = response.get_json()
                response = c.get(f'/v2.1/check/{data["payload"]["id"]}/results', headers=headers)
                assert response.status_code == 200, response.get_json()
                data = response.get_json()
                assert 'cache_from' in data['payload'][source_name][method_name_without_args]
                assert 'cache_from' in data['payload'][source_name][method_name_with_args]


