from flask import Flask, jsonify, request, render_template, send_from_directory # do not import return abort!!!!!!!
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from db import engine, SessionLocal
import os
from datetime import date, datetime
from models import (
    Base,
    Item,
    ItemGroup,
    Tag,
    Location,
    Battery,
    tag_association,
)

app = Flask(__name__)
Base.metadata.create_all(engine)

def abort(resp_status, message): # this one sends JSON instead of HTML
    return {"error": message}, resp_status

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "Hatsune-Miku.ico",
        mimetype="image/vnd.microsoft.icon",
    )


# --------------------
# SEARCH (autocomplete)
# --------------------
def search_by_name(model, q, label_fn=lambda x: x.name, limit=10):
    if not q:
        return []

    with SessionLocal() as s:
        results = (
            s.query(model)
            .filter(model.name.ilike(f"%{q}%"))
            .order_by(model.name)
            .limit(limit)
            .all()
        )
        return [{"id": r.id, "label": label_fn(r)} for r in results]

def location_helper_func(loc: Location) -> str:
    parts = []
    current = loc
    while current:
        parts.append(current.name)
        current = current.parent
    return " > ".join(reversed(parts))

@app.route("/api/tags/search")
def search_tags():
    return jsonify(search_by_name(Tag, request.args.get("q", "")))

@app.route("/api/item-group/search")
def search_item_groups():
    return jsonify(search_by_name(ItemGroup, request.args.get("q", "")))

@app.route("/api/locations/search")
def search_locations():
    return jsonify(search_by_name(
        Location,
        request.args.get("q", ""),
        label_fn=location_helper_func,
    ))
    
def iso(d):
    return d.isoformat() if d else None


def battery_to_dict(b):
    if not b:
        return None
    return {
        "voltage": b.voltage,
        "current": b.current,
        "capacity": b.capacity,
        "charging_type": b.charging_type,
    }


def item_to_dict(i: Item):
    return {
        "id": i.id,
        "group": i.group.name,
        "instruction": i.group.instruction,
        "battery": battery_to_dict(i.group.battery),
        "tags": [t.name for t in i.group.tags],
        "location": location_helper_func(i.location),
        "last_seen": iso(i.last_seen_date),
        "last_charge": iso(i.last_charge_date),
        "acquired": iso(i.acquired_date),
        "has_cable": i.has_dedicated_cable,
        "bought_place": i.bought_place,
        "price": i.price,
    }

@app.route("/api/items/search-by-tag")
def search_items():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    with SessionLocal() as s:
        items = (
            s.query(Item)
            .join(Item.group)
            .join(tag_association)
            .join(Tag)
            .filter(func.lower(Tag.name) == q.lower())
            .limit(50)
            .all()
        )

        return jsonify([item_to_dict(i) for i in items])

# --------------------
# CREATE
# --------------------

def parse_date(value: str) -> date | None:
    if not value:
        return None
    # Try YYYY-MM-DD
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    # Try DD/MM/YYYY
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        pass
    # Try DD-MM-YYYY
    try:
        return datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError:
        return None
    
ITEM_FIELDS = {
    "last_seen_date": parse_date,
    "last_charge_date": parse_date,
    "has_dedicated_cable": bool,
    "acquired_date": parse_date,
    "price": lambda x: x,
}

def apply_item_fields(item, data):
    for field, cast in ITEM_FIELDS.items():
        setattr(item, field, cast(data.get(field)))
    item.bought_place = (data.get("bought_place") or "").strip() or None


@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.json or {}

    group_name = (data.get("group") or "").strip()
    location_name = (data.get("location") or "").strip()

    if not group_name or not location_name:
        return abort(400, "Item Group and Location are required")

    with SessionLocal() as s:
        group = s.query(ItemGroup).filter(ItemGroup.name.ilike(group_name)).one_or_none()
        if not group:
            return abort(400, f"Item Group '{group_name}' not found")

        location_name = location_name.rsplit(">", 1)[-1].strip()
        location = s.query(Location).filter(Location.name.ilike(location_name)).one_or_none()
        if not location:
            return abort(400, f"Location '{location_name}' not found")

        item = s.get(Item, data.get("id")) if data.get("id") else Item()
        if not item:
            return abort(404, "Item not found")

        item.group_id = group.id
        item.location_id = location.id
        apply_item_fields(item, data)

        s.add(item)
        s.commit()

        return {"id": item.id}, 200 if data.get("id") else 201

@app.route("/api/locations", methods=["POST"])
def create_location():
    data = request.json or {}

    name = (data.get("name") or "").rsplit(">", 1)[-1].strip()
    parent_name = data.get("parent")

    if not name:
        return abort(400, "Location name cannot be empty")

    with SessionLocal() as s:
        parent = (
            s.query(Location)
            .filter(Location.name.ilike(parent_name))
            .one_or_none()
            if parent_name else None
        )

        existing = (
            s.query(Location)
            .filter(Location.name.ilike(name), Location.parent_id == (parent.id if parent else None))
            .one_or_none()
        )
        if existing:
            return {"id": existing.id, "name": existing.name}, 200

        loc = Location(name=name, parent=parent)
        s.add(loc)
        s.commit()

        return {"id": loc.id, "name": loc.name}, 201


def get_or_create_battery(s, **fields):
    if not any(fields.values()):
        return None

    battery = s.query(Battery).filter_by(**fields).one_or_none()
    if battery:
        return battery

    battery = Battery(**fields)
    s.add(battery)
    s.flush()
    return battery


def get_or_create_tags(s, names):
    tags = []
    for name in names:
        name = (name or "").strip()
        if not name:
            continue

        tag = (
            s.query(Tag)
            .filter(func.lower(Tag.name) == name.lower())
            .one_or_none()
        )
        if not tag:
            tag = Tag(name=name)
            s.add(tag)
            s.flush()

        tags.append(tag)
    return tags

@app.route("/api/item-group", methods=["POST"])
def create_item_group():
    data = request.json or {}

    name = (data.get("name") or "").strip()
    if not name:
        return abort(400, "Item group name is required")

    with SessionLocal() as s:
        item_group = s.get(ItemGroup, data.get("id"))

        battery = get_or_create_battery(
            s,
            voltage=data.get("voltage"),
            current=data.get("current"),
            capacity=data.get("capacity"),
            charging_type=data.get("charging_type"),
        )

        tags = get_or_create_tags(s, data.get("tags", []))

        if not item_group:
            item_group = ItemGroup()

        item_group.name = name
        item_group.instruction = data.get("instruction")
        item_group.battery = battery
        item_group.tags = tags

        s.add(item_group)
        s.commit()

        return {
            "id": item_group.id,
            "updated": bool(data.get("id")),
        }, 200 if data.get("id") else 201

if __name__ == "__main__":
    app.run(debug=True)
