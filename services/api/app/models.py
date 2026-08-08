"""SQLAlchemy models mirroring supabase/migrations.

These are hand-written on purpose. The SQL migrations are authoritative; if you
change a table there, change it here too. Do not add Alembic.
"""

from __future__ import annotations

import datetime as dt
import enum
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IngestStatus(enum.StrEnum):
    pending = "pending"
    processed = "processed"
    failed = "failed"
    skipped = "skipped"


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    wallet: Mapped[str | None] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IndexedTransaction(Base):
    __tablename__ = "indexed_transactions"

    signature: Mapped[str] = mapped_column(Text, primary_key=True)
    slot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    block_time: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    program_id: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="webhook")
    status: Mapped[IngestStatus] = mapped_column(
        Enum(IngestStatus, name="ingest_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=IngestStatus.pending,
    )
    error: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("indexed_transactions_slot_idx", slot.desc()),)


class CounterEvent(Base):
    __tablename__ = "counter_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    signature: Mapped[str] = mapped_column(
        Text, ForeignKey("indexed_transactions.signature", ondelete="CASCADE"), nullable=False
    )
    counter: Mapped[str] = mapped_column(Text, nullable=False)
    authority: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    slot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    block_time: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("signature", "counter", name="counter_events_signature_counter_key"),
    )


class IndexerCursor(Base):
    __tablename__ = "indexer_cursors"

    program_id: Mapped[str] = mapped_column(Text, primary_key=True)
    last_signature: Mapped[str | None] = mapped_column(Text)
    last_slot: Mapped[int | None] = mapped_column(BigInteger)
    last_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    backfill_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
