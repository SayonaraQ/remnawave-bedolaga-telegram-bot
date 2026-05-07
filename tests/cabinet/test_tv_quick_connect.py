from app.services.tv_quick_connect import parse_tv_quick_connect_target


def test_parse_happ_tv_code_direct():
    target = parse_tv_quick_connect_target('a1b2c')

    assert target is not None
    assert target.provider == 'happ'
    assert target.value == 'A1B2C'


def test_parse_happ_tv_code_from_url():
    target = parse_tv_quick_connect_target('https://check.happ.su/sendtv/A1B2C')

    assert target is not None
    assert target.provider == 'happ'
    assert target.value == 'A1B2C'


def test_parse_v2raytun_streamvault_key_direct():
    target = parse_tv_quick_connect_target('c43ea727b1d748279ebd4af8c096f726')

    assert target is not None
    assert target.provider == 'v2raytun'
    assert target.value == 'c43ea727b1d748279ebd4af8c096f726'


def test_parse_v2raytun_streamvault_key_from_json():
    target = parse_tv_quick_connect_target('{"key":"C43EA727B1D748279EBD4AF8C096F726"}')

    assert target is not None
    assert target.provider == 'v2raytun'
    assert target.value == 'c43ea727b1d748279ebd4af8c096f726'


def test_parse_v2raytun_streamvault_key_from_url():
    target = parse_tv_quick_connect_target(
        'v2raytun://c43ea727b1d748279ebd4af8c096f726'
    )

    assert target is not None
    assert target.provider == 'v2raytun'
    assert target.value == 'c43ea727b1d748279ebd4af8c096f726'


def test_parse_unsupported_qr():
    assert parse_tv_quick_connect_target('https://example.com/subscription') is None
