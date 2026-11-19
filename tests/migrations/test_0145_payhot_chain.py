"""Форк: апстримные 0142/0143 (HOT Pay) перенумерованы в 0144/0145.

У форка 0142 — поля карточки тарифа, 0143 — операции продления (апстримная 0141).
Смещение апстрим → форк теперь +2: следующую апстримную 0144 двигать в 0146.
"""

import importlib


def test_payhot_payments_follows_renewal_operations():
    migration = importlib.import_module('migrations.alembic.versions.0144_create_payhot_payments')
    assert migration.revision == '0144'
    assert migration.down_revision == '0143'


def test_payhot_journal_is_the_head():
    migration = importlib.import_module('migrations.alembic.versions.0145_create_payhot_recurrent_journal')
    assert migration.revision == '0145'
    assert migration.down_revision == '0144'
