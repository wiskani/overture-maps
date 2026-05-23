"""SQLAlchemy ORM models for the reference schema."""

from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Place(Base):
    __tablename__ = "places"
    __table_args__ = {"schema": "reference"}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    geom = mapped_column(Geometry("POINT", srid=4326))
    raw: Mapped[dict | None] = mapped_column(JSONB)


class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = {"schema": "reference"}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    number: Mapped[str | None] = mapped_column(Text)
    street: Mapped[str | None] = mapped_column(Text)
    postcode: Mapped[str | None] = mapped_column(Text)
    locality: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    geom = mapped_column(Geometry("POINT", srid=4326))
    raw: Mapped[dict | None] = mapped_column(JSONB)


class Division(Base):
    __tablename__ = "divisions"
    __table_args__ = {"schema": "reference"}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    division_type: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    geom = mapped_column(Geometry("GEOMETRY", srid=4326))
    raw: Mapped[dict | None] = mapped_column(JSONB)


class TransportationSegment(Base):
    __tablename__ = "transportation_segments"
    __table_args__ = {"schema": "reference"}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    road_class: Mapped[str | None] = mapped_column(Text)
    geom = mapped_column(Geometry("LINESTRING", srid=4326))
    raw: Mapped[dict | None] = mapped_column(JSONB)


class TransportationConnector(Base):
    __tablename__ = "transportation_connectors"
    __table_args__ = {"schema": "reference"}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    geom = mapped_column(Geometry("POINT", srid=4326))
    raw: Mapped[dict | None] = mapped_column(JSONB)


class SchemaMeta(Base):
    __tablename__ = "schema_meta"
    __table_args__ = {"schema": "reference"}

    theme: Mapped[str] = mapped_column(Text, primary_key=True)
    data_release: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(Text)
    columns: Mapped[dict | None] = mapped_column(JSONB)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    load_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
