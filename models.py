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


class Item(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(primary_key=True)

    last_seen_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    last_charge_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    has_dedicated_cable: Mapped[Optional[bool]] = mapped_column(Boolean)
    acquired_date: Mapped[Optional[datetime.date]] = mapped_column(Date)

    bought_place: Mapped[Optional[str]] = mapped_column(String(100))
    variant: Mapped[Optional[str]] = mapped_column(String(100))
    color: Mapped[Optional[str]] = mapped_column(String(50))
    price: Mapped[Optional[float]] = mapped_column(Float)


    group_id: Mapped[int] = mapped_column(ForeignKey("item_group.id"))
    group = relationship("ItemGroup", back_populates="items")

    location_id: Mapped[int] = mapped_column(ForeignKey("location.id"))
    location = relationship("Location", back_populates="items")
