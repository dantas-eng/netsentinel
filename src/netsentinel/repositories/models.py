"""Schema compartilhado SQLite/Postgres; alterações são feitas via Alembic."""
from sqlalchemy import JSON, Float, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = 'devices'
    mac: Mapped[str] = mapped_column(String(17), primary_key=True)
    reputation: Mapped[str] = mapped_column(String(16), nullable=False, default='new')
    first_seen: Mapped[float | None] = mapped_column(Float)
    last_seen: Mapped[float | None] = mapped_column(Float)
    risk: Mapped[dict | None] = mapped_column(JSON)


class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[str] = mapped_column(ForeignKey('devices.mac'), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)


class Calibration(Base):
    __tablename__ = 'calibrations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[str] = mapped_column(ForeignKey('devices.mac'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    last_end: Mapped[float] = mapped_column(Float, nullable=False)
    samples: Mapped[list] = mapped_column(JSON, nullable=False)
    started_at: Mapped[float] = mapped_column(Float, nullable=False)
    completed_at: Mapped[float | None] = mapped_column(Float)


class Baseline(Base):
    __tablename__ = 'baselines'
    mac: Mapped[str] = mapped_column(ForeignKey('devices.mac'), primary_key=True)
    bytes_per_second: Mapped[float | None] = mapped_column(Float)
    calibration_id: Mapped[int] = mapped_column(ForeignKey('calibrations.id'), nullable=False)
    calibrated_at: Mapped[float] = mapped_column(Float, nullable=False)


class StoredEvent(Base):
    __tablename__ = 'events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class LatestSnapshot(Base):
    __tablename__ = 'latest_snapshot'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class ArpFrame(Base):
    __tablename__ = 'arp_frames'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    captured_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    capture_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    eth_src: Mapped[str] = mapped_column(String(17), nullable=False, index=True)
    eth_dst: Mapped[str] = mapped_column(String(17), nullable=False)
    opcode: Mapped[int] = mapped_column(Integer, nullable=False)
    sender_mac: Mapped[str] = mapped_column(String(17), nullable=False)
    sender_ip: Mapped[str] = mapped_column(String(15), nullable=False, index=True)
    target_mac: Mapped[str] = mapped_column(String(17), nullable=False)
    target_ip: Mapped[str] = mapped_column(String(15), nullable=False)
    raw: Mapped[bytes] = mapped_column(LargeBinary(128), nullable=False)
