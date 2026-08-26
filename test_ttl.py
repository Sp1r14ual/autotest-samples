import datetime
import logging
from time import sleep

from bson import ObjectId
from collection_api.enums import EntityType, MethodStatus, CheckStatus, ErrorCode
from simple_settings import settings

from app import app
from db import Db
from tasks import monitoring_timeout_checks
from utils.base import check_methods_as_keys

log = logging.getLogger(__name__)


def test_timeout_in_check_status():
    headers = {'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'}
    ttl = 2
    with app.test_client() as c:
        response = c.post('/v2.1/check/create', headers=headers,
                          json={
                              "application_id": "test",
                              "entity_type": EntityType.INDIVIDUAL,
                              "ttl": ttl,
                              "payload": {
                                  "name_last": "ПЛЮСНИН",
                                  "name_first": "ПАВЕЛ",
                                  "name_middle": "АНАТОЛЬЕВИЧ",
                                  "dob": "12.12.1987"
                              },
                              "check_methods": {
                                  'test_source': [{
                                      'test_method_with_sleep': {'sleep': 100}
                                  }]
                              }
                          })
        assert response.status_code == 201
        response_json = response.get_json()
        check_id = response_json['payload']['id']
        while True:
            response = c.get(f'/v2.1/check/{check_id}/status', headers=headers)
            assert response.status_code == 200
            response_json = response.get_json()
            status = response_json['payload']['status']
            if status != CheckStatus.NOT_COMPLETED.name:
                assert status == CheckStatus.ERROR.name
                assert ttl <= (datetime.datetime.now(datetime.timezone.utc) -
                               ObjectId(check_id).generation_time).total_seconds() <= ttl + 1
                break
        response = c.get(f'/v2.1/check/{check_id}/results', headers=headers)
        assert response.status_code == 200
        response_json = response.get_json()
        check_result = response_json['payload']['test_source']['test_method_with_sleep']
        assert check_result['status'] == MethodStatus.ERROR.name
        assert check_result['error_code'] == ErrorCode.TIMEOUT.value


def test_timeout_in_check_results():
    headers = {'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'}
    ttl = 4
    check_methods = {
        'test_source': [{
            'test_method_with_sleep': {'sleep': 100}
        }],
        'common': ['young']
    }
    with app.test_client() as c:
        response = c.post('/v2.1/check/create', headers=headers,
                          json={
                              "application_id": "test",
                              "entity_type": EntityType.INDIVIDUAL,
                              "ttl": ttl,
                              "payload": {
                                  "name_last": "ПЛЮСНИН",
                                  "name_first": "ПАВЕЛ",
                                  "name_middle": "АНАТОЛЬЕВИЧ",
                                  "dob": "12.12.1987"
                              },
                              "check_methods": check_methods
                          })
        assert response.status_code == 201
        response_json = response.get_json()
        check_id = response_json['payload']['id']
        sleep(ttl)
        response = c.get(f'/v2.1/check/{check_id}/results', headers=headers)
        assert response.status_code == 200
        response_json = response.get_json()
        timeout_result = response_json['payload']['test_source']['test_method_with_sleep']
        success_result = response_json['payload']['common']['young']
        assert timeout_result['status'] == MethodStatus.ERROR.name
        assert success_result['status'] == MethodStatus.OK.name
        assert timeout_result['error_code'] == ErrorCode.TIMEOUT.value


def test_timeout_in_monitoring_check():
    headers = {'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'}
    ttl = 4
    check_methods = {
        'test_source': [{
            'test_method_with_sleep': {'sleep': 100}
        }],
        'common': ['young']
    }
    with app.test_client() as c:
        response = c.post('/v2.1/check/create', headers=headers,
                          json={
                              "application_id": "test",
                              "entity_type": EntityType.INDIVIDUAL,
                              "ttl": ttl,
                              "payload": {
                                  "name_last": "ПЛЮСНИН",
                                  "name_first": "ПАВЕЛ",
                                  "name_middle": "АНАТОЛЬЕВИЧ",
                                  "dob": "12.12.1987"
                              },
                              "check_methods": check_methods
                          })
        assert response.status_code == 201
        response_json = response.get_json()
        check_id = response_json['payload']['id']
        check = Db().get_check(check_id)
        assert check['meta']['status'] == CheckStatus.NOT_COMPLETED.name
        sleep(ttl)
        checks = monitoring_timeout_checks()
        assert len(checks) == 1
        assert checks[0] == check_id
        check = Db().get_check(check_id)
        assert check['meta']['status'] != CheckStatus.NOT_COMPLETED.name
        results = Db().get_check_results(check_id)
        assert len(results) == 2
        assert set(check_methods_as_keys(check_methods)) == set([result['key'] for result in results])
        timeout_result = list(filter(lambda x: x['key'] == 'test_source.test_method_with_sleep', results))[0]['result']
        success_result = list(filter(lambda x: x['key'] == 'common.young', results))[0]['result']
        assert timeout_result['status'] == MethodStatus.ERROR.name
        assert success_result['status'] == MethodStatus.OK.name
        assert timeout_result['error_code'] == ErrorCode.TIMEOUT.value
