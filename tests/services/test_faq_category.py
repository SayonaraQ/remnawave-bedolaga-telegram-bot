"""FAQ topic (category) is stored, kept on partial updates and can be cleared."""

from app.database.models import FaqPage, FaqSetting
from app.services.faq_service import FaqService
from tests.fixtures.sqlite_memory import memory_session


async def test_create_stores_category_and_update_keeps_it_unless_passed(monkeypatch):
    async with memory_session(monkeypatch, [FaqPage.__table__, FaqSetting.__table__]) as db:
        page = await FaqService.create_page(
            db, language='ru', title='Как продлить подписку?', content='<p>a</p>', category='billing'
        )
        assert page.category == 'billing'

        page = await FaqService.update_page(db, page, title='Как продлить?')
        assert page.category == 'billing'

        page = await FaqService.update_page(db, page, category=None)
        assert page.category is None


async def test_create_without_category_stores_null(monkeypatch):
    async with memory_session(monkeypatch, [FaqPage.__table__, FaqSetting.__table__]) as db:
        page = await FaqService.create_page(db, language='ru', title='Q', content='<p>a</p>')
        assert page.category is None
