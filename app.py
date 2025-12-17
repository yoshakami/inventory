from flask import Flask, jsonify, request, render_template
from sqlalchemy import select
from db import engine, SessionLocal
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


@app.route("/")
def index():
    return render_template("index.html")


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
    q = request.args.get("q", "")
    with SessionLocal() as s:
        tags = s.execute(
            select(Tag).where(Tag.name.ilike(f"%{q}%"))
        ).scalars()
        return jsonify([{"id": t.id, "name": t.name} for t in tags])

"""
@app.route("/api/locations/search")
def search_locations():
    q = request.args.get("q", "")
    with SessionLocal() as s:
        locs = s.execute(
            select(Location).where(Location.name.ilike(f"%{q}%"))
        ).scalars()
        return jsonify([{"id": l.id, "name": l.name} for l in locs])
"""

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



@app.route("/api/item-types", methods=["POST"])
def create_item_type():
    data = request.json

    required = ("name", "voltage", "current", "capacity", "charging_type")
    for key in required:
        if key not in data:
            abort(400, f"Missing field: {key}")

    with SessionLocal() as s:
        # Find or create battery
        battery = (
            s.query(Battery)
            .filter_by(
                voltage=data["voltage"],
                current=data["current"],
                capacity=data["capacity"],
                charging_type=data["charging_type"],
            )
            .one_or_none()
        )

        if battery is None:
            battery = Battery(
                voltage=float(data["voltage"]),
                current=float(data["current"]),
                capacity=float(data["capacity"]),
                charging_type=data["charging_type"],
            )
            s.add(battery)
            s.flush()  # ensures battery.id exists

        # Resolve tags safely
        tag_ids = data.get("tag_ids", [])
        tags: list[Tag] = []

        if tag_ids:
            tags = s.query(Tag).filter(Tag.id.in_(tag_ids)).all()

            if len(tags) != len(tag_ids):
                abort(400, "One or more tag_ids are invalid")

        # Create ItemType
        item_type = ItemType(
            name=data["name"],
            instruction=data.get("instruction"),
            battery=battery,
            tags=tags,
        )

        s.add(item_type)
        s.commit()

        return {"id": item_type.id}, 201

@app.route("/api/search/item-types")
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

        return jsonify([
            {"id": it.id, "label": it.name}
            for it in results
        ])

@app.route("/api/locations", methods=["POST"])
def create_location():
    data = request.json
    name = data["name"].strip()
    parent_id = data.get("parent_id")

    with SessionLocal() as s:
        existing = (
            s.query(Location)
            .filter(
                Location.name.ilike(name),
                Location.parent_id == parent_id
            )
            .one_or_none()
        )

        if existing:
            return {"id": existing.id, "name": existing.name}

        loc = Location(
            name=name,
            parent_id=parent_id,
        )
        s.add(loc)
        s.commit()
        return {"id": loc.id, "name": loc.name}



@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.json
    with SessionLocal() as s:
        item = Item(**data)
        s.add(item)
        s.commit()
        return {"id": item.id}


if __name__ == "__main__":
    app.run(debug=True)
