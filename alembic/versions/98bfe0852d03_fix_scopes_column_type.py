"""Fix scopes column type

Revision ID: 98bfe0852d03
Revises: c8dca5bf3198
Create Date: 2025-09-24 21:45:01.238462

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '98bfe0852d03'
down_revision = 'c8dca5bf3198'
branch_labels = None
depends_on = None


def upgrade():
    # Change scopes column from character varying[] to JSONB
    # First convert array to JSON string, then to JSONB
    op.execute('ALTER TABLE api_tokens ALTER COLUMN scopes TYPE JSONB USING array_to_json(scopes)::JSONB')


def downgrade():
    # Change scopes column back to character varying[]
    op.execute('ALTER TABLE api_tokens ALTER COLUMN scopes TYPE character varying[] USING scopes::character varying[]')
