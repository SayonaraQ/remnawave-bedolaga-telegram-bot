"""Имя приложения-клиента из User-Agent устройства в панели.

Клиенты VPN шлют за подпиской User-Agent вида `Happ/3.12.1/ios/<HWID>`,
`INCY/3.7.0`, `koala-clash/0.4.2`: первое поле до `/` — само приложение.
Панель хранит его у каждого HWID (`hwid_user_devices.user_agent`), и кабинет
показывает его в слоте: одно устройство с подпиской в двух приложениях — это два
HWID и два слота, и без имени приложения их не отличить.

Здесь только сырой токен; красивое имя («Koala Clash», «v2RayTun») — забота
кабинета, он же решает, как показать незнакомый клиент.
"""

MAX_APP_LENGTH = 40


def client_app_from_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    head = user_agent.strip().split('/', 1)[0].strip()
    return head[:MAX_APP_LENGTH] or None
