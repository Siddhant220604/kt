from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query, BackgroundTasks, Request
from fastapi.responses import Response, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument, MongoClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from typing import List, Optional, Any, Dict, Literal
import uuid
from datetime import datetime, timezone, timedelta
import asyncio
import csv
import hashlib
import hmac
import io
import re
import base64
import time
import qrcode
import requests
from PIL import Image as PILImage

import auth
import audit
import dependencies
import security
from config.whatsapp import get_whatsapp_config
from config import rate_limits
from services.whatsapp_service import build_whatsapp_number, send_text_message, send_template_message
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

# Separate *synchronous* client, used only to record outgoing WhatsApp message IDs for
# delivery-status correlation (see record_whatsapp_message_sent below). The functions that
# send WhatsApp notifications run via BackgroundTasks in a worker thread, not on the asyncio
# event loop, so they can't `await` the motor client above without a bigger refactor - a tiny
# dedicated sync client sidesteps that instead of restructuring every call site to async.
_sync_mongo_client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
_sync_db = _sync_mongo_client[os.environ.get('DB_NAME', 'kiran_traders')]


def record_whatsapp_message_sent(result: Optional[Dict[str, Any]], **context: Any) -> None:
    """Persists every WhatsApp message ID (wamid) this app generates, right after Meta accepts
    a send, so the webhook handler below can later correlate an incoming delivery-status event
    (sent/delivered/read/failed) back to what was actually sent and to which order/template."""
    if not isinstance(result, dict):
        return
    try:
        recipient = ((result.get('contacts') or [{}])[0]).get('wa_id', '')
        for msg in result.get('messages', []):
            wamid = msg.get('id')
            if not wamid:
                continue
            _sync_db.whatsapp_message_events.update_one(
                {'wamid': wamid},
                {
                    '$set': {
                        'wamid': wamid,
                        'recipient': recipient,
                        'accepted_status': msg.get('message_status', 'accepted'),
                        **context,
                    },
                    '$setOnInsert': {'created_at': now_iso(), 'status_history': []},
                },
                upsert=True,
            )
    except Exception:
        logger.exception('Failed to record WhatsApp message id for delivery-status correlation')

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all safety net for anything that isn't an intentionally-raised HTTPException
    (FastAPI's own HTTPException handler still takes precedence for those, since it's
    registered on the more specific type) - e.g. an uncaught pymongo error, a bug in a route
    with no try/except. Full exception + traceback goes to the server log; the client only
    ever sees a generic message, never the exception text, a stack trace, or a file path."""
    logger.exception('Unhandled exception on %s %s', request.method, request.url.path)
    return JSONResponse(status_code=500, content={'detail': 'Something went wrong on our end. Please try again shortly.'})

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


def _current_financial_year_label(now: Optional[datetime] = None) -> str:
    """Indian financial year: 1 Apr - 31 Mar, e.g. 2026-27 for any date from 2026-04-01 to
    2027-03-31. Matches the numbering scheme already used on the business's printed invoice
    book, so GST invoice numbers stay consistent whether raised on paper or generated here."""
    now = now or datetime.now(timezone.utc)
    fy_start_year = now.year if now.month >= 4 else now.year - 1
    return f"{fy_start_year}-{str(fy_start_year + 1)[-2:]}"


async def generate_invoice_number() -> str:
    """Atomically allocates the next sequential GST invoice number for the current financial
    year, e.g. "2026-27/0001". Uses a per-financial-year counter document with $inc (same
    race-safe pattern as stock reservation elsewhere) so two orders created at the same instant
    can never be handed the same invoice number."""
    fy_label = _current_financial_year_label()
    counter_id = f'invoice_{fy_label}'
    doc = await db.counters.find_one_and_update(
        {'id': counter_id},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"{fy_label}/{doc['seq']:04d}"


async def get_or_assign_invoice_number(order: Dict[str, Any]) -> str:
    """Orders created before invoice numbering existed won't have one yet - this assigns and
    persists one the first time such an order's invoice is actually needed, so nothing crashes
    or shows a blank number for pre-existing orders, without needing a bulk migration."""
    existing = order.get('invoice_number')
    if existing:
        return existing
    invoice_number = await generate_invoice_number()
    await db.orders.update_one({'id': order['id']}, {'$set': {'invoice_number': invoice_number}})
    order['invoice_number'] = invoice_number
    return invoice_number


def generate_razorpay_signature(payload: str, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()


def verify_razorpay_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    expected = generate_razorpay_signature(f"{order_id}|{payment_id}", secret)
    return hmac.compare_digest(expected, signature or '')

# ------------------ MODELS ------------------

# Strict format constraints shared across models below. Every user-supplied string field that
# has a well-defined shape (mobile number, PIN code, GST number) is validated against these at
# the schema level and rejected outright on mismatch - not sanitized/escaped and passed through.
INDIAN_MOBILE_REGEX = r'^[6-9]\d{9}$'  # 10 digits, Indian mobile numbers never start with 0-5
INDIAN_PINCODE_REGEX = r'^\d{6}$'
GST_NUMBER_REGEX = r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'


def _validate_optional_pattern(value: Optional[str], pattern: str, field_label: str) -> Optional[str]:
    """Shared validator for optional string fields with a strict format: None/'' pass through
    untouched (field simply wasn't provided), anything else must fully match `pattern`."""
    if value is None or value == '':
        return value
    if not re.fullmatch(pattern, value):
        raise ValueError(f'Invalid {field_label} format')
    return value


def _empty_string_to_none(value: Any) -> Any:
    """Frontend forms send '' for an untouched optional email field rather than omitting it.
    Normalize that to None *before* EmailStr validation runs, so leaving the field blank is
    accepted as "not provided" while any non-empty value must still be a real email address."""
    return None if value == '' else value


# All "image upload" fields in this app (product/category/banner images, settings logo/UPI QR)
# arrive as either a plain http(s) URL or a base64 data: URI - there is no multipart file upload
# endpoint anywhere in this app, so uploaded bytes are never written to disk/served as static
# files; they live only as a string inside a MongoDB document and are only ever rendered back
# via <img src="...">, which cannot execute their content as code. The one real gap that pattern
# leaves open is SVG: an `image/svg+xml` data URI can contain a <script> tag that some browsers
# will execute when it's loaded as an <img>. MAX_IMAGE_BYTES/ALLOWED_IMAGE_MIME_TYPES below close
# that by allow-listing only genuine raster formats and verifying the *decoded bytes* actually
# are that format via Pillow - not trusting the data URI's declared MIME type or a filename
# extension, since either can lie about what the bytes actually contain.
MAX_IMAGE_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_MIME_TYPES = {'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/webp': 'WEBP'}


def validate_image_field(value: Optional[str], field_label: str) -> Optional[str]:
    """Validates an image field's value in place and returns it unchanged if valid.

    - None/'' (field not provided) passes through untouched.
    - A plain http(s):// URL passes through untouched (nothing to decode - the image itself
      lives on whatever host serves that URL, out of this app's control either way).
    - A data: URI must declare an allow-listed image MIME type, decode as valid base64, be
      under MAX_IMAGE_BYTES once decoded, and Pillow must be able to open the decoded bytes and
      confirm they're a genuine image whose actual format matches what was declared.
    Anything else raises ValueError, which FastAPI turns into a 422 - the upload is rejected
    outright rather than stored and dealt with later.
    """
    if not value:
        return value
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if not value.startswith('data:'):
        raise ValueError(f'{field_label} must be an image URL or a base64 data URI')

    try:
        header, b64_data = value.split(',', 1)
    except ValueError:
        raise ValueError(f'{field_label} is not a valid data URI')

    declared_mime = header[len('data:'):].split(';')[0].strip().lower()
    if declared_mime not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError(f'{field_label} must be a PNG, JPEG, or WEBP image (got "{declared_mime or "unknown"}")')

    try:
        raw = base64.b64decode(b64_data, validate=True)
    except Exception:
        raise ValueError(f'{field_label} is not valid base64-encoded data')

    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(f'{field_label} must be under 2MB')

    try:
        with PILImage.open(io.BytesIO(raw)) as probe:
            actual_format = (probe.format or '').upper()
        with PILImage.open(io.BytesIO(raw)) as probe2:
            probe2.verify()
    except Exception:
        raise ValueError(f'{field_label} content is not a valid image file')

    if actual_format != ALLOWED_IMAGE_MIME_TYPES[declared_mime]:
        raise ValueError(f'{field_label} content does not match its declared type ({declared_mime})')

    return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)

class ChangeEmailRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr

class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=6, max_length=100)
    confirm_password: str = Field(min_length=1, max_length=100)

class CategoryIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    slug: Optional[str] = Field(None, max_length=120)
    description: Optional[str] = Field('', max_length=1000)
    icon: Optional[str] = Field('Package', max_length=100)
    image: Optional[str] = Field('', max_length=2_800_000)
    order: int = Field(0, ge=0, le=100000)

    @field_validator('image')
    @classmethod
    def validate_image(cls, v: Optional[str]) -> Optional[str]:
        return validate_image_field(v, 'Category image')

class PriceTier(BaseModel):
    model_config = ConfigDict(extra='forbid')
    min_qty: int = Field(gt=0, le=1_000_000)
    price: float = Field(gt=0, le=10_000_000)

class ProductIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=220)
    category_id: str = Field(min_length=1, max_length=100)
    description: str = Field('', max_length=5000)
    short_description: Optional[str] = Field('', max_length=500)
    size: Optional[str] = Field('', max_length=50)
    unit: Optional[str] = Field('piece', max_length=30)
    price: float = Field(gt=0, le=10_000_000)
    compare_price: Optional[float] = Field(0, ge=0, le=10_000_000)
    moq: int = Field(1, ge=1, le=100000)
    stock: int = Field(0, ge=0, le=10_000_000)
    images: List[str] = []
    specs: Optional[Dict[str, str]] = {}
    featured: bool = False
    active: bool = True
    tags: List[str] = Field(default_factory=list, max_length=50)
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
        for img in images:
            validate_image_field(img, 'Product image')
        return images

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, tags: List[str]) -> List[str]:
        for tag in tags:
            if not (1 <= len(tag) <= 50):
                raise ValueError('Each tag must be 1-50 characters')
        return tags

class CartItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(ge=0, le=10_000_000)
    image: Optional[str] = Field('', max_length=2_800_000)
    size: Optional[str] = Field('', max_length=50)
    unit: Optional[str] = Field('piece', max_length=30)
    quantity: int = Field(gt=0, le=100000)
    moq: int = Field(1, ge=1, le=100000)

class AddressIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    mobile: str = Field(pattern=INDIAN_MOBILE_REGEX)
    email: EmailStr
    address_line1: str = Field(min_length=1, max_length=300)
    address_line2: Optional[str] = Field('', max_length=300)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    pincode: str = Field(pattern=INDIAN_PINCODE_REGEX)
    landmark: Optional[str] = Field('', max_length=200)
    gst_number: Optional[str] = Field('', max_length=20)

    @field_validator('gst_number')
    @classmethod
    def validate_gst_number(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_pattern(v, GST_NUMBER_REGEX, 'GST number')

class OrderIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: List[CartItem] = Field(min_length=1, max_length=200)
    address: AddressIn
    payment_method: Literal['cod', 'online']
    notes: Optional[str] = Field('', max_length=1000)
    coupon_code: Optional[str] = Field('', max_length=50)

class CartSyncItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(ge=0, le=10_000_000)
    quantity: int = Field(gt=0, le=100000)

class CartSyncIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mobile: str = Field(pattern=INDIAN_MOBILE_REGEX)
    name: Optional[str] = Field('', max_length=200)
    items: List[CartSyncItem] = Field(default_factory=list, max_length=200)
    subtotal: float = Field(0, ge=0, le=100_000_000)

class PaymentCreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    order_id: str = Field(min_length=1, max_length=100)
    amount: Optional[int] = Field(None, gt=0, le=10_000_000_00)
    currency: str = Field('INR', min_length=3, max_length=3)
    notes: Optional[Dict[str, Any]] = None

class PaymentVerifyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    order_id: str = Field(min_length=1, max_length=100)
    razorpay_order_id: str = Field(min_length=1, max_length=100)
    razorpay_payment_id: str = Field(min_length=1, max_length=100)
    razorpay_signature: str = Field(min_length=1, max_length=200)

class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['pending', 'confirmed', 'processing', 'packed', 'out for delivery', 'delivered', 'cancelled']
    tracking_note: Optional[str] = Field('', max_length=1000)

class ReturnItemIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0, le=100000)

class ReturnRequestIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=1000)
    items: List[ReturnItemIn] = Field(min_length=1, max_length=200)

class ReturnResolveIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['approved', 'rejected', 'refunded']
    note: Optional[str] = Field('', max_length=1000)

class TrackOrderRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    order_id: str = Field(min_length=1, max_length=50)
    mobile: str = Field(pattern=INDIAN_MOBILE_REGEX)

class CustomerSignupIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    mobile: str = Field(pattern=INDIAN_MOBILE_REGEX)

class CustomerLoginIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr
    password: str = Field(min_length=1, max_length=100)

class CustomerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    mobile: Optional[str] = Field(None, pattern=INDIAN_MOBILE_REGEX)

class SavedAddressIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: Optional[str] = Field(None, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    mobile: str = Field(pattern=INDIAN_MOBILE_REGEX)
    address_line1: str = Field(min_length=1, max_length=300)
    address_line2: Optional[str] = Field('', max_length=300)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    pincode: str = Field(pattern=INDIAN_PINCODE_REGEX)
    landmark: Optional[str] = Field('', max_length=200)
    gst_number: Optional[str] = Field(None, max_length=20)
    is_default: bool = False

    @field_validator('gst_number')
    @classmethod
    def validate_gst_number(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_pattern(v, GST_NUMBER_REGEX, 'GST number')

class SavedAddressUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    mobile: Optional[str] = Field(None, pattern=INDIAN_MOBILE_REGEX)
    address_line1: Optional[str] = Field(None, min_length=1, max_length=300)
    address_line2: Optional[str] = Field(None, max_length=300)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=1, max_length=100)
    pincode: Optional[str] = Field(None, pattern=INDIAN_PINCODE_REGEX)
    landmark: Optional[str] = Field(None, max_length=200)
    gst_number: Optional[str] = Field(None, max_length=20)
    is_default: Optional[bool] = None

    @field_validator('gst_number')
    @classmethod
    def validate_gst_number(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_pattern(v, GST_NUMBER_REGEX, 'GST number')

    @field_validator('gst_number')
    @classmethod
    def validate_gst_number(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_pattern(v, GST_NUMBER_REGEX, 'GST number')

class CustomerPasswordChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=6, max_length=100)

class WishlistMerge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_ids: List[str] = Field(default_factory=list, max_length=500)

class WhatsAppMessageIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=4096)
    mobile: Optional[str] = Field(None, pattern=r'^\d{10,15}$')

class CouponIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1, max_length=50, pattern=r'^[A-Za-z0-9_-]+$')
    type: Literal['percent', 'flat'] = 'percent'
    value: float = Field(gt=0, le=1_000_000)
    min_order: float = Field(0, ge=0, le=10_000_000)
    max_discount: Optional[float] = Field(0, ge=0, le=10_000_000)
    expiry: Optional[str] = Field('', max_length=40)
    active: bool = True
    usage_limit: int = Field(0, ge=0, le=1_000_000)

class CouponValidate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1, max_length=50)
    subtotal: float = Field(ge=0, le=100_000_000)

class BannerIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    subtitle: Optional[str] = Field('', max_length=300)
    image: str = Field('', max_length=2_800_000)
    link: Optional[str] = Field('', max_length=500)
    cta_text: Optional[str] = Field('Shop Now', max_length=50)
    active: bool = True
    order: int = Field(0, ge=0, le=100000)

    @field_validator('image')
    @classmethod
    def validate_image(cls, v: str) -> str:
        return validate_image_field(v, 'Banner image')

class ReviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    rating: int = Field(ge=1, le=5)
    title: Optional[str] = Field('', max_length=300)
    comment: str = Field(min_length=1, max_length=3000)
    order_id: Optional[str] = Field('', max_length=50)

class ContactIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    mobile: str = Field(pattern=INDIAN_MOBILE_REGEX)
    subject: Optional[str] = Field('', max_length=300)
    message: str = Field(min_length=1, max_length=3000)

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, v: Any) -> Any:
        return _empty_string_to_none(v)

class SettingsIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    business_name: Optional[str] = Field(None, max_length=200)
    tagline: Optional[str] = Field(None, max_length=300)
    address: Optional[str] = Field(None, max_length=500)
    landmark: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    phone2: Optional[str] = Field(None, max_length=20)
    whatsapp: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    upi_id: Optional[str] = Field(None, max_length=100)
    upi_qr: Optional[str] = Field(None, max_length=2_800_000)
    logo: Optional[str] = Field(None, max_length=2_800_000)
    bank_details: Optional[str] = Field(None, max_length=1000)
    hours: Optional[str] = Field(None, max_length=200)
    gstin: Optional[str] = Field(None, max_length=20)
    cgst_rate: Optional[float] = Field(None, ge=0, le=50)
    sgst_rate: Optional[float] = Field(None, ge=0, le=50)
    shipping_flat: Optional[float] = Field(None, ge=0, le=100_000)
    free_shipping_above: Optional[float] = Field(None, ge=0, le=100_000_000)

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, v: Any) -> Any:
        return _empty_string_to_none(v)

    @field_validator('gstin')
    @classmethod
    def validate_gstin(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_pattern(v, GST_NUMBER_REGEX, 'GSTIN')

    @field_validator('logo')
    @classmethod
    def validate_logo(cls, v: Optional[str]) -> Optional[str]:
        return validate_image_field(v, 'Logo')

    @field_validator('upi_qr')
    @classmethod
    def validate_upi_qr(cls, v: Optional[str]) -> Optional[str]:
        return validate_image_field(v, 'UPI QR code')

# ------------------ AUTH ROUTES ------------------

@api_router.post('/auth/login')
async def admin_login(req: LoginRequest, request: Request):
    email = req.email.lower()
    dependencies.check_auth_rate_limit(request, 'admin_login', email)
    u = await db.users.find_one({'email': email})
    if not u or not verify_password(req.password, u.get('password_hash', '')):
        dependencies.record_auth_failure(request, 'admin_login', email)
        raise HTTPException(status_code=401, detail='Invalid email or password')
    dependencies.clear_auth_attempts(request, 'admin_login', email)
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
    # Requiring a valid bearer token already keeps this from being a fully anonymous target,
    # but someone with a stolen/leaked token could otherwise brute-force current_password with
    # no limit at all - so it gets the same auth-tier backoff as login, keyed by account id.
    account_key = payload['sub']
    dependencies.check_auth_rate_limit(request, 'change_admin_password', account_key)
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail='New password and confirmation do not match')
    u = await db.users.find_one({'id': payload['sub']})
    if not u or not auth.verify_password(req.current_password, u.get('password_hash', '')):
        dependencies.record_auth_failure(request, 'change_admin_password', account_key)
        raise HTTPException(status_code=401, detail='Invalid email or password')
    dependencies.clear_auth_attempts(request, 'change_admin_password', account_key)
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
async def validate_coupon(req: CouponValidate, request: Request):
    # Public tier limit - otherwise this is an unauthenticated oracle for brute-forcing valid
    # discount codes (each guess is free and confirms/denies a code in one round trip).
    dependencies.check_rate_limit(request, 'coupon_validate', *rate_limits.get_bucket_limit('coupon_validate', 20, 15 * 60))
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
async def create_razorpay_order(req: PaymentCreateOrderRequest, request: Request):
    dependencies.check_rate_limit(request, 'payment_create_order', *rate_limits.get_bucket_limit('payment_create_order', 20, 15 * 60))
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
        logger.exception('Failed to create Razorpay order')
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
    # Auth-style limit with backoff, keyed by order_id - each call is effectively a guess at a
    # valid (payment_id, signature) pair for that order, so repeated failures should slow down
    # the same way a wrong-password attempt does.
    dependencies.check_auth_rate_limit(request, 'payment_verify', req.order_id)
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
    # Online payment success transitions the order straight to 'confirmed' (the order_pending
    # notification already went out at order creation) - send order_confirmation, the same
    # template/params an admin's manual "Confirmed" status change sends via
    # send_order_status_update_whatsapp(). invoice_ready is sent later, on delivery, not here.
    background_tasks.add_task(send_order_status_update_whatsapp, updated, 'confirmed', settings)
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
    dependencies.check_rate_limit(request, 'cart_sync', *rate_limits.get_bucket_limit('cart_sync', 30, 300))
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
async def create_order(order: OrderIn, background_tasks: BackgroundTasks, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    dependencies.check_authenticated_rate_limit(request, 'create_order', payload['sub'])
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
            res = await validate_coupon(CouponValidate(code=order.coupon_code, subtotal=subtotal), request)
        except HTTPException as e:
            raise HTTPException(status_code=400, detail=f'Coupon "{order.coupon_code}" is no longer valid: {e.detail}')
        discount = res['discount']
        coupon_code = res['code']
    settings = await db.settings.find_one({'id': 'main'}, {'_id': 0}) or {}
    cgst_rate = settings.get('cgst_rate', 0.0)
    sgst_rate = settings.get('sgst_rate', 0.0)
    tax_rate = cgst_rate + sgst_rate
    shipping_flat = settings.get('shipping_flat', 0.0)
    free_ship_above = settings.get('free_shipping_above', 0.0)
    taxable = max(0.0, subtotal - discount)
    tax = round(taxable * (tax_rate / 100.0), 2) if tax_rate else 0.0
    shipping = 0.0 if (free_ship_above and taxable >= free_ship_above) else shipping_flat
    total = round(taxable + tax + shipping, 2)
    oid = gen_order_id()
    # Invoice number is assigned at order placement (not lazily at first download) so it's
    # raised at the time of sale, matching how a GST tax invoice is meant to work - and stays
    # stable regardless of when the invoice PDF is actually first viewed.
    invoice_number = await generate_invoice_number()
    # GST invoices must split tax as IGST for interstate supply and CGST+SGST for intrastate;
    # the business is registered in Uttar Pradesh, so any other billing state is interstate.
    is_interstate = (order.address.state or '').strip().lower() != 'uttar pradesh'
    doc = {
        'id': oid,
        'order_number': oid,
        'invoice_number': invoice_number,
        'customer_id': payload['sub'],
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
        'cgst_rate': cgst_rate,
        'sgst_rate': sgst_rate,
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
async def track_order(req: TrackOrderRequest, request: Request):
    order_id = req.order_id.strip().upper()
    # Treated like an auth check (order_id + mobile is effectively a credential pair) rather
    # than a plain public read - without this, an attacker holding/guessing an order_id could
    # otherwise brute-force mobile numbers to pull someone else's name/address off the order.
    dependencies.check_auth_rate_limit(request, 'track_order', order_id)
    o = await db.orders.find_one({'id': order_id}, {'_id': 0})
    if not o or str(o['address'].get('mobile', '')).strip() != req.mobile.strip():
        dependencies.record_auth_failure(request, 'track_order', order_id)
        raise HTTPException(status_code=404, detail='Order not found')
    dependencies.clear_auth_attempts(request, 'track_order', order_id)
    return o

# ------------------ CUSTOMER ACCOUNTS ------------------

CUSTOMER_TOKEN_EXPIRE_DAYS = 30


async def _link_past_orders_to_customer(customer_id: str, email: str, mobile: str) -> None:
    """Best-effort backfill: orders placed as a guest (or before this account system existed)
    that match this customer's email/mobile get retroactively attached, so signing up doesn't
    orphan someone's order history. Safe to call repeatedly - only touches unlinked orders."""
    await db.orders.update_many(
        {'customer_id': {'$exists': False}, '$or': [{'address.mobile': mobile}, {'address.email': email}]},
        {'$set': {'customer_id': customer_id}},
    )


@api_router.post('/customer/auth/signup')
async def customer_signup(req: CustomerSignupIn, request: Request):
    email = req.email.lower()
    # Backoff (not just a flat cap) on signup too: repeatedly probing "does this email/mobile
    # already have an account" is itself an enumeration attack, so a rejected signup counts as
    # a failure the same way a wrong password would.
    dependencies.check_auth_rate_limit(request, 'customer_signup', email)
    if await db.customers.find_one({'email': email}):
        dependencies.record_auth_failure(request, 'customer_signup', email)
        raise HTTPException(status_code=400, detail='An account with this email already exists')
    mobile = ''.join(ch for ch in req.mobile if ch.isdigit())
    # Mobile must be unique too, not just email: _link_past_orders_to_customer backfills orders
    # by matching mobile OR email, so two accounts sharing a mobile number could otherwise end
    # up with each other's order history silently mixed together.
    if await db.customers.find_one({'mobile': mobile}):
        dependencies.record_auth_failure(request, 'customer_signup', email)
        raise HTTPException(status_code=400, detail='An account with this mobile number already exists')
    dependencies.clear_auth_attempts(request, 'customer_signup', email)
    cid = str(uuid.uuid4())
    doc = {
        'id': cid,
        'name': req.name.strip(),
        'email': email,
        'password_hash': auth.hash_password(req.password),
        'mobile': mobile,
        'token_version': 0,
        'created_at': now_iso(),
    }
    await db.customers.insert_one(doc)
    await _link_past_orders_to_customer(cid, email, mobile)
    token = create_token(cid, email, 'customer', 0, expires_delta=timedelta(days=CUSTOMER_TOKEN_EXPIRE_DAYS))
    return {'token': token, 'name': doc['name'], 'email': email}


@api_router.post('/customer/auth/login')
async def customer_login(req: CustomerLoginIn, request: Request):
    email = req.email.lower()
    dependencies.check_auth_rate_limit(request, 'customer_login', email)
    c = await db.customers.find_one({'email': email})
    if not c or not auth.verify_password(req.password, c.get('password_hash', '')):
        dependencies.record_auth_failure(request, 'customer_login', email)
        raise HTTPException(status_code=401, detail='Invalid email or password')
    dependencies.clear_auth_attempts(request, 'customer_login', email)
    await _link_past_orders_to_customer(c['id'], email, c.get('mobile', ''))
    token = create_token(c['id'], email, 'customer', c.get('token_version', 0), expires_delta=timedelta(days=CUSTOMER_TOKEN_EXPIRE_DAYS))
    return {'token': token, 'name': c.get('name', ''), 'email': email}


@api_router.get('/customer/auth/me')
async def customer_me(payload: Dict = Depends(dependencies.require_customer)):
    c = await db.customers.find_one({'id': payload['sub']}, {'_id': 0, 'password_hash': 0})
    if not c:
        raise HTTPException(status_code=404, detail='Account not found')
    return c


@api_router.get('/customer/profile')
async def get_customer_profile(payload: Dict = Depends(dependencies.require_customer)):
    c = await db.customers.find_one({'id': payload['sub']}, {'_id': 0, 'password_hash': 0})
    if not c:
        raise HTTPException(status_code=404, detail='Account not found')
    return c


@api_router.put('/customer/profile')
async def update_customer_profile(req: CustomerProfileUpdate, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    dependencies.check_authenticated_rate_limit(request, 'update_customer_profile', payload['sub'])
    doc = {k: v for k, v in req.model_dump().items() if v is not None}
    if not doc:
        raise HTTPException(status_code=400, detail='Nothing to update')
    if 'email' in doc:
        doc['email'] = doc['email'].lower()
        existing = await db.customers.find_one({'email': doc['email']})
        if existing and existing['id'] != payload['sub']:
            raise HTTPException(status_code=400, detail='Another account already uses this email')
    if 'mobile' in doc:
        doc['mobile'] = ''.join(ch for ch in doc['mobile'] if ch.isdigit())
        existing = await db.customers.find_one({'mobile': doc['mobile']})
        if existing and existing['id'] != payload['sub']:
            raise HTTPException(status_code=400, detail='Another account already uses this mobile number')
    doc['updated_at'] = now_iso()
    await db.customers.update_one({'id': payload['sub']}, {'$set': doc})
    return await db.customers.find_one({'id': payload['sub']}, {'_id': 0, 'password_hash': 0})


@api_router.post('/customer/profile/password')
async def change_customer_password(req: CustomerPasswordChange, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    account_key = payload['sub']
    dependencies.check_auth_rate_limit(request, 'change_customer_password', account_key)
    c = await db.customers.find_one({'id': payload['sub']})
    if not c or not auth.verify_password(req.current_password, c.get('password_hash', '')):
        dependencies.record_auth_failure(request, 'change_customer_password', account_key)
        raise HTTPException(status_code=401, detail='Current password is incorrect')
    dependencies.clear_auth_attempts(request, 'change_customer_password', account_key)
    new_version = c.get('token_version', 0) + 1
    await db.customers.update_one({'id': payload['sub']}, {'$set': {
        'password_hash': auth.hash_password(req.new_password),
        'token_version': new_version,
    }})
    token = create_token(c['id'], c['email'], 'customer', new_version, expires_delta=timedelta(days=CUSTOMER_TOKEN_EXPIRE_DAYS))
    return {'ok': True, 'token': token}


@api_router.get('/customer/orders')
async def customer_orders(payload: Dict = Depends(dependencies.require_customer)):
    orders = await db.orders.find({'customer_id': payload['sub']}, {'_id': 0}).sort('created_at', -1).to_list(200)
    return orders


MAX_CUSTOMER_ADDRESSES = 15


async def _get_or_migrate_addresses(customer_id: str) -> List[Dict]:
    c = await db.customers.find_one({'id': customer_id})
    if not c:
        return []
    addresses = c.get('addresses')
    if addresses is not None:
        return addresses
    # Accounts created before the address book existed may still have a single flat
    # address on the profile - migrate it in once (rather than running two parallel
    # address concepts) so nothing already saved is lost.
    if c.get('address_line1'):
        legacy = {
            'id': str(uuid.uuid4()),
            'label': 'Home',
            'name': c.get('name', ''),
            'mobile': c.get('mobile', ''),
            'address_line1': c.get('address_line1', ''),
            'address_line2': c.get('address_line2', ''),
            'city': c.get('city', ''),
            'state': c.get('state', ''),
            'pincode': c.get('pincode', ''),
            'landmark': c.get('landmark', ''),
            'gst_number': c.get('gst_number', ''),
            'is_default': True,
            'created_at': now_iso(),
        }
        await db.customers.update_one({'id': customer_id}, {'$set': {'addresses': [legacy]}})
        return [legacy]
    await db.customers.update_one({'id': customer_id}, {'$set': {'addresses': []}})
    return []


@api_router.get('/customer/addresses')
async def list_addresses(payload: Dict = Depends(dependencies.require_customer)):
    return await _get_or_migrate_addresses(payload['sub'])


@api_router.post('/customer/addresses')
async def add_address(req: SavedAddressIn, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    dependencies.check_authenticated_rate_limit(request, 'address_update', payload['sub'])
    addresses = await _get_or_migrate_addresses(payload['sub'])
    if len(addresses) >= MAX_CUSTOMER_ADDRESSES:
        raise HTTPException(status_code=400, detail=f'You can save up to {MAX_CUSTOMER_ADDRESSES} addresses. Delete one before adding another.')
    new_addr = req.model_dump()
    new_addr['id'] = str(uuid.uuid4())
    new_addr['created_at'] = now_iso()
    make_default = new_addr['is_default'] or not addresses
    new_addr['is_default'] = make_default
    if make_default:
        for a in addresses:
            a['is_default'] = False
    addresses.append(new_addr)
    await db.customers.update_one({'id': payload['sub']}, {'$set': {'addresses': addresses}})
    return addresses


@api_router.put('/customer/addresses/{address_id}')
async def update_address(address_id: str, req: SavedAddressUpdate, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    dependencies.check_authenticated_rate_limit(request, 'address_update', payload['sub'])
    addresses = await _get_or_migrate_addresses(payload['sub'])
    idx = next((i for i, a in enumerate(addresses) if a.get('id') == address_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail='Address not found')
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    addresses[idx] = {**addresses[idx], **updates}
    if updates.get('is_default'):
        for i, a in enumerate(addresses):
            a['is_default'] = (i == idx)
    await db.customers.update_one({'id': payload['sub']}, {'$set': {'addresses': addresses}})
    return addresses


@api_router.delete('/customer/addresses/{address_id}')
async def delete_address(address_id: str, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    dependencies.check_authenticated_rate_limit(request, 'address_update', payload['sub'])
    addresses = await _get_or_migrate_addresses(payload['sub'])
    remaining = [a for a in addresses if a.get('id') != address_id]
    if len(remaining) == len(addresses):
        raise HTTPException(status_code=404, detail='Address not found')
    if remaining and not any(a.get('is_default') for a in remaining):
        remaining[0]['is_default'] = True
    await db.customers.update_one({'id': payload['sub']}, {'$set': {'addresses': remaining}})
    return remaining


@api_router.post('/customer/addresses/{address_id}/default')
async def set_default_address(address_id: str, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    dependencies.check_authenticated_rate_limit(request, 'address_update', payload['sub'])
    addresses = await _get_or_migrate_addresses(payload['sub'])
    if not any(a.get('id') == address_id for a in addresses):
        raise HTTPException(status_code=404, detail='Address not found')
    for a in addresses:
        a['is_default'] = (a.get('id') == address_id)
    await db.customers.update_one({'id': payload['sub']}, {'$set': {'addresses': addresses}})
    return addresses


@api_router.get('/customer/wishlist')
async def get_wishlist(payload: Dict = Depends(dependencies.require_customer)):
    c = await db.customers.find_one({'id': payload['sub']}, {'_id': 0, 'wishlist': 1})
    return {'product_ids': (c or {}).get('wishlist', [])}


@api_router.post('/customer/wishlist/merge')
async def merge_wishlist(req: WishlistMerge, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    # Called once right after login to fold in any product IDs a guest saved to
    # localStorage before signing in, so switching devices/browsers never loses a save
    # that was already made - the account's list is the union, never a replace.
    dependencies.check_authenticated_rate_limit(request, 'wishlist_merge', payload['sub'])
    if req.product_ids:
        await db.customers.update_one({'id': payload['sub']}, {'$addToSet': {'wishlist': {'$each': req.product_ids}}})
    c = await db.customers.find_one({'id': payload['sub']}, {'_id': 0, 'wishlist': 1})
    return {'product_ids': (c or {}).get('wishlist', [])}


@api_router.post('/customer/wishlist/{product_id}')
async def add_to_wishlist(product_id: str, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    dependencies.check_authenticated_rate_limit(request, 'wishlist_update', payload['sub'])
    await db.customers.update_one({'id': payload['sub']}, {'$addToSet': {'wishlist': product_id}})
    c = await db.customers.find_one({'id': payload['sub']}, {'_id': 0, 'wishlist': 1})
    return {'product_ids': (c or {}).get('wishlist', [])}


@api_router.delete('/customer/wishlist/{product_id}')
async def remove_from_wishlist(product_id: str, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    dependencies.check_authenticated_rate_limit(request, 'wishlist_update', payload['sub'])
    await db.customers.update_one({'id': payload['sub']}, {'$pull': {'wishlist': product_id}})
    c = await db.customers.find_one({'id': payload['sub']}, {'_id': 0, 'wishlist': 1})
    return {'product_ids': (c or {}).get('wishlist', [])}


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
        writer.writerow([security.csv_safe(v) for v in [
            o.get('id', ''), o.get('created_at', '')[:10], o.get('status', ''),
            addr.get('name', ''), addr.get('mobile', ''), addr.get('email', ''),
            addr.get('city', ''), addr.get('state', ''), addr.get('pincode', ''),
            items_summary, o.get('subtotal', 0), o.get('discount', 0), o.get('tax', 0),
            o.get('shipping', 0), o.get('total', 0), o.get('payment_method', ''), o.get('payment_status', ''),
        ]])
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
    # Only notify on an actual status transition, so re-submitting the same status (e.g. a
    # double click/retry in the admin UI) never sends a duplicate WhatsApp message.
    status_changed = upd.status != old_status
    if status_changed:
        # Feature 1: WhatsApp status-update notification (non-blocking).
        background_tasks.add_task(send_order_status_update_whatsapp, updated, upd.status, settings)
        # Feature 2: once delivered, send order_delivered then, immediately after, invoice_ready
        # with the invoice PDF attached. BackgroundTasks runs tasks sequentially in the order
        # they're added, so queuing this after the line above guarantees order_delivered lands
        # before invoice_ready.
        if upd.status == 'delivered':
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

RETURN_WINDOW_DAYS = 7


@api_router.post('/customer/orders/{oid}/return')
async def request_return(oid: str, req: ReturnRequestIn, request: Request, payload: Dict = Depends(dependencies.require_customer)):
    dependencies.check_authenticated_rate_limit(request, 'return_request', payload['sub'])
    o = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not o or o.get('customer_id') != payload['sub']:
        raise HTTPException(status_code=404, detail='Order not found')
    if o.get('status') != 'delivered':
        raise HTTPException(status_code=400, detail='Only delivered orders can be returned')
    existing = o.get('return_request')
    if existing and existing.get('status') in ('requested', 'approved', 'refunded'):
        raise HTTPException(status_code=400, detail='A return request already exists for this order')
    delivered_at = next((h['at'] for h in reversed(o.get('status_history', [])) if h['status'] == 'delivered'), None)
    if delivered_at:
        try:
            delivered_dt = datetime.fromisoformat(delivered_at.replace('Z', '+00:00'))
            if delivered_dt.tzinfo is None:
                delivered_dt = delivered_dt.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - delivered_dt).days > RETURN_WINDOW_DAYS:
                raise HTTPException(status_code=400, detail=f'Return window of {RETURN_WINDOW_DAYS} days has passed')
        except HTTPException:
            raise
        except Exception:
            pass
    order_items = {it['product_id']: it for it in o.get('items', [])}
    return_items = []
    for ri in req.items:
        oi = order_items.get(ri.product_id)
        if not oi:
            raise HTTPException(status_code=400, detail=f'Item {ri.product_id} is not part of this order')
        if ri.quantity > oi['quantity']:
            raise HTTPException(status_code=400, detail=f'Cannot return more than the ordered quantity for {oi["name"]}')
        return_items.append({'product_id': ri.product_id, 'name': oi['name'], 'quantity': ri.quantity})
    return_request = {
        'id': str(uuid.uuid4()),
        'status': 'requested',
        'reason': req.reason,
        'items': return_items,
        'requested_at': now_iso(),
        'resolved_at': None,
        'resolution_note': '',
        'refunded_at': None,
    }
    await db.orders.update_one({'id': oid}, {'$set': {'return_request': return_request}})
    return await db.orders.find_one({'id': oid}, {'_id': 0})


@api_router.put('/orders/{oid}/return')
async def resolve_return(oid: str, req: ReturnResolveIn, request: Request, payload: Dict = Depends(require_admin)):
    o = await db.orders.find_one({'id': oid}, {'_id': 0})
    if not o:
        raise HTTPException(status_code=404, detail='Order not found')
    rr = o.get('return_request')
    if not rr:
        raise HTTPException(status_code=400, detail='No return request on this order')
    valid_transitions = {'requested': {'approved', 'rejected'}, 'approved': {'refunded'}}
    if req.status not in valid_transitions.get(rr['status'], set()):
        raise HTTPException(status_code=400, detail=f"Cannot move a return request from '{rr['status']}' to '{req.status}'")
    rr['status'] = req.status
    rr['resolution_note'] = req.note or rr.get('resolution_note', '')
    if req.status in ('approved', 'rejected'):
        rr['resolved_at'] = now_iso()
    if req.status == 'refunded':
        rr['refunded_at'] = now_iso()
    await db.orders.update_one({'id': oid}, {'$set': {'return_request': rr}})
    await audit.record_audit(db, payload.get('email', 'unknown'), security.get_client_ip(request), 'resolve_return', oid, {'status': req.status})
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
        # Customers can only download once the order is actually delivered - admins (payload
        # is truthy above) are exempt, since they legitimately need to view/print it earlier
        # (e.g. to attach with the shipment).
        if o.get('status') != 'delivered':
            raise HTTPException(status_code=403, detail='Invoice will be available for download once your order is delivered.')
    await get_or_assign_invoice_number(o)
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
        writer.writerow([security.csv_safe(v) for v in [
            d.get('name', ''), d.get('mobile', ''), d.get('email', ''), d.get('city', ''),
            d.get('orders', 0), d.get('spent', 0), (d.get('last_order') or '')[:10],
        ]])
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
    dependencies.check_rate_limit(request, 'create_review', *rate_limits.get_bucket_limit('create_review', 5, 15 * 60))
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

# ------------------ WHATSAPP APPROVED TEMPLATES (Meta WhatsApp Manager, Utility category) ------------------
# Exact template names as approved in Meta WhatsApp Manager. All are approved in English ('en'),
# which is send_template_message()'s default language_code. Body parameters, in order, per
# template (must exactly match the approved template's {{1}}, {{2}}, ... variable count, or
# Meta's Cloud API rejects the send with error #132000):
#   order_pending:              [customer_name, order_id, total_amount]
#   order_confirmation:         [customer_name, order_id, total_amount]
#   order_packed:               [customer_name, order_id]
#   order_out_for_dilivery:     [customer_name, order_id]
#   order_delivered:            [customer_name, order_id]
#   order_cancelled:            [customer_name, order_id, total_amount]
#   invoice_ready:              [customer_name, order_id, invoice_number]
#   review_request:             [customer_name, order_id]
WHATSAPP_TEMPLATE_ORDER_PENDING = 'order_pending'
WHATSAPP_TEMPLATE_ORDER_CONFIRMATION = 'order_confirmation'
WHATSAPP_TEMPLATE_ORDER_PACKED = 'order_packed'
WHATSAPP_TEMPLATE_ORDER_OUT_FOR_DELIVERY = 'order_out_for_dilivery'
WHATSAPP_TEMPLATE_ORDER_DELIVERED = 'order_delivered'
WHATSAPP_TEMPLATE_ORDER_CANCELLED = 'order_cancelled'
WHATSAPP_TEMPLATE_INVOICE_READY = 'invoice_ready'
WHATSAPP_TEMPLATE_REVIEW_REQUEST = 'review_request'

# Order statuses that have an approved lifecycle template, used by send_order_status_update_whatsapp()
# below. 'pending' is deliberately absent here - that notification is sent once, directly from order
# creation (see send_order_whatsapp()), not from a status transition. Statuses without an approved
# template (e.g. 'processing') keep using the free-form text fallback in build_status_update_message()/
# STATUS_WHATSAPP_TEMPLATES below, unchanged from before this migration.
STATUS_TO_WHATSAPP_TEMPLATE = {
    'confirmed': WHATSAPP_TEMPLATE_ORDER_CONFIRMATION,
    'packed': WHATSAPP_TEMPLATE_ORDER_PACKED,
    'out for delivery': WHATSAPP_TEMPLATE_ORDER_OUT_FOR_DELIVERY,
    'delivered': WHATSAPP_TEMPLATE_ORDER_DELIVERED,
    'cancelled': WHATSAPP_TEMPLATE_ORDER_CANCELLED,
}

# Templates whose body includes the order total as its 3rd parameter (in addition to the standard
# [customer_name, order_id] every lifecycle template starts with).
WHATSAPP_TEMPLATES_WITH_TOTAL_AMOUNT = {WHATSAPP_TEMPLATE_ORDER_CONFIRMATION, WHATSAPP_TEMPLATE_ORDER_CANCELLED}


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
    customer_name = address.get('name') or 'Customer'
    total_amount = f"{order.get('total', 0):.2f}"

    config = get_whatsapp_config()
    if not config.is_valid:
        logger.warning('WhatsApp Cloud API not configured; order notification skipped for order %s', order_id)
        return

    try:
        # Order placement/receipt notification -> the order_pending approved template. The order
        # is only confirmed later by an admin (see send_order_status_update_whatsapp(), triggered
        # from the 'confirmed' status transition), which sends order_confirmation instead.
        # Body variables: {{1}} customer name, {{2}} order id, {{3}} total amount.
        result = send_template_message(
            phone,
            WHATSAPP_TEMPLATE_ORDER_PENDING,
            body_parameters=[customer_name, order_id, total_amount],
            config=config,
        )
        record_whatsapp_message_sent(result, template=WHATSAPP_TEMPLATE_ORDER_PENDING, order_id=order_id)
    except Exception:
        logger.exception('Failed to send WhatsApp order notification for order %s', order_id)


# Feature 1: per-status WhatsApp text fallback for statuses with no approved template
# (e.g. 'pending', 'processing', 'cancelled') - see STATUS_TO_WHATSAPP_TEMPLATE above for the
# statuses that use an approved template instead.
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
    customer_name = address.get('name') or 'Customer'

    config = get_whatsapp_config()
    if not config.is_valid:
        logger.warning('WhatsApp Cloud API not configured; status update skipped for order %s', order_id)
        return

    template_name = STATUS_TO_WHATSAPP_TEMPLATE.get(status)
    try:
        if template_name:
            # Approved Utility Template for the five status-transition lifecycle stages Meta has
            # templates for. order_confirmation/order_cancelled expect a 3rd body variable (total
            # amount); the other mapped statuses (packed/out for delivery/delivered) are still
            # 2-parameter templates.
            body_parameters = [customer_name, order_id]
            if template_name in WHATSAPP_TEMPLATES_WITH_TOTAL_AMOUNT:
                body_parameters.append(f"{order.get('total', 0):.2f}")
            result = send_template_message(
                phone,
                template_name,
                body_parameters=body_parameters,
                config=config,
            )
        else:
            # No approved template for this status (e.g. 'cancelled', 'pending', 'processing') -
            # unchanged free-form text fallback, same behavior as before this migration.
            msg_body = build_status_update_message(customer_name, order_id, status, business_name)
            result = send_text_message(config, phone, msg_body)
        message_id = (result.get('messages') or [{}])[0].get('id') if isinstance(result, dict) else None
        logger.info('WhatsApp status update (%s) sent for order %s, message_id=%s', status, order_id, message_id)
        if template_name:
            record_whatsapp_message_sent(result, template=template_name, order_id=order_id, status=status)
    except Exception:
        logger.exception('Failed to send status update WhatsApp notification for order %s', order_id)


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
    """Background task: validate the invoice can be generated, then WhatsApp it (invoice_ready,
    PDF attached) to the customer. Triggered once an order is marked 'delivered', immediately
    after the order_delivered notification. Runs after the response has been sent; never raises
    (all failures are logged and swallowed) so it can never affect the order-status flow it's
    attached to."""
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
        customer_name = address.get('name') or 'Customer'
        # Same invoice-number assignment used by the /orders/{oid}/invoice endpoint itself, so the
        # number quoted in the WhatsApp message always matches the PDF Meta fetches from invoice_url.
        invoice_number = await get_or_assign_invoice_number(order)

        config = get_whatsapp_config()
        if not config.is_valid:
            logger.warning('WhatsApp Cloud API not configured; invoice message skipped for order %s', order_id)
            return

        # invoice_ready template: document header (the invoice PDF link) + body params
        # [customer_name, order_id, invoice_number]. invoice_url is a publicly-fetchable link
        # (Meta's servers need to be able to download it) to the same on-demand PDF endpoint used
        # everywhere else, so the attached document is exactly the backend-generated invoice.
        result = await asyncio.to_thread(
            send_template_message,
            phone,
            WHATSAPP_TEMPLATE_INVOICE_READY,
            [customer_name, order_id, invoice_number],
            {'link': invoice_url, 'filename': f'Invoice-{order_id}.pdf'},
            config,
        )
        message_id = (result.get('messages') or [{}])[0].get('id') if isinstance(result, dict) else None
        await db.orders.update_one({'id': order_id}, {'$set': {'invoice_sent': True, 'invoice_sent_at': now_iso()}})
        await asyncio.to_thread(record_whatsapp_message_sent, result, template=WHATSAPP_TEMPLATE_INVOICE_READY, order_id=order_id)
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

        customer_name = address.get('name') or 'Customer'
        try:
            result = await asyncio.to_thread(
                send_template_message,
                phone,
                WHATSAPP_TEMPLATE_REVIEW_REQUEST,
                [customer_name, order_id],
                None,
                config,
            )
            message_id = (result.get('messages') or [{}])[0].get('id') if isinstance(result, dict) else None
            await asyncio.to_thread(record_whatsapp_message_sent, result, template=WHATSAPP_TEMPLATE_REVIEW_REQUEST, order_id=order_id)
            logger.info('Review request WhatsApp sent for order %s, message_id=%s', order_id, message_id)
        except Exception:
            logger.exception('Failed to send review request WhatsApp for order %s', order_id)
    except Exception:
        logger.exception('Unexpected error in review request scheduler for order %s', order_id)


@api_router.post('/contact')
async def contact_submit(c: ContactIn, request: Request, background_tasks: BackgroundTasks):
    dependencies.check_rate_limit(request, 'contact_submit', *rate_limits.get_bucket_limit('contact_submit', 5, 15 * 60))
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

def _verify_whatsapp_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    if not signature_header.startswith('sha256='):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header[len('sha256='):])


@api_router.post('/webhooks/whatsapp')
async def handle_whatsapp_webhook(payload: Dict[str, Any], request: Request):
    """Meta calls this for every delivery-status update (sent/delivered/read/failed) and every
    inbound customer message, for every template/text message this app has ever sent - this is
    the *only* source of ground truth for what actually happened to a message after Meta's
    "accepted" response to the initial send call. Each event is logged in full and, for status
    callbacks, correlated back to the wamid recorded at send time (record_whatsapp_message_sent)."""
    dependencies.check_rate_limit(request, 'whatsapp_webhook', *rate_limits.get_bucket_limit('whatsapp_webhook', 120, 60))

    config = get_whatsapp_config()
    if config.app_secret:
        signature = request.headers.get('x-hub-signature-256', '')
        if not _verify_whatsapp_signature(await request.body(), signature, config.app_secret):
            logger.warning('Rejected WhatsApp webhook POST with invalid/missing signature')
            raise HTTPException(status_code=403, detail='Invalid signature')
    else:
        logger.warning(
            'WHATSAPP_APP_SECRET is not set - webhook POSTs are accepted without verifying they '
            'actually came from Meta. Set WHATSAPP_APP_SECRET (Meta App Dashboard > Settings > '
            'Basic) to enable signature verification.'
        )

    logger.info('WhatsApp webhook event received: %s', payload)

    for entry in payload.get('entry', []) or []:
        for change in entry.get('changes', []) or []:
            value = change.get('value', {}) or {}

            for status_event in value.get('statuses', []) or []:
                wamid = status_event.get('id')
                status = status_event.get('status')
                recipient = status_event.get('recipient_id')
                errors = status_event.get('errors') or []
                error_summary = '; '.join(
                    f"{e.get('code')}: {e.get('title') or e.get('message') or ''}" for e in errors
                ) if errors else None
                logger.info(
                    'WhatsApp status callback - Message ID: %s | Status: %s | Recipient: %s | Error: %s',
                    wamid, status, recipient, error_summary or 'none',
                )
                if wamid:
                    await db.whatsapp_message_events.update_one(
                        {'wamid': wamid},
                        {
                            '$set': {
                                'wamid': wamid,
                                'latest_status': status,
                                'latest_error': error_summary,
                                'recipient': recipient,
                                'updated_at': now_iso(),
                            },
                            '$push': {'status_history': {'status': status, 'at': now_iso(), 'error': error_summary}},
                            '$setOnInsert': {'created_at': now_iso()},
                        },
                        upsert=True,
                    )

            for inbound in value.get('messages', []) or []:
                logger.info(
                    'WhatsApp inbound message - Message ID: %s | From: %s | Type: %s',
                    inbound.get('id'), inbound.get('from'), inbound.get('type'),
                )

    return {'status': 'received'}


@api_router.get('/debug/whatsapp')
async def debug_whatsapp(payload: Dict = Depends(require_admin)):
    """Admin-only live diagnostic snapshot of the WhatsApp Cloud API integration: current
    config, Meta's own view of the phone number, whether the access token is actually valid,
    and the most recent message this app sent plus its latest known delivery status (if the
    webhook above has heard back about it yet). Gated behind admin auth - phone/app/business
    IDs and token validity are internal infrastructure details, not something to expose publicly."""
    config = get_whatsapp_config()
    result: Dict[str, Any] = {
        'phone_number_id': config.phone_number_id,
        'api_version': config.api_version,
        'graph_url': config.api_url,
        'webhook_configured': bool(config.verify_token),
        'access_token_valid': None,
        'display_phone_number': None,
        'verified_name': None,
        'quality_rating': None,
        'app_id': None,
        'last_message_id': None,
        'last_message_status': None,
    }

    if not config.is_valid:
        result['access_token_valid'] = False
        return result

    try:
        r = await asyncio.to_thread(
            requests.get,
            f'https://graph.facebook.com/{config.api_version}/{config.phone_number_id}',
            headers={'Authorization': f'Bearer {config.access_token}'},
            params={'fields': 'id,display_phone_number,verified_name,quality_rating,code_verification_status'},
            timeout=10,
        )
        phone_info = r.json()
        result['display_phone_number'] = phone_info.get('display_phone_number')
        result['verified_name'] = phone_info.get('verified_name')
        result['quality_rating'] = phone_info.get('quality_rating')
        result['code_verification_status'] = phone_info.get('code_verification_status')
    except Exception:
        logger.exception('debug/whatsapp: phone number lookup against Meta failed')

    try:
        r2 = await asyncio.to_thread(
            requests.get,
            f'https://graph.facebook.com/{config.api_version}/debug_token',
            params={'input_token': config.access_token, 'access_token': config.access_token},
            timeout=10,
        )
        token_info = (r2.json() or {}).get('data', {})
        result['access_token_valid'] = token_info.get('is_valid', False)
        result['app_id'] = token_info.get('app_id')
    except Exception:
        logger.exception('debug/whatsapp: access token debug lookup against Meta failed')
        result['access_token_valid'] = False

    last_event = await db.whatsapp_message_events.find_one({}, sort=[('created_at', -1)])
    if last_event:
        result['last_message_id'] = last_event.get('wamid')
        result['last_message_status'] = last_event.get('latest_status') or last_event.get('accepted_status')

    return result

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
        result = send_text_message(config, phone, body.message.strip())
        await asyncio.to_thread(record_whatsapp_message_sent, result, template='manual_text', order_id=oid)
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
    invoice_number = order.get('invoice_number', '') or '-'

    # ==================== TOP STRIP: GSTIN/PAN | TAX INVOICE | INVOICE NO. ====================
    gst_pan_block = Table([
        [Paragraph(f'<b>GSTIN :</b> {gstin}', small_style)],
        [Paragraph(f'<b>PAN :</b> {pan}', small_style)],
    ], colWidths=[58*mm])
    gst_pan_block.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))

    invoice_no_block = Table([
        [Paragraph('Invoice No.', label_style)],
        [Paragraph(invoice_number, order_id_style)],
    ], colWidths=[69*mm])
    invoice_no_block.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.75, BLACK),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    top_strip = Table([[gst_pan_block, Paragraph('TAX INVOICE', tax_invoice_style), invoice_no_block]], colWidths=[58*mm, 65*mm, 69*mm])
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
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
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
    cgst_rate = order.get('cgst_rate', 0)
    sgst_rate = order.get('sgst_rate', 0)
    tax_rate = order.get('tax_rate', cgst_rate + sgst_rate)
    is_interstate = order.get('is_interstate', False)
    taxable_value = max(0.0, order.get('subtotal', 0) - discount)
    cgst = sgst = igst = 0
    if tax > 0:
        if is_interstate:
            igst = tax
        else:
            cgst = round(taxable_value * (cgst_rate / 100.0), 2) if cgst_rate else 0.0
            sgst = round(taxable_value * (sgst_rate / 100.0), 2) if sgst_rate else 0.0

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
        total_rows.append([total_label(f'CGST @ {cgst_rate:g}%'), *rp(cgst)])
    if sgst > 0:
        total_rows.append([total_label(f'SGST @ {sgst_rate:g}%'), *rp(sgst)])
    if igst > 0:
        total_rows.append([total_label(f'IGST @ {tax_rate:g}%'), *rp(igst)])
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
            'cgst_rate': 0.0,
            'sgst_rate': 0.0,
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

async def _create_index_safely(collection, *args, **kwargs) -> None:
    """A single bad index (e.g. a unique index that can't build because existing data already
    has duplicates) must not take down the rest of startup with it - previously all indexes and
    start_abandoned_cart_watcher() shared one try/except, so one failure here silently skipped
    everything after it, including the background watcher ever starting."""
    try:
        await collection.create_index(*args, **kwargs)
    except Exception:
        logger.exception('Failed to create index %s on %s', args, collection.name)


@app.on_event('startup')
async def on_start():
    try:
        await seed_db()
        # indexes
        await _create_index_safely(db.products, 'slug')
        await _create_index_safely(db.products, 'category_id')
        await _create_index_safely(db.products, [('name', 'text'), ('description', 'text'), ('tags', 'text')])
        await _create_index_safely(db.orders, 'id')
        await _create_index_safely(db.orders, 'address.mobile')
        await _create_index_safely(db.categories, 'slug')
        await _create_index_safely(db.users, 'email')
        await _create_index_safely(db.audit_logs, [('timestamp', -1)])
        await _create_index_safely(db.abandoned_carts, 'mobile', unique=True)
        await _create_index_safely(db.customers, 'email', unique=True)
        await _create_index_safely(db.customers, 'mobile', unique=True)
        await _create_index_safely(db.orders, 'customer_id')
        start_abandoned_cart_watcher()
        logger.info('Startup complete')
    except Exception:
        logger.exception('Startup failed')

# Root
@api_router.get('/')
async def root():
    return {'app': 'Kiran Traders API', 'version': '1.0.0'}

@api_router.get('/health')
async def health():
    try:
        await db.command('ping')
        return {'status': 'ok', 'db': 'connected'}
    except Exception:
        logger.exception('Health check failed')
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
