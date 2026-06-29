from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import CheckConstraint, DateTime, Double, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from openclassrooms_projet5.db.base import Base


class PredictionLog(Base):
    __tablename__ = "prediction_logs"
    __table_args__ = (
        CheckConstraint(
            "prediction_attrition IN (0, 1)",
            name="ck_prediction_logs_prediction_attrition_binary",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    probabilite_attrition: Mapped[float] = mapped_column(Double, nullable=False)
    prediction_attrition: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    threshold: Mapped[float] = mapped_column(Double, nullable=False)
    model_identifier: Mapped[str | None] = mapped_column(Text, nullable=True)
