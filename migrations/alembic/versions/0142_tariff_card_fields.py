"""Card fields for cabinet tariffs.

Revision ID: 0142
Revises: 0141
"""

import sqlalchemy as sa
from alembic import op


revision = '0142'
down_revision = '0141'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tariffs', sa.Column('tagline', sa.String(160), nullable=True))
    op.add_column('tariffs', sa.Column('speed_limit_mbps', sa.Integer(), nullable=True))
    op.add_column('tariffs', sa.Column('has_premium_servers', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    with op.batch_alter_table('tariffs') as batch:
        batch.drop_column('has_premium_servers')
        batch.drop_column('speed_limit_mbps')
        batch.drop_column('tagline')
