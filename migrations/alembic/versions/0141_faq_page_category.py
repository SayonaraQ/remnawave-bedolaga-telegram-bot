"""Topic (category) of a bot FAQ page — the cabinet help center groups questions by it.

Revision ID: 0141
Revises: 0140
"""

import sqlalchemy as sa
from alembic import op


revision = '0141'
down_revision = '0140'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('faq_pages', sa.Column('category', sa.String(32), nullable=True))


def downgrade():
    with op.batch_alter_table('faq_pages') as batch:
        batch.drop_column('category')
