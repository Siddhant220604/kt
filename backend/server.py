from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query, BackgroundTasks, Request
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import List, Optional, Any, Dict
import uuid
from datetime import datetime, timezone, timedelta
import asyncio
import csv
import hashlib
import hmac
import secrets
import io
import re
import base64
import time
import qrcode
import requests

import auth
import audit
import dependencies
import security
from config.whatsapp import get_whatsapp_config
from services.whatsapp_service import build_whatsapp_number, send_text_message
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'kiran_traders')]

DEFAULT_BUSINESS_EMAIL = 'kirantraders1996@gmail.com'
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://kirantraders.vercel.app').rstrip('/')

RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')

WHATSAPP_DEFAULT_COUNTRY_CODE = os.environ.get('WHATSAPP_DEFAULT_COUNTRY_CODE', '+91')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', '')
WHATSAPP_API_VERSION = os.environ.get('WHATSAPP_API_VERSION', 'v23.0')

GOOGLE_REVIEW_LINK = os.environ.get('GOOGLE_REVIEW_LINK', '')
REVIEW_REQUEST_DELAY_SECONDS = int(os.environ.get('REVIEW_REQUEST_DELAY_SECONDS', str(24 * 60 * 60)))

# Strong references to fire-and-forget asyncio tasks (e.g. the delayed review-request
# job) so they aren't garbage-collected mid-flight; entries are discarded on completion.
_background_asyncio_tasks: set = set()

app = FastAPI(title="Kiran Traders API")
api_router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# ------------------ HELPERS ------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# Small in-process TTL cache for read-heavy public endpoints (settings/categories/banners
# are fetched on nearly every page load). Explicitly invalidated by the relevant admin
# mutations below rather than relying on TTL alone, so edits show up immediately.
_cache: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 30


def cache_get(key: str) -> Any:
    entry = _cache.get(key)
    if entry and entry[0] > time.monotonic():
        return entry[1]
    return None


def cache_set(key: str, value: Any, ttl: int = CACHE_TTL_SECONDS) -> None:
    _cache[key] = (time.monotonic() + ttl, value)


def cache_invalidate(*keys: str) -> None:
    for k in keys:
        _cache.pop(k, None)

def serialize_doc(doc: Any) -> Any:
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(d) for d in doc]
    if isinstance(doc, dict):
        d = {}
        for k, v in doc.items():
            if k == '_id':
                continue
            if isinstance(v, datetime):
                d[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                d[k] = serialize_doc(v)
            else:
                d[k] = v
        return d
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc

hash_password = auth.hash_password
verify_password = auth.verify_password
create_token = auth.create_access_token
require_admin = dependencies.require_admin

def gen_order_id() -> str:
    ts = datetime.now(timezone.utc).strftime('%Y%m%d')
    rand = uuid.uuid4().hex[:6].upper()
    return f"KT{ts}{rand}"


def generate_razorpay_signature(payload: str, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()


def verify_razorpay_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    expected = generate_razorpay_signature(f"{order_id}|{payment_id}", secret)
    return hmac.compare_digest(expected, signature or '')

# ------------------ MODELS ------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChangeEmailRequest(BaseModel):
    email: EmailStr

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class CategoryIn(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = ''
    icon: Optional[str] = 'Package'
    image: Optional[str] = ''
    order: int = 0

class PriceTier(BaseModel):
    min_qty: int = Field(gt=0)
    price: float = Field(gt=0)

class ProductIn(BaseModel):
    name: str
    slug: Optional[str] = None
    category_id: str
    description: str = ''
    short_description: Optional[str] = ''
    size: Optional[str] = ''
    unit: Optional[str] = 'piece'
    price: float
    compare_price: Optional[float] = 0
    moq: int = 1
    stock: int = 0
    images: List[str] = []
    specs: Optional[Dict[str, str]] = {}
    featured: bool = False
    active: bool = True
    tags: List[str] = []
    # Bulk/wholesale pricing: e.g. [{min_qty: 10, price: 95}, {min_qty: 50, price: 90}] means
    # the base `price` applies below 10 units, 95 from 10-49, 90 from 50+. Kept sorted by
    # min_qty ascending so effective_unit_price() can just walk it front-to-back.
    price_tiers: List[PriceTier] = []

    @field_validator('price_tiers')
    @classmethod
    def validate_price_tiers(cls, tiers: List['PriceTier']) -> List['PriceTier']:
        return sorted(tiers, key=lambda t: t.min_qty)

    @field_validator('images')
    @classmethod
    def validate_images(cls, images: List[str]) -> List[str]:
        if len(images) > 10:
            raise ValueError('A product can have at most 10 images')
        # Base64 data-URI uploads only - a ~2MB decoded image is roughly this many
        # base64 characters. Plain image URLs (http/https) are always far shorter and
        # pass through untouched; the frontend already caps uploads at 1MB client-side,
        # this is the server-side backstop for direct API callers.
        max_data_uri_chars = 2_800_000
        for img in images:
            if img.startswith('data:') and len(img) > max_data_uri_chars:
                raise ValueError('Each product image must be under ~2MB')
        return images

class CartItem(BaseModel):
    product_id: str
    name: str
    price: float
    image: Optional[str] = ''
    size: Optional[str] = ''
    unit: Optional[str] = 'piece'
    quantity: int
    moq: int = 1

class AddressIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mobile: str = Field(min_length=1, max_length=20)
    email: EmailStr
    address_line1: str = Field(min_length=1, max_length=300)
    address_line2: Optional[str] = Field('', max_length=300)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    pincode: str = Field(min_length=1, max_length=10)
    landmark: Optional[str] = Field('', max_length=200)
    gst_number: Optional[str] = Field('', max_length=20)

class OrderIn(BaseModel):
    items: List[CartItem]
    address: AddressIn
    payment_method: str  # cod | upi | bank_transfer | online
    notes: Optional[str] = Field('', max_length=1000)
    coupon_code: Optional[str] = Field('', max_length=50)

class CartSyncItem(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int

class CartSyncIn(BaseModel):
    mobile: str = Field(min_length=10, max_length=15)
    name: Optional[str] = Field('', max_length=200)
    items: List[CartSyncItem] = []
    subtotal: float = 0

class PaymentCreateOrderRequest(BaseModel):
    order_id: str
    amount: Optional[int] = None
    currency: str = 'INR'
    notes: Optional[Dict[str, Any]] = None

class PaymentVerifyRequest(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class OrderStatusUpdate(BaseModel):
    status: str  # pending | confirmed | processing | packed | out for delivery | delivered | cancelled
    tracking_note: Optional[str] = ''

class TrackOrderRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=50)
    mobile: str = Field(min_length=1, max_length=20)

class CustomerOtpRequestIn(BaseModel):
    mobile: str = Field(min_length=10, max_length=15)

class CustomerOtpVerifyIn(BaseModel):
    mobile: str = Field(min_length=10, max_length=15)
    otp: str = Field(min_length=4, max_length=8)

class WhatsAppMessageIn(BaseModel):
    message: str
    mobile: Optional[str] = None

class CouponIn(BaseModel):
    code: str
    type: str = 'percent'  # percent | flat
    value: float
    min_order: float = 0
    max_discount: Optional[float] = 0
    expiry: Optional[str] = ''
    active: bool = True
    usage_limit: int = 0

class CouponValidate(BaseModel):
    code: str = Field(max_length=50)
    subtotal: float

class BannerIn(BaseModel):
    title: str
    subtitle: Optional[str] = ''
    image: str = ''
    link: Optional[str] = ''
    cta_text: Optional[str] = 'Shop Now'
    active: bool = True
    order: int = 0

class ReviewIn(BaseModel):
    product_id: str
    name: str = Field(min_length=1, max_length=200)
    rating: int
    title: Optional[str] = Field('', max_length=300)
    comment: str = Field(min_length=1, max_length=3000)
    order_id: Optional[str] = ''

class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field('', max_length=200)
    mobile: str = Field(min_length=1, max_length=20)
    subject: Optional[str] = Field('', max_length=300)
    message: str = Field(min_length=1, max_length=3000)

class SettingsIn(BaseModel):
    business_name: Optional[str] = None
    tagline: Optional[str] = None
    address: Optional[str] = None
    landmark: Optional[str] = None
    phone: Optional[str] = None
    phone2: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    upi_id: Optional[str] = None
    upi_qr: Optional[str] = None
    logo: Optional[str] = None
    bank_details: Optional[str] = None
    hours: Optional[str] = None
    gstin: Optional[str] = None
    tax_rate: Optional[float] = None
    shipping_flat: Optional[float] = None
    free_shipping_above: Optional[float] = None

# ------------------ AUTH ROUTES ------------------

@api_router.post('/auth/login')
async def admin_login(req: LoginRequest, request: Request):
    dependencies.check_login_rate_limit(request)
    u = await db.users.find_one({'email': req.email.lower()})
    if not u or not verify_password(req.password, u.get('password_hash', '')):
        dependencies.record_failed_login(request)
        raise HTTPException(status_code=401, detail='Invalid email or password')
    dependencies.clear_failed_logins(request)
    token = create_token(u['id'], u['email'], u.get('role', 'admin'), u.get('token_version', 0))
    await audit.record_audit(db, u['email'], security.get_client_ip(request), 'admin_login', u['id'])
    return {'token': token, 'user': {'id': u['id'], 'email': u['email'], 'name': u.get('name', ''), 'role': u.get('role', 'admin')}}

@api_router.get('/auth/me')
async def me(payload: Dict = Depends(require_admin)):
    u = await db.users.find_one({'id': payload['sub']})
    if not u:
        raise HTTPException(status_code=404, detail='User not found')
    return {'id': u['id'], 'email': u['email'], 'name': u.get('name', ''), 'role': u.get('role', 'admin')}

@api_router.get('/profile')
async def get_profile(payload: Dict = Depends(require_admin)):
    u = await db.users.find_one({'id': payload['sub']})
    if not u:
        raise HTTPException(status_code=404, detail='User not found')
    return {'name': u.get('name', ''), 'email': u['email'], 'role': u.get('role', 'admin')}

@api_router.get('/login-history')
async def get_login_history(payload: Dict = Depends(require_admin)):
    logs = await db.audit_logs.find({'admin_email': payload.get('email'), 'action': 'admin_login'}, {'_id': 0}).sort('timestamp', -1).limit(50).to_list(50)
    return logs

@api_router.get('/admin/profile')
async def get_admin_profile(payload: Dict = Depends(require_admin)):
    u = await db.users.find_one({'id': payload['sub']}, {'_id': 0, 'password_hash': 0, 'token_version': 0})
    if not u:
        raise HTTPException(status_code=404, detail='User not found')
    return {'id': u['id'], 'email': u['email'], 'name': u.get('name', ''), 'role': u.get('role', 'admin')}

@api_router.get('/admin/login-history')
async def get_admin_login_history(payload: Dict = Depends(require_admin)):
    logs = await db.audit_logs.find({'admin_email': payload.get('email'), 'action': 'admin_login'}, {'_id': 0}).sort('timestamp', -1).limit(50).to_list(50)
    return logs

@api_router.post('/admin/profile/email')
async def change_admin_email(req: ChangeEmailRequest, request: Request, payload: Dict = Depends(require_admin)):
    email = security.sanitize_value(req.email).lower()
    if await db.users.find_one({'email': email}):
        raise HTTPException(status_code=400, detail='Email already in use')
    result = await db.users.update_one({'id': payload['sub']}, {'$set': {'email': email}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail='User not found')
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'change_email', payload['sub'], {'new_email': email})
    return {'ok': True, 'email': email}

@api_router.post('/admin/profile/password')
async def change_admin_password(req: ChangePasswordRequest, request: Request, payload: Dict = Depends(require_admin)):
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail='New password and confirmation do not match')
    u = await db.users.find_one({'id': payload['sub']})
    if not u or not auth.verify_password(req.current_password, u.get('password_hash', '')):
        raise HTTPException(status_code=401, detail='Invalid email or password')
    hashed = auth.hash_password(req.new_password)
    # Bump token_version so any other still-logged-in session (e.g. an attacker who had the
    # old password) is invalidated immediately - then issue a fresh token for *this* session
    # so the admin isn't logged out by their own password change.
    new_token_version = u.get('token_version', 0) + 1
    await db.users.update_one({'id': payload['sub']}, {'$set': {'password_hash': hashed, 'token_version': new_token_version}})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'change_password', payload['sub'])
    new_token = create_token(u['id'], u['email'], u.get('role', 'admin'), new_token_version)
    return {'ok': True, 'token': new_token}

@api_router.post('/admin/profile/logout-all')
async def logout_all_admin_devices(request: Request, payload: Dict = Depends(require_admin)):
    user = await db.users.find_one({'id': payload['sub']})
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    token_version = user.get('token_version', 0) + 1
    await db.users.update_one({'id': payload['sub']}, {'$set': {'token_version': token_version}})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'logout_all_devices', payload['sub'])
    return {'ok': True}

# ------------------ CATEGORIES ------------------

def slugify(s: str) -> str:
    return re.sub(r'-+', '-', ''.join(c if c.isalnum() else '-' for c in s.lower())).strip('-')


async def unique_slug(collection, base_slug: str, exclude_id: Optional[str] = None) -> str:
    """Appends -2, -3, ... to base_slug until it doesn't collide with another document,
    so two products/categories with the same (or similarly-named) title don't silently
    make one of them unreachable by its /slug URL."""
    slug = base_slug
    n = 1
    while True:
        q: Dict = {'slug': slug}
        if exclude_id:
            q['id'] = {'$ne': exclude_id}
        if not await collection.find_one(q, {'_id': 0, 'id': 1}):
            return slug
        n += 1
        slug = f'{base_slug}-{n}'

@api_router.get('/categories')
async def list_categories():
    cached = cache_get('categories')
    if cached is not None:
        return cached
    cats = await db.categories.find({}, {'_id': 0}).sort('order', 1).to_list(500)
    # add product counts
    for c in cats:
        c['product_count'] = await db.products.count_documents({'category_id': c['id'], 'active': True})
    cache_set('categories', cats)
    return cats

@api_router.get('/categories/{cat_id}')
async def get_category(cat_id: str):
    c = await db.categories.find_one({'id': cat_id}, {'_id': 0}) or await db.categories.find_one({'slug': cat_id}, {'_id': 0})
    if not c:
        raise HTTPException(status_code=404, detail='Category not found')
    return c

@api_router.post('/categories')
async def create_category(cat: CategoryIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = cat.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['slug'] = await unique_slug(db.categories, doc.get('slug') or slugify(cat.name))
    doc['created_at'] = now_iso()
    await db.categories.insert_one(doc)
    cache_invalidate('categories')
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'create_category', doc['id'], {'name': doc.get('name')})
    doc.pop('_id', None)
    return doc

@api_router.put('/categories/{cat_id}')
async def update_category(cat_id: str, cat: CategoryIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = cat.model_dump()
    doc['slug'] = await unique_slug(db.categories, doc.get('slug') or slugify(cat.name), exclude_id=cat_id)
    doc['updated_at'] = now_iso()
    res = await db.categories.update_one({'id': cat_id}, {'$set': doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail='Category not found')
    updated = await db.categories.find_one({'id': cat_id}, {'_id': 0})
    cache_invalidate('categories')
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'update_category', cat_id, {'name': doc.get('name')})
    return updated

@api_router.delete('/categories/{cat_id}')
async def delete_category(cat_id: str, request: Request, payload: Dict = Depends(require_admin)):
    product_count = await db.products.count_documents({'category_id': cat_id})
    if product_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f'Cannot delete category: {product_count} product(s) are still assigned to it. Move or delete them first.',
        )
    await db.categories.delete_one({'id': cat_id})
    cache_invalidate('categories')
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'delete_category', cat_id)
    return {'ok': True}

# ------------------ PRODUCTS ------------------

@api_router.get('/products')
async def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    featured: Optional[bool] = None,
    in_stock: Optional[bool] = None,
    sort: Optional[str] = 'newest',
    page: int = 1,
    limit: int = 24,
):
    q: Dict = {'active': True}
    if category:
        q['category_id'] = category
    if featured is not None:
        q['featured'] = featured
    if in_stock:
        q['stock'] = {'$gt': 0}
    if min_price is not None or max_price is not None:
        pr: Dict = {}
        if min_price is not None: pr['$gte'] = min_price
        if max_price is not None: pr['$lte'] = max_price
        q['price'] = pr
    if search:
        q['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'description': {'$regex': search, '$options': 'i'}},
            {'tags': {'$regex': search, '$options': 'i'}},
        ]
    sort_map = {
        'newest': [('created_at', -1)],
        'price_asc': [('price', 1)],
        'price_desc': [('price', -1)],
        'name': [('name', 1)],
        'rating': [('avg_rating', -1)],
    }
    sort_by = sort_map.get(sort or 'newest', sort_map['newest'])
    skip = max(0, (page - 1) * limit)
    total = await db.products.count_documents(q)
    docs = await db.products.find(q, {'_id': 0}).sort(sort_by).skip(skip).limit(limit).to_list(limit)
    return {'items': docs, 'total': total, 'page': page, 'limit': limit, 'pages': max(1, (total + limit - 1) // limit)}

@api_router.get('/products/{pid}')
async def get_product(pid: str):
    p = await db.products.find_one({'id': pid}, {'_id': 0}) or await db.products.find_one({'slug': pid}, {'_id': 0})
    if not p:
        raise HTTPException(status_code=404, detail='Product not found')
    # attach category
    cat = await db.categories.find_one({'id': p.get('category_id')}, {'_id': 0})
    p['category'] = cat
    # related
    related = await db.products.find({'category_id': p.get('category_id'), 'id': {'$ne': p['id']}, 'active': True}, {'_id': 0}).limit(6).to_list(6)
    p['related'] = related
    return p

@api_router.post('/products')
async def create_product(pr: ProductIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = pr.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['slug'] = await unique_slug(db.products, doc.get('slug') or slugify(pr.name))
    doc['created_at'] = now_iso()
    doc['avg_rating'] = 0.0
    doc['review_count'] = 0
    await db.products.insert_one(doc)
    cache_invalidate('categories')  # product_count in /categories depends on this
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'create_product', doc['id'], {'name': doc.get('name')})
    doc.pop('_id', None)
    return doc

@api_router.put('/products/{pid}')
async def update_product(pid: str, pr: ProductIn, request: Request, background_tasks: BackgroundTasks, payload: Dict = Depends(require_admin)):
    doc = pr.model_dump()
    doc['slug'] = await unique_slug(db.products, doc.get('slug') or slugify(pr.name), exclude_id=pid)
    doc['updated_at'] = now_iso()
    res = await db.products.update_one({'id': pid}, {'$set': doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail='Product not found')
    p = await db.products.find_one({'id': pid}, {'_id': 0})
    cache_invalidate('categories')
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'update_product', pid, {'name': doc.get('name')})
    background_tasks.add_task(maybe_send_low_stock_alert, pid)
    return p

@api_router.delete('/products/{pid}')
async def delete_product(pid: str, request: Request, payload: Dict = Depends(require_admin)):
    await db.products.delete_one({'id': pid})
    cache_invalidate('categories')
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'delete_product', pid)
    return {'ok': True}

# ------------------ COUPONS ------------------

@api_router.get('/coupons')
async def list_coupons(_: Dict = Depends(require_admin)):
    docs = await db.coupons.find({}, {'_id': 0}).sort('created_at', -1).to_list(500)
    return docs

@api_router.get('/coupons/public')
async def public_coupons():
    docs = await db.coupons.find({'active': True}, {'_id': 0}).sort('created_at', -1).to_list(500)
    return docs

@api_router.post('/coupons')
async def create_coupon(c: CouponIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = c.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['code'] = c.code.upper()
    doc['created_at'] = now_iso()
    doc['used_count'] = 0
    if await db.coupons.find_one({'code': doc['code']}):
        raise HTTPException(status_code=400, detail='Coupon code exists')
    await db.coupons.insert_one(doc)
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'create_coupon', doc['id'], {'code': doc.get('code')})
    doc.pop('_id', None)
    return doc

@api_router.put('/coupons/{cid}')
async def update_coupon(cid: str, c: CouponIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = c.model_dump()
    doc['code'] = c.code.upper()
    doc['updated_at'] = now_iso()
    res = await db.coupons.update_one({'id': cid}, {'$set': doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail='Coupon not found')
    coupon = await db.coupons.find_one({'id': cid}, {'_id': 0})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'update_coupon', cid, {'code': doc.get('code')})
    return coupon

@api_router.delete('/coupons/{cid}')
async def delete_coupon(cid: str, request: Request, payload: Dict = Depends(require_admin)):
    await db.coupons.delete_one({'id': cid})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'delete_coupon', cid)
    return {'ok': True}

@api_router.post('/coupons/validate')
async def validate_coupon(req: CouponValidate):
    code = req.code.strip().upper()
    c = await db.coupons.find_one({'code': code, 'active': True}, {'_id': 0})
    if not c:
        raise HTTPException(status_code=404, detail='Invalid coupon')
    if c.get('expiry'):
        try:
            exp = datetime.fromisoformat(c['expiry'])
            if exp < datetime.now(timezone.utc).replace(tzinfo=exp.tzinfo):
                raise HTTPException(status_code=400, detail='Coupon expired')
        except HTTPException:
            raise
        except Exception:
            pass
    if req.subtotal < (c.get('min_order') or 0):
        raise HTTPException(status_code=400, detail=f"Minimum order Rs.{c.get('min_order')}")
    if c.get('usage_limit') and c.get('used_count', 0) >= c['usage_limit']:
        raise HTTPException(status_code=400, detail='Coupon usage limit reached')
    if c['type'] == 'percent':
        discount = req.subtotal * (c['value'] / 100.0)
        if c.get('max_discount'):
            discount = min(discount, c['max_discount'])
    else:
        discount = c['value']
    discount = round(min(discount, req.subtotal), 2)
    return {'code': c['code'], 'discount': discount, 'type': c['type'], 'value': c['value']}

# ------------------ PAYMENTS ------------------

@api_router.post('/payment/create-order')
async def create_razorpay_order(req: PaymentCreateOrderRequest):
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=400, detail='Razorpay is not configured yet. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to the backend environment.')

    order = await db.orders.find_one({'id': req.order_id}, {'_id': 0})
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')

    # The amount to charge is always derived from the order's own server-computed total,
    # never from the client - otherwise a caller could request a Razorpay order for a
    # trivial amount, pay that, and have the (still cryptographically valid) signature
    # accepted in /payment/verify to mark a much larger order as fully paid.
    amount = max(1, int(round(float(order.get('total', 0)) * 100)))
    payload = {
        'amount': amount,
        'currency': req.currency or 'INR',
        'receipt': order['id'],
        'notes': req.notes or {
            'order_id': order['id'],
            'customer_name': (order.get('address') or {}).get('name', ''),
            'customer_mobile': (order.get('address') or {}).get('mobile', ''),
        },
    }

    try:
        response = requests.post(
            'https://api.razorpay.com/v1/orders',
            auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.error('Failed to create Razorpay order: %s', exc)
        raise HTTPException(status_code=502, detail='Unable to create Razorpay order right now.') from exc

    # Persist which Razorpay order this local order was billed against, so /payment/verify
    # can refuse to accept a signature that was actually issued for a *different* order
    # (otherwise a genuine low-value payment could be replayed to mark a high-value order paid).
    await db.orders.update_one({'id': order['id']}, {'$set': {'razorpay_order_id': data.get('id')}})

    return {
        'order_id': order['id'],
        'razorpay_order_id': data.get('id'),
        'amount': data.get('amount'),
        'currency': data.get('currency'),
        'key_id': RAZORPAY_KEY_ID,
    }


@api_router.post('/payment/verify')
async def verify_razorpay_payment(req: PaymentVerifyRequest, request: Request, background_tasks: BackgroundTasks):
    if not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=400, detail='Razorpay is not configured yet.')

    if not verify_razorpay_signature(req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature, RAZORPAY_KEY_SECRET):
        raise HTTPException(status_code=400, detail='Invalid payment signature')

    order = await db.orders.find_one({'id': req.order_id}, {'_id': 0})
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')

    # A valid signature only proves *some* payment was made to *some* Razorpay order - it must also
    # be the Razorpay order we actually created for this order_id, otherwise a genuine payment on a
    # cheap order could be replayed here to mark an unrelated, more expensive order as paid.
    if order.get('razorpay_order_id') != req.razorpay_order_id:
        logger.warning('Razorpay order_id mismatch for order %s: expected %s, got %s',
                        req.order_id, order.get('razorpay_order_id'), req.razorpay_order_id)
        raise HTTPException(status_code=400, detail='Payment does not match this order')

    if order.get('payment_status') == 'paid':
        return {'ok': True, 'order': order}

    await db.orders.update_one({'id': req.order_id}, {'$set': {
        'payment_status': 'paid',
        'status': 'confirmed',
        'updated_at': now_iso(),
        'payment_details': {
            'razorpay_order_id': req.razorpay_order_id,
            'razorpay_payment_id': req.razorpay_payment_id,
            'verified_at': now_iso(),
        },
    }})
    updated = await db.orders.find_one({'id': req.order_id}, {'_id': 0})
    settings = await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
    background_tasks.add_task(send_order_notification, updated, settings)
    # Feature 2: order is now confirmed via online payment - validate/deliver the invoice link
    background_tasks.add_task(send_invoice_whatsapp_task, req.order_id, settings, str(request.base_url))
    return {'ok': True, 'order': updated}


@api_router.post('/payment/webhook')
async def razorpay_webhook(request: Request):
    signature = request.headers.get('X-Razorpay-Signature', '')
    if not signature or not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=400, detail='Invalid webhook request')

    body = await request.body()
    expected = generate_razorpay_signature(body.decode('utf-8'), RAZORPAY_KEY_SECRET)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail='Invalid webhook signature')

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid webhook payload')

    event = payload.get('event', '')
    if event in {'payment.authorized', 'order.paid'}:
        payment = payload.get('payload', {}).get('payment', {}).get('entity', {})
        order_id = payment.get('notes', {}).get('order_id') or payload.get('payload', {}).get('order', {}).get('entity', {}).get('receipt')
        if order_id:
            await db.orders.update_one({'id': order_id}, {'$set': {
                'payment_status': 'paid',
                'status': 'confirmed',
                'updated_at': now_iso(),
                'payment_details': {
                    'razorpay_order_id': payload.get('payload', {}).get('order', {}).get('entity', {}).get('id'),
                    'razorpay_payment_id': payment.get('id'),
                    'verified_at': now_iso(),
                },
            }})
    return {'ok': True}


# ------------------ ORDERS ------------------

# Rejects an identical order (same mobile + cart contents + payment method) resubmitted
# within DUPLICATE_ORDER_WINDOW_SECONDS - guards against double-clicking "Place Order"
# creating two orders (and reserving stock twice) before the button's own disabled
# state has a chance to catch it.
_recent_order_fingerprints: Dict[str, datetime] = {}
DUPLICATE_ORDER_WINDOW_SECONDS = 15


def _order_fingerprint(order: 'OrderIn') -> str:
    items_key = sorted((it.product_id, it.quantity) for it in order.items)
    raw = f"{order.address.mobile}|{items_key}|{order.payment_method}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _check_duplicate_order(order: 'OrderIn') -> None:
    now = datetime.now(timezone.utc)
    expired = [k for k, ts in _recent_order_fingerprints.items() if (now - ts).total_seconds() >= DUPLICATE_ORDER_WINDOW_SECONDS]
    for k in expired:
        del _recent_order_fingerprints[k]
    fp = _order_fingerprint(order)
    if fp in _recent_order_fingerprints:
        raise HTTPException(status_code=409, detail='This order was just submitted. Please wait a moment before trying again.')
    _recent_order_fingerprints[fp] = now


# ------------------ ABANDONED CART NUDGE ------------------

@api_router.post('/cart/sync')
async def sync_abandoned_cart(req: CartSyncIn, request: Request):
    """Called opportunistically from the checkout page once the customer has entered a valid
    mobile number, so we have something to remind them with if they never finish checking out.
    Not tied to auth/order creation - just a lightweight snapshot, upserted by mobile number."""
    dependencies.check_rate_limit(request, 'cart_sync', max_requests=30, window_seconds=300)
    if not req.items:
        await db.abandoned_carts.delete_one({'mobile': req.mobile})
        return {'ok': True}
    await db.abandoned_carts.update_one(
        {'mobile': req.mobile},
        {
            '$set': {
                'mobile': req.mobile,
                'name': req.name or '',
                'items': [i.model_dump() for i in req.items],
                'subtotal': req.subtotal,
                'updated_at': now_iso(),
                'nudge_sent': False,
            },
            '$setOnInsert': {'created_at': now_iso()},
        },
        upsert=True,
    )
    return {'ok': True}


ABANDONED_CART_DELAY_SECONDS = int(os.environ.get('ABANDONED_CART_DELAY_SECONDS', str(60 * 60)))
ABANDONED_CART_CHECK_INTERVAL_SECONDS = int(os.environ.get('ABANDONED_CART_CHECK_INTERVAL_SECONDS', str(15 * 60)))


def start_abandoned_cart_watcher() -> None:
    """Fire-and-forget asyncio task (same pattern as schedule_review_request) that runs for the
    life of the process, periodically nudging customers who synced a cart but never checked out.
    Best-effort: on a host that can idle/sleep, a check simply runs late rather than not at all -
    acceptable for a reminder feature, and much simpler than standing up a separate cron/queue."""
    task = asyncio.create_task(_abandoned_cart_watch_loop())
    _background_asyncio_tasks.add(task)
    task.add_done_callback(_background_asyncio_tasks.discard)


async def _abandoned_cart_watch_loop() -> None:
    while True:
        try:
            await asyncio.sleep(ABANDONED_CART_CHECK_INTERVAL_SECONDS)
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=ABANDONED_CART_DELAY_SECONDS)).isoformat()
            stale = await db.abandoned_carts.find({'nudge_sent': {'$ne': True}, 'updated_at': {'$lte': cutoff}}).to_list(200)
            for cart in stale:
                await _send_abandoned_cart_nudge(cart)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Abandoned-cart watch loop iteration failed')


async def _send_abandoned_cart_nudge(cart: Dict[str, Any]) -> None:
    mobile = cart.get('mobile', '')
    try:
        phone = build_whatsapp_number(mobile, WHATSAPP_DEFAULT_COUNTRY_CODE)
        if not phone:
            await db.abandoned_carts.update_one({'mobile': mobile}, {'$set': {'nudge_sent': True}})
            return
        config = get_whatsapp_config()
        if not config.is_valid:
            return
        items = cart.get('items') or []
        item_names = ', '.join(i.get('name', '') for i in items[:3])
        more = f' and {len(items) - 3} more item(s)' if len(items) > 3 else ''
        name = cart.get('name') or 'there'
        msg = (
            f'Hi {name}, you left {item_names}{more} in your cart at Kiran Traders. '
            'Complete your order anytime - just reply here or visit our site to checkout.'
        )
        send_text_message(config, phone, msg)
        await db.abandoned_carts.update_one({'mobile': mobile}, {'$set': {'nudge_sent': True}})
        logger.info('Abandoned-cart nudge sent to %s', mobile)
    except Exception:
        logger.exception('Failed to send abandoned-cart nudge for %s', mobile)


def effective_unit_price(product: Dict[str, Any], quantity: int) -> float:
    """Returns the per-unit price for buying `quantity` of `product`, applying whichever
    bulk-pricing tier the quantity qualifies for (highest min_qty <= quantity), falling back
    to the base price. `price_tiers` is stored sorted ascending by min_qty."""
    price = product.get('price', 0)
    for tier in product.get('price_tiers') or []:
        if quantity >= tier.get('min_qty', 0):
            price = tier.get('price', price)
        else:
            break
    return price


@api_router.post('/orders')
async def create_order(order: OrderIn, background_tasks: BackgroundTasks):
    if not order.items:
        raise HTTPException(status_code=400, detail='No items')
    _check_duplicate_order(order)
    subtotal = 0.0
    validated_items = []
    for it in order.items:
        p = await db.products.find_one({'id': it.product_id}, {'_id': 0})
        if not p:
            raise HTTPException(status_code=400, detail=f'Product not found: {it.name}')
        if p.get('stock', 0) < it.quantity:
            raise HTTPException(status_code=400, detail=f'Insufficient stock for {p["name"]}')
        unit_price = effective_unit_price(p, it.quantity)
        line = {
            'product_id': p['id'],
            'name': p['name'],
            'price': unit_price,
            'size': p.get('size', ''),
            'unit': p.get('unit', 'piece'),
            'image': (p.get('images') or [''])[0],
            'quantity': it.quantity,
            'total': round(unit_price * it.quantity, 2),
        }
        subtotal += line['total']
        validated_items.append(line)
    subtotal = round(subtotal, 2)
    discount = 0.0
    coupon_code = ''
    if order.coupon_code:
        # If the coupon the customer applied in the cart can no longer be honoured (expired,
        # deactivated, or a limited-use code that just got used up), fail loudly here instead
        # of silently placing the order at full price - the customer saw a discounted total
        # and must be told it changed, not be charged more without explanation.
        try:
            res = await validate_coupon(CouponValidate(code=order.coupon_code, subtotal=subtotal))
        except HTTPException as e:
            raise HTTPException(status_code=400, detail=f'Coupon "{order.coupon_code}" is no longer valid: {e.detail}')
        discount = res['discount']
        coupon_code = res['code']
    settings = await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
    tax_rate = settings.get('tax_rate', 0.0)
    shipping_flat = settings.get('shipping_flat', 0.0)
    free_ship_above = settings.get('free_shipping_above', 0.0)
    taxable = max(0.0, subtotal - discount)
    tax = round(taxable * (tax_rate / 100.0), 2) if tax_rate else 0.0
    shipping = 0.0 if (free_ship_above and taxable >= free_ship_above) else shipping_flat
    total = round(taxable + tax + shipping, 2)
    oid = gen_order_id()
    # GST invoices must split tax as IGST for interstate supply and CGST+SGST for intrastate;
    # the business is registered in Uttar Pradesh, so any other billing state is interstate.
    is_interstate = (order.address.state or '').strip().lower() != 'uttar pradesh'
    doc = {
        'id': oid,
        'order_number': oid,
        'items': validated_items,
        'address': order.address.model_dump(),
        'payment_method': order.payment_method,
        'payment_status': 'pending',
        'notes': order.notes or '',
        'coupon_code': coupon_code,
        'is_interstate': is_interstate,
        'subtotal': subtotal,
        'discount': discount,
        'tax': tax,
        'tax_rate': tax_rate,
        'shipping': shipping,
        'total': total,
        'status': 'pending',
        'status_history': [{'status': 'pending', 'at': now_iso(), 'note': 'Order placed'}],
        'created_at': now_iso(),
    }
    # Atomically reserve stock for every line item before creating the order, rolling
    # back any lines already reserved if a later one fails. The $gte guard makes this
    # safe under concurrency (unlike a plain read-then-write), so two customers racing
    # for the last unit can't both succeed.
    reserved: List[Dict] = []
    for it in validated_items:
        res = await db.products.update_one(
            {'id': it['product_id'], 'stock': {'$gte': it['quantity']}},
            {'$inc': {'stock': -it['quantity']}},
        )
        if res.matched_count == 0:
            for r in reserved:
                await db.products.update_one({'id': r['product_id']}, {'$inc': {'stock': r['quantity']}})
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {it['name']}")
        reserved.append(it)

    # Atomically reserve the coupon use too: a plain check-then-$inc (the old code) lets two
    # concurrent checkouts both pass the usage_limit check and both increment, overrunning the
    # limit. Folding the limit check into the update's filter makes it race-safe the same way
    # stock reservation above is.
    if coupon_code:
        coupon_res = await db.coupons.update_one(
            {
                'code': coupon_code,
                '$or': [
                    {'usage_limit': {'$in': [0, None]}},
                    {'$expr': {'$lt': ['$used_count', '$usage_limit']}},
                ],
            },
            {'$inc': {'used_count': 1}},
        )
        if coupon_res.matched_count == 0:
            for r in reserved:
                await db.products.update_one({'id': r['product_id']}, {'$inc': {'stock': r['quantity']}})
            raise HTTPException(status_code=400, detail=f'Coupon "{coupon_code}" just reached its usage limit. Please remove it and try again.')

    await db.orders.insert_one(doc)
    doc.pop('_id', None)
    background_tasks.add_task(send_order_notification, doc, settings)
    for it in reserved:
        background_tasks.add_task(maybe_send_low_stock_alert, it['product_id'], settings)
    # The customer just completed checkout, so any cart snapshot synced earlier for this
    # mobile is no longer "abandoned" - drop it so the nudge job doesn't message them later.
    await db.abandoned_carts.delete_one({'mobile': order.address.mobile})
    return doc

@api_router.post('/orders/track')
async def track_order(req: TrackOrderRequest):
    o = await db.orders.find_one({'id': req.order_id.strip().upper()}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    if str(o['address'].get('mobile', '')).strip() != req.mobile.strip():
        raise HTTPException(status_code=403, detail='Mobile number does not match')
    return o

# ------------------ CUSTOMER OTP LOGIN ------------------

CUSTOMER_OTP_EXPIRE_SECONDS = 5 * 60
CUSTOMER_TOKEN_EXPIRE_DAYS = 30


@api_router.post('/customer/auth/request-otp')
async def request_customer_otp(req: CustomerOtpRequestIn, request: Request):
    dependencies.check_rate_limit(request, 'customer_otp_request', max_requests=5, window_seconds=15 * 60)
    mobile = ''.join(ch for ch in req.mobile if ch.isdigit())
    # Only customers who've actually ordered before can log in - this feature is "see my past
    # orders", not new-account signup. Respond identically either way so a caller can't use this
    # endpoint to enumerate which mobile numbers have placed orders.
    has_order = await db.orders.find_one({'address.mobile': mobile}, {'_id': 0, 'id': 1})
    if has_order:
        otp = f'{secrets.randbelow(1_000_000):06d}'
        await db.customer_otps.update_one(
            {'mobile': mobile},
            {'$set': {
                'otp': otp,
                'expires_at': (datetime.now(timezone.utc) + timedelta(seconds=CUSTOMER_OTP_EXPIRE_SECONDS)).isoformat(),
                'attempts': 0,
            }},
            upsert=True,
        )
        phone = build_whatsapp_number(mobile, WHATSAPP_DEFAULT_COUNTRY_CODE)
        config = get_whatsapp_config()
        if phone and config.is_valid:
            try:
                send_text_message(config, phone, f'Your Kiran Traders login code is {otp}. It expires in 5 minutes.')
            except Exception:
                logger.exception('Failed to send customer login OTP to %s', mobile)
    return {'ok': True}


@api_router.post('/customer/auth/verify-otp')
async def verify_customer_otp(req: CustomerOtpVerifyIn, request: Request):
    dependencies.check_rate_limit(request, 'customer_otp_verify', max_requests=15, window_seconds=15 * 60)
    mobile = ''.join(ch for ch in req.mobile if ch.isdigit())
    rec = await db.customer_otps.find_one({'mobile': mobile})
    if not rec:
        raise HTTPException(status_code=400, detail='Invalid or expired code. Please request a new one.')
    if rec.get('attempts', 0) >= 5:
        await db.customer_otps.delete_one({'mobile': mobile})
        raise HTTPException(status_code=429, detail='Too many incorrect attempts. Please request a new code.')
    expires_at = rec.get('expires_at')
    if not expires_at or datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        await db.customer_otps.delete_one({'mobile': mobile})
        raise HTTPException(status_code=400, detail='Code expired. Please request a new one.')
    if rec.get('otp') != req.otp.strip():
        await db.customer_otps.update_one({'mobile': mobile}, {'$inc': {'attempts': 1}})
        raise HTTPException(status_code=400, detail='Incorrect code')
    await db.customer_otps.delete_one({'mobile': mobile})
    token = create_token(mobile, mobile, 'customer', 0, expires_delta=timedelta(days=CUSTOMER_TOKEN_EXPIRE_DAYS))
    return {'token': token, 'mobile': mobile}


@api_router.get('/customer/orders')
async def customer_orders(payload: Dict = Depends(dependencies.require_customer)):
    mobile = payload.get('sub')
    orders = await db.orders.find({'address.mobile': mobile}, {'_id': 0}).sort('created_at', -1).to_list(200)
    return orders


@api_router.get('/orders')
async def list_orders(
    status_f: Optional[str] = Query(None, alias='status'),
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 30,
    _: Dict = Depends(require_admin),
):
    q: Dict = {}
    if status_f:
        q['status'] = status_f
    if search:
        q['$or'] = [
            {'id': {'$regex': search, '$options': 'i'}},
            {'address.name': {'$regex': search, '$options': 'i'}},
            {'address.mobile': {'$regex': search, '$options': 'i'}},
        ]
    total = await db.orders.count_documents(q)
    skip = max(0, (page - 1) * limit)
    docs = await db.orders.find(q, {'_id': 0}).sort('created_at', -1).skip(skip).limit(limit).to_list(limit)
    return {'items': docs, 'total': total, 'page': page, 'limit': limit}

@api_router.get('/orders/export')
async def export_orders(
    status_f: Optional[str] = Query(None, alias='status'),
    search: Optional[str] = None,
    _: Dict = Depends(require_admin),
):
    q: Dict = {}
    if status_f:
        q['status'] = status_f
    if search:
        q['$or'] = [
            {'id': {'$regex': search, '$options': 'i'}},
            {'address.name': {'$regex': search, '$options': 'i'}},
            {'address.mobile': {'$regex': search, '$options': 'i'}},
        ]
    docs = await db.orders.find(q, {'_id': 0}).sort('created_at', -1).to_list(100000)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Order ID', 'Date', 'Status', 'Customer Name', 'Mobile', 'Email', 'City', 'State', 'Pincode',
                      'Items', 'Subtotal', 'Discount', 'Tax', 'Shipping', 'Total', 'Payment Method', 'Payment Status'])
    for o in docs:
        addr = o.get('address', {})
        items_summary = '; '.join(f"{it.get('name', '')} x{it.get('quantity', 0)}" for it in o.get('items', []))
        writer.writerow([
            o.get('id', ''), o.get('created_at', '')[:10], o.get('status', ''),
            addr.get('name', ''), addr.get('mobile', ''), addr.get('email', ''),
            addr.get('city', ''), addr.get('state', ''), addr.get('pincode', ''),
            items_summary, o.get('subtotal', 0), o.get('discount', 0), o.get('tax', 0),
            o.get('shipping', 0), o.get('total', 0), o.get('payment_method', ''), o.get('payment_status', ''),
        ])
    return Response(content=buf.getvalue(), media_type='text/csv', headers={
        'Content-Disposition': f'attachment; filename=orders-{datetime.now(timezone.utc).strftime("%Y%m%d")}.csv'
    })

@api_router.get('/orders/{oid}')
async def get_order(oid: str, _: Dict = Depends(require_admin)):
    o = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    return o

@api_router.put('/orders/{oid}/status')
async def update_order_status(oid: str, upd: OrderStatusUpdate, request: Request, background_tasks: BackgroundTasks, payload: Dict = Depends(require_admin)):
    valid = ['pending', 'confirmed', 'processing', 'packed', 'out for delivery', 'delivered', 'cancelled']
    if upd.status not in valid:
        raise HTTPException(status_code=400, detail='Invalid status')
    o = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    old_status = o.get('status')

    # Cancelling releases the stock the order reserved; un-cancelling re-reserves it
    # atomically (so un-cancelling fails cleanly if that stock has since been sold
    # elsewhere), rolling back any lines already reserved if a later one can't be.
    if upd.status == 'cancelled' and old_status != 'cancelled':
        for it in o.get('items', []):
            await db.products.update_one({'id': it['product_id']}, {'$inc': {'stock': it['quantity']}})
            background_tasks.add_task(maybe_send_low_stock_alert, it['product_id'])
    elif old_status == 'cancelled' and upd.status != 'cancelled':
        reserved: List[Dict] = []
        for it in o.get('items', []):
            res = await db.products.update_one(
                {'id': it['product_id'], 'stock': {'$gte': it['quantity']}},
                {'$inc': {'stock': -it['quantity']}},
            )
            if res.matched_count == 0:
                for r in reserved:
                    await db.products.update_one({'id': r['product_id']}, {'$inc': {'stock': r['quantity']}})
                raise HTTPException(status_code=400, detail=f"Cannot un-cancel order: insufficient stock for {it['name']}")
            reserved.append(it)
        for it in reserved:
            background_tasks.add_task(maybe_send_low_stock_alert, it['product_id'])

    hist = o.get('status_history', [])
    hist.append({'status': upd.status, 'at': now_iso(), 'note': upd.tracking_note or ''})
    update_fields = {'status': upd.status, 'status_history': hist, 'updated_at': now_iso()}
    # A cancelled order that had already been paid needs a manual refund - flag it so it
    # doesn't get lost. Refunds themselves happen outside this system (bank transfer/UPI),
    # an admin marks it done via /orders/{oid}/mark-refunded once actually processed.
    if upd.status == 'cancelled' and old_status != 'cancelled' and o.get('payment_status') == 'paid':
        update_fields['refund_status'] = 'pending'
    await db.orders.update_one({'id': oid}, {'$set': update_fields})
    updated = await db.orders.find_one({'id': oid}, {'_id': 0})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'update_order_status', oid, {'status': upd.status})
    settings = await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
    # Feature 1: WhatsApp status-update notification (non-blocking)
    background_tasks.add_task(send_order_status_update_whatsapp, updated, upd.status, settings)
    # Feature 2: once an order is confirmed, generate/validate the invoice and WhatsApp the link
    if upd.status == 'confirmed':
        background_tasks.add_task(send_invoice_whatsapp_task, oid, settings, str(request.base_url))
    # Feature 3: once delivered, schedule a one-time review request ~24h later
    if upd.status == 'delivered':
        schedule_review_request(oid)
    return updated

@api_router.post('/orders/{oid}/mark-refunded')
async def mark_order_refunded(oid: str, request: Request, payload: Dict = Depends(require_admin)):
    o = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    if o.get('refund_status') != 'pending':
        raise HTTPException(status_code=400, detail='This order has no pending refund')
    await db.orders.update_one({'id': oid}, {'$set': {'refund_status': 'refunded', 'refunded_at': now_iso()}})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'mark_order_refunded', oid)
    return await db.orders.find_one({'id': oid}, {'_id': 0})

@api_router.get('/orders/{oid}/invoice')
async def order_invoice(oid: str, mobile: Optional[str] = None, payload: Optional[Dict] = Depends(dependencies.optional_admin)):
    o = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    # Requires either a matching customer mobile number or an authenticated admin session -
    # omitting `mobile` must never skip the check, or any guessed/leaked order id would
    # expose the customer's full name, address and order contents to anyone.
    if not payload:
        if not mobile or str(o['address'].get('mobile', '')).strip() != mobile.strip():
            raise HTTPException(status_code=403, detail='Mobile mismatch')
    settings = await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
    pdf = build_invoice_pdf(o, settings)
    return Response(content=pdf, media_type='application/pdf', headers={
        'Content-Disposition': f'inline; filename=invoice-{oid}.pdf'
    })

# ------------------ CUSTOMERS ------------------

@api_router.get('/customers')
async def list_customers(_: Dict = Depends(require_admin)):
    pipeline = [
        {'$group': {
            '_id': '$address.mobile',
            'name': {'$last': '$address.name'},
            'email': {'$last': '$address.email'},
            'mobile': {'$last': '$address.mobile'},
            'city': {'$last': '$address.city'},
            'orders': {'$sum': 1},
            'spent': {'$sum': '$total'},
            'last_order': {'$max': '$created_at'},
        }},
        {'$sort': {'last_order': -1}},
    ]
    docs = await db.orders.aggregate(pipeline).to_list(1000)
    for d in docs:
        d.pop('_id', None)
    return docs

@api_router.get('/customers/export')
async def export_customers(_: Dict = Depends(require_admin)):
    pipeline = [
        {'$group': {
            '_id': '$address.mobile',
            'name': {'$last': '$address.name'},
            'email': {'$last': '$address.email'},
            'mobile': {'$last': '$address.mobile'},
            'city': {'$last': '$address.city'},
            'orders': {'$sum': 1},
            'spent': {'$sum': '$total'},
            'last_order': {'$max': '$created_at'},
        }},
        {'$sort': {'last_order': -1}},
    ]
    docs = await db.orders.aggregate(pipeline).to_list(10000)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Name', 'Mobile', 'Email', 'City', 'Orders', 'Total Spent', 'Last Order'])
    for d in docs:
        writer.writerow([
            d.get('name', ''), d.get('mobile', ''), d.get('email', ''), d.get('city', ''),
            d.get('orders', 0), d.get('spent', 0), (d.get('last_order') or '')[:10],
        ])
    return Response(content=buf.getvalue(), media_type='text/csv', headers={
        'Content-Disposition': f'attachment; filename=customers-{datetime.now(timezone.utc).strftime("%Y%m%d")}.csv'
    })

# ------------------ BANNERS ------------------

@api_router.get('/banners')
async def list_banners():
    cached = cache_get('banners')
    if cached is not None:
        return cached
    docs = await db.banners.find({'active': True}, {'_id': 0}).sort('order', 1).to_list(50)
    cache_set('banners', docs)
    return docs

@api_router.get('/banners/all')
async def all_banners(_: Dict = Depends(require_admin)):
    docs = await db.banners.find({}, {'_id': 0}).sort('order', 1).to_list(100)
    return docs

@api_router.post('/banners')
async def create_banner(b: BannerIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = b.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['created_at'] = now_iso()
    await db.banners.insert_one(doc)
    cache_invalidate('banners')
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'create_banner', doc['id'], {'title': doc.get('title')})
    doc.pop('_id', None)
    return doc

@api_router.put('/banners/{bid}')
async def update_banner(bid: str, b: BannerIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = b.model_dump()
    doc['updated_at'] = now_iso()
    res = await db.banners.update_one({'id': bid}, {'$set': doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail='Banner not found')
    banner = await db.banners.find_one({'id': bid}, {'_id': 0})
    cache_invalidate('banners')
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'update_banner', bid, {'title': doc.get('title')})
    return banner

@api_router.delete('/banners/{bid}')
async def delete_banner(bid: str, request: Request, payload: Dict = Depends(require_admin)):
    await db.banners.delete_one({'id': bid})
    cache_invalidate('banners')
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'delete_banner', bid)
    return {'ok': True}

# ------------------ REVIEWS ------------------

@api_router.get('/reviews/product/{pid}')
async def product_reviews(pid: str):
    docs = await db.reviews.find({'product_id': pid, 'approved': True}, {'_id': 0}).sort('created_at', -1).to_list(200)
    return docs

@api_router.post('/reviews')
async def create_review(r: ReviewIn, request: Request):
    dependencies.check_rate_limit(request, 'create_review', max_requests=5, window_seconds=15 * 60)
    if r.rating < 1 or r.rating > 5:
        raise HTTPException(status_code=400, detail='Rating must be 1-5')
    doc = r.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['approved'] = False
    doc['created_at'] = now_iso()
    await db.reviews.insert_one(doc)
    doc.pop('_id', None)
    return doc

@api_router.get('/reviews')
async def all_reviews(approved: Optional[bool] = None, _: Dict = Depends(require_admin)):
    q = {} if approved is None else {'approved': approved}
    docs = await db.reviews.find(q, {'_id': 0}).sort('created_at', -1).to_list(500)
    return docs

@api_router.put('/reviews/{rid}/approve')
async def approve_review(rid: str, request: Request, payload: Dict = Depends(require_admin)):
    r = await db.reviews.find_one({'id': rid}, {'_id': 0})
    if not r:
        raise HTTPException(status_code=404, detail='Review not found')
    await db.reviews.update_one({'id': rid}, {'$set': {'approved': True}})
    # recalculate product rating
    pid = r['product_id']
    approved = await db.reviews.find({'product_id': pid, 'approved': True}, {'_id': 0, 'rating': 1}).to_list(1000)
    ratings = [a['rating'] for a in approved]
    avg = sum(ratings) / len(ratings) if ratings else 0
    await db.products.update_one({'id': pid}, {'$set': {'avg_rating': round(avg, 2), 'review_count': len(ratings)}})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'approve_review', rid, {'product_id': pid})
    return {'ok': True}

@api_router.delete('/reviews/{rid}')
async def delete_review(rid: str, request: Request, payload: Dict = Depends(require_admin)):
    await db.reviews.delete_one({'id': rid})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'delete_review', rid)
    return {'ok': True}

def send_order_whatsapp(order: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> None:
    address = order.get('address') or {}
    mobile = str(address.get('mobile') or '').strip()
    if not mobile:
        logger.info('WhatsApp order notification skipped: no customer mobile number for order %s', order.get('id'))
        return

    phone = build_whatsapp_number(mobile, WHATSAPP_DEFAULT_COUNTRY_CODE)
    if not phone:
        logger.info('WhatsApp order notification skipped: invalid mobile number for order %s', order.get('id'))
        return

    order_id = order.get('id') or order.get('order_number') or 'N/A'
    business_name = (settings or {}).get('business_name') or 'Kiran Traders'
    total = order.get('total') or 0
    items = order.get('items') or []
    item_summary = ', '.join(f"{item.get('name', 'Item')} x{item.get('quantity', 1)}" for item in items[:3])
    if len(items) > 3:
        item_summary += ' ...'

    msg_body = (
        f"Hi {address.get('name') or 'Customer'}, your order {order_id} with {business_name} has been received. "
        f"Total ₹{total:.2f}. Items: {item_summary or 'See order details'}. "
        "We will send you updates as your order is processed."
    )

    config = get_whatsapp_config()
    if not config.is_valid:
        logger.warning('WhatsApp Cloud API not configured; order notification skipped for order %s', order_id)
        return

    try:
        send_text_message(config, phone, msg_body)
    except Exception as exc:
        logger.error('Failed to send WhatsApp order notification for order %s: %s', order_id, exc)


# Feature 1: per-status WhatsApp templates. Statuses without a dedicated template
# (e.g. 'pending', 'processing') fall back to the generic "is now {status}" message below.
STATUS_WHATSAPP_TEMPLATES = {
    'confirmed': "Hi {name},\n\nYour order #{order_id} has been confirmed.",
    'packed': "Hi {name},\n\nYour order #{order_id} has been packed and is ready for dispatch.",
    'out for delivery': "Hi {name},\n\nYour order #{order_id} is out for delivery and should arrive shortly.",
    'delivered': "Hi {name},\n\nYour order #{order_id} has been delivered successfully.\n\nThank you for shopping with Kiran Traders.",
    'cancelled': "Hi {name},\n\nUnfortunately your order #{order_id} has been cancelled.\n\nPlease contact us if you have any questions.",
}


def build_status_update_message(name: str, order_id: str, status: str, business_name: str) -> str:
    template = STATUS_WHATSAPP_TEMPLATES.get(status)
    if template:
        return template.format(name=name, order_id=order_id)
    return f"Hi {name}, your order {order_id} with {business_name} is now {status.title()}. Thank you for shopping with us."


def send_order_status_update_whatsapp(order: Dict[str, Any], status: str, settings: Optional[Dict[str, Any]] = None) -> None:
    address = order.get('address') or {}
    mobile = str(address.get('mobile') or '').strip()
    if not mobile:
        logger.info('WhatsApp status update skipped: no customer mobile number for order %s', order.get('id'))
        return
    phone = build_whatsapp_number(mobile, WHATSAPP_DEFAULT_COUNTRY_CODE)
    if not phone:
        logger.info('WhatsApp status update skipped: invalid mobile number for order %s', order.get('id'))
        return

    order_id = order.get('id') or 'N/A'
    business_name = (settings or {}).get('business_name') or 'Kiran Traders'
    msg_body = build_status_update_message(address.get('name') or 'Customer', order_id, status, business_name)

    config = get_whatsapp_config()
    if not config.is_valid:
        logger.warning('WhatsApp Cloud API not configured; status update skipped for order %s', order_id)
        return

    try:
        result = send_text_message(config, phone, msg_body)
        message_id = (result.get('messages') or [{}])[0].get('id') if isinstance(result, dict) else None
        logger.info('WhatsApp status update (%s) sent for order %s, message_id=%s', status, order_id, message_id)
    except Exception as exc:
        logger.error('Failed to send status update WhatsApp notification for order %s: %s', order_id, exc)


def send_order_notification(order: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> None:
    send_order_whatsapp(order, settings)


# ------------------ LOW STOCK ALERTS ------------------

LOW_STOCK_THRESHOLD = 10


async def maybe_send_low_stock_alert(product_id: str, settings: Optional[Dict[str, Any]] = None) -> None:
    """Sends a one-time WhatsApp alert to the business's own number the moment a product's stock
    first drops to/below LOW_STOCK_THRESHOLD, using a `low_stock_alerted` flag on the product so
    every subsequent order for the same product doesn't re-send it. The flag clears itself once
    stock rises back above the threshold (e.g. after restocking), so the next dip alerts again.
    Never raises - a background task, must never affect the order/stock flow it's attached to."""
    try:
        p = await db.products.find_one({'id': product_id}, {'_id': 0, 'name': 1, 'stock': 1, 'low_stock_alerted': 1})
        if not p:
            return
        stock = p.get('stock', 0)
        if stock > LOW_STOCK_THRESHOLD:
            if p.get('low_stock_alerted'):
                await db.products.update_one({'id': product_id}, {'$set': {'low_stock_alerted': False}})
            return
        if p.get('low_stock_alerted'):
            return

        settings = settings or await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
        phone = build_whatsapp_number(settings.get('whatsapp', ''), WHATSAPP_DEFAULT_COUNTRY_CODE)
        if not phone:
            return
        config = get_whatsapp_config()
        if not config.is_valid:
            return
        stock_word = 'out of stock' if stock <= 0 else f'down to {stock} units'
        msg = f'Stock alert: "{p.get("name")}" is {stock_word}. Restock soon to avoid missed sales.'
        send_text_message(config, phone, msg)
        await db.products.update_one({'id': product_id}, {'$set': {'low_stock_alerted': True}})
    except Exception:
        logger.exception('Low-stock alert failed for product %s', product_id)


# ------------------ FEATURE 2: PDF INVOICE + WHATSAPP ------------------

async def send_invoice_whatsapp_task(order_id: str, settings: Optional[Dict[str, Any]] = None, base_url: str = '') -> None:
    """Background task: validate the invoice can be generated, then WhatsApp a link to it.
    Runs after the response has been sent; never raises (all failures are logged and swallowed)
    so it can never affect the order-confirmation flow it's attached to."""
    try:
        order = await db.orders.find_one({'id': order_id}, {'_id': 0})
        if not order:
            logger.warning('Invoice WhatsApp skipped: order %s not found', order_id)
            return
        if order.get('invoice_sent'):
            logger.info('Invoice WhatsApp already sent for order %s, skipping', order_id)
            return

        address = order.get('address') or {}
        mobile = str(address.get('mobile') or '').strip()
        if not mobile:
            logger.info('Invoice WhatsApp skipped: no customer mobile number for order %s', order_id)
            return
        phone = build_whatsapp_number(mobile, WHATSAPP_DEFAULT_COUNTRY_CODE)
        if not phone:
            logger.info('Invoice WhatsApp skipped: invalid mobile number for order %s', order_id)
            return

        settings = settings if settings is not None else (await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {})

        try:
            # Generate (and validate) the PDF off the event loop; the customer-facing link
            # re-generates it on demand via the existing /orders/{oid}/invoice endpoint, so
            # nothing needs to be persisted here - this call just confirms it won't fail.
            await asyncio.to_thread(build_invoice_pdf, order, settings)
        except Exception:
            logger.exception('Invoice PDF generation failed for order %s; skipping WhatsApp send', order_id)
            return

        base = (base_url or '').rstrip('/')
        # request.base_url reflects whatever scheme the ASGI server saw, which is http:// if a
        # TLS-terminating proxy in front of it doesn't forward X-Forwarded-Proto. Force https
        # for any non-local host so the invoice link (containing the customer's name/address)
        # sent over WhatsApp is never plain-text over the wire.
        if base.startswith('http://') and 'localhost' not in base and '127.0.0.1' not in base:
            base = 'https://' + base[len('http://'):]
        invoice_url = f"{base}/api/orders/{order_id}/invoice?mobile={mobile}"
        msg_body = (
            f"Hi {address.get('name') or 'Customer'},\n\n"
            "Thank you for your order.\n\n"
            "Your invoice is ready.\n\n"
            f"Invoice:\n{invoice_url}\n\n"
            "Thank you for choosing Kiran Traders."
        )

        config = get_whatsapp_config()
        if not config.is_valid:
            logger.warning('WhatsApp Cloud API not configured; invoice message skipped for order %s', order_id)
            return

        result = await asyncio.to_thread(send_text_message, config, phone, msg_body)
        message_id = (result.get('messages') or [{}])[0].get('id') if isinstance(result, dict) else None
        await db.orders.update_one({'id': order_id}, {'$set': {'invoice_sent': True, 'invoice_sent_at': now_iso()}})
        logger.info('Invoice WhatsApp sent for order %s, message_id=%s', order_id, message_id)
    except Exception:
        logger.exception('Unexpected error sending invoice WhatsApp for order %s', order_id)


# ------------------ FEATURE 3: DELAYED REVIEW REQUEST ------------------

def schedule_review_request(order_id: str) -> None:
    """Fire-and-forget asyncio task (not tied to any single request's lifecycle) that
    waits REVIEW_REQUEST_DELAY_SECONDS (default 24h) then sends a one-time WhatsApp
    review request, provided the order is still delivered and hasn't already been sent one.
    Deliberately synchronous: it must be a plain function call (not awaited) at the call
    site so asyncio.create_task() detaches the 24h wait from the triggering request."""
    task = asyncio.create_task(_send_review_request_after_delay(order_id))
    _background_asyncio_tasks.add(task)
    task.add_done_callback(_background_asyncio_tasks.discard)


async def _send_review_request_after_delay(order_id: str) -> None:
    try:
        logger.info('Review request for order %s scheduled in %ss', order_id, REVIEW_REQUEST_DELAY_SECONDS)
        await asyncio.sleep(REVIEW_REQUEST_DELAY_SECONDS)

        order = await db.orders.find_one({'id': order_id}, {'_id': 0})
        if not order:
            logger.warning('Review request skipped: order %s not found', order_id)
            return
        if order.get('review_request_sent'):
            logger.info('Review request already sent for order %s, skipping', order_id)
            return
        if order.get('status') != 'delivered':
            logger.info('Review request skipped: order %s status changed to %s', order_id, order.get('status'))
            return

        address = order.get('address') or {}
        mobile = str(address.get('mobile') or '').strip()
        if not mobile:
            logger.info('Review request skipped: no customer mobile number for order %s', order_id)
            return
        phone = build_whatsapp_number(mobile, WHATSAPP_DEFAULT_COUNTRY_CODE)
        if not phone:
            logger.info('Review request skipped: invalid mobile number for order %s', order_id)
            return
        if not GOOGLE_REVIEW_LINK:
            logger.warning('Review request skipped: GOOGLE_REVIEW_LINK is not configured (order %s)', order_id)
            return

        config = get_whatsapp_config()
        if not config.is_valid:
            logger.warning('WhatsApp Cloud API not configured; review request skipped for order %s', order_id)
            return

        # Atomically claim the send so a status flapping back to 'delivered' can't
        # schedule (and eventually fire) a second review request for the same order.
        claimed = await db.orders.find_one_and_update(
            {'id': order_id, 'review_request_sent': {'$ne': True}},
            {'$set': {'review_request_sent': True, 'review_request_sent_at': now_iso()}},
        )
        if not claimed:
            logger.info('Review request already claimed for order %s, skipping', order_id)
            return

        msg_body = (
            f"Hi {address.get('name') or 'Customer'},\n\n"
            "We hope you enjoyed your purchase from Kiran Traders.\n\n"
            "Your feedback means a lot to us.\n\n"
            f"Please leave us a review:\n\n{GOOGLE_REVIEW_LINK}\n\n"
            "Thank you for supporting our business."
        )
        try:
            result = await asyncio.to_thread(send_text_message, config, phone, msg_body)
            message_id = (result.get('messages') or [{}])[0].get('id') if isinstance(result, dict) else None
            logger.info('Review request WhatsApp sent for order %s, message_id=%s', order_id, message_id)
        except Exception as exc:
            logger.error('Failed to send review request WhatsApp for order %s: %s', order_id, exc)
    except Exception:
        logger.exception('Unexpected error in review request scheduler for order %s', order_id)


@api_router.post('/contact')
async def contact_submit(c: ContactIn, request: Request, background_tasks: BackgroundTasks):
    dependencies.check_rate_limit(request, 'contact_submit', max_requests=5, window_seconds=15 * 60)
    doc = c.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['created_at'] = now_iso()
    doc['read'] = False
    await db.contacts.insert_one(doc)
    doc.pop('_id', None)
    return doc

@api_router.get('/contact')
async def list_contacts(_: Dict = Depends(require_admin)):
    docs = await db.contacts.find({}, {'_id': 0}).sort('created_at', -1).to_list(500)
    return docs

@api_router.put('/contact/{cid}/read')
async def mark_contact_read(cid: str, request: Request, payload: Dict = Depends(require_admin)):
    await db.contacts.update_one({'id': cid}, {'$set': {'read': True}})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'mark_contact_read', cid)
    return {'ok': True}

@api_router.delete('/contact/{cid}')
async def delete_contact(cid: str, request: Request, payload: Dict = Depends(require_admin)):
    await db.contacts.delete_one({'id': cid})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'delete_contact', cid)
    return {'ok': True}

# ------------------ SETTINGS ------------------

@api_router.get('/settings')
async def get_settings():
    cached = cache_get('settings')
    if cached is not None:
        return cached
    s = await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
    if not s.get('email'):
        s['email'] = DEFAULT_BUSINESS_EMAIL
    cache_set('settings', s)
    return s

@api_router.put('/settings')
async def update_settings(s: SettingsIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = {k: v for k, v in s.model_dump().items() if v is not None}
    doc['id'] = 'main'
    doc['updated_at'] = now_iso()
    await db.settings.update_one({'id': 'main'}, {'$set': doc}, upsert=True)
    cache_invalidate('settings')
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'update_settings', 'main')
    return await db.settings.find_one({'id': 'main'}, {'_id': 0})

@api_router.get('/webhooks/whatsapp')
async def verify_whatsapp_webhook(request: Request):
    params = request.query_params
    mode = params.get('hub.mode') or params.get('mode')
    challenge = params.get('hub.challenge') or params.get('challenge')
    verify_token = params.get('hub.verify_token') or params.get('verify_token')
    config = get_whatsapp_config()
    if mode == 'subscribe' and verify_token == config.verify_token:
        return Response(content=challenge or '', media_type='text/plain')
    raise HTTPException(status_code=403, detail='Invalid verification token')

@api_router.post('/webhooks/whatsapp')
async def handle_whatsapp_webhook(payload: Dict[str, Any], request: Request):
    logger.info('WhatsApp webhook event received: %s', payload)
    return {'status': 'received'}

@api_router.post('/orders/{oid}/whatsapp')
async def send_order_whatsapp_message(
    oid: str,
    body: WhatsAppMessageIn,
    request: Request,
    payload: Dict = Depends(require_admin),
):
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail='Message text is required')
    order = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')

    mobile = body.mobile.strip() if body.mobile else str(order.get('address', {}).get('mobile', '')).strip()
    if not mobile:
        raise HTTPException(status_code=400, detail='Mobile number is required')

    phone = build_whatsapp_number(mobile, WHATSAPP_DEFAULT_COUNTRY_CODE)
    if not phone:
        raise HTTPException(status_code=400, detail='Unable to parse mobile number')

    try:
        config = get_whatsapp_config()
        if not config.is_valid:
            raise HTTPException(status_code=502, detail='WhatsApp Cloud API is not configured')
        send_text_message(config, phone, body.message.strip())
    except HTTPException:
        raise
    except Exception:
        logger.exception('Manual WhatsApp send failed for order %s', oid)
        raise HTTPException(status_code=502, detail='Failed to send WhatsApp message')

    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'send_whatsapp', oid, {'mobile': mobile})
    return {'ok': True}

# ------------------ ADMIN STATS ------------------

@api_router.get('/admin/stats')
async def admin_stats(_: Dict = Depends(require_admin)):
    total_orders = await db.orders.count_documents({})
    pending = await db.orders.count_documents({'status': 'pending'})
    confirmed = await db.orders.count_documents({'status': 'confirmed'})
    out_for_delivery = await db.orders.count_documents({'status': 'out for delivery'})
    delivered = await db.orders.count_documents({'status': 'delivered'})
    total_products = await db.products.count_documents({'active': True})
    low_stock = await db.products.count_documents({'stock': {'$lt': 10}, 'active': True})
    low_stock_products = await db.products.find(
        {'stock': {'$lt': 10}, 'active': True}, {'_id': 0, 'id': 1, 'name': 1, 'stock': 1, 'slug': 1}
    ).sort('stock', 1).limit(10).to_list(10)
    total_customers = len(await db.orders.distinct('address.mobile'))
    revenue_pipeline = [
        {'$match': {'status': {'$ne': 'cancelled'}}},
        {'$group': {'_id': None, 'total': {'$sum': '$total'}}},
    ]
    rev_docs = await db.orders.aggregate(revenue_pipeline).to_list(1)
    total_revenue = rev_docs[0]['total'] if rev_docs else 0
    # Last 7 days
    seven_days = datetime.now(timezone.utc) - timedelta(days=7)
    sales_by_day: Dict[str, float] = {}
    for i in range(7):
        d = (datetime.now(timezone.utc) - timedelta(days=6 - i)).strftime('%Y-%m-%d')
        sales_by_day[d] = 0
    recent_orders = await db.orders.find({'created_at': {'$gte': seven_days.isoformat()}, 'status': {'$ne': 'cancelled'}}, {'_id': 0}).to_list(1000)
    for o in recent_orders:
        d = o['created_at'][:10]
        if d in sales_by_day:
            sales_by_day[d] += o.get('total', 0)
    sales_chart = [{'date': k, 'sales': round(v, 2)} for k, v in sales_by_day.items()]
    recent = await db.orders.find({}, {'_id': 0}).sort('created_at', -1).limit(8).to_list(8)
    # Top products
    top_pipeline = [
        {'$unwind': '$items'},
        {'$group': {'_id': '$items.product_id', 'name': {'$last': '$items.name'}, 'qty': {'$sum': '$items.quantity'}, 'revenue': {'$sum': '$items.total'}}},
        {'$sort': {'qty': -1}},
        {'$limit': 5},
    ]
    top_products = await db.orders.aggregate(top_pipeline).to_list(5)
    for tp in top_products:
        tp.pop('_id', None)
    return {
        'total_orders': total_orders,
        'pending_orders': pending,
        'confirmed_orders': confirmed,
        'out_for_delivery_orders': out_for_delivery,
        'delivered_orders': delivered,
        'total_products': total_products,
        'low_stock': low_stock,
        'low_stock_products': low_stock_products,
        'total_customers': total_customers,
        'total_revenue': round(total_revenue, 2),
        'sales_chart': sales_chart,
        'recent_orders': recent,
        'top_products': top_products,
    }

@api_router.get('/admin/audit-logs')
async def list_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    admin_email: Optional[str] = None,
    _: Dict = Depends(require_admin),
):
    q: Dict[str, Any] = {}
    if action:
        q['action'] = action
    if admin_email:
        q['admin_email'] = admin_email
    total = await db.audit_logs.count_documents(q)
    items = await db.audit_logs.find(q, {'_id': 0}).sort('timestamp', -1).skip((page - 1) * limit).limit(limit).to_list(limit)
    actions = await db.audit_logs.distinct('action')
    return {'items': items, 'total': total, 'page': page, 'limit': limit, 'actions': sorted(actions)}

# ------------------ INVOICE PDF ------------------

def build_invoice_pdf(order: Dict, settings: Dict) -> bytes:
    """Build a GST tax invoice PDF styled after the business's printed invoice-book format."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=9*mm, leftMargin=9*mm, topMargin=9*mm, bottomMargin=9*mm)

    BLACK = colors.black

    def rp(value):
        s = f"{value:.2f}"
        rs, p = s.split('.')
        return rs, p

    name_style = ParagraphStyle('name', fontSize=28, leading=31, fontName='Times-Bold', textColor=BLACK)
    tax_invoice_style = ParagraphStyle('taxinv', fontSize=16, leading=18, fontName='Helvetica-Bold', textColor=BLACK, alignment=1)
    small_style = ParagraphStyle('small', fontSize=9, leading=12, fontName='Helvetica', textColor=BLACK)
    label_style = ParagraphStyle('label', fontSize=9, leading=12, fontName='Helvetica-Bold', textColor=BLACK)
    bill_header_style = ParagraphStyle('billhdr', fontSize=10, leading=13, fontName='Helvetica-Bold', textColor=BLACK)
    signature_style = ParagraphStyle('signature', fontSize=15, leading=17, fontName='Times-Italic', textColor=BLACK, alignment=1)
    small_center_style = ParagraphStyle('smallcenter', fontSize=9, leading=12, fontName='Helvetica', textColor=BLACK, alignment=1)
    order_id_style = ParagraphStyle('orderid', fontSize=15, leading=17, fontName='Helvetica-Bold', textColor=BLACK)

    story = []

    bname = settings.get('business_name', 'KIRAN TRADERS')
    gstin = settings.get('gstin', '')
    pan = settings.get('pan', '')
    address = settings.get('address', '')
    phone = settings.get('phone', '')
    phone2 = settings.get('phone2', '')
    email = settings.get('email', '')
    addr = order.get('address', {})
    invoice_date = order.get('created_at', '')[:10] if order.get('created_at') else ''

    # ==================== TOP STRIP: GSTIN/PAN | TAX INVOICE | COPY BOXES ====================
    gst_pan_block = Table([
        [Paragraph(f'<b>GSTIN :</b> {gstin}', small_style)],
        [Paragraph(f'<b>PAN :</b> {pan}', small_style)],
    ], colWidths=[58*mm])
    gst_pan_block.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))

    copy_rows = [
        ['ORIGINAL', 'White', 'For Receiver'],
        ['DUPLICATE', 'Pink', 'For Transporter'],
        ['TRIPLICATE', 'Yellow', 'For Supplier'],
    ]
    copy_table = Table(copy_rows, colWidths=[24*mm, 15*mm, 30*mm])
    copy_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.75, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    top_strip = Table([[gst_pan_block, Paragraph('TAX INVOICE', tax_invoice_style), copy_table]], colWidths=[58*mm, 65*mm, 69*mm])
    top_strip.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(top_strip)
    story.append(Spacer(1, 7))

    # ==================== LOGO / BUSINESS NAME / ADDRESS / DATE ====================
    logo_img = None
    logo_data = settings.get('logo')
    if logo_data:
        try:
            b64_data = logo_data.split(',', 1)[1] if ',' in logo_data else logo_data
            logo_img = Image(io.BytesIO(base64.b64decode(b64_data)), width=22*mm, height=22*mm)
            logo_img.hAlign = 'LEFT'
        except Exception:
            logger.warning('Invoice logo could not be decoded/embedded; continuing without it')
            logo_img = None

    contact_line = f'Mob.: {phone}' + (f', {phone2}' if phone2 else '') + (f'&nbsp;&nbsp;e-mail : {email}' if email else '')
    biz_width = 122 if logo_img else 148
    biz_block = Table([
        [Paragraph(bname, name_style)],
        [Paragraph(address, small_style)],
        [Paragraph(contact_line, small_style)],
    ], colWidths=[biz_width*mm])
    biz_block.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    date_cell = Paragraph(f'Date: {invoice_date}', label_style)
    if logo_img:
        biz_row = Table([[logo_img, biz_block, date_cell]], colWidths=[26*mm, biz_width*mm, 44*mm])
    else:
        biz_row = Table([[biz_block, date_cell]], colWidths=[biz_width*mm, 44*mm])
    biz_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(biz_row)
    story.append(Spacer(1, 6))

    # ==================== ORDER ID / STATE  |  TRANSPORT / SUPPLY ====================
    seller_state = 'Uttar Pradesh'
    seller_state_code = '09'
    order_id_block = Table([
        [Paragraph('Order ID', label_style)],
        [Paragraph(order.get('id', ''), order_id_style)],
        [Paragraph(f"State : {seller_state}&nbsp;&nbsp;&nbsp;State Code : {seller_state_code}", small_style)],
    ], colWidths=[94*mm])
    order_id_block.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LINEBELOW', (0, 0), (0, 1), 0.4, BLACK),
    ]))

    mode_supply_block = Table([
        [Paragraph("Mode of Transportation : Self", small_style)],
        [Paragraph(f"Date of Supply : {invoice_date}", small_style)],
        [Paragraph(f"Place of Supply : {addr.get('state', '')}", small_style)],
    ], colWidths=[96*mm])
    mode_supply_block.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LINEBELOW', (0, 0), (0, 1), 0.4, BLACK),
    ]))

    meta_row = Table([[order_id_block, mode_supply_block]], colWidths=[96*mm, 96*mm])
    meta_row.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.9, BLACK),
        ('LINEAFTER', (0, 0), (0, 0), 0.9, BLACK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_row)

    # ==================== DETAILS OF RECEIVER ====================
    bill_rows = [
        [Paragraph('Details of Receiver / Billed to :', bill_header_style)],
        [Paragraph(f"Name : {addr.get('name', '')}", small_style)],
        [Paragraph(f"Address : {addr.get('address_line1', '')} {addr.get('address_line2', '')}".strip(), small_style)],
        [Paragraph(f"{addr.get('city', '')}, {addr.get('state', '')} - {addr.get('pincode', '')}" + (f"&nbsp;&nbsp;&nbsp;GSTIN : {addr.get('gst_number')}" if addr.get('gst_number') else ''), small_style)],
        [Paragraph(f"State : {addr.get('state', '')}&nbsp;&nbsp;&nbsp;State Code : 09&nbsp;&nbsp;&nbsp;Mobile : {addr.get('mobile', '')}", small_style)],
    ]
    bill_table = Table(bill_rows, colWidths=[192*mm])
    bill_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.9, BLACK),
        ('LINEBELOW', (0, 0), (0, 0), 0.4, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LINEABOVE', (0, 0), (-1, 0), 0, colors.white),
    ]))
    story.append(bill_table)

    # ==================== ITEMS TABLE ====================
    total_taxable = 0
    item_rows = []
    for i, item in enumerate(order.get('items', []), 1):
        amt = item.get('total', 0)
        rs, p = rp(amt)
        item_rows.append([str(i), item.get('name', ''), item.get('hsn_code', ''), item.get('uom', 'UNIT'),
                           str(item.get('quantity', 0)), f"{item.get('price', 0):.2f}", rs, p])
        total_taxable += amt

    # Pad with blank ruled rows so the table stretches down the page like the printed bill book
    # (which always has a fixed number of ruled lines regardless of how many items are written in).
    MIN_ITEM_ROWS = 9
    real_row_count = len(item_rows)
    filler_count = max(0, MIN_ITEM_ROWS - real_row_count)
    filler_rows = [['', '', '', '', '', '', '', ''] for _ in range(filler_count)]

    items_data = [
        ['Sl.\nNo.', 'PRODUCT DESCRIPTION', 'HSN\nCode', 'UOM', 'Qty.', 'Rate', 'Amount Taxable Value', ''],
        ['', '', '', '', '', '', 'Rs.', 'P.'],
    ] + item_rows + filler_rows
    col_widths = [8*mm, 94*mm, 16*mm, 12*mm, 10*mm, 19*mm, 21*mm, 12*mm]
    row_heights = [None, None] + [None] * real_row_count + [10*mm] * filler_count
    items_table = Table(items_data, colWidths=col_widths, rowHeights=row_heights, repeatRows=2)
    style_cmds = [
        ('SPAN', (0, 0), (0, 1)), ('SPAN', (1, 0), (1, 1)), ('SPAN', (2, 0), (2, 1)),
        ('SPAN', (3, 0), (3, 1)), ('SPAN', (4, 0), (4, 1)), ('SPAN', (5, 0), (5, 1)),
        ('SPAN', (6, 0), (7, 0)),
        ('FONT', (0, 0), (-1, 1), 'Helvetica-Bold', 8),
        ('FONT', (0, 2), (-1, -1), 'Helvetica', 8),
        ('BOX', (0, 0), (-1, -1), 0.9, BLACK),
        ('INNERGRID', (0, 0), (-1, 1), 0.5, BLACK),
        ('LINEBELOW', (0, 1), (-1, -1), 0.4, BLACK),
        ('LINEAFTER', (0, 2), (-2, -1), 0.4, BLACK),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (4, -1), 'CENTER'),
        ('ALIGN', (5, 0), (7, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, 1), 'CENTER'),
        ('ALIGN', (1, 2), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]
    items_table.setStyle(TableStyle(style_cmds))
    story.append(items_table)

    # ==================== TOTALS ====================
    discount = order.get('discount', 0)
    tax = order.get('tax', 0)
    shipping = order.get('shipping', 0)
    grand_total = order.get('total', 0)
    tax_rate = order.get('tax_rate', 0)
    is_interstate = order.get('is_interstate', False)
    cgst = sgst = igst = 0
    if tax > 0:
        if is_interstate:
            igst = tax
        else:
            cgst = tax / 2
            sgst = tax / 2

    totals_label_style = ParagraphStyle('totlabel', fontSize=8, leading=10, fontName='Helvetica', textColor=BLACK)
    totals_label_bold_style = ParagraphStyle('totlabelbold', fontSize=8.5, leading=10.5, fontName='Helvetica-Bold', textColor=BLACK)

    def total_label(text, bold=False):
        return Paragraph(text, totals_label_bold_style if bold else totals_label_style)

    total_rows = [[total_label('NET AMOUNT'), *rp(total_taxable)]]
    if discount > 0:
        label = 'Discount' + (f' ({order.get("coupon_code")})' if order.get('coupon_code') else '')
        d_rs, d_p = rp(discount)
        total_rows.append([total_label(label), f"-{d_rs}", d_p])
    if cgst > 0:
        total_rows.append([total_label(f'ADD : CGST @ {tax_rate/2:g}%'), *rp(cgst)])
    if sgst > 0:
        total_rows.append([total_label(f'ADD : SGST @ {tax_rate/2:g}%'), *rp(sgst)])
    if igst > 0:
        total_rows.append([total_label(f'ADD : IGST @ {tax_rate:g}%'), *rp(igst)])
    if shipping > 0:
        total_rows.append([total_label('Other Charges'), *rp(shipping)])
    total_rows.append([total_label('TOTAL AMOUNT OF INVOICE', bold=True), *rp(grand_total)])

    n = len(total_rows)
    totals_table = Table(total_rows, colWidths=[46*mm, 22*mm, 10*mm])
    totals_table.setStyle(TableStyle([
        ('FONT', (1, 0), (-1, -1), 'Helvetica', 8),
        ('FONT', (1, n - 1), (-1, n - 1), 'Helvetica-Bold', 9),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (2, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.9, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    try:
        from num2words import num2words
        rupees = int(grand_total)
        paise = round((grand_total - rupees) * 100)
        amount_words = f"{num2words(rupees, lang='en').title()} Rupees"
        if paise > 0:
            amount_words += f" and {num2words(paise, lang='en').title()} Paise"
    except Exception:
        amount_words = f"{grand_total:.2f} Rupees"

    bank_details = settings.get('bank_details', '')
    bank_lines = [l.strip() for l in bank_details.split('\n') if l.strip()] if bank_details else []
    if bank_lines:
        bank_name, *bank_rest = bank_lines
        indent = '&nbsp;' * 6
        bank_para = f"<b>{bank_name.upper()}</b>" + ''.join(f"<br/>{indent}{line}" for line in bank_rest)
    else:
        bank_para = ''

    if order.get('payment_method') == 'online':
        payment_line = f"Payment Status : PAID via {order.get('payment_gateway', 'Online').upper()}" + \
                        (f" (Txn ID: {order.get('transaction_id')})" if order.get('transaction_id') else '')
    elif order.get('payment_method') == 'cod':
        payment_line = 'Payment Status : CASH ON DELIVERY'
    else:
        payment_line = ''

    left_block_rows = [
        [Paragraph(f"Total Invoice Value in Words : {amount_words} Only", small_style)],
        [Paragraph("Certified that the particulars given above are true &amp; correct", small_style)],
    ]
    if bank_lines:
        left_block_rows.append([Paragraph(f"<b>Bankers :</b> {bank_para}", small_style)])
    if payment_line:
        left_block_rows.append([Paragraph(f"<b>{payment_line}</b>", small_style)])

    left_block = Table(left_block_rows, colWidths=[114*mm])
    left_block.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.9, BLACK),
        ('LINEBELOW', (0, 0), (0, -2), 0.3, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    totals_row = Table([[left_block, totals_table]], colWidths=[114*mm, 78*mm])
    totals_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(totals_row)

    # ==================== FOOTER: TERMS & SIGNATURE (single table so both sides stay level) ====================
    footer_rows = [
        [Paragraph('<b>Terms &amp; Conditions :</b>', small_style), Paragraph(f'For <b>{bname}</b>', small_center_style)],
        [Paragraph('1. All disputes subject to Lucknow Jurisdiction only.', small_style), ''],
        [Paragraph('2. Goods once sold will not be taken back.', small_style), Paragraph('Rohit Kumar Jaiswal', signature_style)],
        [Paragraph('E.&amp;O.E.', small_style), Paragraph('Authorised Signatory', small_center_style)],
    ]
    footer_table = Table(footer_rows, colWidths=[114*mm, 78*mm])
    footer_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.9, BLACK),
        ('LINEAFTER', (0, 0), (0, -1), 0.9, BLACK),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(footer_table)

    def _page_border(canvas, doc_):
        canvas.saveState()
        canvas.setLineWidth(1.1)
        canvas.roundRect(doc_.leftMargin - 5, doc_.bottomMargin - 5, doc_.width + 10, doc_.height + 10, 6, stroke=1, fill=0)
        canvas.restoreState()

    doc.build(story, onFirstPage=_page_border, onLaterPages=_page_border)
    return buf.getvalue()

# ------------------ SEED ------------------

async def seed_db():
    # admin user
    admin_email = os.environ.get('ADMIN_EMAIL')
    admin_password = os.environ.get('ADMIN_PASSWORD')
    if admin_email and admin_password and not await db.users.find_one({'email': admin_email.lower()}):
        await db.users.insert_one({
            'id': str(uuid.uuid4()),
            'email': admin_email.lower(),
            'password_hash': auth.hash_password(admin_password),
            'name': 'Kiran Traders Admin',
            'role': 'admin',
            'token_version': 0,
            'created_at': now_iso(),
        })
        logger.info('Seeded admin user: %s', admin_email.lower())
    elif not await db.users.find_one({'role': 'admin'}):
        logger.warning('No admin user found. Set ADMIN_EMAIL and ADMIN_PASSWORD in environment to create an admin account.')

    # settings
    if not await db.settings.find_one({'id': 'main'}):
        upi_id = 'kirantraders@ybl'
        # generate UPI QR image
        qr_data = f'upi://pay?pa={upi_id}&pn=Kiran%20Traders&cu=INR'
        img = qrcode.make(qr_data)
        buf = io.BytesIO(); img.save(buf, format='PNG')
        qr_b64 = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        await db.settings.insert_one({
            'id': 'main',
            'business_name': 'Kiran Traders',
            'tagline': 'Wholesale & Retail Packaging Essentials - Since 1996',
            'address': '253/121, Below Jaiswal Dharamshala, Nehru Cross, Nadan Mahal Road, Lucknow \u2013 226004, Uttar Pradesh',
            'landmark': 'Below Jaiswal Dharamshala',
            'phone': '+91 9044057739',
            'phone2': '+91 9044097739',
            'whatsapp': '919044057739',
            'email': 'kirantraders1996@gmail.com',
            'upi_id': upi_id,
            'upi_qr': qr_b64,
            'bank_details': 'Account Name: Kiran Traders\nBank: State Bank of India\nA/C No: 12345678901\nIFSC: SBIN0001234\nBranch: Aashiyana, Lucknow',
            'hours': 'Mon-Wed, Fri-Sun: 10:00 AM - 8:00 PM | Thursday: Closed',
            'gstin': '09AAAAA0000A1Z5',
            'tax_rate': 0.0,
            'shipping_flat': 100.0,
            'free_shipping_above': 2000.0,
            'created_at': now_iso(),
        })
        logger.info('Seeded settings')

    # categories
    default_cats = [
        {'name': 'Thermocol Plates', 'icon': 'CircleDot', 'description': 'Premium quality disposable thermocol plates for events, catering & everyday use.', 'order': 1},
        {'name': 'Thermocol Bowls', 'icon': 'Soup', 'description': 'Lightweight thermocol bowls in various sizes.', 'order': 2},
        {'name': 'Carry Bags', 'icon': 'ShoppingBag', 'description': 'Non-woven, cotton & jute carry bags for retail & wholesale.', 'order': 3},
        {'name': 'Plastic Bags', 'icon': 'Package', 'description': 'Food-grade plastic bags for packaging.', 'order': 4},
        {'name': 'Disposable Glasses', 'icon': 'GlassWater', 'description': 'Paper & plastic disposable glasses for events.', 'order': 5},
        {'name': 'Packaging Materials', 'icon': 'Boxes', 'description': 'Bubble wraps, corrugated sheets, and packaging essentials.', 'order': 6},
        {'name': 'Luggage Bags', 'icon': 'Luggage', 'description': 'Wholesale luggage & travel bags.', 'order': 7},
    ]
    if await db.categories.count_documents({}) == 0:
        for c in default_cats:
            c['id'] = str(uuid.uuid4())
            c['slug'] = slugify(c['name'])
            c['image'] = ''
            c['created_at'] = now_iso()
            await db.categories.insert_one(c)
        logger.info('Seeded categories')

    # products
    if await db.products.count_documents({}) == 0:
        cats = await db.categories.find({}, {'_id': 0}).to_list(100)
        cat_map = {c['name']: c['id'] for c in cats}
        sample = [
            # Thermocol Plates
            {'name': '10 inch Thermocol Plate (Pack of 100)', 'category': 'Thermocol Plates', 'price': 180, 'compare_price': 220, 'size': '10 inch', 'unit': 'pack', 'moq': 5, 'stock': 500, 'featured': True, 'description': 'Premium 10 inch round thermocol plates. Ideal for weddings, parties, and catering. Sturdy, leak-proof, and food-safe.', 'image': 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=800&q=80', 'specs': {'Material': 'EPS Thermocol', 'Shape': 'Round', 'Color': 'White', 'Diameter': '10 inch'}, 'tags': ['plate', 'thermocol', 'disposable', 'catering']},
            {'name': '12 inch Thermocol Plate (Pack of 100)', 'category': 'Thermocol Plates', 'price': 240, 'compare_price': 280, 'size': '12 inch', 'unit': 'pack', 'moq': 5, 'stock': 400, 'featured': True, 'description': 'Extra large 12 inch thermocol plates for buffet & full-meal servings.', 'image': 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=800&q=80', 'specs': {'Material': 'EPS Thermocol', 'Shape': 'Round', 'Color': 'White', 'Diameter': '12 inch'}, 'tags': ['plate', 'thermocol', 'large']},
            {'name': '6 inch Thermocol Plate (Pack of 100)', 'category': 'Thermocol Plates', 'price': 90, 'size': '6 inch', 'unit': 'pack', 'moq': 10, 'stock': 800, 'description': 'Small snack/dessert size thermocol plates.', 'image': 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=800&q=80', 'specs': {'Material': 'Thermocol', 'Diameter': '6 inch'}, 'tags': ['snack', 'plate']},
            # Bowls
            {'name': 'Thermocol Bowl 250ml (Pack of 100)', 'category': 'Thermocol Bowls', 'price': 150, 'size': '250ml', 'unit': 'pack', 'moq': 5, 'stock': 350, 'featured': True, 'description': 'Ideal for curry, dal, ice-cream, and desserts. Lightweight and durable.', 'image': 'https://images.unsplash.com/photo-1584743579083-b331c4adbb15?w=800&q=80', 'specs': {'Capacity': '250ml', 'Material': 'Thermocol'}, 'tags': ['bowl', 'curry']},
            {'name': 'Thermocol Bowl 500ml (Pack of 100)', 'category': 'Thermocol Bowls', 'price': 220, 'size': '500ml', 'unit': 'pack', 'moq': 5, 'stock': 300, 'description': 'Large capacity bowl for main course.', 'image': 'https://images.unsplash.com/photo-1584743579083-b331c4adbb15?w=800&q=80', 'specs': {'Capacity': '500ml'}, 'tags': ['bowl', 'large']},
            # Carry Bags
            {'name': 'Non-woven Carry Bag 12x15 (Pack of 100)', 'category': 'Carry Bags', 'price': 380, 'compare_price': 450, 'size': '12x15 inch', 'unit': 'pack', 'moq': 2, 'stock': 250, 'featured': True, 'description': 'Eco-friendly non-woven carry bags for shopping, retail, and grocery. Available in multiple colors.', 'image': 'https://images.unsplash.com/photo-1573106456020-5ce9db6d3679?w=800&q=80', 'specs': {'Material': 'Non-woven fabric', 'Size': '12x15 inch', 'GSM': '60'}, 'tags': ['bag', 'eco-friendly', 'carry']},
            {'name': 'Non-woven Carry Bag 15x18 (Pack of 100)', 'category': 'Carry Bags', 'price': 480, 'size': '15x18 inch', 'unit': 'pack', 'moq': 2, 'stock': 200, 'description': 'Larger non-woven bags perfect for garments and gifts.', 'image': 'https://images.unsplash.com/photo-1573106456020-5ce9db6d3679?w=800&q=80', 'specs': {'Size': '15x18 inch', 'GSM': '70'}, 'tags': ['bag', 'garment']},
            # Plastic Bags
            {'name': 'Food Grade Plastic Bag 8x12 (1kg)', 'category': 'Plastic Bags', 'price': 160, 'size': '8x12 inch', 'unit': 'kg', 'moq': 1, 'stock': 600, 'description': 'Transparent food-grade plastic bags for packaging.', 'image': 'https://images.unsplash.com/photo-1618477388954-7852f32655ec?w=800&q=80', 'specs': {'Grade': 'Food safe', 'Size': '8x12 inch'}, 'tags': ['plastic', 'food']},
            # Disposable Glasses
            {'name': 'Paper Glass 200ml (Pack of 100)', 'category': 'Disposable Glasses', 'price': 120, 'size': '200ml', 'unit': 'pack', 'moq': 5, 'stock': 500, 'featured': True, 'description': 'Food-grade paper glasses for tea, coffee, and cold beverages.', 'image': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=800&q=80', 'specs': {'Capacity': '200ml', 'Material': 'Food-grade paper'}, 'tags': ['glass', 'paper', 'tea']},
            {'name': 'Plastic Disposable Glass 250ml (Pack of 100)', 'category': 'Disposable Glasses', 'price': 90, 'size': '250ml', 'unit': 'pack', 'moq': 5, 'stock': 800, 'description': 'Clear plastic disposable glasses for parties.', 'image': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=800&q=80', 'specs': {'Capacity': '250ml', 'Material': 'PP Plastic'}, 'tags': ['glass', 'plastic']},
            # Packaging
            {'name': 'Bubble Wrap Roll 1m x 50m', 'category': 'Packaging Materials', 'price': 850, 'size': '1m x 50m', 'unit': 'roll', 'moq': 1, 'stock': 40, 'description': 'Heavy-duty bubble wrap for fragile items.', 'image': 'https://images.unsplash.com/photo-1607083206869-4c7672e72a8a?w=800&q=80', 'specs': {'Length': '50 meters', 'Width': '1 meter'}, 'tags': ['bubble wrap', 'packaging']},
            {'name': 'Corrugated Sheet A4 Pack of 50', 'category': 'Packaging Materials', 'price': 320, 'size': 'A4', 'unit': 'pack', 'moq': 1, 'stock': 100, 'description': '3-ply corrugated sheets for packing.', 'image': 'https://images.unsplash.com/photo-1607083206869-4c7672e72a8a?w=800&q=80', 'specs': {'Ply': '3-ply', 'Size': 'A4'}, 'tags': ['corrugated', 'sheet']},
            # Luggage
            {'name': 'Cabin Trolley Bag 20 inch', 'category': 'Luggage Bags', 'price': 1499, 'compare_price': 1899, 'size': '20 inch', 'unit': 'piece', 'moq': 1, 'stock': 25, 'featured': True, 'description': 'Durable ABS cabin luggage with 360-degree wheels. Ideal for wholesale buyers, resellers & gift shops.', 'image': 'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=800&q=80', 'specs': {'Size': '20 inch', 'Material': 'ABS', 'Wheels': '4 (360°)'}, 'tags': ['luggage', 'cabin', 'trolley']},
        ]
        for s in sample:
            cat_id = cat_map.get(s['category'])
            if not cat_id:
                continue
            doc = {
                'id': str(uuid.uuid4()),
                'name': s['name'],
                'slug': slugify(s['name']),
                'category_id': cat_id,
                'description': s['description'],
                'short_description': s['description'][:120],
                'size': s.get('size', ''),
                'unit': s.get('unit', 'piece'),
                'price': s['price'],
                'compare_price': s.get('compare_price', 0),
                'moq': s.get('moq', 1),
                'stock': s.get('stock', 0),
                'images': [s.get('image', '')],
                'specs': s.get('specs', {}),
                'featured': s.get('featured', False),
                'active': True,
                'tags': s.get('tags', []),
                'avg_rating': 0.0,
                'review_count': 0,
                'created_at': now_iso(),
            }
            await db.products.insert_one(doc)
        logger.info('Seeded products')

    # banners
    if await db.banners.count_documents({}) == 0:
        banners = [
            {'title': 'Wholesale Prices, Retail Convenience', 'subtitle': 'Thermocol plates, carry bags, packaging materials & more - delivered across Lucknow & UP.', 'cta_text': 'Shop Now', 'link': '/products', 'active': True, 'order': 1, 'image': 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=1400&q=80'},
            {'title': 'Since 1996 - Nearly 3 Decades of Trust', 'subtitle': 'Serving caterers, retailers, and event organizers with quality disposables.', 'cta_text': 'Explore Categories', 'link': '/products', 'active': True, 'order': 2, 'image': 'https://images.unsplash.com/photo-1584743579083-b331c4adbb15?w=1400&q=80'},
        ]
        for b in banners:
            b['id'] = str(uuid.uuid4())
            b['created_at'] = now_iso()
            await db.banners.insert_one(b)
        logger.info('Seeded banners')

    # sample coupons
    if await db.coupons.count_documents({}) == 0:
        coupons = [
            {'code': 'WELCOME10', 'type': 'percent', 'value': 10, 'min_order': 500, 'max_discount': 500, 'active': True, 'usage_limit': 0, 'expiry': ''},
            {'code': 'BULK500', 'type': 'flat', 'value': 500, 'min_order': 5000, 'max_discount': 0, 'active': True, 'usage_limit': 0, 'expiry': ''},
        ]
        for c in coupons:
            c['id'] = str(uuid.uuid4())
            c['used_count'] = 0
            c['created_at'] = now_iso()
            await db.coupons.insert_one(c)
        logger.info('Seeded coupons')

@app.on_event('startup')
async def on_start():
    try:
        await seed_db()
        # indexes
        await db.products.create_index('slug')
        await db.products.create_index('category_id')
        await db.products.create_index([('name', 'text'), ('description', 'text'), ('tags', 'text')])
        await db.orders.create_index('id')
        await db.orders.create_index('address.mobile')
        await db.categories.create_index('slug')
        await db.users.create_index('email')
        await db.audit_logs.create_index([('timestamp', -1)])
        await db.abandoned_carts.create_index('mobile', unique=True)
        start_abandoned_cart_watcher()
        logger.info('Startup complete')
    except Exception as e:
        logger.error(f'Startup error: {e}')

# Root
@api_router.get('/')
async def root():
    return {'app': 'Kiran Traders API', 'version': '1.0.0'}

@api_router.get('/health')
async def health():
    try:
        await db.command('ping')
        return {'status': 'ok', 'db': 'connected'}
    except Exception as exc:
        logger.error('Health check failed: %s', exc)
        raise HTTPException(status_code=503, detail='Database unavailable')

app.include_router(api_router)


@app.get('/sitemap.xml')
async def sitemap():
    cats = await db.categories.find({}, {'_id': 0, 'id': 1}).to_list(500)
    prods = await db.products.find({'active': True}, {'_id': 0, 'slug': 1, 'updated_at': 1, 'created_at': 1}).to_list(10000)

    static_urls = [
        (f'{FRONTEND_URL}/', '1.0'),
        (f'{FRONTEND_URL}/products', '0.9'),
        (f'{FRONTEND_URL}/about', '0.5'),
        (f'{FRONTEND_URL}/contact', '0.5'),
    ]
    entries = [f'<url><loc>{loc}</loc><priority>{priority}</priority></url>' for loc, priority in static_urls]
    entries += [f"<url><loc>{FRONTEND_URL}/products?category={c['id']}</loc><priority>0.7</priority></url>" for c in cats]
    for p in prods:
        lastmod = (p.get('updated_at') or p.get('created_at') or '')[:10]
        lastmod_tag = f'<lastmod>{lastmod}</lastmod>' if lastmod else ''
        entries.append(f"<url><loc>{FRONTEND_URL}/products/{p['slug']}</loc>{lastmod_tag}<priority>0.8</priority></url>")

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(entries) + '\n</urlset>'
    return Response(content=xml, media_type='application/xml')


app.add_middleware(
    security.SecureHeadersMiddleware,
)

app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.on_event('shutdown')
async def shutdown_db_client():
    client.close()
