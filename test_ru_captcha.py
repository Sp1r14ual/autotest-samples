from collection_service.utils.base import ru_captcha
import os
from simple_settings import settings
import pytest


@pytest.mark.skipif(not settings.RUCAPTCHA_TOKEN,
                    reason="Необходмио ввести ключ от рукапча в настройках")
@pytest.mark.skip('Test failed due to captcha')
def test_ru_captcha():
    captcha = open(os.path.join(settings.TEST_DATA, 'getCaptcha.gif'), 'rb')
    captcha_bytes = captcha.read()
    t1 = ru_captcha(captcha_bytes)
    assert t1.lower() == 'ф91'


