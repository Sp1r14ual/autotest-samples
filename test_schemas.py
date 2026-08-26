import random

import pytest
from cerberus import Validator
from collection_api.api.v2.schemas import PAYLOAD_INDIVIDUAL_SCHEMA
from collection_api.enums import EntityType, MethodStatus, ErrorMessage, ErrorCode
from collection_api.utils.base import get_region
from collection_api.utils.validation import CollectionValidator

from resources.schemas import INPUT_BASE_SCHEMA, METHOD_OK_SCHEMA, METHOD_ERROR_SCHEMA


@pytest.fixture
def input_validator():
    return CollectionValidator(INPUT_BASE_SCHEMA)


@pytest.fixture
def method_ok_validator():
    return CollectionValidator(METHOD_OK_SCHEMA)


@pytest.fixture
def method_error_validator():
    return CollectionValidator(METHOD_ERROR_SCHEMA)


@pytest.mark.parametrize(
    'payload',
    [
        {
            'application_id': 'test',
            'entity_type': random.choice(EntityType.all()),
            'payload': {'key': 'value'},
            'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
        },
    ]
)
def test_input(input_validator, payload):
    assert input_validator.validate(payload) is True
    assert not input_validator.errors


@pytest.mark.parametrize(
    'payload,fields,count',
    [
        [
            {
                'application_id': '',
                'entity_type': random.choice(EntityType.all()),
                'payload': {'key': 'value'},
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['application_id'],
            1
        ],
        [
            {
                'entity_type': random.choice(EntityType.all()),
                'payload': {'key': 'value'},
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['application_id'],
            1
        ],
        [
            {
                'application_id': 1,
                'entity_type': random.choice(EntityType.all()),
                'payload': {'key': 'value'},
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['application_id'],
            1
        ],
        [
            {
                'application_id': 'test',
                'entity_type': '',
                'payload': {'key': 'value'},
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['entity_type'],
            1
        ],
        [
            {
                'application_id': 'test',
                'payload': {'key': 'value'},
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['entity_type'],
            1
        ],
        [
            {
                'application_id': 'test',
                'entity_type': 'person',
                'payload': {'key': 'value'},
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['entity_type'],
            1
        ],
        [
            {
                'application_id': 'test',
                'entity_type': 1,
                'payload': {'key': 'value'},
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['entity_type'],
            1
        ],
        [
            {
                'application_id': 'test',
                'entity_type': random.choice(EntityType.all()),
                'payload': {},
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['payload'],
            1
        ],
        [
            {
                'application_id': 'test',
                'entity_type': random.choice(EntityType.all()),
                'payload': None,
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['payload'],
            1
        ],
        [
            {
                'application_id': 'test',
                'entity_type': random.choice(EntityType.all()),
                'payload': ['key'],
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['payload'],
            1
        ],
        [
            {
                'application_id': 'test',
                'entity_type': random.choice(EntityType.all()),
                'check_methods': {'s1': ['m1', 'm2'], 's2': ['m1', 'm2']},
            },
            ['payload'],
            1
        ],
        [
            {
                'application_id': 'test',
                'entity_type': random.choice(EntityType.all()),
                'payload': {'key': 'value'},
            },
            ['check_methods'],
            1
        ],
        [
            {
                'application_id': 'test',
                'entity_type': random.choice(EntityType.all()),
                'payload': {'key': 'value'},
                'check_methods': {},
            },
            ['check_methods'],
            1
        ],

    ]
)
def test_input_errors(input_validator, payload, fields, count):
    assert input_validator.validate(payload) is False
    assert sorted(list(input_validator.errors.keys())) == sorted(fields)
    assert sum(list(map(len, input_validator.errors.values()))) == count


@pytest.mark.parametrize(
    'payload',
    [
        {'status': MethodStatus.OK, 'risk_exists': True, 'text': 'Text', 'additional_data': {'key': 'value'}},
        {'status': MethodStatus.OK, 'risk_exists': True, 'text': 'Text', 'additional_data': {'key': 'value', 'k': 1}},
        {'status': MethodStatus.OK, 'risk_exists': True, 'text': 'Text', 'additional_data': {'key': 'value', 'k': [1, 2, 3]}},
        {'status': MethodStatus.OK, 'risk_exists': True, 'text': 'Text', 'additional_data': {'key': 'value', 'k': {'inner': 1}}},
        {'status': MethodStatus.OK, 'risk_exists': True, 'text': 'Text'},
        {'status': MethodStatus.OK, 'risk_exists': True},
        {'status': MethodStatus.OK, 'risk_exists': True, 'additional_data': {'key': 'value'}},
        {'status': MethodStatus.OK, 'risk_exists': False, 'text': 'Text'},
        {'status': MethodStatus.OK, 'risk_exists': False},
    ]
)
def test_method_ok_result(method_ok_validator, payload):
    assert method_ok_validator.validate(payload) is True
    assert not method_ok_validator.errors


@pytest.mark.parametrize(
    'payload',
    [
        {
            'status': MethodStatus.ERROR,
            'error': random.choice(ErrorMessage.all()),
            'error_code': random.choice(ErrorCode.all())
        },
        {
            'status': MethodStatus.ERROR,
            'error': 'Custom message',
            'error_code': random.choice(ErrorCode.all())
        },
    ]
)
def test_method_error_result(method_error_validator, payload):
    assert method_error_validator.validate(payload) is True
    assert not method_error_validator.errors


@pytest.mark.parametrize(
    'payload,fields,count',
    [
        [
            {
                'status': '',
                'risk_exists': True,
                'text': 'Text',
                'additional_data': {'key': 'value'}
            },
            ['status'],
            1
        ],
        [
            {
                'risk_exists': True,
                'text': 'Text',
                'additional_data': {'key': 'value'}
            },
            ['status'],
            1
        ],
        [
            {
                'status': 'SHIT',
                'risk_exists': True,
                'text': 'Text',
                'additional_data': {'key': 'value'}
            },
            ['status'],
            1
        ],
        [
            {
                'status': MethodStatus.OK,
                'risk_exists': False,
                'text': 'Text',
                'additional_data': [{'key': 'value'}]
            },
            ['additional_data'],
            1
        ],
        [
            {
                'status': MethodStatus.ERROR,
                'risk_exists': True,
                'text': 'Text',
                'additional_data': {'key': 'value'}
            },
            ['status'],
            1
        ],
    ]
)
def test_method_ok_errors(method_ok_validator, payload, fields, count):
    assert method_ok_validator.validate(payload) is False
    assert sorted(list(method_ok_validator.errors.keys())) == sorted(fields)
    assert sum(list(map(len, method_ok_validator.errors.values()))) == count


@pytest.mark.parametrize(
    'payload,fields,count',
    [
        [
            {
                'error': random.choice(ErrorMessage.all()),
                'error_code': random.choice(ErrorCode.all()),
            },
            ['status'],
            1
        ],
        [
            {
                'status': None,
                'error': random.choice(ErrorMessage.all()),
                'error_code': random.choice(ErrorCode.all()),
            },
            ['status'],
            1
        ],
        [
            {
                'status': '',
                'error': random.choice(ErrorMessage.all()),
                'error_code': random.choice(ErrorCode.all()),
            },
            ['status'],
            1
        ],
        [
            {
                'status': 'SHIT',
                'error': random.choice(ErrorMessage.all()),
                'error_code': random.choice(ErrorCode.all()),
            },
            ['status'],
            1
        ],
        [
            {
                'status': MethodStatus.ERROR,
                'error': random.choice(ErrorMessage.all()),
                'error_code': random.choice(ErrorCode.all()),
                'risk_exists': True,
                'text': 'Text',
                'additional_data': {'key': 'value'}
            },
            ['risk_exists', 'text', 'additional_data'],
            3
        ],
        [
            {
                'status': MethodStatus.ERROR,
                'error': random.choice(ErrorMessage.all()),
            },
            ['error_code'],
            1
        ],
        [
            {
                'status': MethodStatus.ERROR,
                'error_code': random.choice(ErrorCode.all()),
            },
            ['error'],
            1
        ],
        [
            {
                'status': MethodStatus.ERROR,
                'error': '',
                'error_code': random.choice(ErrorCode.all()),
            },
            ['error'],
            1
        ],
        [
            {
                'status': MethodStatus.ERROR,
                'error': random.choice(ErrorMessage.all()),
                'error_code': None,
            },
            ['error_code'],
            1
        ],
        [
            {
                'status': MethodStatus.ERROR,
                'error': random.choice(ErrorMessage.all()),
                'error_code': '',
            },
            ['error_code'],
            1
        ],
        [
            {
                'status': MethodStatus.ERROR,
                'error': random.choice(ErrorMessage.all()),
                'error_code': -1,
            },
            ['error_code'],
            1
        ],

    ]
)
def test_method_error_errors(method_error_validator, payload, fields, count):
    assert method_error_validator.validate(payload) is False
    assert sorted(list(method_error_validator.errors.keys())) == sorted(fields)
    assert sum(list(map(len, method_error_validator.errors.values()))) == count


@pytest.mark.parametrize(
    'region,code', [
        ['тАтарстан респ.', '91'],
        ['НеНецкий', '11'],
        ['ЯМАЛО Ненецкий', '71'],
        ['ХантыМанты', None],
        ['Саха', '98'],
        ['Саха(Якутия)', '98'],
        ['Москва столица', '45'],
        ['Область', None],
        ['Область республика', None],
    ]
)
def test_get_region(region, code):
    try:
        assert get_region(region) == code
    except (TypeError, ValueError):
        if code:
            raise


@pytest.mark.parametrize(
    'region,valid', [
        ['тАтарстан респ.', True],
        ['НеНецкий', True],
        ['ЯМАЛО Ненецкий', True],
        ['ХантыМанты', False],
        ['Саха', True],
        ['Саха(Якутия)', True],
        ['Москва столица', True],
        ['Область', False],
        ['Область республика', False],
        ['40', True],
        ['3', False],
        ['03', True],
        [5, False],
        ['05', True]
    ]
)
def test_get_region(region, valid):
    v = Validator({'region': PAYLOAD_INDIVIDUAL_SCHEMA['region']})
    assert v.validate({'region': region}) is valid, v.errors
