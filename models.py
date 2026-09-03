from __future__ import annotations

from typing import Optional, List
import datetime
from sqlalchemy import String, Text, Float, Boolean, Date

from sqlalchemy import (
    ForeignKey,
    Table,
    Column,
    UniqueConstraint,
)

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


# Association table: ItemGroup <-> Tag
tag_association = Table(
    "tag_association",
    Base.metadata,
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
    Column("item_group_id", ForeignKey("item_group.id"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Battery(Base):
    __tablename__ = "battery"

    id: Mapped[int] = mapped_column(primary_key=True)
    voltage: Mapped[Optional[float]] = mapped_column(Float)
    current: Mapped[Optional[float]] = mapped_column(Float)
    capacity: Mapped[Optional[float]] = mapped_column(Float)
    charging_type: Mapped[Optional[str]] = mapped_column(String(50))



class ItemGroup(Base):
    __tablename__ = "item_group"

    __table_args__ = (
        UniqueConstraint("name", name="uq_item_group_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    instruction: Mapped[Optional[str]] = mapped_column(Text)

    battery_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("battery.id"),
        nullable=True,
    )
    battery = relationship("Battery")

    items = relationship("Item", back_populates="group")
    tags = relationship("Tag", secondary=tag_association)


class Location(Base):
    __tablename__ = "location"

    __table_args__ = (
        UniqueConstraint("name", name="uq_location_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("location.id"),
        nullable=True,
    )
    parent = relationship("Location", remote_side=[id])

    items = relationship("Item", back_populates="location")
    furniture_maps = relationship("FurnitureMap", back_populates="location")


class FurnitureMap(Base):
    """One photo of a furniture pile (Kallax, drawer unit, ...)."""
    __tablename__ = "furniture_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    location_id: Mapped[int] = mapped_column(ForeignKey("location.id"))
    location = relationship("Location", back_populates="furniture_maps")
    photo_filename: Mapped[str] = mapped_column(String(255))
    mask_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    width: Mapped[int] = mapped_column()
    height: Mapped[int] = mapped_column()
    zones = relationship(
        "FurnitureZone",
        back_populates="map",
        cascade="all, delete-orphan",
    )


class FurnitureZone(Base):
    """Bounding box for one painted color on a mask (#000001, #000002, ...)."""
    __tablename__ = "furniture_zone"

    id: Mapped[int] = mapped_column(primary_key=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("furniture_map.id"))
    map = relationship("FurnitureMap", back_populates="zones")
    color: Mapped[str] = mapped_column(String(7))
    slot: Mapped[int] = mapped_column()
    location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("location.id"),
        nullable=True,
    )
    location = relationship("Location")
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    w: Mapped[float] = mapped_column(Float)
    h: Mapped[float] = mapped_column(Float)
    cx: Mapped[float] = mapped_column(Float)
    cy: Mapped[float] = mapped_column(Float)


class Item(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(primary_key=True)

    last_seen_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    last_use_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    has_dedicated_cable: Mapped[Optional[bool]] = mapped_column(Boolean)
    acquired_date: Mapped[Optional[datetime.date]] = mapped_column(Date)

    bought_place: Mapped[Optional[str]] = mapped_column(String(100))
    variant: Mapped[Optional[str]] = mapped_column(String(100))
    color: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    price: Mapped[Optional[float]] = mapped_column(Float)


    group_id: Mapped[int] = mapped_column(ForeignKey("item_group.id"))
    group = relationship("ItemGroup", back_populates="items")

    location_id: Mapped[int] = mapped_column(ForeignKey("location.id"))
    location = relationship("Location", back_populates="items")
