import json
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
from collection_api.enums import MethodStatus, ErrorMessage
from simple_settings import settings

from db import Db, models
from sources.base import SourceUtil
from sources.check import Check
from tasks import check_common
from tests.v2.util import create_check

with (Path(settings.TEST_DATA) / 'recheck.json').open() as f:
    data = json.loads(f.read())


def __get_error_method_params(data):
    params = []
    for test_data in data:
        param = [test_data['data'], test_data['source'], test_data['methods'], test_data['error_methods']]
        params.append(param)
    return params


@pytest.mark.parametrize('data,source,methods,error_methods', __get_error_method_params(data['ERROR_METHOD_PARAMS']))
def test_get_error_method(data, source, methods, error_methods):
    assert SourceUtil.is_single_class(source) or len(methods) == 1
    check_id = create_check(data=data, check_methods={source: methods})
    check = Check(check_id)
    kwargs = dict(check_id=check.obj['_id'], source_name=source, method_name=methods[0])
    check_common(**kwargs)
    results = check.get_results(version='v2.1')
    error_method_names = Check(check_id).get_error_method_names()
    assert len(results[source]) == len(methods)
    assert set(error_method_names) == set(error_methods)


def __get_fake_results(success_recheck_count=None):
    error_result = dict(status=MethodStatus.ERROR, error=ErrorMessage.SOURCE)
    success_result = dict(status=MethodStatus.OK, risk_exists=True, text='OK')
    fake_results = [error_result for _ in range(settings.RECHECK_COUNT + 1)]
    if success_recheck_count is not None:
        assert isinstance(success_recheck_count, int)
        assert success_recheck_count <= settings.RECHECK_COUNT + 1
        fake_results[success_recheck_count] = success_result
    return fake_results


def __get_recheck_count_params(data):
    params = []
    for test_data in data:
        param = [test_data['data'], test_data['source'], test_data['method'], test_data['success_checked_count']]
        params.append(param)
    return params


@pytest.mark.skipif(settings.RECHECK_COUNT == 0, reason="Recheck is deactivated")
@pytest.mark.parametrize('data,source,method,success_checked_count', __get_recheck_count_params(data['RECHECK_COUNT']))
def test_recheck_count(data, source, method, success_checked_count):
    check_id = create_check(data=data, check_methods={source: [method]})
    check = Check(check_id)
    Source = SourceUtil.get_source_cls(source, method_name=method)
    if SourceUtil.is_single_class(source):
        method_name = Source.AVAILABLE_METHODS_MAPPING[method]
    else:
        method_name = 'check'
    method_path = f'{Source.__module__}.{Source.__name__}.{method_name}'
    with mock.patch(method_path) as mock_method:
        fake_results = __get_fake_results(success_recheck_count=success_checked_count)
        mock_method.side_effect = fake_results
        kwargs = dict(check_id=check.obj['_id'], source_name=source, method_name=method)
        check_common(**kwargs)
        call_count = success_checked_count if isinstance(success_checked_count, int) else settings.RECHECK_COUNT
        assert mock_method.call_count == call_count + 1
        assert check.get_results(version='v2.1')[source][method] == fake_results[call_count]
