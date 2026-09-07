"""Store shared site settings in the database."""

from alembic import op
import sqlalchemy as sa

revision = "6e862f28b037"
down_revision = "8e79605fd37a"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("site_setting"):
        op.create_table(
            "site_setting",
            sa.Column("key", sa.String(128), primary_key=True),
            sa.Column("value", sa.String(256), nullable=False),
        )


def downgrade():
    op.drop_table("site_setting")
