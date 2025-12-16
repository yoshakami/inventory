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


@app.route("/api/locations/search")
def search_locations():
    q = request.args.get("q", "")
    with SessionLocal() as s:
        locs = s.execute(
            select(Location).where(Location.name.ilike(f"%{q}%"))
        ).scalars()
        return jsonify([{"id": l.id, "name": l.name} for l in locs])


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


@app.route("/api/batteries", methods=["POST"])
def create_battery():
    data = request.json
    with SessionLocal() as s:
        b = Battery(
            voltage=data["voltage"],
            current=data["current"],
            capacity=data["capacity"],
            charging_type=data["charging_type"],
        )
        s.add(b)
        s.commit()
        return {"id": b.id}



@app.route("/api/item-types", methods=["POST"])
def create_item_type():
    data = request.json
    with SessionLocal() as s:
        tags = s.query(Tag).filter(Tag.id.in_(data["tag_ids"])).all()
        it = ItemType(
            name=data["name"],
            instruction=data.get("instruction"),
            battery_id=data.get("battery_id"),
            tags=tags,
        )
        s.add(it)
        s.commit()
        return {"id": it.id}


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
