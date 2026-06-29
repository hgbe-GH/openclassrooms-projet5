"""Create prediction_logs table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260507_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prediction_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("probabilite_attrition", sa.Double(), nullable=False),
        sa.Column("prediction_attrition", sa.SmallInteger(), nullable=False),
        sa.Column("threshold", sa.Double(), nullable=False),
        sa.Column("model_identifier", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "prediction_attrition IN (0, 1)",
            name="ck_prediction_logs_prediction_attrition_binary",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("prediction_logs")
