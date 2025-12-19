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

def abort(resp_status, message): # flask moment
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
# META
# --------------------

@app.route("/api/meta")
def meta():
    with SessionLocal() as s:
        return jsonify({
            "types": [
                {"id": t.id, "name": t.name}
                for t in s.query(ItemGroup)
            ],
            "batteries": [
                {
                    "id": b.id,
                    "label": f"{b.voltage}V {b.capacity}mAh",
                    "charging_type": b.charging_type,
                }
                for b in s.query(Battery)
            ],
        })



# --------------------
# SEARCH (autocomplete)
# --------------------

@app.route("/api/tags/search")
def search_tags():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    with SessionLocal() as s:
        results = (
            s.query(Tag)
            .filter(Tag.name.ilike(f"%{q}%"))
            .order_by(Tag.name)
            .limit(10)
            .all()
        )

        return jsonify([{"id": t.id, "label": t.name} for t in results])

def location_helper_func(loc: Location) -> str:
    parts = []
    current = loc
    while current:
        parts.append(current.name)
        current = current.parent
    return " > ".join(reversed(parts))

@app.route("/api/items/search-by-tag")
def search_items():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    with SessionLocal() as s:
        items = (
        s.query(Item)
        .join(ItemGroup, Item.group)
        .join(tag_association, ItemGroup.id == tag_association.c.item_group_id)
        .join(Tag, Tag.id == tag_association.c.tag_id)
        .filter(func.lower(Tag.name) == q.lower())
        .limit(50)
        .all()
        )
        return jsonify([
            {
                "id": i.id,
                "group": i.group.name,
                "instruction": i.group.instruction,
                "battery": (
                    {
                        "voltage": i.group.battery.voltage,
                        "current": i.group.battery.current,
                        "capacity": i.group.battery.capacity,
                        "charging_type": i.group.battery.charging_type,
                    }
                    if i.group.battery else None
                ),
                "tags": [t.name for t in i.group.tags],
                "location": location_helper_func(i.location),
                "last_seen": i.last_seen_date.isoformat() if i.last_seen_date else None,
                "last_charge": i.last_charge_date.isoformat() if i.last_charge_date else None,
                "acquired": i.acquired_date.isoformat() if i.acquired_date else None,
                "has_cable": i.has_dedicated_cable,
                "bought_place": i.bought_place,
                "price": i.price,
            }
            for i in items
        ])

@app.route("/api/tags")
def get_all_tags():
    with SessionLocal() as s:
        results = s.query(Tag).order_by(Tag.name).all()
        return jsonify([{"id": t.id, "name": t.name} for t in results])

@app.route("/api/tags2")
def get_all_tags2():
    with SessionLocal() as s:
        results = s.query(Tag).filter(func.lower(Tag.name) == "Lovense".lower()).all()
        return jsonify([{"id": t.id, "name": t.name} for t in results])


"""
@app.route("/api/locations/search") # this ver doesn't care about parent
def search_locations():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    with SessionLocal() as s:
        results = (
            s.query(Location)
            .filter(Location.name.ilike(f"%{q}%"))
            .order_by(Location.name)
            .limit(10)
            .all()
        )
        return jsonify([{"id": l.id, "label": l.name} for l in results])
"""

@app.route("/api/locations/search") # this ver also show parents
def search_locations():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    with SessionLocal() as s:
        results = (
            s.query(Location)
            .filter(Location.name.ilike(f"%{q}%"))
            .order_by(Location.name)
            .limit(10)
            .all()
        )
        for loc in results:
            print(location_helper_func(loc))
        return jsonify([
            {
                "id": loc.id,
                "label": location_helper_func(loc)
            }
            for loc in results
        ])


@app.route("/api/item-group/search")
def search_item_groups():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    with SessionLocal() as s:
        results = (
            s.query(ItemGroup)
            .filter(ItemGroup.name.ilike(f"%{q}%"))
            .order_by(ItemGroup.name)
            .limit(10)
            .all()
        )
        return jsonify([{"id": it.id, "label": it.name} for it in results])


# --------------------
# CREATE
# --------------------

"""@app.route("/api/tags", methods=["POST"])
def create_tag():
    name = request.json["name"].strip()
    with SessionLocal() as s:
        existing = s.execute(
            select(Tag).where(Tag.name.ilike(name))
        ).scalar_one_or_none()
        if existing:
            return {"id": existing.id, "name": existing.name}

        tag = Tag(name=name)
        s.add(tag)
        s.commit()
        return {"id": tag.id, "name": tag.name}"""

"""
@app.route("/api/locations", methods=["POST"])
def create_location():
    data = request.json
    with SessionLocal() as s:
        loc = Location(
            name=data["name"],
            parent_id=data.get("parent_id"),
        )
        s.add(loc)
        s.commit()
        return {"id": loc.id, "name": loc.name}

"""

@app.route("/api/locations", methods=["POST"])
def create_location():
    data = request.json or {}

    name = (data.get("name") or "").rsplit('>', 1)[-1].strip()
    parent = data.get("parent")

    if not name:
        return abort(400, "Location name cannot be empty")

    with SessionLocal() as s:
        if type(parent) == type(None): # python moment
            parent_id = None
        else:
            # check if parent exists
            parent_location_obj = s.query(Location).filter(Location.name.ilike(parent)).one_or_none()
            if type(parent_location_obj) == type(None): # python moment
                parent_id = None
            else:
                parent_id = parent_location_obj.id

        existing = (  # check duplicate
            s.query(Location)
            .filter(
                Location.name.ilike(name),
                Location.parent_id == parent_id
            )
            .one_or_none()
        )

        if existing:
            return {"id": existing.id, "name": existing.name}, 200

        loc = Location(
            name=name,
            parent_id=parent_id,
        )
        s.add(loc)
        s.commit()

        return {"id": loc.id, "name": loc.name}, 201


def parse_date(value: str) -> date | None:
    if not value:
        return None
    # Try ISO first
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    # Try DD/MM/YYYY
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        return None


@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.json or {}

    group_name = (data.get("group") or "").strip()
    location_name = (data.get("location") or "").strip()

    if not group_name or not location_name:
        return abort(400, "Item Group and Location are required")

    itemID = data.get("id")

    with SessionLocal() as s:
        group_obj = (
            s.query(ItemGroup)
            .filter(ItemGroup.name.ilike(group_name))
            .one_or_none()
        )
        if not group_obj:
            return abort(400, f"Item Group '{group_name}' not found")

        # Resolve Location
        location_name = location_name.rsplit(">", 1)[-1].strip()
        location_obj = (
            s.query(Location)
            .filter(Location.name.ilike(location_name))
            .one_or_none()
        )
        if location_obj is None:
            return abort(400, f"Location '{location_name}' not found")

        if itemID is not None:
            # Updating existing item
            item = s.query(Item).get(itemID)
            if not item:
                return abort(404, f"Item with id {itemID} not found")

            item.group_id = group_obj.id
            item.location_id = location_obj.id
            item.last_seen_date = parse_date(data.get("last_seen_date"))
            item.last_charge_date = parse_date(data.get("last_charge_date"))
            item.has_dedicated_cable = bool(data.get("has_dedicated_cable"))
            item.acquired_date = parse_date(data.get("acquired_date"))
            item.bought_place = (data.get("bought_place") or "").strip() or None
            item.price = data.get("price")

            s.commit()
            return {"id": item.id}, 200

        # Create Item
        item = Item(
            group_id=group_obj.id,
            location_id=location_obj.id,
            last_seen_date=parse_date(data.get("last_seen_date")),
            last_charge_date=parse_date(data.get("last_charge_date")),
            has_dedicated_cable=bool(data.get("has_dedicated_cable")),
            acquired_date=parse_date(data.get("acquired_date")),
            bought_place=(data.get("bought_place") or "").strip() or None,
            price=data.get("price"),
        )

        s.add(item)
        s.commit()

        return {"id": item.id}, 201



@app.route("/api/item-group", methods=["POST"])
def create_item_group():
    data = request.json or {}

    name = (data.get("name") or "").strip()
    if not name:
        return abort(400, "Item group name is required")

    tags_payload = data.get("tags", [])

    voltage = data.get("voltage")
    current = data.get("current")
    capacity = data.get("capacity")
    charging_type = data.get("charging_type")
    item_group_id = data.get("id")

    with SessionLocal() as s:
        # ---------------------------------
        # Load existing ItemGroup (update mode)
        # ---------------------------------
        item_group = None
        if item_group_id is not None:
            item_group = (
                s.query(ItemGroup)
                .filter_by(id=item_group_id)
                .one_or_none()
            )

        # ---------------------------------
        # Battery: create ONLY if not all null
        # ---------------------------------
        battery = None
        if any(v is not None for v in (voltage, current, capacity, charging_type)):
            battery = (
                s.query(Battery)
                .filter_by(
                    voltage=voltage,
                    current=current,
                    capacity=capacity,
                    charging_type=charging_type,
                )
                .one_or_none()
            )

            if battery is None:
                battery = Battery(
                    voltage=voltage,
                    current=current,
                    capacity=capacity,
                    charging_type=charging_type,
                )
                s.add(battery)
                s.flush()

        # ---------------------------------
        # Tags: get or create (GLOBAL tags)
        # ---------------------------------
        tags: list[Tag] = []

        for raw_name in tags_payload:
            tag_name = (raw_name or "").strip()
            if not tag_name:
                continue

            tag = (
                s.query(Tag)
                .filter(func.lower(Tag.name) == tag_name.lower())
                .one_or_none()
            )

            if tag is None:
                tag = Tag(name=tag_name)
                s.add(tag)
                s.flush()

            tags.append(tag)

        # ---------------------------------
        # UPDATE existing ItemGroup
        # ---------------------------------
        if item_group is not None:
            item_group.name = name
            item_group.instruction = data.get("instruction")
            item_group.battery = battery
            item_group.tags = tags  # replace associations

            s.commit()
            return {"id": item_group.id, "updated": True}, 200

        # ---------------------------------
        # CREATE new ItemGroup
        # ---------------------------------
        item_group = ItemGroup(
            name=name,
            instruction=data.get("instruction"),
            battery=battery,
            tags=tags,
        )

        s.add(item_group)
        s.commit()

        return {"id": item_group.id, "created": True}, 201




if __name__ == "__main__":
    app.run(debug=True)
