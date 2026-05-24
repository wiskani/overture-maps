"""SQLAlchemy ORM models — exact mirror of the Overture Maps schema."""

from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Double, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Place(Base):
    __tablename__ = "places"
    __table_args__ = (
        Index(None, "basic_category"),
        Index(None, "names", postgresql_using="gin"),
        {"schema": "reference"},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Double)
    operating_status: Mapped[str | None] = mapped_column(Text)
    basic_category: Mapped[str | None] = mapped_column(Text)
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    sources: Mapped[list | None] = mapped_column(JSONB)
    names: Mapped[dict | None] = mapped_column(JSONB)
    categories: Mapped[dict | None] = mapped_column(JSONB)
    taxonomy: Mapped[dict | None] = mapped_column(JSONB)
    websites: Mapped[list | None] = mapped_column(JSONB)
    emails: Mapped[list | None] = mapped_column(JSONB)
    socials: Mapped[list | None] = mapped_column(JSONB)
    phones: Mapped[list | None] = mapped_column(JSONB)
    brand: Mapped[dict | None] = mapped_column(JSONB)
    addresses: Mapped[list | None] = mapped_column(JSONB)
    geom = mapped_column(Geometry("POINT", srid=4326))


class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = (
        Index(None, "street"),
        Index(None, "postcode"),
        Index(None, "country"),
        {"schema": "reference"},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[int | None] = mapped_column(Integer)
    country: Mapped[str | None] = mapped_column(Text)
    number: Mapped[str | None] = mapped_column(Text)
    postal_city: Mapped[str | None] = mapped_column(Text)
    postcode: Mapped[str | None] = mapped_column(Text)
    street: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(Text)
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    sources: Mapped[list | None] = mapped_column(JSONB)
    address_levels: Mapped[list | None] = mapped_column(JSONB)
    geom = mapped_column(Geometry("POINT", srid=4326))


class Division(Base):
    """Stores division_area features (polygon/multipolygon)."""

    __tablename__ = "divisions"
    __table_args__ = (
        Index(None, "subtype"),
        Index(None, "country"),
        Index(None, "names", postgresql_using="gin"),
        {"schema": "reference"},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[int | None] = mapped_column(Integer)
    subtype: Mapped[str | None] = mapped_column(Text)
    # 'class' is a SQL reserved word; mapped to the correct column name
    division_class: Mapped[str | None] = mapped_column("class", Text)
    is_land: Mapped[bool | None] = mapped_column(Boolean)
    is_territorial: Mapped[bool | None] = mapped_column(Boolean)
    division_id: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    admin_level: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    sources: Mapped[list | None] = mapped_column(JSONB)
    names: Mapped[dict | None] = mapped_column(JSONB)
    geom = mapped_column(Geometry("GEOMETRY", srid=4326))


class TransportationSegment(Base):
    __tablename__ = "transportation_segments"
    __table_args__ = (
        Index(None, "subtype"),
        Index(None, "class"),
        Index(None, "names", postgresql_using="gin"),
        {"schema": "reference"},
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[int | None] = mapped_column(Integer)
    subtype: Mapped[str | None] = mapped_column(Text)
    # 'class' is a SQL reserved word; mapped to the correct column name
    road_class: Mapped[str | None] = mapped_column("class", Text)
    subclass: Mapped[str | None] = mapped_column(Text)
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    sources: Mapped[list | None] = mapped_column(JSONB)
    names: Mapped[dict | None] = mapped_column(JSONB)
    subclass_rules: Mapped[list | None] = mapped_column(JSONB)
    connectors: Mapped[list | None] = mapped_column(JSONB)
    road_surface: Mapped[list | None] = mapped_column(JSONB)
    road_flags: Mapped[list | None] = mapped_column(JSONB)
    rail_flags: Mapped[list | None] = mapped_column(JSONB)
    width_rules: Mapped[list | None] = mapped_column(JSONB)
    level_rules: Mapped[list | None] = mapped_column(JSONB)
    access_restrictions: Mapped[list | None] = mapped_column(JSONB)
    speed_limits: Mapped[list | None] = mapped_column(JSONB)
    prohibited_transitions: Mapped[list | None] = mapped_column(JSONB)
    routes: Mapped[list | None] = mapped_column(JSONB)
    destinations: Mapped[list | None] = mapped_column(JSONB)
    geom = mapped_column(Geometry("LINESTRING", srid=4326))


class TransportationConnector(Base):
    __tablename__ = "transportation_connectors"
    __table_args__ = {"schema": "reference"}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    sources: Mapped[list | None] = mapped_column(JSONB)
    geom = mapped_column(Geometry("POINT", srid=4326))


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
