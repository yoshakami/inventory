from flask import Flask, jsonify, request, render_template # do not import return abort!!!!!!!
from sqlalchemy import select
from db import engine, SessionLocal
from datetime import date, datetime
from models import (
    Base,
    Item,
    ItemType,
    Tag,
    Location,
    Battery,
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
                for t in s.query(ItemType)
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


@app.route("/api/items/search")
def search_items():
    q = request.args.get("q", "").strip()

    with SessionLocal() as s:
        query = (
            s.query(Item)
            .join(Item.type)
            .join(Item.location)
        )

        if q:
            query = query.filter(ItemType.name.ilike(f"%{q}%"))

        items = query.limit(50).all()

        return jsonify([
            {
                "id": i.id,
                "type": i.type.name,
                "instruction": i.type.instruction,
                "battery": (
                    {
                        "voltage": i.type.battery.voltage,
                        "current": i.type.battery.current,
                        "capacity": i.type.battery.capacity,
                        "charging_type": i.type.battery.charging_type,
                    } if i.type.battery else None
                ),
                "tags": [t.name for t in i.type.tags],
                "location": location_helper_func(i.location),
                "last_seen": i.last_seen_date,
                "last_charge": i.last_charge_date,
                "acquired": i.acquired_date,
                "has_cable": i.has_dedicated_cable,
                "bought_place": i.bought_place,
                "price": i.price,
            }
            for i in items
        ])


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


@app.route("/api/item-types/search")
def search_item_types():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    with SessionLocal() as s:
        results = (
            s.query(ItemType)
            .filter(ItemType.name.ilike(f"%{q}%"))
            .order_by(ItemType.name)
            .limit(10)
            .all()
        )
        return jsonify([{"id": it.id, "label": it.name} for it in results])


# --------------------
# CREATE
# --------------------

@app.route("/api/tags", methods=["POST"])
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
        return {"id": tag.id, "name": tag.name}

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

    type_name = (data.get("type") or "").strip()
    location_name = (data.get("location") or "").strip()

    if not type_name or not location_name:
        return abort(400, "Item Group and Location are required")

    with SessionLocal() as s:
        # Resolve ItemType
        type_obj = s.query(ItemType).filter(ItemType.name.ilike(type_name)).one_or_none()
        if not type_obj:
            return abort(400, f"Item Group '{type_name}' not found")

        # Resolve Location
        location_name = location_name.rsplit('>', 1)[-1].strip()
        location_obj = s.query(Location).filter(Location.name.ilike(location_name)).one_or_none()
        if type(location_obj) == type(None): # python moment
            return abort(400, f"Location '{location_name}' not found")


        # Create Item
        item = Item(
            type_id=type_obj.id,
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

@app.route("/api/item-types", methods=["POST"])
def create_item_type():
    data = request.json or {}

    name = (data.get("name") or "").strip()
    if not name:
        return abort(400, "Item type name is required")

    tags_payload = data.get("tags", [])

    voltage = data.get("voltage")
    current = data.get("current")
    capacity = data.get("capacity")
    charging_type = data.get("charging_type")

    with SessionLocal() as s:
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
                s.flush()  # ensure battery.id exists

        # ---------------------------------
        # Tags: find or create by NAME
        # ---------------------------------
        tags: list[Tag] = []

        for raw_name in tags_payload:
            tag_name = (raw_name or "").strip()
            if not tag_name:
                continue

            tag = (
                s.query(Tag)
                .filter(Tag.name.ilike(tag_name))
                .one_or_none()
            )

            if tag is None:
                tag = Tag(name=tag_name)
                s.add(tag)
                s.flush()

            tags.append(tag)

        # ---------------------------------
        # Create ItemType (unique name enforced by DB)
        # ---------------------------------
        item_type = ItemType(
            name=name,
            instruction=data.get("instruction"),
            battery=battery,
            tags=tags,
        )

        s.add(item_type)
        s.commit()

        return {"id": item_type.id}, 201



if __name__ == "__main__":
    app.run(debug=True)
