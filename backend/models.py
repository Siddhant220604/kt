"""Shared Pydantic models for the wholesale platform."""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    company: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    role: str
    company: Optional[str] = None
    created_at: str


# ---------- Category ----------
class CategoryCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = ""


class Category(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    slug: str
    description: str = ""
    created_at: str = Field(default_factory=now_iso)


# ---------- Product ----------
class PriceTier(BaseModel):
    min_qty: int
    price: float  # per unit


class ProductCreate(BaseModel):
    name: str
    description: str = ""
    category_id: str
    sku: str
    unit: str = "unit"  # e.g. carton, pallet, box
    base_price: float
    moq: int = 1  # minimum order quantity
    stock: int = 0
    price_tiers: List[PriceTier] = []
    images: List[str] = []  # storage paths
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    sku: Optional[str] = None
    unit: Optional[str] = None
    base_price: Optional[float] = None
    moq: Optional[int] = None
    stock: Optional[int] = None
    price_tiers: Optional[List[PriceTier]] = None
    images: Optional[List[str]] = None
    is_active: Optional[bool] = None


class Product(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    description: str = ""
    category_id: str
    sku: str
    unit: str = "unit"
    base_price: float
    moq: int = 1
    stock: int = 0
    price_tiers: List[PriceTier] = []
    images: List[str] = []
    is_active: bool = True
    rating_avg: float = 0.0
    rating_count: int = 0
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


# ---------- Orders ----------
class OrderItemInput(BaseModel):
    product_id: str
    quantity: int


class ShippingAddress(BaseModel):
    full_name: str
    company: Optional[str] = ""
    line1: str
    line2: Optional[str] = ""
    city: str
    state: str
    postal_code: str
    country: str
    phone: str


class OrderCreate(BaseModel):
    items: List[OrderItemInput]
    shipping_address: ShippingAddress
    notes: Optional[str] = ""


class OrderItem(BaseModel):
    product_id: str
    product_name: str
    sku: str
    unit_price: float
    quantity: int
    subtotal: float


class Order(BaseModel):
    id: str = Field(default_factory=new_id)
    order_number: str
    user_id: str
    user_email: str
    items: List[OrderItem]
    subtotal: float
    total: float
    status: str = "pending"  # pending, confirmed, shipped, delivered, cancelled
    payment_status: str = "unpaid"  # unpaid, paid
    shipping_address: ShippingAddress
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class OrderStatusUpdate(BaseModel):
    status: str


# ---------- Reviews ----------
class ReviewCreate(BaseModel):
    product_id: str
    order_id: str
    rating: int = Field(ge=1, le=5)
    title: str
    comment: str


class Review(BaseModel):
    id: str = Field(default_factory=new_id)
    product_id: str
    order_id: str
    user_id: str
    user_name: str
    rating: int
    title: str
    comment: str
    approved: bool = False
    created_at: str = Field(default_factory=now_iso)
