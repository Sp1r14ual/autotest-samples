from time import sleep

import pytest
from collection_api.enums import EntityType, CheckStatus

from app import app
from celery_app import create_queue_for_application_handle
from tests.v2.util import create_token


@pytest.fixture()
def application_fixture():
    flood_application, flood_token = create_token('flood')
    normal_application, normal_token = create_token('normal')
    create_queue_for_application_handle(str(flood_application.id))
    create_queue_for_application_handle(str(normal_application.id))
    applications = ((flood_application, flood_token), (normal_application, normal_token))
    yield applications
    for application, token in applications:
        application.delete_one()
        token.delete_one()


def test_application_queues_with_priority(application_fixture):
    flood_application_data, normal_application_data = application_fixture
    flood_application, flood_token = flood_application_data
    normal_application, normal_token = normal_application_data
    flood_application_headers = {'Authorization': f'Bearer {flood_token.token}'}
    normal_application_headers = {'Authorization': f'Bearer {normal_token.token}'}
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
        # create checks for one application(flood) with highest priority
        # concurrency count must be three times less iterations
        for i in range(100):
            response = c.post('/v2.1/check/create', headers=flood_application_headers, json={'priority': 6, **data})
            assert response.status_code == 201, response.get_json()
        response_json = response.get_json()
        last_check_id = response_json['payload']['id']
        # create check for other application(normal) with lowest priority
        response = c.post('/v2.1/check/create', headers=normal_application_headers, json={'priority': 1, **data})
        assert response.status_code == 201, response.get_json()
        response_json = response.get_json()
        normal_application_check_id = response_json['payload']['id']
        sleep(sleep_param * 3 + 2)  # waiting started and received checks and 2 sec allowable error
        # check status for normal application check
        response = c.get(f'/v2.1/check/{normal_application_check_id}/status', headers=normal_application_headers)
        assert response.status_code == 200, response.get_json()
        response_json = response.get_json()
        status = response_json['payload']['status']
        assert status == CheckStatus.COMPLETED.name, c.get(f'/v2.1/check/{normal_application_check_id}/results', headers=normal_application_headers).get_json()
        # check last check for flood application
        response = c.get(f'/v2.1/check/{last_check_id}/status', headers=flood_application_headers)
        assert response.status_code == 200, response.get_json()
        response_json = response.get_json()
        status = response_json['payload']['status']
        assert status == CheckStatus.NOT_COMPLETED.name
