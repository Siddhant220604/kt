import requests
import sys
from datetime import datetime

BASE_URL = "https://kiran-ecommerce-2.preview.emergentagent.com/api"

class KiranTradersAPITester:
    def __init__(self):
        self.base_url = BASE_URL
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_product_id = None
        self.test_category_id = None
        self.test_order_id = None
        self.test_coupon_id = None
        self.test_banner_id = None
        self.test_review_id = None
        self.test_contact_id = None

    def log(self, msg, level='INFO'):
        print(f"[{level}] {msg}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        req_headers = {'Content-Type': 'application/json'}
        if self.token:
            req_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            req_headers.update(headers)

        self.tests_run += 1
        self.log(f"Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=req_headers, params=params, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=req_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=req_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}", 'PASS')
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}", 'FAIL')
                if response.text:
                    self.log(f"   Response: {response.text[:200]}", 'FAIL')

            return success, response.json() if response.text and success else {}

        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}", 'FAIL')
            return False, {}

    # ========== AUTH TESTS ==========
    def test_admin_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@kirantraders.com", "password": "Admin@123"}
        )
        if success and 'token' in response:
            self.token = response['token']
            self.log(f"   Token obtained: {self.token[:20]}...", 'INFO')
            return True
        return False

    def test_admin_me(self):
        """Test get current admin user"""
        success, response = self.run_test(
            "Get Admin User (/auth/me)",
            "GET",
            "auth/me",
            200
        )
        return success and response.get('email') == 'admin@kirantraders.com'

    def test_invalid_login(self):
        """Test invalid login credentials"""
        success, _ = self.run_test(
            "Invalid Login (should fail)",
            "POST",
            "auth/login",
            401,
            data={"email": "admin@kirantraders.com", "password": "wrongpassword"}
        )
        return success

    # ========== CATEGORIES TESTS ==========
    def test_list_categories(self):
        """Test list all categories"""
        success, response = self.run_test(
            "List Categories",
            "GET",
            "categories",
            200
        )
        if success and isinstance(response, list) and len(response) > 0:
            self.log(f"   Found {len(response)} categories", 'INFO')
            return True
        return False

    def test_create_category(self):
        """Test create category"""
        success, response = self.run_test(
            "Create Category",
            "POST",
            "categories",
            200,
            data={
                "name": f"Test Category {datetime.now().strftime('%H%M%S')}",
                "description": "Test category description",
                "icon": "Package",
                "order": 99
            }
        )
        if success and 'id' in response:
            self.test_category_id = response['id']
            self.log(f"   Created category ID: {self.test_category_id}", 'INFO')
            return True
        return False

    def test_get_category(self):
        """Test get single category"""
        if not self.test_category_id:
            self.log("   Skipped - no test category ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Get Category by ID",
            "GET",
            f"categories/{self.test_category_id}",
            200
        )
        return success

    def test_update_category(self):
        """Test update category"""
        if not self.test_category_id:
            self.log("   Skipped - no test category ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Update Category",
            "PUT",
            f"categories/{self.test_category_id}",
            200,
            data={
                "name": "Updated Test Category",
                "description": "Updated description",
                "icon": "Box",
                "order": 100
            }
        )
        return success

    def test_delete_category(self):
        """Test delete category"""
        if not self.test_category_id:
            self.log("   Skipped - no test category ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Delete Category",
            "DELETE",
            f"categories/{self.test_category_id}",
            200
        )
        return success

    # ========== PRODUCTS TESTS ==========
    def test_list_products(self):
        """Test list products"""
        success, response = self.run_test(
            "List Products",
            "GET",
            "products",
            200,
            params={"page": 1, "limit": 24}
        )
        if success and 'items' in response and len(response['items']) > 0:
            self.log(f"   Found {len(response['items'])} products", 'INFO')
            return True
        return False

    def test_list_featured_products(self):
        """Test list featured products"""
        success, response = self.run_test(
            "List Featured Products",
            "GET",
            "products",
            200,
            params={"featured": "true", "limit": 8}
        )
        return success and 'items' in response

    def test_search_products(self):
        """Test search products"""
        success, response = self.run_test(
            "Search Products (thermocol)",
            "GET",
            "products",
            200,
            params={"search": "thermocol", "page": 1}
        )
        return success and 'items' in response

    def test_filter_products_by_category(self):
        """Test filter products by category"""
        # Get first category
        _, cats = self.run_test("Get Categories for Filter", "GET", "categories", 200)
        if cats and len(cats) > 0:
            cat_id = cats[0]['id']
            success, response = self.run_test(
                "Filter Products by Category",
                "GET",
                "products",
                200,
                params={"category": cat_id}
            )
            return success and 'items' in response
        return False

    def test_filter_products_by_price(self):
        """Test filter products by price range"""
        success, response = self.run_test(
            "Filter Products by Price (100-500)",
            "GET",
            "products",
            200,
            params={"min_price": 100, "max_price": 500}
        )
        return success and 'items' in response

    def test_sort_products(self):
        """Test sort products"""
        success, response = self.run_test(
            "Sort Products by Price (asc)",
            "GET",
            "products",
            200,
            params={"sort": "price_asc"}
        )
        return success and 'items' in response

    def test_create_product(self):
        """Test create product"""
        # Get first category for product
        _, cats = self.run_test("Get Categories for Product", "GET", "categories", 200)
        if not cats or len(cats) == 0:
            self.log("   No categories found", 'WARN')
            return False
        
        cat_id = cats[0]['id']
        success, response = self.run_test(
            "Create Product",
            "POST",
            "products",
            200,
            data={
                "name": f"Test Product {datetime.now().strftime('%H%M%S')}",
                "category_id": cat_id,
                "description": "Test product description",
                "short_description": "Test product",
                "size": "10 inch",
                "unit": "piece",
                "price": 199.99,
                "compare_price": 249.99,
                "moq": 5,
                "stock": 100,
                "images": ["https://via.placeholder.com/400"],
                "featured": True,
                "active": True,
                "tags": ["test", "sample"]
            }
        )
        if success and 'id' in response:
            self.test_product_id = response['id']
            self.log(f"   Created product ID: {self.test_product_id}", 'INFO')
            return True
        return False

    def test_get_product(self):
        """Test get single product"""
        if not self.test_product_id:
            self.log("   Skipped - no test product ID", 'WARN')
            return True
        success, response = self.run_test(
            "Get Product by ID",
            "GET",
            f"products/{self.test_product_id}",
            200
        )
        return success and 'category' in response and 'related' in response

    def test_update_product(self):
        """Test update product"""
        if not self.test_product_id:
            self.log("   Skipped - no test product ID", 'WARN')
            return True
        
        _, cats = self.run_test("Get Categories for Update", "GET", "categories", 200)
        cat_id = cats[0]['id'] if cats else None
        if not cat_id:
            return False
            
        success, _ = self.run_test(
            "Update Product",
            "PUT",
            f"products/{self.test_product_id}",
            200,
            data={
                "name": "Updated Test Product",
                "category_id": cat_id,
                "description": "Updated description",
                "price": 299.99,
                "stock": 150,
                "moq": 10,
                "unit": "pack"
            }
        )
        return success

    def test_delete_product(self):
        """Test delete product"""
        if not self.test_product_id:
            self.log("   Skipped - no test product ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Delete Product",
            "DELETE",
            f"products/{self.test_product_id}",
            200
        )
        return success

    # ========== COUPONS TESTS ==========
    def test_list_coupons(self):
        """Test list coupons"""
        success, response = self.run_test(
            "List Coupons",
            "GET",
            "coupons",
            200
        )
        if success and isinstance(response, list):
            self.log(f"   Found {len(response)} coupons", 'INFO')
            return True
        return False

    def test_validate_coupon_welcome10(self):
        """Test validate WELCOME10 coupon"""
        success, response = self.run_test(
            "Validate Coupon WELCOME10 (Rs.500+ order)",
            "POST",
            "coupons/validate",
            200,
            data={"code": "WELCOME10", "subtotal": 600}
        )
        if success and response.get('discount') == 60:  # 10% of 600
            self.log(f"   Discount: Rs.{response.get('discount')}", 'INFO')
            return True
        return False

    def test_validate_coupon_below_min(self):
        """Test validate coupon below minimum order"""
        success, _ = self.run_test(
            "Validate Coupon Below Min Order (should fail)",
            "POST",
            "coupons/validate",
            400,
            data={"code": "WELCOME10", "subtotal": 300}
        )
        return success

    def test_validate_invalid_coupon(self):
        """Test validate invalid coupon"""
        success, _ = self.run_test(
            "Validate Invalid Coupon (should fail)",
            "POST",
            "coupons/validate",
            404,
            data={"code": "INVALID123", "subtotal": 1000}
        )
        return success

    def test_create_coupon(self):
        """Test create coupon"""
        success, response = self.run_test(
            "Create Coupon",
            "POST",
            "coupons",
            200,
            data={
                "code": f"TEST{datetime.now().strftime('%H%M%S')}",
                "type": "percent",
                "value": 15,
                "min_order": 1000,
                "max_discount": 200,
                "active": True,
                "usage_limit": 100
            }
        )
        if success and 'id' in response:
            self.test_coupon_id = response['id']
            self.log(f"   Created coupon ID: {self.test_coupon_id}", 'INFO')
            return True
        return False

    def test_update_coupon(self):
        """Test update coupon"""
        if not self.test_coupon_id:
            self.log("   Skipped - no test coupon ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Update Coupon",
            "PUT",
            f"coupons/{self.test_coupon_id}",
            200,
            data={
                "code": "TESTUPDATED",
                "type": "flat",
                "value": 100,
                "min_order": 500,
                "active": True,
                "usage_limit": 50
            }
        )
        return success

    def test_delete_coupon(self):
        """Test delete coupon"""
        if not self.test_coupon_id:
            self.log("   Skipped - no test coupon ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Delete Coupon",
            "DELETE",
            f"coupons/{self.test_coupon_id}",
            200
        )
        return success

    # ========== ORDERS TESTS ==========
    def test_create_order(self):
        """Test create order"""
        # Get a product first
        _, products = self.run_test("Get Products for Order", "GET", "products", 200, params={"limit": 1})
        if not products or 'items' not in products or len(products['items']) == 0:
            self.log("   No products found", 'WARN')
            return False
        
        product = products['items'][0]
        success, response = self.run_test(
            "Create Order",
            "POST",
            "orders",
            200,
            data={
                "items": [
                    {
                        "product_id": product['id'],
                        "name": product['name'],
                        "price": product['price'],
                        "image": product.get('images', [''])[0] if product.get('images') else '',
                        "size": product.get('size', ''),
                        "unit": product.get('unit', 'piece'),
                        "quantity": product.get('moq', 1),
                        "moq": product.get('moq', 1)
                    }
                ],
                "address": {
                    "name": "Test Customer",
                    "mobile": "9876543210",
                    "email": "test@example.com",
                    "address_line1": "123 Test Street",
                    "address_line2": "Near Test Market",
                    "city": "Lucknow",
                    "state": "Uttar Pradesh",
                    "pincode": "226001",
                    "landmark": "Test Landmark"
                },
                "payment_method": "cod",
                "notes": "Test order from API test"
            }
        )
        if success and 'id' in response:
            self.test_order_id = response['id']
            self.log(f"   Created order ID: {self.test_order_id}", 'INFO')
            self.log(f"   Order total: Rs.{response.get('total')}", 'INFO')
            return True
        return False

    def test_create_order_with_coupon(self):
        """Test create order with valid coupon"""
        # Get a product
        _, products = self.run_test("Get Products for Coupon Order", "GET", "products", 200, params={"limit": 1})
        if not products or 'items' not in products or len(products['items']) == 0:
            return False
        
        product = products['items'][0]
        # Use quantity to make subtotal > 500 for WELCOME10
        quantity = max(product.get('moq', 1), int(600 / product['price']) + 1)
        
        success, response = self.run_test(
            "Create Order with WELCOME10 Coupon",
            "POST",
            "orders",
            200,
            data={
                "items": [
                    {
                        "product_id": product['id'],
                        "name": product['name'],
                        "price": product['price'],
                        "image": product.get('images', [''])[0] if product.get('images') else '',
                        "size": product.get('size', ''),
                        "unit": product.get('unit', 'piece'),
                        "quantity": quantity,
                        "moq": product.get('moq', 1)
                    }
                ],
                "address": {
                    "name": "Coupon Test Customer",
                    "mobile": "9876543211",
                    "email": "coupon@example.com",
                    "address_line1": "456 Coupon Street",
                    "city": "Lucknow",
                    "state": "UP",
                    "pincode": "226002"
                },
                "payment_method": "upi",
                "coupon_code": "WELCOME10"
            }
        )
        if success and response.get('discount', 0) > 0:
            self.log(f"   Discount applied: Rs.{response.get('discount')}", 'INFO')
            return True
        return False

    def test_track_order(self):
        """Test track order"""
        if not self.test_order_id:
            self.log("   Skipped - no test order ID", 'WARN')
            return True
        success, response = self.run_test(
            "Track Order",
            "POST",
            "orders/track",
            200,
            data={"order_id": self.test_order_id, "mobile": "9876543210"}
        )
        return success and 'status_history' in response

    def test_track_order_wrong_mobile(self):
        """Test track order with wrong mobile (should fail)"""
        if not self.test_order_id:
            self.log("   Skipped - no test order ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Track Order Wrong Mobile (should fail)",
            "POST",
            "orders/track",
            403,
            data={"order_id": self.test_order_id, "mobile": "0000000000"}
        )
        return success

    def test_list_orders_admin(self):
        """Test list orders (admin)"""
        success, response = self.run_test(
            "List Orders (Admin)",
            "GET",
            "orders",
            200,
            params={"page": 1, "limit": 30}
        )
        if success and 'items' in response:
            self.log(f"   Found {len(response['items'])} orders", 'INFO')
            return True
        return False

    def test_get_order_admin(self):
        """Test get order detail (admin)"""
        if not self.test_order_id:
            self.log("   Skipped - no test order ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Get Order Detail (Admin)",
            "GET",
            f"orders/{self.test_order_id}",
            200
        )
        return success

    def test_update_order_status(self):
        """Test update order status"""
        if not self.test_order_id:
            self.log("   Skipped - no test order ID", 'WARN')
            return True
        success, response = self.run_test(
            "Update Order Status to Confirmed",
            "PUT",
            f"orders/{self.test_order_id}/status",
            200,
            data={"status": "confirmed", "tracking_note": "Order confirmed by admin"}
        )
        if success and response.get('status') == 'confirmed':
            self.log(f"   Status updated to: {response.get('status')}", 'INFO')
            return True
        return False

    def test_order_invoice_pdf(self):
        """Test order invoice PDF generation"""
        if not self.test_order_id:
            self.log("   Skipped - no test order ID", 'WARN')
            return True
        
        url = f"{self.base_url}/orders/{self.test_order_id}/invoice?mobile=9876543210"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200 and response.headers.get('content-type') == 'application/pdf':
                self.tests_run += 1
                self.tests_passed += 1
                self.log(f"✅ Order Invoice PDF - Status: 200, Content-Type: application/pdf", 'PASS')
                return True
            else:
                self.tests_run += 1
                self.log(f"❌ Order Invoice PDF - Status: {response.status_code}, Content-Type: {response.headers.get('content-type')}", 'FAIL')
                return False
        except Exception as e:
            self.tests_run += 1
            self.log(f"❌ Order Invoice PDF - Error: {str(e)}", 'FAIL')
            return False

    # ========== BANNERS TESTS ==========
    def test_list_banners_public(self):
        """Test list active banners (public)"""
        success, response = self.run_test(
            "List Active Banners (Public)",
            "GET",
            "banners",
            200
        )
        if success and isinstance(response, list):
            self.log(f"   Found {len(response)} active banners", 'INFO')
            return True
        return False

    def test_list_all_banners_admin(self):
        """Test list all banners (admin)"""
        success, response = self.run_test(
            "List All Banners (Admin)",
            "GET",
            "banners/all",
            200
        )
        return success and isinstance(response, list)

    def test_create_banner(self):
        """Test create banner"""
        success, response = self.run_test(
            "Create Banner",
            "POST",
            "banners",
            200,
            data={
                "title": f"Test Banner {datetime.now().strftime('%H%M%S')}",
                "subtitle": "Test banner subtitle",
                "image": "https://via.placeholder.com/1400x400",
                "link": "/products",
                "cta_text": "Shop Now",
                "active": True,
                "order": 99
            }
        )
        if success and 'id' in response:
            self.test_banner_id = response['id']
            self.log(f"   Created banner ID: {self.test_banner_id}", 'INFO')
            return True
        return False

    def test_update_banner(self):
        """Test update banner"""
        if not self.test_banner_id:
            self.log("   Skipped - no test banner ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Update Banner",
            "PUT",
            f"banners/{self.test_banner_id}",
            200,
            data={
                "title": "Updated Test Banner",
                "subtitle": "Updated subtitle",
                "image": "https://via.placeholder.com/1400x400",
                "link": "/products",
                "cta_text": "Buy Now",
                "active": False,
                "order": 100
            }
        )
        return success

    def test_delete_banner(self):
        """Test delete banner"""
        if not self.test_banner_id:
            self.log("   Skipped - no test banner ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Delete Banner",
            "DELETE",
            f"banners/{self.test_banner_id}",
            200
        )
        return success

    # ========== REVIEWS TESTS ==========
    def test_create_review(self):
        """Test create review"""
        # Get a product
        _, products = self.run_test("Get Products for Review", "GET", "products", 200, params={"limit": 1})
        if not products or 'items' not in products or len(products['items']) == 0:
            return False
        
        product = products['items'][0]
        success, response = self.run_test(
            "Create Review",
            "POST",
            "reviews",
            200,
            data={
                "product_id": product['id'],
                "name": "Test Reviewer",
                "rating": 5,
                "title": "Great product!",
                "comment": "This is a test review. Product quality is excellent.",
                "order_id": self.test_order_id or ""
            }
        )
        if success and 'id' in response:
            self.test_review_id = response['id']
            self.log(f"   Created review ID: {self.test_review_id}", 'INFO')
            return True
        return False

    def test_list_reviews_admin(self):
        """Test list all reviews (admin)"""
        success, response = self.run_test(
            "List All Reviews (Admin)",
            "GET",
            "reviews",
            200,
            params={"approved": "false"}
        )
        if success and isinstance(response, list):
            self.log(f"   Found {len(response)} pending reviews", 'INFO')
            return True
        return False

    def test_approve_review(self):
        """Test approve review"""
        if not self.test_review_id:
            self.log("   Skipped - no test review ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Approve Review",
            "PUT",
            f"reviews/{self.test_review_id}/approve",
            200
        )
        return success

    def test_get_product_reviews(self):
        """Test get product reviews (public)"""
        # Get a product
        _, products = self.run_test("Get Products for Reviews", "GET", "products", 200, params={"limit": 1})
        if not products or 'items' not in products or len(products['items']) == 0:
            return False
        
        product = products['items'][0]
        success, response = self.run_test(
            "Get Product Reviews (Public)",
            "GET",
            f"reviews/product/{product['id']}",
            200
        )
        return success and isinstance(response, list)

    def test_delete_review(self):
        """Test delete review"""
        if not self.test_review_id:
            self.log("   Skipped - no test review ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Delete Review",
            "DELETE",
            f"reviews/{self.test_review_id}",
            200
        )
        return success

    # ========== CONTACT TESTS ==========
    def test_submit_contact(self):
        """Test submit contact form"""
        success, response = self.run_test(
            "Submit Contact Form",
            "POST",
            "contact",
            200,
            data={
                "name": "Test Contact",
                "email": "test@example.com",
                "mobile": "9876543210",
                "subject": "Test Inquiry",
                "message": "This is a test contact message from API test."
            }
        )
        if success and 'id' in response:
            self.test_contact_id = response['id']
            self.log(f"   Created contact ID: {self.test_contact_id}", 'INFO')
            return True
        return False

    def test_list_contacts_admin(self):
        """Test list contacts (admin)"""
        success, response = self.run_test(
            "List Contacts (Admin)",
            "GET",
            "contact",
            200
        )
        if success and isinstance(response, list):
            self.log(f"   Found {len(response)} contacts", 'INFO')
            return True
        return False

    def test_mark_contact_read(self):
        """Test mark contact as read"""
        if not self.test_contact_id:
            self.log("   Skipped - no test contact ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Mark Contact as Read",
            "PUT",
            f"contact/{self.test_contact_id}/read",
            200
        )
        return success

    def test_delete_contact(self):
        """Test delete contact"""
        if not self.test_contact_id:
            self.log("   Skipped - no test contact ID", 'WARN')
            return True
        success, _ = self.run_test(
            "Delete Contact",
            "DELETE",
            f"contact/{self.test_contact_id}",
            200
        )
        return success

    # ========== SETTINGS TESTS ==========
    def test_get_settings_public(self):
        """Test get settings (public)"""
        success, response = self.run_test(
            "Get Settings (Public)",
            "GET",
            "settings",
            200
        )
        if success and 'business_name' in response:
            self.log(f"   Business: {response.get('business_name')}", 'INFO')
            return True
        return False

    def test_update_settings(self):
        """Test update settings (admin)"""
        success, _ = self.run_test(
            "Update Settings (Admin)",
            "PUT",
            "settings",
            200,
            data={
                "business_name": "Kiran Traders",
                "tagline": "Wholesale & Retail Packaging Essentials - Since 2004",
                "phone": "+91 98765 43210",
                "tax_rate": 0.0
            }
        )
        return success

    # ========== CUSTOMERS TESTS ==========
    def test_list_customers(self):
        """Test list customers (admin)"""
        success, response = self.run_test(
            "List Customers (Admin)",
            "GET",
            "customers",
            200
        )
        if success and isinstance(response, list):
            self.log(f"   Found {len(response)} customers", 'INFO')
            return True
        return False

    # ========== ADMIN STATS TESTS ==========
    def test_admin_stats(self):
        """Test admin dashboard stats"""
        success, response = self.run_test(
            "Admin Dashboard Stats",
            "GET",
            "admin/stats",
            200
        )
        if success and 'total_orders' in response and 'total_revenue' in response:
            self.log(f"   Total Orders: {response.get('total_orders')}", 'INFO')
            self.log(f"   Total Revenue: Rs.{response.get('total_revenue')}", 'INFO')
            self.log(f"   Total Products: {response.get('total_products')}", 'INFO')
            self.log(f"   Total Customers: {response.get('total_customers')}", 'INFO')
            return True
        return False

    # ========== RUN ALL TESTS ==========
    def run_all_tests(self):
        """Run all tests in sequence"""
        self.log("=" * 60, 'INFO')
        self.log("KIRAN TRADERS API TEST SUITE", 'INFO')
        self.log("=" * 60, 'INFO')
        
        # Auth tests
        self.log("\n--- AUTH TESTS ---", 'INFO')
        self.test_invalid_login()
        if not self.test_admin_login():
            self.log("❌ Admin login failed - stopping tests", 'FAIL')
            return False
        self.test_admin_me()
        
        # Settings tests (public)
        self.log("\n--- SETTINGS TESTS (PUBLIC) ---", 'INFO')
        self.test_get_settings_public()
        
        # Categories tests
        self.log("\n--- CATEGORIES TESTS ---", 'INFO')
        self.test_list_categories()
        self.test_create_category()
        self.test_get_category()
        self.test_update_category()
        self.test_delete_category()
        
        # Products tests
        self.log("\n--- PRODUCTS TESTS ---", 'INFO')
        self.test_list_products()
        self.test_list_featured_products()
        self.test_search_products()
        self.test_filter_products_by_category()
        self.test_filter_products_by_price()
        self.test_sort_products()
        self.test_create_product()
        self.test_get_product()
        self.test_update_product()
        self.test_delete_product()
        
        # Coupons tests
        self.log("\n--- COUPONS TESTS ---", 'INFO')
        self.test_list_coupons()
        self.test_validate_coupon_welcome10()
        self.test_validate_coupon_below_min()
        self.test_validate_invalid_coupon()
        self.test_create_coupon()
        self.test_update_coupon()
        self.test_delete_coupon()
        
        # Orders tests
        self.log("\n--- ORDERS TESTS ---", 'INFO')
        self.test_create_order()
        self.test_create_order_with_coupon()
        self.test_track_order()
        self.test_track_order_wrong_mobile()
        self.test_list_orders_admin()
        self.test_get_order_admin()
        self.test_update_order_status()
        self.test_order_invoice_pdf()
        
        # Banners tests
        self.log("\n--- BANNERS TESTS ---", 'INFO')
        self.test_list_banners_public()
        self.test_list_all_banners_admin()
        self.test_create_banner()
        self.test_update_banner()
        self.test_delete_banner()
        
        # Reviews tests
        self.log("\n--- REVIEWS TESTS ---", 'INFO')
        self.test_create_review()
        self.test_list_reviews_admin()
        self.test_approve_review()
        self.test_get_product_reviews()
        self.test_delete_review()
        
        # Contact tests
        self.log("\n--- CONTACT TESTS ---", 'INFO')
        self.test_submit_contact()
        self.test_list_contacts_admin()
        self.test_mark_contact_read()
        self.test_delete_contact()
        
        # Settings tests (admin)
        self.log("\n--- SETTINGS TESTS (ADMIN) ---", 'INFO')
        self.test_update_settings()
        
        # Customers tests
        self.log("\n--- CUSTOMERS TESTS ---", 'INFO')
        self.test_list_customers()
        
        # Admin stats tests
        self.log("\n--- ADMIN STATS TESTS ---", 'INFO')
        self.test_admin_stats()
        
        return True

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "=" * 60, 'INFO')
        self.log("TEST SUMMARY", 'INFO')
        self.log("=" * 60, 'INFO')
        self.log(f"Total Tests: {self.tests_run}", 'INFO')
        self.log(f"Passed: {self.tests_passed}", 'PASS')
        self.log(f"Failed: {self.tests_run - self.tests_passed}", 'FAIL')
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"Success Rate: {success_rate:.1f}%", 'INFO')
        self.log("=" * 60, 'INFO')
        
        return 0 if self.tests_passed == self.tests_run else 1


def main():
    tester = KiranTradersAPITester()
    tester.run_all_tests()
    return tester.print_summary()


if __name__ == "__main__":
    sys.exit(main())
