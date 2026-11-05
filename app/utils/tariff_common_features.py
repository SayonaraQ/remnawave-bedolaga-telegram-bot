"""Parse the cabinet's common tariff features setting."""

ALLOWED_ICONS = ('globe', 'youtube', 'infinity', 'plus', 'check')


def parse_tariff_common_features(raw: str | None) -> list[dict[str, str]]:
    """Return at most eight nonempty features with bounded display text."""
    features = []
    for item in (raw or '').replace(';', '\n').splitlines():
        item = item.strip()
        if not item:
            continue
        prefix, separator, remainder = item.partition(':')
        icon = prefix.strip().lower()
        if separator and icon in ALLOWED_ICONS:
            text = remainder.strip()
        else:
            icon = 'check'
            text = item
        if not text:
            continue
        features.append({'icon': icon, 'text': text[:80].rstrip()})
        if len(features) == 8:
            break
    return features
