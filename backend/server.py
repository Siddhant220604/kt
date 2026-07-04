"""FastAPI application entry point for the wholesale disposal goods platform."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import re
import uuid
import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Query, Header
from fastapi.responses import Response as FastResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from models import (
    RegisterRequest, LoginRequest, UserPublic,
    CategoryCreate, Category,
    ProductCreate, ProductUpdate, Product,
    OrderCreate, Order, OrderItem, OrderStatusUpdate,
    ReviewCreate, Review,
    new_id, now_iso,
)
from auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    get_current_user, require_admin,
)
from storage import init_storage, put_object, get_object, APP_NAME
from seed import seed_data


# ---------- Setup ----------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Wholesale Disposal API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


def _tier_price(base_price: float, tiers: list[dict], qty: int) -> float:
    """Return per-unit price for given qty using descending tier match."""
    if not tiers:
        return base_price
    # Sort by min_qty descending, pick first tier where qty >= min_qty
    for t in sorted(tiers, key=lambda x: x["min_qty"], reverse=True):
        if qty >= t["min_qty"]:
            return float(t["price"])
    return base_price


def _set_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=60 * 60 * 24, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=60 * 60 * 24 * 7, path="/")


# ---------- Health ----------
@api.get("/")
async def root():
    return {"status": "ok", "service": "wholesale-disposal"}


# ---------- Auth ----------
@api.post("/auth/register")
async def register(payload: RegisterRequest, response: Response):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = {
        "id": new_id(),
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "company": payload.company or "",
        "role": "buyer",
        "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"])
    _set_cookies(response, access, refresh)
    return {"user": _clean(dict(user)), "access_token": access}


@api.post("/auth/login")
async def login(payload: LoginRequest, response: Response):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"])
    _set_cookies(response, access, refresh)
    return {"user": _clean(dict(user)), "access_token": access}


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return _clean(dict(user))


# ---------- Categories ----------
@api.get("/categories")
async def list_categories():
    docs = await db.categories.find({}, {"_id": 0}).sort("name", 1).to_list(1000)
    return docs


@api.post("/categories")
async def create_category(payload: CategoryCreate, _=Depends(require_admin)):
    slug = payload.slug or _slugify(payload.name)
    if await db.categories.find_one({"slug": slug}):
        raise HTTPException(status_code=400, detail="Slug already exists")
    cat = Category(name=payload.name, slug=slug, description=payload.description or "").model_dump()
    await db.categories.insert_one(cat)
    return cat


@api.put("/categories/{cid}")
async def update_category(cid: str, payload: CategoryCreate, _=Depends(require_admin)):
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and not updates.get("slug"):
        updates["slug"] = _slugify(updates["name"])
    res = await db.categories.update_one({"id": cid}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return await db.categories.find_one({"id": cid}, {"_id": 0})


@api.delete("/categories/{cid}")
async def delete_category(cid: str, _=Depends(require_admin)):
    await db.categories.delete_one({"id": cid})
    return {"ok": True}


# ---------- Products ----------
@api.get("/products")
async def list_products(
    q: Optional[str] = None,
    category_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    max_moq: Optional[int] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    skip: int = 0,
):
    query: dict = {}
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"sku": {"$regex": q, "$options": "i"}},
        ]
    if category_id:
        query["category_id"] = category_id
    if min_price is not None or max_price is not None:
        price_q = {}
        if min_price is not None:
            price_q["$gte"] = min_price
        if max_price is not None:
            price_q["$lte"] = max_price
        query["base_price"] = price_q
    if max_moq is not None:
        query["moq"] = {"$lte": max_moq}
    if is_active is not None:
        query["is_active"] = is_active
    else:
        query["is_active"] = True

    total = await db.products.count_documents(query)
    docs = await db.products.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "items": docs}


@api.get("/products/{pid}")
async def get_product(pid: str):
    doc = await db.products.find_one({"id": pid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return doc


@api.post("/products")
async def create_product(payload: ProductCreate, _=Depends(require_admin)):
    prod = Product(**payload.model_dump()).model_dump()
    await db.products.insert_one(prod)
    return prod


@api.put("/products/{pid}")
async def update_product(pid: str, payload: ProductUpdate, _=Depends(require_admin)):
    updates = payload.model_dump(exclude_unset=True)
    if "price_tiers" in updates and updates["price_tiers"] is not None:
        updates["price_tiers"] = [t if isinstance(t, dict) else t.model_dump() for t in updates["price_tiers"]]
    updates["updated_at"] = now_iso()
    res = await db.products.update_one({"id": pid}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return await db.products.find_one({"id": pid}, {"_id": 0})


@api.delete("/products/{pid}")
async def delete_product(pid: str, _=Depends(require_admin)):
    await db.products.delete_one({"id": pid})
    return {"ok": True}


# ---------- Uploads ----------
@api.post("/uploads")
async def upload_file(file: UploadFile = File(...), user=Depends(require_admin)):
    ext = (file.filename or "bin").rsplit(".", 1)[-1].lower()
    if ext not in {"jpg", "jpeg", "png", "webp", "gif"}:
        raise HTTPException(status_code=400, detail="Only image files allowed")
    path = f"{APP_NAME}/products/{user['id']}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    try:
        result = put_object(path, data, file.content_type or "image/jpeg")
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")
    doc = {
        "id": new_id(),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "uploaded_by": user["id"],
        "is_deleted": False,
        "created_at": now_iso(),
    }
    await db.files.insert_one(doc)
    return {"storage_path": result["path"], "url": f"/api/files/{result['path']}"}


@api.get("/files/{path:path}")
async def serve_file(path: str):
    # Publicly serve product images
    try:
        data, content_type = get_object(path)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")
    return FastResponse(content=data, media_type=content_type)


# ---------- Orders ----------
async def _generate_order_number() -> str:
    count = await db.orders.count_documents({})
    return f"ORD-{datetime.now(timezone.utc).strftime('%Y%m')}-{count + 1:05d}"


@api.post("/orders")
async def create_order(payload: OrderCreate, user=Depends(get_current_user)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    order_items: list[OrderItem] = []
    subtotal = 0.0
    for it in payload.items:
        prod = await db.products.find_one({"id": it.product_id})
        if not prod:
            raise HTTPException(status_code=400, detail=f"Product not found: {it.product_id}")
        if it.quantity < prod.get("moq", 1):
            raise HTTPException(status_code=400, detail=f"{prod['name']} requires MOQ of {prod['moq']}")
        if it.quantity > prod.get("stock", 0):
            raise HTTPException(status_code=400, detail=f"{prod['name']} — insufficient stock (available: {prod.get('stock', 0)})")
        unit_price = _tier_price(prod["base_price"], prod.get("price_tiers", []), it.quantity)
        item_subtotal = round(unit_price * it.quantity, 2)
        subtotal += item_subtotal
        order_items.append(OrderItem(
            product_id=prod["id"], product_name=prod["name"], sku=prod["sku"],
            unit_price=unit_price, quantity=it.quantity, subtotal=item_subtotal,
        ))

    order = Order(
        order_number=await _generate_order_number(),
        user_id=user["id"],
        user_email=user["email"],
        items=order_items,
        subtotal=round(subtotal, 2),
        total=round(subtotal, 2),
        shipping_address=payload.shipping_address,
        notes=payload.notes or "",
    ).model_dump()
    await db.orders.insert_one(order)

    # Decrement stock
    for it in payload.items:
        await db.products.update_one({"id": it.product_id}, {"$inc": {"stock": -it.quantity}})

    return order


@api.get("/orders")
async def list_orders(user=Depends(get_current_user)):
    docs = await db.orders.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@api.get("/orders/{oid}")
async def get_order(oid: str, user=Depends(get_current_user)):
    doc = await db.orders.find_one({"id": oid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.get("role") != "admin" and doc["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not allowed")
    return doc


# ---------- Admin Orders ----------
@api.get("/admin/orders")
async def admin_list_orders(status: Optional[str] = None, _=Depends(require_admin)):
    query = {}
    if status:
        query["status"] = status
    docs = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return docs


@api.put("/admin/orders/{oid}/status")
async def admin_update_order_status(oid: str, payload: OrderStatusUpdate, _=Depends(require_admin)):
    valid = {"pending", "confirmed", "shipped", "delivered", "cancelled"}
    if payload.status not in valid:
        raise HTTPException(status_code=400, detail="Invalid status")
    res = await db.orders.update_one(
        {"id": oid},
        {"$set": {"status": payload.status, "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return await db.orders.find_one({"id": oid}, {"_id": 0})


# ---------- Reviews ----------
@api.get("/reviews")
async def list_reviews(product_id: Optional[str] = None, approved_only: bool = True):
    query = {}
    if product_id:
        query["product_id"] = product_id
    if approved_only:
        query["approved"] = True
    docs = await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@api.post("/reviews")
async def create_review(payload: ReviewCreate, user=Depends(get_current_user)):
    # Verified buyer: must have a delivered order containing this product
    order = await db.orders.find_one({
        "id": payload.order_id, "user_id": user["id"], "status": "delivered",
        "items.product_id": payload.product_id,
    })
    if not order:
        raise HTTPException(status_code=400, detail="You can only review products from delivered orders")
    if await db.reviews.find_one({"user_id": user["id"], "product_id": payload.product_id, "order_id": payload.order_id}):
        raise HTTPException(status_code=400, detail="You have already reviewed this item")
    review = Review(
        product_id=payload.product_id, order_id=payload.order_id,
        user_id=user["id"], user_name=user["name"],
        rating=payload.rating, title=payload.title, comment=payload.comment,
        approved=False,
    ).model_dump()
    await db.reviews.insert_one(review)
    return review


@api.get("/admin/reviews")
async def admin_list_reviews(status: Optional[str] = None, _=Depends(require_admin)):
    query = {}
    if status == "pending":
        query["approved"] = False
    elif status == "approved":
        query["approved"] = True
    docs = await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return docs


@api.put("/admin/reviews/{rid}/moderate")
async def admin_moderate_review(rid: str, approve: bool = True, _=Depends(require_admin)):
    if approve:
        review = await db.reviews.find_one_and_update(
            {"id": rid}, {"$set": {"approved": True}}, return_document=True,
        )
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        # Recompute product rating aggregate
        product_id = review["product_id"]
        approved = await db.reviews.find({"product_id": product_id, "approved": True}).to_list(10000)
        if approved:
            avg = round(sum(r["rating"] for r in approved) / len(approved), 2)
            await db.products.update_one(
                {"id": product_id},
                {"$set": {"rating_avg": avg, "rating_count": len(approved)}},
            )
        return {"ok": True}
    else:
        await db.reviews.delete_one({"id": rid})
        return {"ok": True, "deleted": True}


# ---------- Admin Analytics ----------
@api.get("/admin/analytics")
async def admin_analytics(_=Depends(require_admin)):
    total_orders = await db.orders.count_documents({})
    pending_orders = await db.orders.count_documents({"status": "pending"})
    total_products = await db.products.count_documents({})
    total_users = await db.users.count_documents({"role": "buyer"})

    # Revenue from all non-cancelled orders
    pipeline = [
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}}},
    ]
    rev_res = await db.orders.aggregate(pipeline).to_list(1)
    total_revenue = rev_res[0]["total"] if rev_res else 0.0

    # Top products by units sold
    top_pipe = [
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_id",
            "name": {"$first": "$items.product_name"},
            "units": {"$sum": "$items.quantity"},
            "revenue": {"$sum": "$items.subtotal"},
        }},
        {"$sort": {"units": -1}},
        {"$limit": 5},
    ]
    top_products = await db.orders.aggregate(top_pipe).to_list(5)

    recent = await db.orders.find({}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)

    return {
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "total_products": total_products,
        "total_users": total_users,
        "total_revenue": round(total_revenue, 2),
        "top_products": top_products,
        "recent_orders": recent,
    }


# ---------- App wiring ----------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.products.create_index("id", unique=True)
    await db.products.create_index("sku")
    await db.categories.create_index("id", unique=True)
    await db.categories.create_index("slug", unique=True)
    await db.orders.create_index("id", unique=True)
    await db.orders.create_index([("user_id", 1), ("created_at", -1)])
    await db.reviews.create_index("id", unique=True)
    try:
        init_storage()
    except Exception as e:
        logger.warning(f"Storage init warning: {e}")
    await seed_data(db)
    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown():
    client.close()
