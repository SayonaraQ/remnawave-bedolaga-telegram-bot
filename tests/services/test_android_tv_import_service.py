import json

from app.services.android_tv_import_service import (
    build_streamvault_put_message,
    extract_streamvault_key,
)


def test_extract_streamvault_key_from_plain_value():
    key = '49c2bc6da2e449e29704bcba5f261b4d'
    assert extract_streamvault_key(key) == key


def test_extract_streamvault_key_from_json_payload():
    payload = json.dumps({'key': '49C2BC6DA2E449E29704BCBA5F261B4D', 'ttl': 120})
    assert extract_streamvault_key(payload) == '49c2bc6da2e449e29704bcba5f261b4d'


def test_extract_streamvault_key_from_mixed_text():
    payload = 'scan://import?session=49c2bc6da2e449e29704bcba5f261b4d&device=tv'
    assert extract_streamvault_key(payload) == '49c2bc6da2e449e29704bcba5f261b4d'


def test_extract_streamvault_key_returns_none_for_invalid_payload():
    assert extract_streamvault_key('no-key-here') is None


def test_build_streamvault_put_message_shape():
    message = build_streamvault_put_message(
        '49c2bc6da2e449e29704bcba5f261b4d',
        'https://speed.null-core.com/BCJqM1HPE6FKUUk6',
    )

    payload = json.loads(message)
    assert payload['action'] == 'PUT'

    nested = json.loads(payload['data'])
    assert nested == {
        'key': '49c2bc6da2e449e29704bcba5f261b4d',
        'value': 'https://speed.null-core.com/BCJqM1HPE6FKUUk6',
    }
