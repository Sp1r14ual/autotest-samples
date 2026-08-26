import pytest
from collection_api.enums import EntityType, CheckStatus, MethodStatus, ErrorCode
from simple_settings import settings

from app import app

params = [
    [
        EntityType.INDIVIDUAL,
        {'name_last': 'Иванов', 'name_first': 'Иван', 'name_middle': 'Иванович'},
        {
            'cft_postgres': ['deny_list', 'terrors', {'client_documents': {
                'client_id': '123123',
                'period_start': '12.01.2021',
                'period_end': '12.01.2021'
            }}],
            'spark': ['lead_companies']
        },
        ['cft_postgres.deny_list', 'spark.lead_companies']
    ],
    [
        EntityType.CORPORATE,
        {'inn': '1234567890'},
        {
            'spark': ['status']
        },
        []
    ],
    [
        EntityType.CORPORATE,
        {'inn': '1234567890'},
        {
            'cft_postgres': ['deny_list']
        },
        []
    ],
    [
        EntityType.INDIVIDUAL,
        {'name_last': 'Иванов', 'name_first': 'Иван', 'name_middle': 'Иванович'},
        {
            'cft_postgres': ['deny_list'],
            'spark': ['lead_companies']
        },
        ['cft_postgres.deny_list', 'spark.lead_companies']
    ]
]


@pytest.mark.parametrize('entity_type,payload,check_methods,required_keys_errors', params)
def test_required_keys_errors(entity_type, payload,check_methods, required_keys_errors):
    headers = {'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'}
    with app.test_client() as c:
        response = c.post('/v2.1/check/create', headers=headers,
                          json={
                              "application_id": "test",
                              "entity_type": EntityType(entity_type),
                              "payload": payload,
                              "check_methods": check_methods
                          })
        assert response.status_code == 201, response.get_json()
        response_json = response.get_json()
        check_id = response_json['payload']['id']
        status = CheckStatus.NOT_COMPLETED
        while True:
            if status != CheckStatus.NOT_COMPLETED:
                break
            response = c.get(f'/v2.1/check/{check_id}/status', headers=headers)
            assert response.status_code == 200, response.get_json()
            response_json = response.get_json()
            status = response_json['payload']['status']
        response = c.get(f'/v2.1/check/{check_id}/results', headers=headers)
        assert response.status_code == 200
        response_json = response.get_json()
        for source, methods in response_json['payload'].items():
            for method, result in methods.items():
                check_result = response_json['payload'][source][method]
                if f'{source}.{method}' in required_keys_errors:
                    assert check_result['status'] == MethodStatus.ERROR.name
                    assert 'error_code' in check_result
                    assert check_result['error_code'] == ErrorCode.MISSING_REQUIRED_KEYS
                else:
                    if check_result['status'] == MethodStatus.ERROR.name and 'error_code' in check_result:
                        assert check_result['error_code'] != ErrorCode.MISSING_REQUIRED_KEYS
