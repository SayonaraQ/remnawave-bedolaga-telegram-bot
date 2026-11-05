import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def _columns(connection) -> set[str]:
    return {column['name'] for column in inspect(connection).get_columns('faq_pages')}


def test_faq_category_sqlite_upgrade_downgrade_keeps_rows():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(
            text(
                'CREATE TABLE faq_pages (id INTEGER PRIMARY KEY, language VARCHAR(10) NOT NULL, '
                'title VARCHAR(255) NOT NULL, content TEXT NOT NULL, display_order INTEGER NOT NULL, '
                'is_active BOOLEAN NOT NULL)'
            )
        )
        connection.execute(
            text(
                'INSERT INTO faq_pages (id, language, title, content, display_order, is_active) '
                "VALUES (9, 'ru', 'Что делать, если VPN не работает?', '<p>x</p>', 5, 1)"
            )
        )
        migration = importlib.import_module('migrations.alembic.versions.0141_faq_page_category')
        assert migration.down_revision == '0140'
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert 'category' in _columns(connection)
            assert connection.scalar(text('SELECT category FROM faq_pages WHERE id = 9')) is None
            migration.downgrade()
            assert 'category' not in _columns(connection)
            migration.upgrade()
        assert (
            connection.scalar(text('SELECT title FROM faq_pages WHERE id = 9')) == 'Что делать, если VPN не работает?'
        )
    engine.dispose()
