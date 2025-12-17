from __future__ import annotations

from typing import Optional, List
import datetime

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


# Association table: ItemType <-> Tag
tag_association = Table(
    "tag_association",
    Base.metadata,
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
    Column("item_type_id", ForeignKey("item_type.id"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class Battery(Base):
    __tablename__ = "battery"

    id: Mapped[int] = mapped_column(primary_key=True)
    voltage: Mapped[float]
    current: Mapped[float]
    capacity: Mapped[float]
    charging_type: Mapped[str]


class ItemType(Base):
    __tablename__ = "item_type"
    
    __table_args__ = (
        UniqueConstraint("name", name="uq_item_type_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    instruction: Mapped[Optional[str]]

    battery_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("battery.id"),
        nullable=True,
    )
    battery = relationship("Battery")

    items = relationship("Item", back_populates="type")
    tags = relationship("Tag", secondary=tag_association)


class Location(Base):
    __tablename__ = "location"
    
    __table_args__ = (
        UniqueConstraint("name", "parent_id", name="uq_location_name_parent"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("location.id"),
        nullable=True,
    )
    parent = relationship("Location", remote_side=[id])

    items = relationship("Item", back_populates="location")


class Item(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(primary_key=True)

    last_seen_date: Mapped[Optional[datetime.date]]
    last_charge_date: Mapped[Optional[datetime.date]]
    has_dedicated_cable: Mapped[Optional[bool]]
    acquired_date: Mapped[Optional[datetime.date]]
    bought_place: Mapped[Optional[str]]
    price: Mapped[Optional[float]]

    type_id: Mapped[int] = mapped_column(ForeignKey("item_type.id"))
    type = relationship("ItemType", back_populates="items")

    location_id: Mapped[int] = mapped_column(ForeignKey("location.id"))
    location = relationship("Location", back_populates="items")
