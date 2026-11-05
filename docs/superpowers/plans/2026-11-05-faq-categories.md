# FAQ categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** give every bot FAQ page an optional topic (`category`) that the cabinet help center groups questions by.

**Architecture:** one nullable column on `faq_pages`, carried through CRUD, `FaqService`, the public `/cabinet/info/faq` response and the cabinet admin editors. The bot's own Telegram menu stays a flat list (already ordered by topic through `display_order`).

**Tech Stack:** SQLAlchemy 2 async, Alembic, FastAPI/Pydantic v2, pytest (sqlite memory + optional postgres).

**Spec:** owner-approved design canvas https://claude.ai/artifact/DkFjsKd4H2ffEMd5aeH3ua (page «Справка: A+B на живом FAQ», sheet «Структура FAQ»); cabinet side — `bedolaga-cabinet/docs/superpowers/plans/2026-11-05-help-center.md`.

## Global Constraints

- Column: `faq_pages.category VARCHAR(32) NULL`, migration revision `0141`, down_revision `0140`.
- Allowed value: `None` or matching `^[a-z][a-z0-9_-]{0,31}$`. No fixed enum in the bot — the cabinet owns labels; unknown keys show as «Другое».
- Keys used on prod (cabinet constants): `connect`, `trouble`, `services`, `devices`, `whitelist`, `billing`, `support`.
- Existing calls that do not pass `category` must keep the stored value (update) / store `NULL` (create).
- Commits without AI attribution trailers.

## Review Focus

- Admin legacy PUT without `category` in the body (old cabinet build still deployed) must not wipe the stored topic → test in Task 1.
- Explicit `"category": null` in legacy PUT must clear it → test in Task 1.
- Invalid key (`"Оплата"`, upper case, 40 chars) → 422, nothing written → test in Task 2.
- Migration on sqlite (tests) and postgres (prod) up/down/up keeps existing rows → test in Task 1.
- Public FAQ for a language with fallback still returns `category` → covered by Task 2 public GET assertion.

---

### Task 1: Column, migration, CRUD and service

**Files:**
- Create: `migrations/alembic/versions/0141_faq_page_category.py`
- Modify: `app/database/models.py` (`FaqPage`), `app/database/crud/faq.py` (`create_faq_page`, `update_faq_page`), `app/services/faq_service.py` (`create_page`, `update_page`)
- Test: `tests/migrations/test_0141_faq_category.py`, `tests/services/test_faq_category.py`

**Interfaces:**
- Produces: `FaqPage.category: str | None`; `create_faq_page(..., category: str | None = None)`; `update_faq_page(..., category: str | None | object = UNSET)` where `UNSET` is a module-level sentinel in `app/database/crud/faq.py`; same keywords on `FaqService.create_page` / `FaqService.update_page` (default `UNSET` re-exported from crud).

- [ ] **Step 1: failing tests**
  - `test_0141_faq_category.py::test_faq_category_sqlite_upgrade_downgrade_keeps_rows` — create `faq_pages(id, language, title, content, display_order, is_active)` with one row, run `upgrade()` → column `category` present and row intact, `downgrade()` → column gone, `upgrade()` again.
  - `test_faq_category.py` (memory_session with `FaqPage`, `FaqSetting`): `create_page(category='billing')` stores it; `update_page(page, title='x')` keeps `'billing'`; `update_page(page, category=None)` clears it.
- [ ] **Step 2:** `uv run pytest tests/migrations/test_0141_faq_category.py tests/services/test_faq_category.py -q` → FAIL.
- [ ] **Step 3:** implement (migration `op.add_column('faq_pages', sa.Column('category', sa.String(32), nullable=True))` / `op.drop_column`; sqlite downgrade via `batch_alter_table`).
- [ ] **Step 4:** same command → PASS.
- [ ] **Step 5:** commit `feat(faq): тема у вопроса FAQ (миграция 0141)`.

### Task 2: API schemas — public FAQ and cabinet admin editors

**Files:**
- Modify: `app/cabinet/routes/info.py` (`FaqPageResponse` + both FAQ routes), `app/cabinet/schemas/info_pages.py` (`LegacyFaqResponse`, `LegacyFaqUpdateRequest`), `app/cabinet/routes/admin_info_pages.py` (`update_legacy_faq` — pass `category` only when present in the request: `request.model_dump(exclude_unset=True)` for that key), `app/cabinet/routes/admin_legal_pages.py` (`FaqPageItem`, `FaqPageCreateRequest`, `FaqPageUpdateRequest`, `_faq_page_item`, create/update routes)
- Test: `tests/cabinet/test_legacy_faq_admin.py` (extend `check_legacy_faq`), `tests/cabinet/test_admin_legal_pages_routes.py`

**Interfaces:**
- Consumes: Task 1 keywords.
- Produces: JSON field `category: string | null` on `GET /cabinet/info/faq`, `GET /cabinet/info/faq/{id}`, `GET/PUT /cabinet/admin/info-pages/legacy-faq[/{id}]`, admin legal FAQ page items. `LegacyFaqUpdateRequest.category: str | None = Field(None, pattern=r'^[a-z][a-z0-9_-]{0,31}$')`.

- [ ] **Step 1: failing tests** in `check_legacy_faq`: PUT with `category: 'trouble'` → response and public GET item have `category == 'trouble'`; PUT without the key keeps `'trouble'`; PUT with `category: None` → `None`; PUT with `category: 'Оплата'` → 422 and stored value unchanged.
- [ ] **Step 2:** `uv run pytest tests/cabinet/test_legacy_faq_admin.py tests/cabinet/test_admin_legal_pages_routes.py tests/cabinet/test_info_display_mode_gating.py -q` → new assertions FAIL.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** same command → PASS; plus `uv run python -m scripts.generate_structure_reference && uv run pytest tests/test_structure_reference_is_current.py -q` → PASS.
- [ ] **Step 5:** commit `feat(cabinet): тема вопроса FAQ в публичной выдаче и админке`.

### Rollout (after owner's «разрешаю»)

1. Bot image rebuild + `COMPOSE_FILE=docker-compose.local.yml docker compose up -d bot` (migration runs on start); backup dir `panel_fr:/opt/rw-backup-restore/backup/pre_faqcat_<ts>/` with DB dump + previous image tag.
2. One SQL transaction setting `category` for the 36 active pages (ids per the canvas structure sheet).
3. Rollback: retag previous image + `alembic downgrade 0140` is not required (nullable column is harmless to old code).
