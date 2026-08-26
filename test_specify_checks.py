import pytest
from collection_api.enums import EntityType, MethodStatus, CheckStatus
from simple_settings import settings

from db import Db, models
from sources.base import SourceUtil
from tests.v2.util import create_check
from app import app


def _check_result(data, source, method, entity_type=EntityType.INDIVIDUAL, args=None):
    data['entity_type'] = entity_type
    models.Check.bind(Db().db)
    check_id = create_check(data=data, check_methods={source: [{method: args} if args else method]})
    source_cls = SourceUtil.get_source_cls(source_name=source, method_name=method)
    source_instance = source_cls(check_id=check_id)
    source_instance._current_method_key = method
    if SourceUtil.is_single_class(source):
        method_name = source_cls.AVAILABLE_METHODS_MAPPING[method]
        check_method = getattr(source_instance, method_name)
        check_result = check_method()
    else:
        check_result = source_instance.check()
    return check_result


@pytest.mark.skip('http error')
def test_scoring_and_verification():
    personal_data = {
        'phone_number': '79099063855',
        'work_address': 'VMV',
        'home_address': 'asjsg',
    }

    source, method, args = 'beeline', 'scoring_and_verification', {'approval': True, 'precision_address': 1000,
                                                                   'scoring_model': "UNI_V4"}
    result = _check_result(personal_data, source, method, args=args)['additional_data']
    verification = result.get('verification')
    assert result.get('score') is not None
    assert verification is not None
    assert len(verification) == 1
    assert verification[0].get('name') == 'LIFETIME_BIN_V2'

    verification_param = 'OS'
    source, method, args = 'beeline', 'scoring_and_verification', {'approval': True, 'precision_address': 1000,
                                                                   'scoring_model': "UNI_V4",
                                                                   'verification_params': [verification_param]}
    result = _check_result(personal_data, source, method, args=args)['additional_data']
    verification = result.get('verification')
    assert result.get('score') is not None
    assert verification is not None
    assert len(verification) == 1
    assert verification[0].get('name') == verification_param

    source, method, args = 'beeline', 'scoring_and_verification', {'approval': True, 'scoring_model': "INCOME_V1"}
    result = _check_result(personal_data, source, method, args=args)['additional_data']
    assert result.get('score') is not None
    assert result.get('verification') is None

    personal_data['phone_number'] = '78099063851'
    result = _check_result(personal_data, source, method, args=args)['error_data']
    assert result == {'fault_code': 'DATA_NOT_FOUND', 'fault_message': 'Не найдены данные по абоненту'}


@pytest.mark.skip('134705671581 != 99706678773')
def test_cft_postgres_with_args():
    test_data = [
        {
            'to_check': {
                "inn": "770100948307",
            },
            'args': {
                'period_end': '30.07.2020'
            },
            'to_diff': {
                'client_id': 1910816089
            }

        },
        {
            'to_check': {
                'name_last': 'НЕБОЖЕНКО',
                'name_first': 'РУСЛАН',
                'name_middle': 'ВЛАДИМИРОВИЧ',
                'dob': '18.01.1992',
            },
            'args': {
                'period_end': '30.07.2020'
            },
            'to_diff': {
                'client_id': 48665072018
            }

        },
        {
            'to_check': {
                'name_last': 'HBZ',
                'name_first': 'KTO',
                'name_middle': 'ВЛАДИМИРОВИЧ',
                'dob': '18.01.1992',
            },
            'args': {
                'period_end': '30.07.2020'
            },
            'to_diff': {
                'risk_exists': False
            }

        }
    ]

    source, method = 'cft_postgres', 'client_info'
    for test in test_data:
        result = _check_result(test['to_check'], source, method,
                               args=test['args'], entity_type=EntityType.ENTREPRENEUR)
        if result.get('additional_data'):
            assert len(result['additional_data']['records']) == 1
            assert result['additional_data']['records'][0]['client_id'] == test['to_diff']['client_id']
        else:
            assert result['risk_exists'] is test['to_diff']['risk_exists']

    test_data = [
        {
            'to_check': {
                'client_id': 48665072018,
                'period_start': '01.01.2020',
                'period_end': '30.07.2020'
            },
            'to_diff': {
                'account_id': 48675641750
            }

        },
        {
            'to_check': {
                'client_id': 1910816089,
                'period_start': '01.01.2020',
                'period_end': '30.07.2020'
            },
            'to_diff': {
                'account_id': 99706678773
            }

        },
        {
            'to_check': {
                'client_id': 231,
                'period_start': '01.01.2020',
                'period_end': '30.07.2020'
            },
            'to_diff': {
                'risk_exists': False
            }

        },

    ]

    source, method = 'cft_postgres', 'client_documents'
    for test in test_data:
        result = _check_result({}, source, method,
                               args=test['to_check'], entity_type=EntityType.ENTREPRENEUR)
        if result.get('additional_data'):
            assert result['additional_data']['records'][0]['account'][0]['account_id'] == test['to_diff']['account_id']
        else:
            assert result['risk_exists'] is test['to_diff']['risk_exists']

    test_data = [
        {
            'to_check': {
                'required_keys': {
                    'inn': '691105823007'

                },
                'args': {
                    'period_start': '01.01.2020',
                    'period_end': '30.07.2020',
                    'receiver_inn': True,
                    'account_number': '40817810901010774990'
                }
            },
            'to_diff': {
                'count_descr': 1
            }

        },
        {
            'to_check': {
                'required_keys': {
                    'inn': '463403720736'

                },
                'args': {
                    'period_start': '20.03.2020',
                    'period_end': '30.09.2020',
                    'receiver_inn': False,
                    'account_number': '40817810216105000002'
                }
            },
            'to_diff': {
                'count_descr': 9
            }

        },

        {
            'to_check': {
                'required_keys': {
                    'inn': '463403720731'

                },
                'args': {
                    'period_start': '20.03.2020',
                    'period_end': '30.09.2020',
                    'receiver_inn': False,
                    'account_number': '40817810216105000002'
                }
            },
            'to_diff': {
                'risk_exists': False
            }

        },

    ]

    source, method = 'cft_postgres', 'client_purpose_payment'
    for test in test_data:
        result = _check_result(test['to_check']['required_keys'], source, method,
                               args=test['to_check']['args'], entity_type=EntityType.ENTREPRENEUR)
        if result.get('additional_data'):
            assert len(result['additional_data']['records']) == test['to_diff']['count_descr']
        else:
            assert result['risk_exists'] is test['to_diff']['risk_exists']


@pytest.mark.skip('INN check is unstable')
def test_stress_get_inn():
    checks = {}
    headers = {'Authorization': f'Bearer {settings.COLLECTION_TOKEN}'}
    source, method = 'service_nalog', 'inn'
    with app.test_client() as c:
        for _ in range(20):
            response = c.post('/v2.1/check/create', headers=headers,
                              json={
                                  "application_id": "test",
                                  "entity_type": EntityType.INDIVIDUAL,
                                  "payload": {
                                      "name_last": "ПЛЮСНИН",
                                      "name_first": "ПАВЕЛ",
                                      "name_middle": "АНАТОЛЬЕВИЧ",
                                      "dob": "12.09.1978",
                                      "passport_series": "5718",
                                      "passport_number": "715833",
                                  },
                                  "check_methods": {
                                      source: [method]
                                  }
                              })
            assert response.status_code == 201
            response_json = response.get_json()
            check_id = response_json['payload']['id']
            checks[check_id] = CheckStatus.NOT_COMPLETED
        while True:
            checks_id = list(filter(lambda x: checks[x] == 'NOT_COMPLETED', checks))
            if not checks_id:
                break
            for check_id in checks_id:
                response = c.get(f'/v2.1/check/{check_id}/status', headers=headers)
                assert response.status_code == 200
                response_json = response.get_json()
                status = response_json['payload']['status']
                assert status != CheckStatus.ERROR.name
                if status == CheckStatus.COMPLETED:
                    response = c.get(f'/v2.1/check/{check_id}/results', headers=headers)
                    assert response.status_code == 200
                    response_json = response.get_json()
                    check_result = response_json['payload'][source][method]
                    assert check_result['status'] == MethodStatus.OK.name
                    assert check_result['risk_exists'] is True
                    assert check_result['additional_data']['inn'] == '590709474033'
                    checks[check_id] = CheckStatus.COMPLETED


@pytest.mark.skip('http status 403')
def test_smart_data_scoring_data():
    personal_data = {
        'phone_number': '79099063855',
    }

    source, method, args = 'common', 'smart_data_scoring_data', {'user_agreement': True, 'model': "bins40"}
    result = _check_result(personal_data, source, method, args=args)['additional_data']
    assert result.get('success') is not None
    assert result.get('error') is None

    personal_data['phone_number'] = '79901234567'
    result = _check_result(personal_data, source, method, args=args)['additional_data']
    assert result.get('error') is not None


