from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query, status, BackgroundTasks, Request
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Any, Dict
import uuid
from datetime import datetime, timezone, timedelta
import asyncio
import hashlib
import hmac
import io
import base64
import qrcode
import smtplib
import requests

import auth
import audit
import dependencies
import security
from backend.config.whatsapp import get_whatsapp_config
from backend.services.whatsapp_service import build_whatsapp_number, send_text_message, send_whatsapp_via_twilio
from email.message import EmailMessage
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'kiran_traders')]

DEFAULT_BUSINESS_EMAIL = 'kirantraders1996@gmail.com'

MAIL_HOST = os.environ.get('MAIL_HOST', '')
mail_port_env = os.environ.get('MAIL_PORT', '587')
MAIL_PORT = int(mail_port_env) if mail_port_env and mail_port_env.strip().isdigit() else 587
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
MAIL_FROM = os.environ.get('MAIL_FROM', f'Kiran Traders <{DEFAULT_BUSINESS_EMAIL}>')
MAIL_TO = os.environ.get('MAIL_TO', DEFAULT_BUSINESS_EMAIL)

RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', '')
WHATSAPP_DEFAULT_COUNTRY_CODE = os.environ.get('WHATSAPP_DEFAULT_COUNTRY_CODE', '+91')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', '')
WHATSAPP_API_VERSION = os.environ.get('WHATSAPP_API_VERSION', 'v23.0')

app = FastAPI(title="Kiran Traders API")
api_router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# ------------------ HELPERS ------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

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
    name: str
    mobile: str
    email: EmailStr
    address_line1: str
    address_line2: Optional[str] = ''
    city: str
    state: str
    pincode: str
    landmark: Optional[str] = ''
    gst_number: Optional[str] = ''

class OrderIn(BaseModel):
    items: List[CartItem]
    address: AddressIn
    payment_method: str  # cod | upi | bank_transfer | online
    notes: Optional[str] = ''
    coupon_code: Optional[str] = ''

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
    status: str  # pending | confirmed | packed | shipped | delivered | cancelled
    tracking_note: Optional[str] = ''

class TrackOrderRequest(BaseModel):
    order_id: str
    mobile: str

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
    code: str
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
    name: str
    rating: int
    title: Optional[str] = ''
    comment: str
    order_id: Optional[str] = ''

class ContactIn(BaseModel):
    name: str
    email: Optional[str] = ''
    mobile: str
    subject: Optional[str] = ''
    message: str

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
    await db.users.update_one({'id': payload['sub']}, {'$set': {'password_hash': hashed}})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'change_password', payload['sub'])
    return {'ok': True}

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
    return ''.join(c if c.isalnum() else '-' for c in s.lower()).strip('-').replace('--', '-')

@api_router.get('/categories')
async def list_categories():
    cats = await db.categories.find({}, {'_id': 0}).sort('order', 1).to_list(500)
    # add product counts
    for c in cats:
        c['product_count'] = await db.products.count_documents({'category_id': c['id'], 'active': True})
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
    doc['slug'] = doc.get('slug') or slugify(cat.name)
    doc['created_at'] = now_iso()
    await db.categories.insert_one(doc)
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'create_category', doc['id'], {'name': doc.get('name')})
    doc.pop('_id', None)
    return doc

@api_router.put('/categories/{cat_id}')
async def update_category(cat_id: str, cat: CategoryIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = cat.model_dump()
    if not doc.get('slug'):
        doc['slug'] = slugify(cat.name)
    doc['updated_at'] = now_iso()
    res = await db.categories.update_one({'id': cat_id}, {'$set': doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail='Category not found')
    updated = await db.categories.find_one({'id': cat_id}, {'_id': 0})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'update_category', cat_id, {'name': doc.get('name')})
    return updated

@api_router.delete('/categories/{cat_id}')
async def delete_category(cat_id: str, request: Request, payload: Dict = Depends(require_admin)):
    await db.categories.delete_one({'id': cat_id})
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
    doc['slug'] = doc.get('slug') or slugify(pr.name)
    doc['created_at'] = now_iso()
    doc['avg_rating'] = 0.0
    doc['review_count'] = 0
    await db.products.insert_one(doc)
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'create_product', doc['id'], {'name': doc.get('name')})
    doc.pop('_id', None)
    return doc

@api_router.put('/products/{pid}')
async def update_product(pid: str, pr: ProductIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = pr.model_dump()
    if not doc.get('slug'):
        doc['slug'] = slugify(pr.name)
    doc['updated_at'] = now_iso()
    res = await db.products.update_one({'id': pid}, {'$set': doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail='Product not found')
    p = await db.products.find_one({'id': pid}, {'_id': 0})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'update_product', pid, {'name': doc.get('name')})
    return p

@api_router.delete('/products/{pid}')
async def delete_product(pid: str, request: Request, payload: Dict = Depends(require_admin)):
    await db.products.delete_one({'id': pid})
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

    amount = req.amount if req.amount is not None else max(1, int(round(float(order.get('total', 0)) * 100)))
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

    return {
        'order_id': order['id'],
        'razorpay_order_id': data.get('id'),
        'amount': data.get('amount'),
        'currency': data.get('currency'),
        'key_id': RAZORPAY_KEY_ID,
    }


@api_router.post('/payment/verify')
async def verify_razorpay_payment(req: PaymentVerifyRequest):
    if not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=400, detail='Razorpay is not configured yet.')

    if not verify_razorpay_signature(req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature, RAZORPAY_KEY_SECRET):
        raise HTTPException(status_code=400, detail='Invalid payment signature')

    order = await db.orders.find_one({'id': req.order_id}, {'_id': 0})
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')

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
    send_order_notification(updated, settings)
    return {'ok': True, 'order': updated}


@api_router.post('/payment/webhook')
async def razorpay_webhook(request: Any):
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

@api_router.post('/orders')
async def create_order(order: OrderIn):
    if not order.items:
        raise HTTPException(status_code=400, detail='No items')
    subtotal = 0.0
    validated_items = []
    for it in order.items:
        p = await db.products.find_one({'id': it.product_id}, {'_id': 0})
        if not p:
            raise HTTPException(status_code=400, detail=f'Product not found: {it.name}')
        if p.get('stock', 0) < it.quantity:
            raise HTTPException(status_code=400, detail=f'Insufficient stock for {p["name"]}')
        line = {
            'product_id': p['id'],
            'name': p['name'],
            'price': p['price'],
            'size': p.get('size', ''),
            'unit': p.get('unit', 'piece'),
            'image': (p.get('images') or [''])[0],
            'quantity': it.quantity,
            'total': round(p['price'] * it.quantity, 2),
        }
        subtotal += line['total']
        validated_items.append(line)
    subtotal = round(subtotal, 2)
    discount = 0.0
    coupon_code = ''
    if order.coupon_code:
        try:
            res = await validate_coupon(CouponValidate(code=order.coupon_code, subtotal=subtotal))
            discount = res['discount']
            coupon_code = res['code']
        except HTTPException:
            discount = 0.0
    settings = await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
    tax_rate = settings.get('tax_rate', 0.0)
    shipping_flat = settings.get('shipping_flat', 0.0)
    free_ship_above = settings.get('free_shipping_above', 0.0)
    taxable = max(0.0, subtotal - discount)
    tax = round(taxable * (tax_rate / 100.0), 2) if tax_rate else 0.0
    shipping = 0.0 if (free_ship_above and taxable >= free_ship_above) else shipping_flat
    total = round(taxable + tax + shipping, 2)
    oid = gen_order_id()
    doc = {
        'id': oid,
        'order_number': oid,
        'items': validated_items,
        'address': order.address.model_dump(),
        'payment_method': order.payment_method,
        'payment_status': 'pending',
        'notes': order.notes or '',
        'coupon_code': coupon_code,
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
    await db.orders.insert_one(doc)
    # decrement stock
    for it in validated_items:
        await db.products.update_one({'id': it['product_id']}, {'$inc': {'stock': -it['quantity']}})
    if coupon_code:
        await db.coupons.update_one({'code': coupon_code}, {'$inc': {'used_count': 1}})
    doc.pop('_id', None)
    send_order_notification(doc, settings)
    return doc

@api_router.post('/orders/track')
async def track_order(req: TrackOrderRequest):
    o = await db.orders.find_one({'id': req.order_id.strip().upper()}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    if str(o['address'].get('mobile', '')).strip() != req.mobile.strip():
        raise HTTPException(status_code=403, detail='Mobile number does not match')
    return o

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

@api_router.get('/orders/{oid}')
async def get_order(oid: str, _: Dict = Depends(require_admin)):
    o = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    return o

@api_router.put('/orders/{oid}/status')
async def update_order_status(oid: str, upd: OrderStatusUpdate, request: Request, background_tasks: BackgroundTasks, payload: Dict = Depends(require_admin)):
    valid = ['pending', 'confirmed', 'packed', 'shipped', 'delivered', 'cancelled']
    if upd.status not in valid:
        raise HTTPException(status_code=400, detail='Invalid status')
    o = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    hist = o.get('status_history', [])
    hist.append({'status': upd.status, 'at': now_iso(), 'note': upd.tracking_note or ''})
    await db.orders.update_one({'id': oid}, {'$set': {'status': upd.status, 'status_history': hist, 'updated_at': now_iso()}})
    updated = await db.orders.find_one({'id': oid}, {'_id': 0})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'update_order_status', oid, {'status': upd.status})
    settings = await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
    background_tasks.add_task(send_order_status_update_whatsapp, updated, upd.status, settings)
    return updated

@api_router.get('/orders/{oid}/invoice')
async def order_invoice(oid: str, mobile: Optional[str] = None):
    o = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    # public access requires mobile match; admin can call from admin panel with mobile blank if authenticated (not enforced here for simplicity)
    if mobile is not None:
        if str(o['address'].get('mobile', '')).strip() != mobile.strip():
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

# ------------------ BANNERS ------------------

@api_router.get('/banners')
async def list_banners():
    docs = await db.banners.find({'active': True}, {'_id': 0}).sort('order', 1).to_list(50)
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
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'update_banner', bid, {'title': doc.get('title')})
    return banner

@api_router.delete('/banners/{bid}')
async def delete_banner(bid: str, request: Request, payload: Dict = Depends(require_admin)):
    await db.banners.delete_one({'id': bid})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'delete_banner', bid)
    return {'ok': True}

# ------------------ REVIEWS ------------------

@api_router.get('/reviews/product/{pid}')
async def product_reviews(pid: str):
    docs = await db.reviews.find({'product_id': pid, 'approved': True}, {'_id': 0}).sort('created_at', -1).to_list(200)
    return docs

@api_router.post('/reviews')
async def create_review(r: ReviewIn):
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
    approved.append({'rating': r['rating']}) if not any(a.get('id') == rid for a in approved) else None
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

# ------------------ CONTACTS ------------------

def send_contact_email(contact: Dict[str, Any]) -> None:
    if not MAIL_HOST or not MAIL_USERNAME or not MAIL_PASSWORD or not MAIL_TO:
        logger.warning('SMTP email not sent: missing MAIL_HOST, MAIL_USERNAME, MAIL_PASSWORD, or MAIL_TO configuration')
        return

    msg = EmailMessage()
    subject = contact.get('subject') or 'New contact message from website'
    msg['Subject'] = f'Contact inquiry: {subject}'
    msg['From'] = MAIL_FROM
    msg['To'] = MAIL_TO
    if contact.get('email'):
        msg['Reply-To'] = contact['email']

    lines = [
        f"Name: {contact.get('name', '')}",
        f"Mobile: {contact.get('mobile', '')}",
        f"Email: {contact.get('email', '')}",
        f"Subject: {contact.get('subject', '')}",
        '',
        'Message:',
        contact.get('message', ''),
        '',
        f"Received: {contact.get('created_at', '')}",
    ]
    msg.set_content('\n'.join(lines))

    try:
        logger.info('Connecting to SMTP host...')
        if MAIL_USE_SSL:
            smtp = smtplib.SMTP_SSL(MAIL_HOST, MAIL_PORT, timeout=15)
        else:
            smtp = smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=15)
        logger.info('Connected successfully')
        with smtp:
            logger.info('Starting TLS...')
            if MAIL_USE_TLS and not MAIL_USE_SSL:
                smtp.starttls()
                smtp.ehlo()
            logger.info('TLS started')
            logger.info('Logging in...')
            smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
            logger.info('Logged in successfully')
            logger.info('Sending email...')
            smtp.send_message(msg)
            logger.info('Email sent successfully')
        logger.info('Contact email sent to %s', MAIL_TO)
    except Exception:
        logger.exception('Failed to send contact email')


def send_whatsapp_via_twilio(mobile: str, body: str) -> None:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_FROM:
        raise ValueError('Twilio WhatsApp credentials not configured')
    try:
        resp = requests.post(
            f'https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json',
            data={
                'To': f'whatsapp:+{mobile.lstrip("+") if mobile else mobile}',
                'From': TWILIO_WHATSAPP_FROM,
                'Body': body,
            },
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=15,
        )
        resp.raise_for_status()
        logger.info('WhatsApp message sent via Twilio to %s', mobile)
    except Exception:
        logger.exception('Twilio WhatsApp delivery failed')
        raise


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
        f"Hi {address.get('name') or 'Customer'}, your order {order_id} with {business_name} is confirmed. "
        f"Total ₹{total:.2f}. Items: {item_summary or 'See order details'}. "
        "We will update you once your order ships."
    )

    config = get_whatsapp_config()
    try:
        if config.is_valid:
            send_text_message(config, phone, msg_body)
        else:
            send_whatsapp_via_twilio(phone, msg_body)
    except Exception as exc:
        logger.error('Failed to send WhatsApp order notification for order %s: %s', order_id, exc)


def send_order_status_update_whatsapp(order: Dict[str, Any], status: str, settings: Optional[Dict[str, Any]] = None) -> None:
    address = order.get('address') or {}
    phone = build_whatsapp_number(str(address.get('mobile') or '').strip(), WHATSAPP_DEFAULT_COUNTRY_CODE)
    if not phone:
        logger.info('WhatsApp status update skipped: no valid mobile for order %s', order.get('id'))
        return

    order_id = order.get('id') or 'N/A'
    business_name = (settings or {}).get('business_name') or 'Kiran Traders'
    msg_body = (
        f"Hi {address.get('name') or 'Customer'}, your order {order_id} with {business_name} is now {status.title()}. "
        "Thank you for shopping with us."
    )

    config = get_whatsapp_config()
    try:
        if config.is_valid:
            send_text_message(config, phone, msg_body)
        else:
            send_whatsapp_via_twilio(phone, msg_body)
    except Exception as exc:
        logger.error('Failed to send status update WhatsApp notification for order %s: %s', order_id, exc)


def send_order_notification(order: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> None:
    if not MAIL_HOST or not MAIL_USERNAME or not MAIL_PASSWORD:
        logger.warning('SMTP email not sent: missing MAIL_HOST, MAIL_USERNAME, or MAIL_PASSWORD configuration')
    else:
        address = order.get('address') or {}
        recipient = (address.get('email') or '').strip()
        if not recipient:
            logger.info('Order notification skipped: no customer email provided for order %s', order.get('id'))
        else:
            business_name = (settings or {}).get('business_name') or 'Kiran Traders'
            order_id = order.get('id') or order.get('order_number') or 'N/A'
            total = order.get('total') or 0
            items = order.get('items') or []

            msg = EmailMessage()
            msg['Subject'] = f'Order confirmed | {order_id}'
            msg['From'] = MAIL_FROM
            msg['To'] = recipient
            msg['Reply-To'] = MAIL_FROM
            msg['X-Mailer'] = 'Kiran Traders Order System'

            customer_name = address.get('name') or 'Customer'
            payment_method = order.get('payment_method', 'Pending').replace('_', ' ').title()
            order_date = order.get('created_at', '')[:10] or datetime.now(timezone.utc).strftime('%Y-%m-%d')
            address_lines = [
                address.get('name', ''),
                address.get('address_line1', ''),
                address.get('address_line2', ''),
                f"{address.get('city', '')}, {address.get('state', '')} {address.get('pincode', '')}".strip(', '),
                f"Mobile: {address.get('mobile', '')}",
                f"Email: {address.get('email', '')}",
            ]
            address_lines = [line for line in address_lines if line]

            plain_lines = [
                f'Dear {customer_name},',
                '',
                f'Thank you for your order from {business_name}.',
                f'Order ID: {order_id}',
                f'Date: {order_date}',
                f'Payment method: {payment_method}',
                '',
                'Delivery address:',
                *address_lines,
                '',
                'Order summary:',
            ]
            for item in items:
                name = item.get('name', 'Item')
                qty = item.get('quantity', 1)
                price = item.get('price', 0)
                plain_lines.append(f'- {name} x{qty} @ Rs.{price:.2f}')
            plain_lines.extend([
                '',
                f'Subtotal: Rs.{order.get("subtotal", 0):.2f}',
                f'Discount: Rs.{order.get("discount", 0):.2f}',
                f'Tax: Rs.{order.get("tax", 0):.2f}',
                f'Shipping: Rs.{order.get("shipping", 0):.2f}',
                f'Total: Rs.{total:.2f}',
                '',
                'Please find your invoice attached to this email.',
                '',
                'We will update you as your order moves through processing.',
                '',
                'Warm regards,',
                business_name,
            ])
            msg.set_content('\n'.join(plain_lines))

            if str(MAIL_HOST).lower() != 'smtp.example.com':
                html_items = ''.join(
                    f'<tr>'
                    f'<td style="padding: 8px 12px; border: 1px solid #e0d4c3;">{item.get("name", "Item")}</td>'
                    f'<td style="padding: 8px 12px; border: 1px solid #e0d4c3; text-align:center;">{item.get("quantity", 1)}</td>'
                    f'<td style="padding: 8px 12px; border: 1px solid #e0d4c3; text-align:right;">Rs.{item.get("price", 0):.2f}</td>'
                    f'<td style="padding: 8px 12px; border: 1px solid #e0d4c3; text-align:right;">Rs.{item.get("total", 0):.2f}</td>'
                    f'</tr>'
                    for item in items
                )
                html_address = ''.join(f'<p style="margin:2px 0;">{line}</p>' for line in address_lines)
                html_body = f"""
                <html>
                  <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.5;">
                    <div style="max-width: 680px; margin: 0 auto; padding: 24px; background: #faf7f2; border: 1px solid #e6ddd4;">
                      <h1 style="margin-bottom: 0; font-size: 26px; color: #5a3820;">Order Confirmed</h1>
                      <p style="margin-top: 4px; color: #5a3820;">Thank you for shopping with {business_name}.</p>
                      <hr style="border:none; border-top:1px solid #e0d4c3; margin: 24px 0;" />
                      <p><strong>Order ID:</strong> {order_id}<br />
                      <strong>Date:</strong> {order_date}<br />
                      <strong>Payment:</strong> {payment_method}</p>
                      <h2 style="font-size: 18px; margin-bottom: 8px;">Delivery Address</h2>
                      <div style="padding: 12px; background: #fff; border: 1px solid #e0d4c3; margin-bottom: 16px;">{html_address}</div>
                      <h2 style="font-size: 18px; margin-bottom: 8px;">Order Summary</h2>
                      <table style="border-collapse: collapse; width: 100%; background: #fff;">
                        <thead>
                          <tr>
                            <th style="padding: 10px 12px; border: 1px solid #e0d4c3; background: #f0ece5; text-align:left;">Product</th>
                            <th style="padding: 10px 12px; border: 1px solid #e0d4c3; background: #f0ece5; text-align:center;">Qty</th>
                            <th style="padding: 10px 12px; border: 1px solid #e0d4c3; background: #f0ece5; text-align:right;">Rate</th>
                            <th style="padding: 10px 12px; border: 1px solid #e0d4c3; background: #f0ece5; text-align:right;">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {html_items}
                        </tbody>
                      </table>
                      <div style="margin-top: 16px; padding: 16px; background: #fff; border: 1px solid #e0d4c3;">
                        <p style="margin: 4px 0;"><strong>Subtotal:</strong> Rs.{order.get('subtotal', 0):.2f}</p>
                        <p style="margin: 4px 0;"><strong>Discount:</strong> Rs.{order.get('discount', 0):.2f}</p>
                        <p style="margin: 4px 0;"><strong>GST:</strong> Rs.{order.get('tax', 0):.2f}</p>
                        <p style="margin: 4px 0;"><strong>Shipping:</strong> Rs.{order.get('shipping', 0):.2f}</p>
                        <p style="margin: 10px 0 0; font-size: 16px; font-weight: bold;"><strong>Total:</strong> Rs.{total:.2f}</p>
                      </div>
                      <p style="margin-top: 20px;">Your digital invoice is attached to this email. Please keep it for your records.</p>
                      <p style="margin-top: 20px;">We will update you as your order moves through processing.</p>
                      <p style="margin-top: 32px;">Warm regards,<br />{business_name}</p>
                    </div>
                  </body>
                </html>
                """
                msg.add_alternative(html_body, subtype='html')

                try:
                    invoice_pdf = build_invoice_pdf(order, settings or {})
                    msg.add_attachment(invoice_pdf, maintype='application', subtype='pdf', filename=f'invoice-{order_id}.pdf')
                except Exception as exc:
                    logger.error('Failed to attach invoice PDF: %s', exc)

            try:
                logger.info('Connecting to SMTP host...')
                if MAIL_USE_SSL:
                    smtp = smtplib.SMTP_SSL(MAIL_HOST, MAIL_PORT, timeout=15)
                else:
                    smtp = smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=15)
                logger.info('Connected successfully')
                with smtp:
                    logger.info('Starting TLS...')
                    if MAIL_USE_TLS and not MAIL_USE_SSL:
                        smtp.starttls()
                        smtp.ehlo()
                    logger.info('TLS started')
                    logger.info('Logging in...')
                    smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
                    logger.info('Logged in successfully')
                    logger.info('Sending email...')
                    smtp.send_message(msg)
                    logger.info('Email sent successfully')
                logger.info('Order confirmation email sent to %s for order %s', recipient, order_id)
            except Exception:
                logger.exception('Failed to send order notification email')

    send_order_whatsapp(order, settings)


@api_router.post('/contact')
async def contact_submit(c: ContactIn, background_tasks: BackgroundTasks):
    doc = c.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['created_at'] = now_iso()
    doc['read'] = False
    await db.contacts.insert_one(doc)
    background_tasks.add_task(send_contact_email, doc)
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
    s = await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
    if not s.get('email'):
        s['email'] = DEFAULT_BUSINESS_EMAIL
    return s

@api_router.put('/settings')
async def update_settings(s: SettingsIn, request: Request, payload: Dict = Depends(require_admin)):
    doc = {k: v for k, v in s.model_dump().items() if v is not None}
    doc['id'] = 'main'
    doc['updated_at'] = now_iso()
    await db.settings.update_one({'id': 'main'}, {'$set': doc}, upsert=True)
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
        if config.is_valid:
            send_text_message(config, phone, body.message.strip())
        else:
            send_whatsapp_via_twilio(phone, body.message.strip())
    except Exception as exc:
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
    shipped = await db.orders.count_documents({'status': 'shipped'})
    delivered = await db.orders.count_documents({'status': 'delivered'})
    total_products = await db.products.count_documents({'active': True})
    low_stock = await db.products.count_documents({'stock': {'$lt': 10}, 'active': True})
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
        'shipped_orders': shipped,
        'delivered_orders': delivered,
        'total_products': total_products,
        'low_stock': low_stock,
        'total_customers': total_customers,
        'total_revenue': round(total_revenue, 2),
        'sales_chart': sales_chart,
        'recent_orders': recent,
        'top_products': top_products,
    }

# ------------------ INVOICE PDF ------------------

def build_invoice_pdf(order: Dict, settings: Dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    small = ParagraphStyle('small', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#3d2c22'))
    h1 = ParagraphStyle('h1', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#8b4a2b'))
    story = []
    bname = settings.get('business_name', 'Kiran Traders')
    story.append(Paragraph(f'<b>{bname}</b>', h1))
    story.append(Paragraph(settings.get('tagline', 'Wholesale & Retail Packaging Essentials - Since 1996'), small))
    story.append(Paragraph(settings.get('address', 'Sector K, 805-D, Aashiyana, Lucknow, UP'), small))
    contact_line = ' | '.join(filter(None, [settings.get('phone'), settings.get('email'), settings.get('gstin')]))
    if contact_line:
        story.append(Paragraph(contact_line, small))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f'<b>TAX INVOICE / BILL</b>', styles['Heading3']))
    story.append(Spacer(1, 4))

    addr = order.get('address', {})
    info = [
        ['Invoice No:', order.get('id', ''), 'Date:', order.get('created_at', '')[:10]],
        ['Order Status:', order.get('status', '').title(), 'Payment:', order.get('payment_method', '').upper()],
    ]
    t = Table(info, colWidths=[30*mm, 60*mm, 25*mm, 60*mm])
    t.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#3d2c22')),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>Bill To:</b>', small))
    addr_lines = [
        addr.get('name', ''),
        f"{addr.get('address_line1', '')} {addr.get('address_line2', '')}".strip(),
        f"{addr.get('city', '')}, {addr.get('state', '')} - {addr.get('pincode', '')}",
        f"Mobile: {addr.get('mobile', '')}",
    ]
    if addr.get('email'):
        addr_lines.append(f"Email: {addr.get('email')}")
    if addr.get('gst_number'):
        addr_lines.append(f"GSTIN: {addr.get('gst_number')}")
    for ln in addr_lines:
        story.append(Paragraph(ln, small))
    story.append(Spacer(1, 8))

    items_data = [['#', 'Item', 'Size', 'Qty', 'Rate', 'Amount']]
    for i, it in enumerate(order.get('items', []), 1):
        items_data.append([str(i), it.get('name', ''), it.get('size', '') or '-', str(it.get('quantity', 0)), f"Rs.{it.get('price', 0):.2f}", f"Rs.{it.get('total', 0):.2f}"])
    items_table = Table(items_data, colWidths=[10*mm, 75*mm, 25*mm, 15*mm, 25*mm, 30*mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0dcc8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#5a3820')),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d4b896')),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 10))

    totals = [
        ['Subtotal:', f"Rs.{order.get('subtotal', 0):.2f}"],
    ]
    if order.get('discount', 0):
        totals.append(['Discount (' + (order.get('coupon_code') or '') + '):', f"-Rs.{order.get('discount', 0):.2f}"])
    if order.get('tax', 0):
        totals.append([f"GST ({order.get('tax_rate', 0)}%):", f"Rs.{order.get('tax', 0):.2f}"])
    if order.get('shipping', 0):
        totals.append(['Shipping:', f"Rs.{order.get('shipping', 0):.2f}"])
    totals.append(['TOTAL:', f"Rs.{order.get('total', 0):.2f}"])
    tt = Table(totals, colWidths=[140*mm, 40*mm])
    tt.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
        ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 11),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#8b4a2b')),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#8b4a2b')),
        ('TOPPADDING', (0, -1), (-1, -1), 4),
    ]))
    story.append(tt)
    story.append(Spacer(1, 12))
    if order.get('notes'):
        story.append(Paragraph(f"<b>Notes:</b> {order['notes']}", small))
        story.append(Spacer(1, 6))
    story.append(Paragraph('Thank you for choosing Kiran Traders. Trusted in Lucknow since 1996.', small))
    doc.build(story)
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
        logger.info('Startup complete')
    except Exception as e:
        logger.error(f'Startup error: {e}')

# Root
@api_router.get('/')
async def root():
    return {'app': 'Kiran Traders API', 'version': '1.0.0'}

app.include_router(api_router)

app.add_middleware(
    security.SecureHeadersMiddleware,
)

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
