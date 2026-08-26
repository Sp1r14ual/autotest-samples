import logging
from time import sleep

from collection_api.enums import EntityType, CheckStatus, MethodStatus

from app import app
from simple_settings import settings

log = logging.getLogger(__name__)


def test_priority():
    headers = {'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'}
    sleep_param = 3
    check_methods = {
        'test_source': [{
            'test_method_with_sleep': {'sleep': sleep_param}
        }]
    }
    data = {
        "application_id": "test",
        "entity_type": EntityType.INDIVIDUAL,
        "payload": {
            "name_last": "ПЛЮСНИН",
            "name_first": "ПАВЕЛ",
            "name_middle": "АНАТОЛЬЕВИЧ",
            "dob": "12.12.1987"
        },
        "check_methods": check_methods
    }
    with app.test_client() as c:
        # create checks with default priority
        # concurrency count must be three times less iterations
        for i in range(30):
            response = c.post('/v2.1/check/create', headers=headers, json=data)
            assert response.status_code == 201, response.get_json()
        response_json = response.get_json()
        last_default_priority_check_id = response_json['payload']['id']
        # create check by higher priority
        response = c.post('/v2.1/check/create', headers=headers,
                          json={"priority": settings.CELERY_TASK_DEFAULT_PRIORITY + 1, **data})
        assert response.status_code == 201, response.get_json()
        response_json = response.get_json()
        priority_check_id = response_json['payload']['id']
        sleep(sleep_param * 3 + 5)  # waiting started and received checks and 5 sec allowable error
        # check with higher priority must be completed
        response = c.get(f'/v2.1/check/{priority_check_id}/status', headers=headers)
        assert response.status_code == 200, response.get_json()
        response_json = response.get_json()
        status = response_json['payload']['status']
        assert status == CheckStatus.COMPLETED.name
        response = c.get(f'/v2.1/check/{priority_check_id}/results', headers=headers)
        assert response.status_code == 200, response.get_json()
        response_json = response.get_json()
        timeout_result = response_json['payload']['test_source']['test_method_with_sleep']
        assert timeout_result['status'] == MethodStatus.OK.name
        # check with default priority must be not completed
        response = c.get(f'/v2.1/check/{last_default_priority_check_id}/status', headers=headers)
        assert response.status_code == 200, response.get_json()
        response_json = response.get_json()
        status = response_json['payload']['status']
        assert status == CheckStatus.NOT_COMPLETED.name
