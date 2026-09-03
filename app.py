import os
import re
import uuid
import json
import unicodedata
from sqlalchemy import select, func
from db import engine, SessionLocal
from datetime import date, datetime
from sqlalchemy.orm import joinedload, selectinload
from flask_httpauth import HTTPDigestAuth
from models import (Base, Item, ItemGroup, Tag,
                    Location, Battery, tag_association,
                    FurnitureMap, FurnitureZone,)
from mask_to_zones import mask_to_zones
from PIL import Image
from werkzeug.utils import secure_filename
# do not import return abort!!!!!!!
from flask import Flask, jsonify, request, render_template, send_from_directory
app = Flask(__name__)
auth = HTTPDigestAuth()
#app.config['APPLICATION_ROOT'] = '/inventory' # there's another const in the js
Base.metadata.create_all(engine)

UPLOAD_DIR = os.path.join(app.root_path, "uploads", "furniture")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

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

def get_autocomplete_limit() -> int:
    """
    Max number of autocomplete suggestions to return.
    Defaults to 10 when `limitNumber` is missing/empty/invalid.
    """
    limit = request.args.get("limitNumber", type=int)
    if limit is None or limit <= 0:
        return 10
    return limit


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
    seen_ids = set()
    while current:
        current_id = getattr(current, "id", None)
        if current_id is not None:
            if current_id in seen_ids:
                # Break infinite loops if bad parent cycles exist in data.
                break
            seen_ids.add(current_id)
        parts.append(current.name)
        current = current.parent
    return " > ".join(reversed(parts))


def would_create_location_cycle(loc: Location, new_parent: Location | None) -> bool:
    if not loc or not new_parent:
        return False
    if getattr(loc, "id", None) == getattr(new_parent, "id", None):
        return True
    seen_ids = set()
    current = new_parent
    while current:
        current_id = getattr(current, "id", None)
        if current_id is None:
            return False
        if current_id in seen_ids:
            return True
        if current_id == loc.id:
            return True
        seen_ids.add(current_id)
        current = current.parent
    return False


def location_chain_ids(loc: Location) -> list[int]:
    ids = []
    seen = set()
    current = loc
    while current:
        current_id = getattr(current, "id", None)
        if current_id is None or current_id in seen:
            break
        seen.add(current_id)
        ids.append(current_id)
        current = current.parent
    return ids


def trailing_slot(name: str) -> int | None:
    match = re.search(r"(\d+)\s*$", name or "")
    return int(match.group(1)) if match else None


def resolve_location_by_path(s, raw: str) -> Location | None:
    name = (raw or "").strip()
    if not name:
        return None
    name = name.rsplit(">", 1)[-1].strip()
    return s.query(Location).filter(Location.name.ilike(name)).one_or_none()


def save_upload(file_storage, prefix: str) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        return None
    safe = secure_filename(file_storage.filename) or f"image{ext}"
    _root, ext = os.path.splitext(safe)
    if ext.lower() not in ALLOWED_IMAGE_EXT:
        ext = ".png"
    name = f"{prefix}-{uuid.uuid4().hex}{ext.lower()}"
    file_storage.save(os.path.join(UPLOAD_DIR, name))
    return name


def delete_upload(filename: str | None) -> None:
    if not filename:
        return
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.isfile(path):
        os.remove(path)


def apply_mask_to_map(s, fmap: FurnitureMap, mask_path: str) -> int:
    result = mask_to_zones(mask_path)
    old_by_slot = {z.slot: z.location_id for z in fmap.zones}
    fmap.zones.clear()
    s.flush()
    children = s.query(Location).filter(Location.parent_id == fmap.location_id).all()
    children_by_slot = {}
    for child in children:
        slot = trailing_slot(child.name)
        if slot is not None:
            children_by_slot.setdefault(slot, child.id)
    for z in result["zones"]:
        loc_id = old_by_slot.get(z["slot"]) or children_by_slot.get(z["slot"])
        fmap.zones.append(FurnitureZone(
            color=z["color"],
            slot=z["slot"],
            location_id=loc_id,
            x=z["x"],
            y=z["y"],
            w=z["w"],
            h=z["h"],
            cx=z["cx"],
            cy=z["cy"],
        ))
    return len(result["zones"])


def furniture_map_options():
    return (
        joinedload(FurnitureMap.location).joinedload(Location.parent),
        selectinload(FurnitureMap.zones).joinedload(FurnitureZone.location).joinedload(Location.parent),
    )


def zone_to_dict(z: FurnitureZone) -> dict:
    return {
        "id": z.id,
        "color": z.color,
        "slot": z.slot,
        "location_id": z.location_id,
        "location": location_helper_func(z.location) if z.location else None,
        "x": z.x,
        "y": z.y,
        "w": z.w,
        "h": z.h,
        "cx": z.cx,
        "cy": z.cy,
    }


def pick_highlight(fmap: FurnitureMap, chain_ids: list[int]) -> dict | None:
    by_loc = {z.location_id: z for z in fmap.zones if z.location_id}
    for loc_id in chain_ids:
        z = by_loc.get(loc_id)
        if z:
            return {
                "x": z.x, "y": z.y, "w": z.w, "h": z.h,
                "cx": z.cx, "cy": z.cy, "slot": z.slot, "color": z.color,
            }
    return None


def map_to_dict(fmap: FurnitureMap, highlight=None) -> dict:
    return {
        "id": fmap.id,
        "name": fmap.name,
        "location_id": fmap.location_id,
        "location": location_helper_func(fmap.location) if fmap.location else None,
        "photo_url": f"/uploads/furniture/{fmap.photo_filename}",
        "mask_url": f"/uploads/furniture/{fmap.mask_filename}" if fmap.mask_filename else None,
        "width": fmap.width,
        "height": fmap.height,
        "zones": [zone_to_dict(z) for z in sorted(fmap.zones, key=lambda z: z.slot)],
        "highlight": highlight,
    }


def iso(d):
    return d.isoformat() if d else None


def battery_to_dict(b):
    if not b:
        return None
    return {
        "voltage": b.voltage, "current": b.current, "capacity": b.capacity, "charging_type": b.charging_type, }


def item_to_dict(i: Item): # this dict is used by the js for editing an item. string is the name in the js
    return {
        "id": i.id, "group": i.group.name, "instruction": i.group.instruction, "battery": battery_to_dict(i.group.battery),
        "tags": [t.name for t in i.group.tags], "last_seen": iso(i.last_seen_date),
        "last_use": iso(i.last_use_date), "acquired": iso(i.acquired_date), "has_cable": i.has_dedicated_cable, "bought_place": i.bought_place, "price": i.price,
        "color": i.color, "variant": i.variant, "status": i.status, "location": location_helper_func(i.location), "location_id": i.location.id, "location_parent": location_helper_func(i.location.parent), }


@app.route("/api/items/tag")
@auth.login_required
def search_items_by_tag():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        tags = s.query(Tag).all()
        matching_tags = [t for t in tags if q in normalize(t.name)]

        if is_autocomplete():
            return autocomplete(matching_tags, lambda t: t.name, limit=get_autocomplete_limit())

        if not matching_tags:
            return jsonify([])

        matching_tag_ids = [t.id for t in matching_tags]
        query = (
            s.query(Item)
            .join(Item.group)
            .join(ItemGroup.tags)
            .filter(Tag.id.in_(matching_tag_ids))
            .options(
                joinedload(Item.group).joinedload(ItemGroup.battery),
                joinedload(Item.group).selectinload(ItemGroup.tags),
                joinedload(Item.location).joinedload(Location.parent),
            )
            .distinct()
        )
        if not is_Yosh_allowed():
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        filtered = query.all()
        return jsonify([item_to_dict(i) for i in filtered])


@app.route("/api/items/location")
@auth.login_required
def search_items_by_location():
    q = normalize(request.args.get("q", "").rsplit(">", 1)[-1].strip())
    with SessionLocal() as s:
        locations = s.query(Location).all()
        matching_locations = [loc for loc in locations if q in normalize(location_helper_func(loc))]

        if is_autocomplete():
            return autocomplete(matching_locations, location_helper_func, limit=get_autocomplete_limit())

        if not matching_locations:
            return jsonify([])

        matching_location_ids = [loc.id for loc in matching_locations]
        query = (
            s.query(Item)
            .outerjoin(Item.location)
            .filter(Item.location_id.in_(matching_location_ids))
            .options(
                joinedload(Item.group).joinedload(ItemGroup.battery),
                joinedload(Item.group).selectinload(ItemGroup.tags),
                joinedload(Item.location).joinedload(Location.parent),
            )
        )
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
        return jsonify([item_to_dict(i) for i in query.all()])


@app.route("/api/items/group")
@auth.login_required
def search_items_by_group():
    Yosh_allowed = is_Yosh_allowed()
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        query = s.query(ItemGroup)
        if not Yosh_allowed:
            query = query.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        groups = query.all()
        matching_groups = [g for g in groups if q in normalize(g.name)]

        if is_autocomplete():
            return autocomplete(
                matching_groups,
                lambda g: g.name,
                limit=get_autocomplete_limit())

        if not matching_groups:
            return jsonify([])

        matching_group_ids = [g.id for g in matching_groups]
        items_q = (
            s.query(Item)
            .join(Item.group)
            .filter(Item.group_id.in_(matching_group_ids))
            .options(
                joinedload(Item.group).joinedload(ItemGroup.battery),
                joinedload(Item.group).selectinload(ItemGroup.tags),
                joinedload(Item.location).joinedload(Location.parent),
            )
        )
        if not Yosh_allowed:
            items_q = items_q.filter(
                ~ItemGroup.tags.any(Tag.name.ilike("%+18%"))
            )
        return jsonify([item_to_dict(i) for i in items_q.all()])


def str_match(value, q):
    return q in str(value)


@app.route("/api/items/voltage")
@auth.login_required
def search_items_by_voltage():
    q = request.args.get("q", type=str)
    with SessionLocal() as s:
        query = (s.query(Item).join(Item.group).join(ItemGroup.battery).distinct())
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
        items = query.all()
        if is_autocomplete() and q:
            filtered = [
                i.group.battery.voltage
                for i in items
                if i.group.battery and i.group.battery.voltage is not None and q in str(i.group.battery.voltage)
            ]
            exact_matches = [v for v in filtered if str(v) == q]
            partial_matches = [v for v in filtered if str(v) != q]
            partial_matches.sort() # sort partial matches alphabetically or numerically
            result = exact_matches + partial_matches
            result = list(dict.fromkeys(result)) # deduplicate
            limit = get_autocomplete_limit()
            return jsonify([{"id": v, "label": str(v)} for v in result[:limit]])
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
        query = (s.query(Item).join(Item.group).join(ItemGroup.battery).distinct())
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
        items = query.all()
        if is_autocomplete() and q:
            filtered = [
                i.group.battery.current
                for i in items
                if i.group.battery and i.group.battery.current is not None and q in str(i.group.battery.current)
            ]
            exact_matches = [v for v in filtered if str(v) == q]
            partial_matches = [v for v in filtered if str(v) != q]
            partial_matches.sort() # sort partial matches alphabetically or numerically
            result = exact_matches + partial_matches
            result = list(dict.fromkeys(result)) # deduplicate
            limit = get_autocomplete_limit()
            return jsonify([{"id": v, "label": str(v)} for v in result[:limit]])
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
        query = (s.query(Item).join(Item.group).join(ItemGroup.battery).distinct())
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
        items = query.all()
        if is_autocomplete() and q:
            filtered = [
                i.group.battery.capacity
                for i in items
                if i.group.battery and i.group.battery.capacity is not None and q in str(i.group.battery.capacity)
            ]
            exact_matches = [v for v in filtered if str(v) == q]
            partial_matches = [v for v in filtered if str(v) != q]
            partial_matches.sort() # sort partial matches alphabetically or numerically
            result = exact_matches + partial_matches
            result = list(dict.fromkeys(result)) # deduplicate
            limit = get_autocomplete_limit()
            return jsonify([{"id": v, "label": str(v)} for v in result[:limit]])
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
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
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

            return autocomplete(unique, lambda b: b.charging_type, limit=get_autocomplete_limit())

        return jsonify([item_to_dict(i) for i in filtered])


@app.route("/api/items/bought-place")
@auth.login_required
def search_items_by_bought_place():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        query = s.query(Item).outerjoin(Item.group)
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
        query = query.all()
        filtered = [
            i for i in query if i.bought_place and q in normalize(i.bought_place)
        ]

        if is_autocomplete():
            seen = set()
            unique = []
            for i in filtered:
                bp = i.bought_place
                if bp not in seen:
                    seen.add(bp)
                    unique.append(i)
            result = autocomplete(unique, lambda i: i.bought_place, limit=get_autocomplete_limit())
            return result

        result = [item_to_dict(i) for i in filtered]
        return jsonify(result)


@app.route("/api/items/variant")
@auth.login_required
def search_items_by_variant():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        query = s.query(Item).outerjoin(Item.group)
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
        query = query.all()
        filtered = [
            i for i in query if i.variant and q in normalize(i.variant)]

        if is_autocomplete():
            seen = set()
            unique = []
            for i in filtered:
                col = i.variant
                if col not in seen:
                    seen.add(col)
                    unique.append(i)
            result = autocomplete(unique, lambda i: i.variant, limit=get_autocomplete_limit())
            return result
        return jsonify([item_to_dict(i) for i in filtered])

@app.route("/api/items/color")
@auth.login_required
def search_items_by_color():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        query = s.query(Item).outerjoin(Item.group)
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
        query = query.all()
        filtered = [
            i for i in query if i.color and q in normalize(i.color)]

        if is_autocomplete():
            seen = set()
            unique = []
            for i in filtered:
                col = i.color
                if col not in seen:
                    seen.add(col)
                    unique.append(i)
            result = autocomplete(unique, lambda i: i.color, limit=get_autocomplete_limit())
            return result
        return jsonify([item_to_dict(i) for i in filtered])

@app.route("/api/items/status")
@auth.login_required
def search_items_by_status():
    q = normalize(request.args.get("q", ""))
    with SessionLocal() as s:
        query = s.query(Item).outerjoin(Item.group)
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
        query = query.all()
        filtered = [
            i for i in query if i.status and q in normalize(i.status)]
        if is_autocomplete():
            seen = set()
            unique = []
            for i in filtered:
                col = i.status
                if col not in seen:
                    seen.add(col)
                    unique.append(i)
            result = autocomplete(unique, lambda i: i.status, limit=get_autocomplete_limit())
            return result
        return jsonify([item_to_dict(i) for i in filtered])
    
@app.route("/api/items/price")
@auth.login_required
def search_items_by_price():
    q = request.args.get("q", "")
    with SessionLocal() as s:
        query = s.query(Item).outerjoin(Item.group)
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
        query = query.all()
        if is_autocomplete():
            prices = sorted(
                {
                    i.price
                    for i in query
                    if i.price is not None and q in str(i.price)
                }
            )
            limit = get_autocomplete_limit()
            return jsonify([
                {"id": p, "label": str(p)}
                for p in prices[:limit]
            ])
        return jsonify([item_to_dict(i) for i in query if str(q) in str(i.price)])


@app.route("/api/items/last-seen")
@auth.login_required
def search_items_last_seen():
    q = request.args.get("q")
    with SessionLocal() as s:
        query = s.query(Item).outerjoin(Item.group)
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
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
            limit = get_autocomplete_limit()
            return jsonify([
                {"id": d.isoformat(), "label": d.isoformat()}
                for d in dates[:limit]
            ])
        return jsonify([item_to_dict(i) for i in query if q in str(i.last_seen_date)])


@app.route("/api/items/last-use")
@auth.login_required
def search_items_last_use():
    q = request.args.get("q")
    with SessionLocal() as s:
        query = s.query(Item).outerjoin(Item.group)
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
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
            limit = get_autocomplete_limit()
            return jsonify([
                {"id": d.isoformat(), "label": d.isoformat()}
                for d in dates[:limit]
            ])
        return jsonify([item_to_dict(i) for i in query if q in str(i.last_use_date)])


@app.route("/api/items/acquired")
@auth.login_required
def search_items_acquired():
    q = request.args.get("q")
    with SessionLocal() as s:
        query = s.query(Item).outerjoin(Item.group)
        if not is_Yosh_allowed():
            query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
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
            limit = get_autocomplete_limit()
            return jsonify([
                {"id": d.isoformat(), "label": d.isoformat()}
                for d in dates[:limit]
            ])
        return jsonify([item_to_dict(i) for i in query if q in str(i.acquired_date)])


@app.route("/api/items/id")
@auth.login_required
def search_item_by_id():
    q = request.args.get("q", type=int)
    with SessionLocal() as s:
        if is_autocomplete():
            query = s.query(Item.id).order_by(Item.id.desc())
            limit = get_autocomplete_limit()
            if not is_Yosh_allowed():
                query = query.filter(~Item.group.has(ItemGroup.tags.any(Tag.name.ilike("%+18%"))))
            query = query.limit(limit)
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

    # Keep rsplit for the new location name if it's arriving as a path segment
    name = (data.get("name") or "").rsplit(">", 1)[-1].strip()
    parent_name = (
        (data.get("parent") or "").rsplit(">", 1)[-1].strip()
        if data.get("parent") else None
    )

    if not name:
        return abort(400, "Location name cannot be empty")

    with SessionLocal() as s:
        # 1. Resolve the parent location
        parent = None
        if parent_name:
            # This will now look for "Râches > Yosh's Bedroom" in its entirety
            parent = s.query(Location).filter(Location.name.ilike(parent_name)).first()
            
            if not parent:
                return abort(404, f"The parent location '{parent_name}' does not exist!")
            
        # 2. Find the existing location BY NAME ONLY
        existing = s.query(Location).filter(Location.name.ilike(name)).first()

        if existing:
            # 3. If it exists, update the parent_id
            new_parent_id = parent.id if parent else None
            if parent and would_create_location_cycle(existing, parent):
                return abort(400, "Invalid parent: this would create a location cycle")
            
            if existing.parent_id != new_parent_id:
                existing.parent_id = new_parent_id
                s.commit()
                # Return 200 to JS, meaning "OK, existing item updated"
                return {"id": existing.id, "name": existing.name}, 202
            
            # Return 200, nothing changed
            return {"id": existing.id, "name": existing.name}, 200

        # 4. If it does not exist, create it
        loc = Location(name=name, parent=parent)
        s.add(loc)
        s.commit()

        return {"id": loc.id, "name": loc.name}, 201


@app.route("/api/locations/<int:location_id>", methods=["PUT"])
@auth.login_required
def update_location(location_id):
    if not am_i_admin():
        return abort(400, "You're not admin")

    data = request.json or {}
    # FIX: Use rsplit here too if your frontend sends breadcrumbs/paths
    new_name = (data.get("name") or "").rsplit(">", 1)[-1].strip()

    if not new_name:
        return abort(400, "New name cannot be empty")

    with SessionLocal() as s:
        # 1. Fetch the location by ID (using modern s.get)
        loc = s.get(Location, location_id)
        if not loc:
            return abort(404, "Location not found")

        # 2. Check if another location already has the new name
        existing = s.query(Location).filter(
            Location.name.ilike(new_name), 
            Location.id != location_id
        ).first()
        
        if existing:
            return abort(400, "A location with this name already exists")

        # 3. Update the name
        loc.name = new_name
        s.commit()
        
        # FIX: Return INSIDE the session block to avoid DetachedInstanceError
        return {"id": loc.id, "name": loc.name}, 200

@app.route("/api/item-group", methods=["POST"])
@auth.login_required
def create_or_update_item_group():
    if not am_i_admin():
        return abort(400, "You're not admin")

    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return abort(400, "Item group name is required")

    with SessionLocal() as s:

        # Try to get an existing group by name
        item_group = s.query(ItemGroup).filter(ItemGroup.name.ilike(name)).first()

        # If an ID was provided and it's different from the one found by name, fetch by ID
        group_id = data.get("id")
        if group_id:
            id_group = s.get(ItemGroup, group_id)
            if id_group and id_group != item_group:
                # Prefer the ID group (so edits by ID are respected)
                item_group = id_group

        # If no group exists at all, create a new one
        if not item_group:
            item_group = ItemGroup()
            s.add(item_group)

        # Update all fields
        item_group.name = name
        item_group.instruction = data.get("instruction")

        # Battery
        battery = get_or_create_battery(
            s,
            voltage=data.get("voltage"),
            current=data.get("current"),
            capacity=data.get("capacity"),
            charging_type=data.get("charging_type"),
        )
        item_group.battery = battery

        # Tags
        tags = get_or_create_tags(s, data.get("tags", []))
        item_group.tags = tags

        s.commit()

        return {
            "id": item_group.id,
            "updated": True,
        }, 200


# --------------------
# FURNITURE PHOTOS / "ICI JAMY"
# --------------------

@app.route("/uploads/furniture/<path:filename>")
@auth.login_required
def serve_furniture_photo(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/finder")
@auth.login_required
def furniture_finder():
    location_id = request.args.get("location_id", type=int)
    with SessionLocal() as s:
        maps = (
            s.query(FurnitureMap)
            .options(*furniture_map_options())
            .order_by(FurnitureMap.id)
            .all()
        )
        chain_ids = []
        if location_id:
            loc = s.get(Location, location_id)
            if loc:
                chain_ids = location_chain_ids(loc)
        payload = [
            map_to_dict(m, highlight=pick_highlight(m, chain_ids) if chain_ids else None)
            for m in maps
        ]
        payload.sort(key=lambda m: (m["highlight"] is None, m["id"]))
        return jsonify({"maps": payload})


@app.route("/api/furniture-maps", methods=["GET"])
@auth.login_required
def list_furniture_maps():
    location_id = request.args.get("location_id", type=int)
    with SessionLocal() as s:
        q = s.query(FurnitureMap).options(*furniture_map_options())
        if location_id:
            q = q.filter(FurnitureMap.location_id == location_id)
        maps = q.order_by(FurnitureMap.id).all()
        return jsonify([map_to_dict(m) for m in maps])


@app.route("/api/furniture-maps", methods=["POST"])
@auth.login_required
def create_furniture_map():
    if not am_i_admin():
        return abort(400, "You're not admin")

    name = (request.form.get("name") or "").strip()
    location_raw = (request.form.get("location") or "").strip()
    location_id = request.form.get("location_id", type=int)
    photo = request.files.get("photo")
    mask = request.files.get("mask")

    if not name:
        return abort(400, "Furniture photo name is required")
    if not photo or not photo.filename:
        return abort(400, "A furniture photo is required")

    with SessionLocal() as s:
        loc = s.get(Location, location_id) if location_id else resolve_location_by_path(s, location_raw)
        if not loc:
            return abort(400, "Location not found — save the location first and keep its ID")

        photo_name = save_upload(photo, "photo")
        if not photo_name:
            return abort(400, "Photo must be jpg, png, webp, or gif")

        photo_path = os.path.join(UPLOAD_DIR, photo_name)
        with Image.open(photo_path) as im:
            width, height = im.size

        fmap = FurnitureMap(
            name=name,
            location_id=loc.id,
            photo_filename=photo_name,
            width=width,
            height=height,
        )
        s.add(fmap)
        s.flush()

        zone_count = 0
        if mask and mask.filename:
            mask_name = save_upload(mask, "mask")
            if not mask_name:
                delete_upload(photo_name)
                return abort(400, "Mask must be jpg, png, webp, or gif")
            fmap.mask_filename = mask_name
            zone_count = apply_mask_to_map(s, fmap, os.path.join(UPLOAD_DIR, mask_name))

        s.commit()
        return {"id": fmap.id, "zones": zone_count}, 201


@app.route("/api/furniture-maps/<int:map_id>/mask", methods=["POST"])
@auth.login_required
def upload_furniture_mask(map_id):
    if not am_i_admin():
        return abort(400, "You're not admin")
    mask = request.files.get("mask")
    if not mask or not mask.filename:
        return abort(400, "A color-mask image is required")

    with SessionLocal() as s:
        fmap = s.get(FurnitureMap, map_id)
        if not fmap:
            return abort(404, "Furniture photo not found")
        mask_name = save_upload(mask, "mask")
        if not mask_name:
            return abort(400, "Mask must be jpg, png, webp, or gif")
        old_mask = fmap.mask_filename
        fmap.mask_filename = mask_name
        zone_count = apply_mask_to_map(s, fmap, os.path.join(UPLOAD_DIR, mask_name))
        s.commit()
        if old_mask and old_mask != mask_name:
            delete_upload(old_mask)
        return {"id": map_id, "zones": zone_count}, 200


@app.route("/api/furniture-maps/<int:map_id>", methods=["DELETE"])
@auth.login_required
def delete_furniture_map(map_id):
    if not am_i_admin():
        return abort(400, "You're not admin")
    with SessionLocal() as s:
        fmap = s.get(FurnitureMap, map_id)
        if not fmap:
            return abort(404, "Furniture photo not found")
        photo_name = fmap.photo_filename
        mask_name = fmap.mask_filename
        s.delete(fmap)
        s.commit()
    delete_upload(photo_name)
    delete_upload(mask_name)
    return {"deleted": True, "id": map_id}, 200


@app.route("/api/furniture-zones/<int:zone_id>", methods=["PUT"])
@auth.login_required
def update_furniture_zone(zone_id):
    if not am_i_admin():
        return abort(400, "You're not admin")
    data = request.json or {}
    with SessionLocal() as s:
        zone = s.get(FurnitureZone, zone_id)
        if not zone:
            return abort(404, "Zone not found")
        location_id = data.get("location_id")
        location_raw = data.get("location")
        if location_raw == "" and not location_id:
            zone.location_id = None
            s.commit()
            return {"id": zone.id, "location_id": None}, 200
        if location_id:
            loc = s.get(Location, int(location_id))
        else:
            loc = resolve_location_by_path(s, location_raw or "")
        if not loc:
            return abort(400, "Location not found")
        zone.location_id = loc.id
        s.commit()
        return {"id": zone.id, "location_id": loc.id, "location": loc.name}, 200


if __name__ == "__main__":
    app.run(debug=False)
