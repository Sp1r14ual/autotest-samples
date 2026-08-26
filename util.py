import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from collection_api.enums import EntityType, SimilarityLevel
from openpyxl import load_workbook
from simple_settings import settings

from db import models, Db
from db.models import generate_token
from resources.v2 import source_mapping_items
from sources.base import SourceUtil

log = logging.getLogger(__name__)


entity_type_transfer = {
    'юл': EntityType.CORPORATE,
    'фл': EntityType.INDIVIDUAL,
}

result_transfer = {
    'да': True,
    'нет': False,
}

similarity_transfer = {
    'high': SimilarityLevel.HIGH,
    'mid': SimilarityLevel.MID,
}


def parse_xlsx(fixture=None):
    fixture = fixture or Path(__file__).resolve().parent / 'fixtures' / 'Данные для тестирования.xlsx'
    wb = load_workbook(fixture)
    sheet = wb.active
    fixtures_dict = {}
    for i, row in enumerate(sheet.rows):
        fixture_dict = {}
        method_name = row[2].value
        if not method_name or len(method_name.split()) != 2:
            continue
        try:
            source_name, method_name = method_name.split()[0], method_name.split()[1]
            if source_name not in fixtures_dict:
                fixtures_dict[source_name] = {}
            if method_name not in fixtures_dict[source_name]:
                fixtures_dict[source_name][method_name] = []
            fixture_dict['method'] = SourceUtil.get_check_method(source_name=source_name, method_name=method_name)
            entity_type = entity_type_transfer.get(row[3].value.lower())
            if entity_type == EntityType.CORPORATE:
                fixture_dict['data'] = _corporate_parse(row[4].value)
            elif entity_type == EntityType.INDIVIDUAL:
                fixture_dict['data'] = _individual_parse(row[4].value)
            fixture_dict['data']['entity_type'] = entity_type
            fixture_dict['result'] = result_transfer.get(row[6].value.lower())
            if row[7].value:
                fixture_dict['similarity'] = similarity_transfer.get(row[7].value.lower())
            else:
                fixture_dict['similarity'] = None
            fixtures_dict[source_name][method_name].append(fixture_dict)
        except Exception as e:
            log.error(f"Error while parsing xlsx: {e}", {"event": "collection_service:tests:v2:util:parse_xlsx:error"}, exc_info=True)
    return fixtures_dict


def _corporate_parse(data):
    parsed_data = {}
    if data:
        if data:
            if isinstance(data, (float, int)):
                data = str(int(data))
        inn = re.search(r'\d{10}', data)
        if inn:
            inn = parsed_data['inn'] = inn.group(0)
        data = data.replace(inn or '', '').strip()
        if data:
            parsed_data['name'] = data
    return parsed_data


def _individual_parse(data):
    parsed_data = {}
    if data:
        if isinstance(data, (float, int)):
            data = str(int(data))
        inn = re.search(r'\d{12}', data)
        if inn:
            inn = parsed_data['inn'] = inn.group(0)
        data = data.replace(inn or '', '').strip()
        dob = re.search(r'\d{2}.\d{2}.\d{4}|\d{4}-\d{2}-\d{2}', data)
        if dob:
            dob = parsed_data['dob'] = dob.group(0)
        data = data.replace(dob or '', '').strip()
        passport = re.search(r'\d{4} \d{6}', data)
        if passport:
            passport = passport.group(0)
            parsed_data['passport_series'] = passport.split()[0]
            parsed_data['passport_number'] = passport.split()[1]
        data = data.replace(passport or '', '').strip()
        if data:
            name_parts = data.split()
            parsed_data['name_last'] = name_parts[0]
            parsed_data['name_first'] = name_parts[1]
            if len(name_parts) > 2:
                parsed_data['name_middle'] = ' '.join(name_parts[2:])
    return parsed_data


def get_params(params, is_single=None, source=None, methods=None, exclude_methods=None, exclude_sources=None):
    exclude_methods = exclude_methods or []
    exclude_sources = exclude_sources or []
    methods = methods or []
    filtered_params = []
    if source in exclude_sources:
        raise RuntimeError('Check source in excluded sources')
    for source_name, params_methods in params.items():
        if source_name in exclude_sources:
            continue
        if (not source or source_name == source) and (is_single is None or
                                                      SourceUtil.is_single_class(source_name) is is_single):
            for method, fixtures in params_methods.items():
                if (methods and method in methods or not methods) and method not in exclude_methods:
                    for fixture in fixtures:
                        filtered_params.append([fixture['data'], fixture.get("args"), fixture.get('similarity'), fixture['result'],
                                                fixture.get('error'), source_name, method,
                                                fixture.get('additional_data')])
    return filtered_params


def create_check(data, check_methods):
    models.Check.bind(Db().db)
    check = models.Check(
        data=models.Request(
            entity_type=data.pop('entity_type'),
            payload=data,
            application_id='test',
        ),
        meta_=models.Meta(
            v='2.1',
            date_updated=datetime.now(timezone.utc),
        ),
        methods=check_methods,
        stats=[],
        application='test',
    )
    check.insert_one()
    return check.id


def create_token(description: str, token: str = None, allowed_check_methods: dict = None):
    token = token or generate_token()
    allowed_check_methods = allowed_check_methods or {source: None for source, _ in
                                                      source_mapping_items(settings.SOURCE_MAPPING)}
    models.Application.bind(Db().db)
    models.APIToken.bind(Db().db)
    application = models.Application(
        description=description,
        allowed_check_methods=allowed_check_methods,
    )
    application.insert_one()
    token = models.APIToken(application=application, token=token)
    token.insert_one()
    return application, token
