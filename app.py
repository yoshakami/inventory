import os
import json
import unicodedata
from sqlalchemy import select, func
from db import engine, SessionLocal
from datetime import date, datetime
from sqlalchemy.orm import joinedload
from flask_httpauth import HTTPDigestAuth
from models import (Base, Item, ItemGroup, Tag,
                    Location, Battery, tag_association,)
# do not import return abort!!!!!!!
from flask import Flask, jsonify, request, render_template, send_from_directory
app = Flask(__name__)
auth = HTTPDigestAuth()
#app.config['APPLICATION_ROOT'] = '/inventory' # there's another const in the js
Base.metadata.create_all(engine)

users = {} 
if os.path.exists('users.json'):
    with open('users.json', 'r') as file:
        users = json.load(file)

# the user "server" and "Yosh" need to be mentionned here.
# feel free to edit them. this is the only place they appear

app.config['SECRET_KEY'] = users.get('server')

def is_Yosh_allowed(): # hidden items
    user = auth.current_user()
    header = request.headers.get("X-Yosh", "").lower() == "true"
    return user == "Yosh" and header

def am_i_admin():
    return auth.current_user() == "Yosh"

# everything else is unchanged and can work as is

@auth.get_password
def get_pw(username):
    if username in users:
        return users.get(username)
    return None

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
@auth.login_required
def index():
    return render_template("index.html", user=auth.username())

@app.route("/inventory")
@auth.login_required
def index2():
    return render_template("index.html")

@app.route("/favicon.ico")
@auth.login_required
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
        "last_use": iso(i.last_use_date), "acquired": iso(i.acquired_date), "has_cable": i.has_dedicated_cable, "bought_place": i.bought_place, "price": i.price,
        "color": i.color, "variant": i.variant, "status": i.status, }


@app.route("/api/items/tag")
@auth.login_required
def search_items_by_tag():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        query = (s.query(Item).join(Item.group).join(
            tag_association).join(Tag))
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        filtered = [
            i for i in query
            if any(q in normalize(t.name) for t in i.group.tags)
        ]
        if is_autocomplete():
            tags = [
                t for i in filtered for t in i.group.tags if q in normalize(t.name)]
            return autocomplete(tags, lambda t: t.name)
        return jsonify([item_to_dict(i) for i in filtered])


@app.route("/api/items/location")
@auth.login_required
def search_items_by_location():
    q = normalize(request.args.get("q", "").rsplit(">", 1)[-1])
    with SessionLocal() as s:
        if is_autocomplete():
            query = s.query(Location).all()
            filtered = [i for i in query if q in normalize(
                location_helper_func(i))]
            return autocomplete(
                [i for i in filtered],
                location_helper_func)
        query = s.query(Item).join(Item.location)
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        filtered = [i for i in query if q in normalize(
            location_helper_func(i.location))]
        return jsonify([item_to_dict(i) for i in filtered])


@app.route("/api/items/group")
@auth.login_required
def search_items_by_group():
    Yosh_allowed = is_Yosh_allowed()
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        if is_autocomplete():
            query = s.query(ItemGroup)
            if not Yosh_allowed:
                query = query.filter(
                    ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
                )
            query = query.all()
            filtered = [i for i in query if q in normalize(i.name)]
            return autocomplete(
                [i for i in filtered],
                lambda g: g.name)
        query = s.query(Item).join(Item.group)
        if not Yosh_allowed:
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        filtered = [i for i in query if q in normalize(i.group.name)]
        return jsonify([item_to_dict(i) for i in filtered])


def str_match(value, q):
    return q in str(value)


@app.route("/api/items/voltage")
@auth.login_required
def search_items_by_voltage():
    q = request.args.get("q", type=str)

    with SessionLocal() as s:
        query = (
            s.query(Item)
             .join(Item.group)
             .join(ItemGroup.battery)
             .distinct()
        )

        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )

        items = query.all()

        if is_autocomplete():
            values = sorted({
                i.group.battery.voltage
                for i in items
                if i.group.battery and i.group.battery.voltage is not None
            })
            return jsonify([
                {"id": v, "label": str(v)}
                for v in values[:10]
            ])

        if not q:
            return jsonify([])

        seen = {}
        for i in items:
            if not i.group.battery:
                continue

            v = i.group.battery.voltage
            if v is None:
                continue

            if q in str(v):
                seen.setdefault(v, i)

        return jsonify([
            item_to_dict(i)
            for i in seen.values()
        ])



@app.route("/api/items/current")
@auth.login_required
def search_items_by_current():
    q = request.args.get("q", type=str)

    with SessionLocal() as s:
        query = (
            s.query(Item)
             .join(Item.group)
             .join(ItemGroup.battery)
             .distinct()
        )

        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )

        items = query.all()

        if is_autocomplete():
            values = sorted({
                i.group.battery.current
                for i in items
                if i.group.battery and i.group.battery.current is not None
            })
            return jsonify([
                {"id": v, "label": str(v)}
                for v in values[:10]
            ])

        if not q:
            return jsonify([])

        seen = {}
        for i in items:
            if not i.group.battery:
                continue

            v = i.group.battery.current
            if v is None:
                continue

            if q in str(v):
                seen.setdefault(v, i)

        return jsonify([
            item_to_dict(i)
            for i in seen.values()
        ])



@app.route("/api/items/capacity")
@auth.login_required
def search_items_by_capacity():
    q = request.args.get("q", type=str)

    with SessionLocal() as s:
        query = (
            s.query(Item)
             .join(Item.group)
             .join(ItemGroup.battery)
             .distinct()
        )

        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )

        items = query.all()

        if is_autocomplete():
            values = sorted({
                i.group.battery.capacity
                for i in items
                if i.group.battery and i.group.battery.capacity is not None
            })
            return jsonify([
                {"id": v, "label": str(v)}
                for v in values[:10]
            ])

        if not q:
            return jsonify([])

        seen = {}
        for i in items:
            if not i.group.battery:
                continue

            v = i.group.battery.capacity
            if v is None:
                continue

            if q in str(v):
                seen.setdefault(v, i)

        return jsonify([
            item_to_dict(i)
            for i in seen.values()
        ])



@app.route("/api/items/charging-type")
@auth.login_required
def search_items_by_charging_type():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        query = (s.query(Item).join(Item.group).join(ItemGroup.battery))
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        filtered = [
            i for i in query
            if i.group.battery and q in normalize(i.group.battery.charging_type)
        ]
        if is_autocomplete():
            seen = set()
            unique = []
            for b in (i.group.battery for i in filtered):
                ct = b.charging_type
                if ct not in seen:
                    seen.add(ct)
                    unique.append(b)

            return autocomplete(unique, lambda b: b.charging_type)

        return jsonify([item_to_dict(i) for i in filtered])


@app.route("/api/items/bought-place")
@auth.login_required
def search_items_by_bought_place():
    q = normalize(request.args.get("q", ""))
    print(f"[DEBUG] Raw query parameter: {request.args.get('q')}")
    print(f"[DEBUG] Normalized query: {q}")

    with SessionLocal() as s:
        query = s.query(Item)
        print(f"[DEBUG] Initial query: {query}")

        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
            print("[DEBUG] Applied +18 filter because Yosh is not allowed")

        query = query.all()
        print(f"[DEBUG] Query returned {len(query)} items")
        for i in query:
            print(f"  [DEBUG] Item: id={i.id}, bought_place={i.bought_place}")

        filtered = [
            i for i in query if i.bought_place and q in normalize(i.bought_place)
        ]
        print(f"[DEBUG] Filtered {len(filtered)} items after matching bought_place")
        for i in filtered:
            print(f"  [DEBUG] Filtered Item: id={i.id}, bought_place={i.bought_place}")

        if is_autocomplete():
            print("[DEBUG] Autocomplete mode ON")
            seen = set()
            unique = []
            for i in filtered:
                bp = i.bought_place
                if bp not in seen:
                    seen.add(bp)
                    unique.append(i)
                    print(f"  [DEBUG] Added to unique autocomplete: {bp}")

            result = autocomplete(unique, lambda i: i.bought_place)
            print(f"[DEBUG] Autocomplete result: {result}")
            return result

        result = [item_to_dict(i) for i in filtered]
        print(f"[DEBUG] JSON result: {result}")
        return jsonify(result)


@app.route("/api/items/variant")
@auth.login_required
def search_items_by_variant():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        query = s.query(Item)
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        filtered = [
            i for i in query if i.variant and q in normalize(i.variant)]
        if is_autocomplete():
            return autocomplete(
                filtered,
                lambda i: i.variant)
        return jsonify([item_to_dict(i) for i in filtered])

@app.route("/api/items/color")
@auth.login_required
def search_items_by_color():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        query = s.query(Item)
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        filtered = [
            i for i in query if i.color and q in normalize(i.color)]
        if is_autocomplete():
            return autocomplete(
                filtered,
                lambda i: i.color)
        return jsonify([item_to_dict(i) for i in filtered])

@app.route("/api/items/status")
@auth.login_required
def search_items_by_status():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        query = s.query(Item)
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        filtered = [
            i for i in query if i.status and q in normalize(i.status)]
        if is_autocomplete():
            return autocomplete(
                filtered,
                lambda i: i.status)
        return jsonify([item_to_dict(i) for i in filtered])
    
@app.route("/api/items/price")
@auth.login_required
def search_items_by_price():
    q = request.args.get("q", "")
    with SessionLocal() as s:
        query = s.query(Item)
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        if is_autocomplete():
            prices = sorted(
                {
                    i.price
                    for i in query
                    if i.price is not None and q in str(i.price)
                }
            )
            return jsonify([
                {"id": p, "label": str(p)}
                for p in prices[:10]
            ])
        return jsonify([item_to_dict(i) for i in query if str(q) in str(i.price)])


@app.route("/api/items/last-seen")
@auth.login_required
def search_items_last_seen():
    q = request.args.get("q")
    with SessionLocal() as s:
        query = s.query(Item)
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        if is_autocomplete():
            dates = sorted(
                {
                    i.last_seen_date
                    for i in query
                    if i.last_seen_date and q in i.last_seen_date.isoformat()
                },
                reverse=True
            )
            return jsonify([
                {"id": d.isoformat(), "label": d.isoformat()}
                for d in dates[:10]
            ])
        return jsonify([item_to_dict(i) for i in query if q in str(i.last_seen_date)])


@app.route("/api/items/last-use")
@auth.login_required
def search_items_last_use():
    q = request.args.get("q")
    with SessionLocal() as s:
        query = s.query(Item)
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        if is_autocomplete():
            dates = sorted(
                {
                    i.last_use_date
                    for i in query
                    if i.last_use_date and q in i.last_use_date.isoformat()
                },
                reverse=True
            )
            return jsonify([
                {"id": d.isoformat(), "label": d.isoformat()}
                for d in dates[:10]
            ])
        return jsonify([item_to_dict(i) for i in query if q in str(i.last_use_date)])


@app.route("/api/items/acquired")
@auth.login_required
def search_items_acquired():
    q = request.args.get("q")
    with SessionLocal() as s:
        query = s.query(Item)
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        if is_autocomplete():
            dates = sorted(
                {
                    i.acquired_date
                    for i in query
                    if i.acquired_date and q in i.acquired_date.isoformat()
                },
                reverse=True
            )
            return jsonify([
                {"id": d.isoformat(), "label": d.isoformat()}
                for d in dates[:10]
            ])
        return jsonify([item_to_dict(i) for i in query if q in str(i.acquired_date)])


@app.route("/api/items/id")
@auth.login_required
def search_item_by_id():
    q = request.args.get("q", type=int)
    with SessionLocal() as s:
        if is_autocomplete():
            query = s.query(Item.id).order_by(Item.id.desc())
            if not is_Yosh_allowed():
                query = query.filter(
                    ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
                )
            query = query.limit(10)
            return jsonify([{"id": i[0], "label": str(i[0])} for i in query])
        item = s.get(Item, q)
        return jsonify([item_to_dict(item)]) if item else jsonify([])


@app.route("/api/items/group-id")
@auth.login_required
def search_items_by_group_id():
    q = request.args.get("q", type=int)
    with SessionLocal() as s:
        query = s.query(Item).filter(Item.group_id.ilike(f"%{q}%"))
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        query = query.all()
        if is_autocomplete():
            return jsonify([{"id": q, "label": str(q)}])
        return jsonify([item_to_dict(i) for i in query])


@app.route("/api/items")
@auth.login_required
def advanced_search():
    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)
    after = request.args.get("after")
    before = request.args.get("before")
    tag_partial = normalize(request.args.get("tag_partial", ""))

    with SessionLocal() as s:
        q = s.query(Item).join(Item.group).outerjoin(
            tag_association).outerjoin(Tag)
        if not is_Yosh_allowed():
            q = q.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )

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

        q = q.distinct().all()
        return jsonify([item_to_dict(i) for i in q])

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


ITEM_FIELDS = {"last_seen_date": parse_date, "last_use_date": parse_date, "has_dedicated_cable": bool, "acquired_date": parse_date, "price": lambda x: x }


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
@auth.login_required
def delete_item(): #TODO
    if not am_i_admin():
        return abort(400, "You're not admin")
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
@auth.login_required
def create_item():
    if not am_i_admin():
        return abort(400, "You're not admin")
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
@auth.login_required
def create_location():
    if not am_i_admin():
        return abort(400, "You're not admin")

    data = request.json or {}

    name = (data.get("name") or "").rsplit(">", 1)[-1].strip()
    parent_name = (
        (data.get("parent") or "").rsplit(">", 1)[-1].strip()
        if data.get("parent") else None
    )

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
             .filter(
                 Location.name.ilike(name),
                 Location.parent_id == (parent.id if parent else None),
             )
             .one_or_none()
        )

        if existing:
            return {"id": existing.id, "name": existing.name}, 200

        loc = Location(name=name, parent=parent)
        s.add(loc)
        s.commit()

        return {"id": loc.id, "name": loc.name}, 201


@app.route("/api/item-group", methods=["POST"])
@auth.login_required
def create_item_group():
    if not am_i_admin():
        return abort(400, "You're not admin")
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
