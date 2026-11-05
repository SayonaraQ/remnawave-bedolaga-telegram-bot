import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_tariff_card_fields_sqlite_upgrade_downgrade_keeps_rows():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE tariffs (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)'))
        connection.execute(text("INSERT INTO tariffs (id, name) VALUES (9, 'Семейный')"))
        migration = importlib.import_module('migrations.alembic.versions.0142_tariff_card_fields')
        assert migration.revision == '0142'
        assert migration.down_revision == '0141'
        card_fields = {'tagline', 'speed_limit_mbps', 'has_premium_servers'}
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            columns = {column['name']: column for column in inspect(connection).get_columns('tariffs')}
            assert card_fields <= columns.keys()
            assert columns['tagline']['type'].length == 160
            assert columns['tagline']['nullable']
            assert columns['speed_limit_mbps']['nullable']
            assert not columns['has_premium_servers']['nullable']
            assert connection.execute(
                text('SELECT tagline, speed_limit_mbps, has_premium_servers FROM tariffs WHERE id = 9')
            ).one() == (None, None, 0)
            connection.execute(text("INSERT INTO tariffs (id, name) VALUES (10, 'Базовый')"))
            assert connection.scalar(text('SELECT has_premium_servers FROM tariffs WHERE id = 10')) == 0

            migration.downgrade()
            assert card_fields.isdisjoint(column['name'] for column in inspect(connection).get_columns('tariffs'))
            migration.upgrade()
        assert connection.execute(text('SELECT id, name FROM tariffs ORDER BY id')).all() == [
            (9, 'Семейный'),
            (10, 'Базовый'),
        ]
    engine.dispose()
