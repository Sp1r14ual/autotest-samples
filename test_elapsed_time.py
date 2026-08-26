from datetime import datetime, timedelta, timezone

from collection_api.enums import EntityType, CheckStatus
from simple_settings import settings

from app import app


def test_elapsed_time():
    headers = {'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'}
    sleep_param = 3
    check_methods = {
        'test_source': [{
            'test_method_with_sleep': {'sleep': sleep_param}
        }],
        'common': ['young']
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
        create_time = datetime.now(timezone.utc).replace(microsecond=0)
        create_response = c.post('/v2.1/check/create', headers=headers, json=data)
        assert create_response.status_code == 201
        check_id = create_response.get_json()['payload']['id']
        status_response = c.get(f'/v2.1/check/{check_id}/status',
                                headers={'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'})
        assert status_response.status_code == 200
        status_data = status_response.get_json()
        date_updated = datetime.fromtimestamp(int(status_data['payload']['date_updated'])).replace(tzinfo=timezone.utc)
        assert create_time <= date_updated <= datetime.now(timezone.utc)
        while True:
            if (datetime.now(timezone.utc) - create_time).seconds > settings.CHECK_TIMEOUT:
                raise TimeoutError(f'Collection check timeout({settings.CHECK_TIMEOUT}) error')
            status_response = c.get(f'/v2.1/check/{check_id}/status',
                                    headers={'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'})
            assert status_response.status_code == 200
            status_data = status_response.get_json()
            if status_data['payload']['status'] != CheckStatus.NOT_COMPLETED:
                break
        stats_response = c.get(f'/v2.1/check/{check_id}/stats',
                               headers={'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'})
        stats_data = stats_response.get_json()
        elapsed_total = int(stats_data['payload']['elapsed_total'])
        date_updated = datetime.fromtimestamp(int(status_data['payload']['date_updated'])).replace(tzinfo=timezone.utc)
        assert create_time <= date_updated <= datetime.now(timezone.utc)
        assert elapsed_total > 0
        assert create_time + timedelta(seconds=elapsed_total) <= datetime.now(timezone.utc).replace(microsecond=0)
        assert (create_time + timedelta(seconds=elapsed_total)) <= date_updated
