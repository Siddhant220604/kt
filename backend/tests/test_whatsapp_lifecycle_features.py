import asyncio
import base64
import inspect
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')

import server


def test_schedule_review_request_actually_schedules_a_task():
    # Regression guard: schedule_review_request must be a plain function that calls
    # asyncio.create_task() internally. If it were declared `async def` and called
    # without awaiting/wrapping it at the call site, invoking it would just build an
    # unused coroutine object and silently do nothing (caught via RuntimeWarning during
    # manual verification) - the review-request feature would never fire.
    async def scenario():
        assert not inspect.iscoroutinefunction(server.schedule_review_request)
        before = len(server._background_asyncio_tasks)
        server.schedule_review_request("nonexistent-order-for-regression-test")
        assert len(server._background_asyncio_tasks) == before + 1
        task = next(t for t in server._background_asyncio_tasks if not t.done())
        assert isinstance(task, asyncio.Task)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())


def test_start_abandoned_cart_watcher_actually_schedules_a_task():
    # Same regression guard as above: start_abandoned_cart_watcher must be a plain function
    # that calls asyncio.create_task() internally, not `async def` (which would silently no-op
    # if ever called without being awaited/wrapped at the call site).
    async def scenario():
        assert not inspect.iscoroutinefunction(server.start_abandoned_cart_watcher)
        before = len(server._background_asyncio_tasks)
        server.start_abandoned_cart_watcher()
        assert len(server._background_asyncio_tasks) == before + 1
        task = next(t for t in server._background_asyncio_tasks if not t.done())
        assert isinstance(task, asyncio.Task)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())


def test_status_update_templates_match_spec():
    assert server.build_status_update_message('Alice', 'KT123', 'confirmed', 'Kiran Traders') == (
        "Hi Alice,\n\nYour order #KT123 has been confirmed."
    )
    assert server.build_status_update_message('Alice', 'KT123', 'packed', 'Kiran Traders') == (
        "Hi Alice,\n\nYour order #KT123 has been packed and is ready for dispatch."
    )
    assert server.build_status_update_message('Alice', 'KT123', 'out for delivery', 'Kiran Traders') == (
        "Hi Alice,\n\nYour order #KT123 is out for delivery and should arrive shortly."
    )
    assert server.build_status_update_message('Alice', 'KT123', 'delivered', 'Kiran Traders') == (
        "Hi Alice,\n\nYour order #KT123 has been delivered successfully.\n\nThank you for shopping with Kiran Traders."
    )
    assert server.build_status_update_message('Alice', 'KT123', 'cancelled', 'Kiran Traders') == (
        "Hi Alice,\n\nUnfortunately your order #KT123 has been cancelled.\n\nPlease contact us if you have any questions."
    )


def test_status_update_message_falls_back_for_unmapped_status():
    # 'pending' / 'processing' have no dedicated template - must fall back to the
    # original generic phrasing so existing behavior/tests for those statuses hold.
    msg = server.build_status_update_message('Alice', 'KT123', 'processing', 'Kiran Traders')
    assert msg == "Hi Alice, your order KT123 with Kiran Traders is now Processing. Thank you for shopping with us."


def test_build_invoice_pdf_without_logo_still_works():
    order = {
        'id': 'KT20260101ABCDEF',
        'created_at': '2026-01-01T10:00:00+00:00',
        'status': 'confirmed',
        'payment_method': 'cod',
        'address': {'name': 'Alice', 'mobile': '9999999999', 'address_line1': '1 Main St', 'city': 'Lucknow', 'state': 'UP', 'pincode': '226001'},
        'items': [{'name': 'Paper Glass', 'size': '200ml', 'quantity': 5, 'price': 120.0, 'total': 600.0}],
        'subtotal': 600.0,
        'discount': 60.0,
        'coupon_code': 'WELCOME10',
        'tax': 0,
        'shipping': 100.0,
        'total': 640.0,
    }
    pdf_bytes = server.build_invoice_pdf(order, {'business_name': 'Kiran Traders'})
    assert pdf_bytes.startswith(b'%PDF')


def test_build_invoice_pdf_with_logo_embeds_without_error():
    # 1x1 transparent PNG, base64-encoded, as a data URI (same shape as settings.upi_qr)
    tiny_png = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
    )
    logo_data_uri = 'data:image/png;base64,' + base64.b64encode(tiny_png).decode()
    order = {
        'id': 'KT20260101ABCDEF',
        'created_at': '2026-01-01T10:00:00+00:00',
        'status': 'confirmed',
        'payment_method': 'cod',
        'address': {'name': 'Alice', 'mobile': '9999999999', 'address_line1': '1 Main St', 'city': 'Lucknow', 'state': 'UP', 'pincode': '226001'},
        'items': [{'name': 'Paper Glass', 'size': '200ml', 'quantity': 5, 'price': 120.0, 'total': 600.0}],
        'subtotal': 600.0,
        'discount': 0,
        'tax': 0,
        'shipping': 0,
        'total': 600.0,
    }
    pdf_bytes = server.build_invoice_pdf(order, {'business_name': 'Kiran Traders', 'logo': logo_data_uri})
    assert pdf_bytes.startswith(b'%PDF')


def test_build_invoice_pdf_with_invalid_logo_degrades_gracefully():
    order = {
        'id': 'KT20260101ABCDEF',
        'created_at': '2026-01-01T10:00:00+00:00',
        'status': 'confirmed',
        'payment_method': 'cod',
        'address': {'name': 'Alice', 'mobile': '9999999999', 'address_line1': '1 Main St', 'city': 'Lucknow', 'state': 'UP', 'pincode': '226001'},
        'items': [{'name': 'Paper Glass', 'size': '200ml', 'quantity': 5, 'price': 120.0, 'total': 600.0}],
        'subtotal': 600.0,
        'discount': 0,
        'tax': 0,
        'shipping': 0,
        'total': 600.0,
    }
    pdf_bytes = server.build_invoice_pdf(order, {'business_name': 'Kiran Traders', 'logo': 'not-valid-base64!!'})
    assert pdf_bytes.startswith(b'%PDF')


def test_effective_unit_price_uses_base_price_below_first_tier():
    product = {'price': 100.0, 'price_tiers': [{'min_qty': 10, 'price': 90.0}, {'min_qty': 50, 'price': 80.0}]}
    assert server.effective_unit_price(product, 1) == 100.0
    assert server.effective_unit_price(product, 9) == 100.0


def test_effective_unit_price_applies_matching_tier():
    product = {'price': 100.0, 'price_tiers': [{'min_qty': 10, 'price': 90.0}, {'min_qty': 50, 'price': 80.0}]}
    assert server.effective_unit_price(product, 10) == 90.0
    assert server.effective_unit_price(product, 49) == 90.0
    assert server.effective_unit_price(product, 50) == 80.0
    assert server.effective_unit_price(product, 1000) == 80.0


def test_effective_unit_price_with_no_tiers_returns_base_price():
    assert server.effective_unit_price({'price': 55.0}, 500) == 55.0
