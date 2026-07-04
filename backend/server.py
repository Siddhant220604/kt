from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
import bcrypt
import jwt
import asyncio
import io
import base64
import qrcode
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

JWT_SECRET = os.environ.get('JWT_SECRET', 'kiran-traders-secret-key-change-in-prod-2004')
JWT_ALGO = 'HS256'
JWT_EXPIRE_HOURS = 24 * 7

app = FastAPI(title="Kiran Traders API")
api_router = APIRouter(prefix="/api")
bearer_scheme = HTTPBearer(auto_error=False)

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

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def create_token(user_id: str, email: str, role: str = 'admin') -> str:
    payload = {
        'sub': user_id,
        'email': email,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

async def require_admin(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Dict:
    if creds is None:
        raise HTTPException(status_code=401, detail='Missing token')
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get('role') != 'admin':
            raise HTTPException(status_code=403, detail='Admin only')
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expired')
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail='Invalid token')

def gen_order_id() -> str:
    ts = datetime.now(timezone.utc).strftime('%Y%m%d')
    rand = uuid.uuid4().hex[:6].upper()
    return f"KT{ts}{rand}"

# ------------------ MODELS ------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

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
    email: Optional[str] = ''
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
    payment_method: str  # cod | upi | bank_transfer
    notes: Optional[str] = ''
    coupon_code: Optional[str] = ''

class OrderStatusUpdate(BaseModel):
    status: str  # pending | confirmed | packed | shipped | delivered | cancelled
    tracking_note: Optional[str] = ''

class TrackOrderRequest(BaseModel):
    order_id: str
    mobile: str

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
async def admin_login(req: LoginRequest):
    u = await db.users.find_one({'email': req.email.lower()})
    if not u or not verify_password(req.password, u.get('password_hash', '')):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    token = create_token(u['id'], u['email'], u.get('role', 'admin'))
    return {'token': token, 'user': {'id': u['id'], 'email': u['email'], 'name': u.get('name', ''), 'role': u.get('role', 'admin')}}

@api_router.get('/auth/me')
async def me(payload: Dict = Depends(require_admin)):
    u = await db.users.find_one({'id': payload['sub']})
    if not u:
        raise HTTPException(status_code=404, detail='User not found')
    return {'id': u['id'], 'email': u['email'], 'name': u.get('name', ''), 'role': u.get('role', 'admin')}

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
async def create_category(cat: CategoryIn, _: Dict = Depends(require_admin)):
    doc = cat.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['slug'] = doc.get('slug') or slugify(cat.name)
    doc['created_at'] = now_iso()
    await db.categories.insert_one(doc)
    doc.pop('_id', None)
    return doc

@api_router.put('/categories/{cat_id}')
async def update_category(cat_id: str, cat: CategoryIn, _: Dict = Depends(require_admin)):
    doc = cat.model_dump()
    if not doc.get('slug'):
        doc['slug'] = slugify(cat.name)
    doc['updated_at'] = now_iso()
    res = await db.categories.update_one({'id': cat_id}, {'$set': doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail='Category not found')
    updated = await db.categories.find_one({'id': cat_id}, {'_id': 0})
    return updated

@api_router.delete('/categories/{cat_id}')
async def delete_category(cat_id: str, _: Dict = Depends(require_admin)):
    await db.categories.delete_one({'id': cat_id})
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
async def create_product(pr: ProductIn, _: Dict = Depends(require_admin)):
    doc = pr.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['slug'] = doc.get('slug') or slugify(pr.name)
    doc['created_at'] = now_iso()
    doc['avg_rating'] = 0.0
    doc['review_count'] = 0
    await db.products.insert_one(doc)
    doc.pop('_id', None)
    return doc

@api_router.put('/products/{pid}')
async def update_product(pid: str, pr: ProductIn, _: Dict = Depends(require_admin)):
    doc = pr.model_dump()
    if not doc.get('slug'):
        doc['slug'] = slugify(pr.name)
    doc['updated_at'] = now_iso()
    res = await db.products.update_one({'id': pid}, {'$set': doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail='Product not found')
    p = await db.products.find_one({'id': pid}, {'_id': 0})
    return p

@api_router.delete('/products/{pid}')
async def delete_product(pid: str, _: Dict = Depends(require_admin)):
    await db.products.delete_one({'id': pid})
    return {'ok': True}

# ------------------ COUPONS ------------------

@api_router.get('/coupons')
async def list_coupons(_: Dict = Depends(require_admin)):
    docs = await db.coupons.find({}, {'_id': 0}).sort('created_at', -1).to_list(500)
    return docs

@api_router.post('/coupons')
async def create_coupon(c: CouponIn, _: Dict = Depends(require_admin)):
    doc = c.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['code'] = c.code.upper()
    doc['created_at'] = now_iso()
    doc['used_count'] = 0
    if await db.coupons.find_one({'code': doc['code']}):
        raise HTTPException(status_code=400, detail='Coupon code exists')
    await db.coupons.insert_one(doc)
    doc.pop('_id', None)
    return doc

@api_router.put('/coupons/{cid}')
async def update_coupon(cid: str, c: CouponIn, _: Dict = Depends(require_admin)):
    doc = c.model_dump()
    doc['code'] = c.code.upper()
    doc['updated_at'] = now_iso()
    res = await db.coupons.update_one({'id': cid}, {'$set': doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail='Coupon not found')
    return await db.coupons.find_one({'id': cid}, {'_id': 0})

@api_router.delete('/coupons/{cid}')
async def delete_coupon(cid: str, _: Dict = Depends(require_admin)):
    await db.coupons.delete_one({'id': cid})
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
async def update_order_status(oid: str, upd: OrderStatusUpdate, _: Dict = Depends(require_admin)):
    valid = ['pending', 'confirmed', 'packed', 'shipped', 'delivered', 'cancelled']
    if upd.status not in valid:
        raise HTTPException(status_code=400, detail='Invalid status')
    o = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    hist = o.get('status_history', [])
    hist.append({'status': upd.status, 'at': now_iso(), 'note': upd.tracking_note or ''})
    await db.orders.update_one({'id': oid}, {'$set': {'status': upd.status, 'status_history': hist, 'updated_at': now_iso()}})
    return await db.orders.find_one({'id': oid}, {'_id': 0})

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
async def create_banner(b: BannerIn, _: Dict = Depends(require_admin)):
    doc = b.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['created_at'] = now_iso()
    await db.banners.insert_one(doc)
    doc.pop('_id', None)
    return doc

@api_router.put('/banners/{bid}')
async def update_banner(bid: str, b: BannerIn, _: Dict = Depends(require_admin)):
    doc = b.model_dump()
    doc['updated_at'] = now_iso()
    res = await db.banners.update_one({'id': bid}, {'$set': doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail='Banner not found')
    return await db.banners.find_one({'id': bid}, {'_id': 0})

@api_router.delete('/banners/{bid}')
async def delete_banner(bid: str, _: Dict = Depends(require_admin)):
    await db.banners.delete_one({'id': bid})
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
async def approve_review(rid: str, _: Dict = Depends(require_admin)):
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
    return {'ok': True}

@api_router.delete('/reviews/{rid}')
async def delete_review(rid: str, _: Dict = Depends(require_admin)):
    await db.reviews.delete_one({'id': rid})
    return {'ok': True}

# ------------------ CONTACTS ------------------

@api_router.post('/contact')
async def contact_submit(c: ContactIn):
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
async def mark_contact_read(cid: str, _: Dict = Depends(require_admin)):
    await db.contacts.update_one({'id': cid}, {'$set': {'read': True}})
    return {'ok': True}

@api_router.delete('/contact/{cid}')
async def delete_contact(cid: str, _: Dict = Depends(require_admin)):
    await db.contacts.delete_one({'id': cid})
    return {'ok': True}

# ------------------ SETTINGS ------------------

@api_router.get('/settings')
async def get_settings():
    s = await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
    return s

@api_router.put('/settings')
async def update_settings(s: SettingsIn, _: Dict = Depends(require_admin)):
    doc = {k: v for k, v in s.model_dump().items() if v is not None}
    doc['id'] = 'main'
    doc['updated_at'] = now_iso()
    await db.settings.update_one({'id': 'main'}, {'$set': doc}, upsert=True)
    return await db.settings.find_one({'id': 'main'}, {'_id': 0})

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
    story.append(Paragraph(settings.get('tagline', 'Wholesale & Retail Packaging Essentials - Since 2004'), small))
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
    story.append(Paragraph('Thank you for choosing Kiran Traders. Trusted in Lucknow since 2004.', small))
    doc.build(story)
    return buf.getvalue()

# ------------------ SEED ------------------

async def seed_db():
    # admin user
    if not await db.users.find_one({'email': 'admin@kirantraders.com'}):
        await db.users.insert_one({
            'id': str(uuid.uuid4()),
            'email': 'admin@kirantraders.com',
            'password_hash': hash_password('Admin@123'),
            'name': 'Kiran Traders Admin',
            'role': 'admin',
            'created_at': now_iso(),
        })
        logger.info('Seeded admin user: admin@kirantraders.com / Admin@123')

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
            'tagline': 'Wholesale & Retail Packaging Essentials - Since 2004',
            'address': '253/121, Below Jaiswal Dharamshala, Nehru Cross, Nadan Mahal Road, Lucknow \u2013 226004, Uttar Pradesh',
            'landmark': 'Below Jaiswal Dharamshala',
            'phone': '+91 9044057739',
            'phone2': '+91 9044097739',
            'whatsapp': '919044057739',
            'email': 'sales@kirantraders.com',
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
            {'title': 'Since 2004 - 20+ Years of Trust', 'subtitle': 'Serving caterers, retailers, and event organizers with quality disposables.', 'cta_text': 'Explore Categories', 'link': '/products', 'active': True, 'order': 2, 'image': 'https://images.unsplash.com/photo-1584743579083-b331c4adbb15?w=1400&q=80'},
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
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.on_event('shutdown')
async def shutdown_db_client():
    client.close()
