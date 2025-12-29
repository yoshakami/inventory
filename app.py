import os
import unicodedata
from sqlalchemy import select, func
from db import engine, SessionLocal
from datetime import date, datetime
from sqlalchemy.orm import joinedload
from models import (Base, Item, ItemGroup, Tag,
                    Location, Battery, tag_association,)
# do not import return abort!!!!!!!
from flask import Flask, jsonify, request, render_template, send_from_directory
app = Flask(__name__)
app.config['APPLICATION_ROOT'] = '/inventory'
Base.metadata.create_all(engine)

# @overwrite Flask function
def abort(resp_status, message):  # this one sends JSON instead of HTML
    return {"error": message}, resp_status

def is_autocomplete() -> bool:
    return request.args.get("autocomplete", "").lower() in ("1", "true", "yes")


def normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def autocomplete(items, label_fn, limit=10):
    seen = {}
    for i in items:
        seen[id(i)] = i
    return jsonify([
        {"id": getattr(i, "id", label_fn(i)), "label": label_fn(i)}
        for i in list(seen.values())[:limit]
    ])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"), "Hatsune-Miku.ico", mimetype="image/vnd.microsoft.icon",)
# --------------------
# SEARCH
# --------------------


def autocomplete_response(rows, label_fn, limit=10):
    return jsonify([
        {"id": r.id, "label": label_fn(r)}
        for r in rows[:limit]
    ])


def search_by_name(model, q, label_fn=lambda x: x.name, limit=10):
    q_norm = normalize(q)
    if not q_norm:
        return []
    with SessionLocal() as s:
        rows = s.query(model).order_by(model.name).all()
        results = [
            r for r in rows
            if q_norm in normalize(r.name)
        ][:limit]
        return [{"id": r.id, "label": label_fn(r)} for r in results]


def location_helper_func(loc: Location) -> str:
    parts = []
    current = loc
    while current:
        parts.append(current.name)
        current = current.parent
    return " > ".join(reversed(parts))


def iso(d):
    return d.isoformat() if d else None


def battery_to_dict(b):
    if not b:
        return None
    return {
        "voltage": b.voltage, "current": b.current, "capacity": b.capacity, "charging_type": b.charging_type, }


def item_to_dict(i: Item):
    return {
        "id": i.id, "group": i.group.name, "instruction": i.group.instruction, "battery": battery_to_dict(i.group.battery),
        "tags": [t.name for t in i.group.tags], "location": location_helper_func(i.location), "last_seen": iso(i.last_seen_date),
        "last_charge": iso(i.last_charge_date), "acquired": iso(i.acquired_date), "has_cable": i.has_dedicated_cable, "bought_place": i.bought_place, "price": i.price,
        "color": i.color, "variant": i.variant, "status": i.status, }


@app.route("/api/items/tag")
def search_items_by_tag():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        items = (s.query(Item).join(Item.group).join(
            tag_association).join(Tag).all())
        filtered = [
            i for i in items
            if any(q in normalize(t.name) for t in i.group.tags)
        ]
        if is_autocomplete():
            tags = [
                t for i in filtered for t in i.group.tags if q in normalize(t.name)]
            return autocomplete(tags, lambda t: t.name)
        return jsonify([item_to_dict(i) for i in filtered])


@app.route("/api/items/location")
def search_items_by_location():
    q = normalize(request.args.get("q", "").rsplit(">", 1)[-1])
    with SessionLocal() as s:
        if is_autocomplete():
            items = s.query(Location).all()
            filtered = [i for i in items if q in normalize(
                location_helper_func(i))]
            return autocomplete(
                [i for i in filtered],
                location_helper_func)
        items = s.query(Item).join(Item.location).all()
        filtered = [i for i in items if q in normalize(
            location_helper_func(i.location))]
        return jsonify([item_to_dict(i) for i in filtered])


@app.route("/api/items/group")
def search_items_by_group():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        if is_autocomplete():
            items = s.query(ItemGroup).all()
            filtered = [i for i in items if q in normalize(i.name)]
            return autocomplete(
                [i for i in filtered],
                lambda g: g.name)
        items = s.query(Item).join(Item.group).all()
        filtered = [i for i in items if q in normalize(i.group.name)]
        return jsonify([item_to_dict(i) for i in filtered])


@app.route("/api/items/voltage")
def search_items_by_voltage():
    q = request.args.get("q", type=float)
    with SessionLocal() as s:
        items = (s.query(Item).join(Item.group).join(ItemGroup.battery).all())
        if is_autocomplete():
            values = sorted({
                i.group.battery.voltage
                for i in items
                if i.group.battery and i.group.battery.voltage is not None
            })
            return jsonify([{"id": v, "label": str(v)} for v in values[:10]])
        return jsonify([
            item_to_dict(i)
            for i in items
            if i.group.battery and str(q) in i.group.battery.voltage
        ])


@app.route("/api/items/current")
def search_items_by_current():
    q = request.args.get("q", type=float)
    with SessionLocal() as s:
        items = (s.query(Item).join(Item.group).join(ItemGroup.battery).all())
        if is_autocomplete():
            values = sorted({
                i.group.battery.current
                for i in items
                if i.group.battery and i.group.battery.current is not None
            })
            return jsonify([{"id": v, "label": str(v)} for v in values[:10]])
        return jsonify([
            item_to_dict(i)
            for i in items
            if i.group.battery and str(q) in i.group.battery.current
        ])


@app.route("/api/items/capacity")
def search_items_by_capacity():
    q = request.args.get("q", type=float)
    with SessionLocal() as s:
        items = (s.query(Item).join(Item.group).join(ItemGroup.battery).all())
        if is_autocomplete():
            values = sorted({
                i.group.battery.capacity
                for i in items
                if i.group.battery and i.group.battery.capacity is not None
            })
            return jsonify([{"id": v, "label": str(v)} for v in values[:10]])
        return jsonify([
            item_to_dict(i)
            for i in items
            if i.group.battery and str(q) in i.group.battery.capacity
        ])


@app.route("/api/items/charging-type")
def search_items_by_charging_type():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        items = (s.query(Item).join(Item.group).join(ItemGroup.battery).all())
        filtered = [
            i for i in items
            if i.group.battery and q in normalize(i.group.battery.charging_type)
        ]
        if is_autocomplete():
            return autocomplete(
                [i.group.battery for i in filtered],
                lambda b: b.charging_type)
        return jsonify([item_to_dict(i) for i in filtered])


@app.route("/api/items/bought-place")
def search_items_by_bought_place():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        items = s.query(Item).all()
        filtered = [
            i for i in items if i.bought_place and q in normalize(i.bought_place)]
        if is_autocomplete():
            return autocomplete(
                filtered,
                lambda i: i.bought_place)
        return jsonify([item_to_dict(i) for i in filtered])

@app.route("/api/items/variant")
def search_items_by_variant():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        items = s.query(Item).all()
        filtered = [
            i for i in items if i.variant and q in normalize(i.variant)]
        if is_autocomplete():
            return autocomplete(
                filtered,
                lambda i: i.variant)
        return jsonify([item_to_dict(i) for i in filtered])

@app.route("/api/items/color")
def search_items_by_color():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        items = s.query(Item).all()
        filtered = [
            i for i in items if i.color and q in normalize(i.color)]
        if is_autocomplete():
            return autocomplete(
                filtered,
                lambda i: i.color)
        return jsonify([item_to_dict(i) for i in filtered])

@app.route("/api/items/status")
def search_items_by_status():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        items = s.query(Item).all()
        filtered = [
            i for i in items if i.status and q in normalize(i.status)]
        if is_autocomplete():
            return autocomplete(
                filtered,
                lambda i: i.status)
        return jsonify([item_to_dict(i) for i in filtered])
    
@app.route("/api/items/price")
def search_items_by_price():
    q = request.args.get("q", type=float)
    with SessionLocal() as s:
        items = s.query(Item).all()
        if is_autocomplete():
            prices = sorted({i.price for i in items if i.price is not None})
            return jsonify([{"id": p, "label": str(p)} for p in prices[:10]])
        return jsonify([item_to_dict(i) for i in items if str(q) in str(i.price)])


@app.route("/api/items/last-seen")
def search_items_last_seen():
    q = request.args.get("q")
    with SessionLocal() as s:
        items = s.query(Item).all()
        if is_autocomplete():
            dates = sorted(
                {i.last_seen_date for i in items if i.last_seen_date}, reverse=True)
            return jsonify([{"id": d.isoformat(), "label": d.isoformat()} for d in dates[:10]])
        return jsonify([item_to_dict(i) for i in items if q in str(i.last_seen_date)])


@app.route("/api/items/last-charge")
def search_items_last_charge():
    q = request.args.get("q")
    with SessionLocal() as s:
        items = s.query(Item).all()
        if is_autocomplete():
            dates = sorted(
                {i.last_charge_date for i in items if i.last_charge_date}, reverse=True)
            return jsonify([{"id": d.isoformat(), "label": d.isoformat()} for d in dates[:10]])
        return jsonify([item_to_dict(i) for i in items if q in str(i.last_charge_date)])


@app.route("/api/items/acquired")
def search_items_acquired():
    q = request.args.get("q")
    with SessionLocal() as s:
        items = s.query(Item).all()
        if is_autocomplete():
            dates = sorted(
                {i.acquired_date for i in items if i.acquired_date}, reverse=True)
            return jsonify([{"id": d.isoformat(), "label": d.isoformat()} for d in dates[:10]])
        return jsonify([item_to_dict(i) for i in items if q in str(i.acquired_date)])


@app.route("/api/items/id")
def search_item_by_id():
    q = request.args.get("q", type=int)
    with SessionLocal() as s:
        if is_autocomplete():
            ids = s.query(Item.id).order_by(Item.id.desc()).limit(10).all()
            return jsonify([{"id": i[0], "label": str(i[0])} for i in ids])
        item = s.get(Item, q)
        return jsonify([item_to_dict(item)]) if item else jsonify([])


@app.route("/api/items/group-id")
def search_items_by_group_id():
    q = request.args.get("q", type=int)
    with SessionLocal() as s:
        items = s.query(Item).filter(Item.group_id.ilike(f"%{q}%")).all()
        if is_autocomplete():
            return jsonify([{"id": q, "label": str(q)}])
        return jsonify([item_to_dict(i) for i in items])


@app.route("/api/items")
def advanced_search():
    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)
    after = request.args.get("after")
    before = request.args.get("before")
    tag_partial = normalize(request.args.get("tag_partial", ""))

    with SessionLocal() as s:
        q = s.query(Item).join(Item.group).outerjoin(
            tag_association).outerjoin(Tag)

        if price_min is not None:
            q = q.filter(Item.price >= price_min)

        if price_max is not None:
            q = q.filter(Item.price <= price_max)

        if after:
            q = q.filter(Item.last_seen_date >= after)

        if before:
            q = q.filter(Item.last_seen_date <= before)

        if tag_partial:
            q = q.filter(func.lower(Tag.name).ilike(f"%{tag_partial}%"))

        items = q.distinct().all()
        return jsonify([item_to_dict(i) for i in items])

# --------------------
# HELPERS FOR CREATE FUNCTIONS
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


ITEM_FIELDS = {"last_seen_date": parse_date, "last_charge_date": parse_date, "has_dedicated_cable": bool, "acquired_date": parse_date, "price": lambda x: x }


def apply_item_fields(item, data):
    for field, cast in ITEM_FIELDS.items():
        setattr(item, field, cast(data.get(field)))
    item.bought_place = (data.get("bought_place") or "").strip() or None
    item.color = (data.get("color") or "").strip() or None
    item.status = (data.get("status") or "").strip() or None
    item.variant = (data.get("variant") or "").strip() or None


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
        tag = (s.query(Tag).filter(func.lower(
            Tag.name) == name.lower()).one_or_none())
        if not tag:
            tag = Tag(name=name)
            s.add(tag)
            s.flush()
        tags.append(tag)
    return tags

# --------------------
# DELETE
# --------------------

@app.route("/api/items", methods=["DELETE"])
def delete_item():
    item_id = request.args.get("id", type=int)
    if not item_id:
        return abort(400, "Item id is required")
    with SessionLocal() as s:
        item = s.get(Item, item_id)
        if not item:
            return abort(404, "Item not found")
        s.delete(item)
        s.commit()
        return {"deleted": True, "id": item_id}, 200

# --------------------
# CREATE AND UPDATE
# --------------------

@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.json or {}
    group_name = (data.get("group") or "").strip()
    location_name = (data.get("location") or "").strip()
    if not group_name or not location_name:
        return abort(400, "Item Group and Location are required")
    with SessionLocal() as s:
        group = s.query(ItemGroup).filter(
            ItemGroup.name.ilike(group_name)).one_or_none()
        if not group:
            return abort(400, f"Item Group '{group_name}' not found")
        location_name = location_name.rsplit(">", 1)[-1].strip()
        location = s.query(Location).filter(
            Location.name.ilike(location_name)).one_or_none()
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
        parent = (s.query(Location).filter(Location.name.ilike(parent_name)).one_or_none()
                  if parent_name else None)
        existing = (s.query(Location).filter(Location.name.ilike(
            name), Location.parent_id == (parent.id if parent else None)).one_or_none())
        if existing:
            return {"id": existing.id, "name": existing.name}, 200
        loc = Location(name=name, parent=parent)
        s.add(loc)
        s.commit()
        return {"id": loc.id, "name": loc.name}, 201

@app.route("/api/item-group", methods=["POST"])
def create_item_group():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return abort(400, "Item group name is required")
    with SessionLocal() as s:
        item_group = s.get(ItemGroup, data.get("id"))
        battery = get_or_create_battery(
            s, voltage=data.get("voltage"), current=data.get("current"), capacity=data.get("capacity"), charging_type=data.get("charging_type"),)
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
            "id": item_group.id, "updated": bool(data.get("id")), }, 200 if data.get("id") else 201


if __name__ == "__main__":
    app.run(debug=True)
