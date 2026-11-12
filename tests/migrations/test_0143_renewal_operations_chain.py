"""Форк: апстримная 0141 (операции продления) перенумерована в 0143.

У форка 0141 — тема вопроса FAQ, 0142 — поля карточки тарифа. Две ревизии
с одним id Alembic не грузит вовсе, поэтому цепочка обязана остаться линейной.
"""

import importlib
from pathlib import Path


VERSIONS = Path(__file__).resolve().parents[2] / 'migrations' / 'alembic' / 'versions'


def test_renewal_operations_migration_follows_fork_0142():
    migration = importlib.import_module('migrations.alembic.versions.0143_subscription_renewal_operations')
    assert migration.revision == '0143'
    assert migration.down_revision == '0142'


def test_revision_ids_are_unique_and_linear():
    revisions: dict[str, str | None] = {}
    for path in sorted(VERSIONS.glob('[0-9][0-9][0-9][0-9]_*.py')):
        module = importlib.import_module(f'migrations.alembic.versions.{path.stem}')
        assert module.revision not in revisions, f'duplicate revision {module.revision}: {path.name}'
        revisions[module.revision] = module.down_revision
    children = [down for down in revisions.values() if down is not None]
    assert len(children) == len(set(children)), 'two revisions share one parent (branch)'
    heads = set(revisions) - set(children)
    assert len(heads) == 1, f'expected one head, got {sorted(heads)}'
