import json
import logging
from copy import deepcopy
from pathlib import Path
from time import sleep

import pytest
from flaky import flaky
from simple_settings import settings

from db import Db, models
from sources.base import SourceUtil
from sources.v2.inphosphere import Inphosphere
from tests.v2.util import get_params, create_check

log = logging.getLogger(__name__)

with (Path(settings.TEST_DATA) / 'auto_check.json').open() as f:
    data = json.loads(f.read())


def ensure_auto_check_covers_all_methods(data):
    all_methods = set()
    for source in settings.SOURCE_MAPPING.keys():
        for method in SourceUtil.get_methods_list(source):
            all_methods.add(f'{source}.{method}')

    check_methods = set()
    for source, methods in data.items():
        for method in methods.keys():
            check_methods.add(f'{source}.{method}')

    assert check_methods == all_methods, (
        'auto_check.json method list is mismatched SOURCE_MAPPING. '
        f'Checks are missed {", ".join(sorted(all_methods - check_methods)) or "none"}. '
        f'Checks are redundant {", ".join(sorted(check_methods - all_methods)) or "none"}. '
    )


def inphosphere_initial_post(instance):
    instance.create_request()
    inphosphere_response_data = instance.get_current_results()
    while inphosphere_response_data['@status'] != '1':
        inphosphere_response_data = instance.get_current_results()
        sleep(0.5)
    instance.inphosphere_response_data = inphosphere_response_data
    return instance


additional_initial = {
    Inphosphere.SOURCE_KEY: inphosphere_initial_post
}


@pytest.mark.parametrize(
    'data,args,similarity,result,error,source,method,additional_data', get_params(
        params=data,
        exclude_sources=[
            'inphosphere',
            'ews_buffer',
        ],
        exclude_methods=[
            'check_compromat_sledcom',  # failed by external source timeout
            'vestnik',  # failed by external source timeout
            'diploma',  # failed due to captcha
            'check_tax_penalty',  # failed due many requests(429 status code)
            'check_compromat',
            'get_contact',  # сервис временно не доступен
            "check_compromat_prosecutor",  # сервис сменил сайт и больше не работает
            "gibdd_history",  # сервис ГИБДД последнее время работает крайне нестабильно
            "gibdd_aiusdtp",  # сервис ГИБДД последнее время работает крайне нестабильно
            "gibdd_restricted",  # сервис ГИБДД последнее время работает крайне нестабильно
            "gibdd_wanted",  # сервис ГИБДД последнее время работает крайне нестабильно
            "rosfinmonitoring", # Ответ от rucapthca на POST: ERROR_ZERO_BALANCE
            "check_compromat_group", # На сайте висит баннер, что сайт временно не работает
            "check_compromat_kommersant", # request timeout
            "gosuslugi_passport", # падает по таймауту
            "unscrupulous_supplier",  # проблема с подключением
            "check_rucompromat",  # ресурс недоступен
            "check_arbitration_plaintiff",  # ошибка при работе с БД
            "check_arbitration_defendant",  # ошибка при работе с БД
            "get_negative_net_assets",  # ошибка при работе с БД
            "get_ews_execution_proceedings",  # ошибка при работе с БД
            "get_ews_unfulfilled_settlement_documents",  # ошибка при проверке
            "get_ews_account_block",  # ошибка при проверке
            "negative_net_assets",  # ошибка при проверке
    ]))
@flaky(max_runs=2)
def test_check(data, args, similarity, result, error, source, method, additional_data):
    copied_data = deepcopy(data)
    models.Check.bind(Db().db)
    check_id = create_check(data=copied_data, check_methods={source: [method] if not args else [{method: args}]})
    source_cls = SourceUtil.get_source_cls(source_name=source, method_name=method)
    source_instance = source_cls(check_id=check_id)
    if source in additional_initial:
        source_instance = additional_initial[source](source_instance)
    source_instance._current_method_key = method
    if SourceUtil.is_single_class(source):
        method_name = source_cls.AVAILABLE_METHODS_MAPPING[method]
        check_method = getattr(source_instance, method_name)
        try:
            check_result = check_method()
        except Exception as err:
            if error:
                assert error == err.err_code.value
                return
            else:
                raise err
    else:
        check_result = source_instance.check()
    source_instance.clear_instance()
    log.info('[CHECK]: {source}.{method}'.format(source=source, method=method), {"event": "collection_service:tests:v2:test_checks:test_check:process"})
    log.info('[SEARCH]: {data}'.format(data=copied_data), {"event": "collection_service:tests:v2:test_checks:test_check:process"})
    log.info('[RESULT]: {result}'.format(result=check_result), {"event": "collection_service:tests:v2:test_checks:test_check:process"})
    if result is not None:
        assert result is check_result.get('risk_exists')
    if similarity:
        assert similarity in [record['similarity'] for record in check_result['additional_data']['records']]
    if additional_data:
        assert additional_data == check_result.get('additional_data')
