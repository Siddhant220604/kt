"""Seed sample categories, products and default admin."""
import os
import logging
from datetime import datetime, timezone
from auth import hash_password
from models import Category, Product, PriceTier, new_id, now_iso

logger = logging.getLogger(__name__)


SAMPLE_CATEGORIES = [
    {"name": "Food Containers", "slug": "food-containers", "description": "Takeout, meal prep and food-safe disposable containers."},
    {"name": "Cups & Lids", "slug": "cups-lids", "description": "Paper, foam and PLA cups plus matching lids."},
    {"name": "Cutlery", "slug": "cutlery", "description": "Compostable and plastic disposable cutlery."},
    {"name": "Napkins & Towels", "slug": "napkins-towels", "description": "Bulk napkins, paper towels and dispensers."},
    {"name": "Cleaning Supplies", "slug": "cleaning", "description": "Bulk gloves, wipes and janitorial disposables."},
]


def _product(name, cat_id, sku, unit, price, moq, stock, tiers, img, desc):
    return Product(
        name=name, description=desc, category_id=cat_id, sku=sku, unit=unit,
        base_price=price, moq=moq, stock=stock,
        price_tiers=[PriceTier(**t) for t in tiers],
        images=[img],
    ).model_dump()


async def seed_data(db):
    # Admin
    admin_email = os.environ["ADMIN_EMAIL"]
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing_admin = await db.users.find_one({"email": admin_email})
    if not existing_admin:
        await db.users.insert_one({
            "id": new_id(),
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Store Admin",
            "role": "admin",
            "company": "Wholesale HQ",
            "created_at": now_iso(),
        })
        logger.info(f"Seeded admin: {admin_email}")
    else:
        # Rehash if password was changed via env
        from auth import verify_password
        if not verify_password(admin_password, existing_admin.get("password_hash", "")):
            await db.users.update_one(
                {"email": admin_email},
                {"$set": {"password_hash": hash_password(admin_password)}},
            )

    # Buyer test user
    buyer_email = "buyer@wholesale.com"
    existing_buyer = await db.users.find_one({"email": buyer_email})
    if not existing_buyer:
        await db.users.insert_one({
            "id": new_id(),
            "email": buyer_email,
            "password_hash": hash_password("buyer123"),
            "name": "Sample Buyer",
            "role": "buyer",
            "company": "Acme Reseller Co.",
            "created_at": now_iso(),
        })

    if await db.categories.count_documents({}) > 0:
        return  # already seeded

    cat_docs = []
    cat_map = {}
    for c in SAMPLE_CATEGORIES:
        cat = Category(**c).model_dump()
        cat_docs.append(cat)
        cat_map[c["slug"]] = cat["id"]
    await db.categories.insert_many(cat_docs)

    p_img_1 = "https://images.unsplash.com/photo-1597317292822-d0fa5be43aea"
    p_img_2 = "https://images.unsplash.com/photo-1654078054613-a56cfcabdb84"
    p_img_3 = "https://images.unsplash.com/photo-1597974828431-9078248d8cc9"

    products = [
        _product("Kraft Takeout Box — 26oz", cat_map["food-containers"], "FC-KTB-26",
                 "carton (200 pcs)", 42.00, 5, 500,
                 [{"min_qty": 5, "price": 42.00}, {"min_qty": 20, "price": 39.50}, {"min_qty": 100, "price": 36.25}],
                 p_img_2,
                 "Grease-resistant kraft paper takeout boxes with locking lids. 26oz capacity, 200 units per carton. Ideal for restaurants and catering."),
        _product("Bagasse Clamshell — 9\"", cat_map["food-containers"], "FC-BGC-09",
                 "carton (200 pcs)", 68.00, 3, 320,
                 [{"min_qty": 3, "price": 68.00}, {"min_qty": 15, "price": 63.90}, {"min_qty": 60, "price": 58.75}],
                 p_img_1,
                 "100% compostable bagasse (sugarcane) clamshells, three compartments. Microwave-safe."),
        _product("PLA Cold Cup — 16oz", cat_map["cups-lids"], "CL-PLA-16",
                 "sleeve (50 pcs)", 12.50, 10, 900,
                 [{"min_qty": 10, "price": 12.50}, {"min_qty": 40, "price": 11.20}, {"min_qty": 200, "price": 9.90}],
                 p_img_3,
                 "Crystal-clear PLA cold cups made from plant-based bioplastics. 16oz, sleeve of 50."),
        _product("Double-Wall Paper Cup — 12oz", cat_map["cups-lids"], "CL-DWP-12",
                 "carton (500 pcs)", 78.00, 2, 240,
                 [{"min_qty": 2, "price": 78.00}, {"min_qty": 10, "price": 72.50}, {"min_qty": 40, "price": 66.90}],
                 p_img_2,
                 "Double-wall insulated paper cups. No sleeve required. Perfect for hot beverages."),
        _product("Wooden Cutlery Kit", cat_map["cutlery"], "CT-WCK-01",
                 "case (1000 kits)", 96.00, 2, 180,
                 [{"min_qty": 2, "price": 96.00}, {"min_qty": 8, "price": 89.90}, {"min_qty": 30, "price": 82.50}],
                 p_img_1,
                 "Fork, knife, spoon and napkin — birchwood cutlery kit individually wrapped."),
        _product("CPLA Compostable Fork", cat_map["cutlery"], "CT-CPF-01",
                 "case (1000 pcs)", 54.00, 4, 420,
                 [{"min_qty": 4, "price": 54.00}, {"min_qty": 16, "price": 49.80}, {"min_qty": 60, "price": 45.20}],
                 p_img_3,
                 "Heat-resistant CPLA compostable forks. Case of 1000."),
        _product("2-Ply Dinner Napkin", cat_map["napkins-towels"], "NT-2PN-01",
                 "case (3000 pcs)", 62.00, 2, 340,
                 [{"min_qty": 2, "price": 62.00}, {"min_qty": 10, "price": 57.90}, {"min_qty": 40, "price": 52.50}],
                 p_img_2,
                 "Soft 2-ply dinner napkins, unbleached. Case of 3000."),
        _product("Nitrile Gloves — Powder Free", cat_map["cleaning"], "CS-NGP-01",
                 "case (10 boxes x 100)", 89.00, 1, 220,
                 [{"min_qty": 1, "price": 89.00}, {"min_qty": 5, "price": 82.00}, {"min_qty": 20, "price": 74.50}],
                 p_img_1,
                 "Food-safe nitrile gloves, powder-free, textured fingertips. Case of 10 boxes (100 gloves each)."),
    ]
    await db.products.insert_many(products)
    logger.info(f"Seeded {len(products)} products across {len(cat_docs)} categories")
