import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import server


# ---------------- ProductIn.colors validation ----------------

def _product_in(**overrides):
    base = dict(name='Ribbon', category_id='cat-1', price=10)
    base.update(overrides)
    return server.ProductIn(**base)  # pyright: ignore[reportCallIssue]


def test_colors_default_to_empty_list():
    assert _product_in().colors == []


def test_colors_are_trimmed_and_blanks_dropped():
    assert _product_in(colors=['  Red ', '', '   ', 'Blue']).colors == ['Red', 'Blue']


def test_colors_dedupe_case_insensitively_keeping_first_spelling():
    assert _product_in(colors=['Red', 'RED', 'red ', 'Blue']).colors == ['Red', 'Blue']


def test_color_longer_than_50_chars_is_rejected():
    with pytest.raises(ValidationError):
        _product_in(colors=['x' * 51])


# ---------------- resolve_item_color ----------------

COLOURED = {'name': 'Ribbon', 'colors': ['Red', 'Golden Yellow']}
PLAIN = {'name': 'Kitchen Roll', 'colors': []}


def test_resolve_returns_the_catalog_spelling_not_the_customers():
    assert server.resolve_item_color(COLOURED, 'golden   yellow'.replace('   ', ' ')) == 'Golden Yellow'
    assert server.resolve_item_color(COLOURED, '  red  ') == 'Red'


def test_resolve_rejects_a_colour_the_product_does_not_come_in():
    with pytest.raises(HTTPException) as e:
        server.resolve_item_color(COLOURED, 'Purple')
    assert e.value.status_code == 400
    assert 'Purple' in e.value.detail


def test_resolve_requires_a_choice_when_the_product_has_colours():
    with pytest.raises(HTTPException) as e:
        server.resolve_item_color(COLOURED, '')
    assert e.value.status_code == 400


def test_resolve_ignores_a_colour_sent_for_a_product_without_any():
    # A stale cart line must not stamp a colour onto a product that isn't sold in colours.
    assert server.resolve_item_color(PLAIN, 'Red') == ''
    assert server.resolve_item_color({'name': 'Ribbon'}, 'Red') == ''


# ---------------- display name ----------------

def test_display_name_appends_colour_only_when_present():
    assert server.item_display_name({'name': 'Ribbon', 'color': 'Red'}) == 'Ribbon (Red)'
    assert server.item_display_name({'name': 'Ribbon', 'color': ''}) == 'Ribbon'
    assert server.item_display_name({'name': 'Ribbon'}) == 'Ribbon'


# ---------------- duplicate-order fingerprint ----------------

def _order(items):
    return server.OrderIn(
        items=items,
        address=server.AddressIn(  # pyright: ignore[reportCallIssue]
            name='Test', mobile='9876543210', email='a@b.com',
            address_line1='1 Road', city='Lucknow', state='Uttar Pradesh', pincode='226004',
        ),
        payment_method='cod',
    )  # pyright: ignore[reportCallIssue]


def _item(color, quantity=1):
    return server.CartItem(product_id='p1', name='Ribbon', price=10, quantity=quantity, color=color)  # pyright: ignore[reportCallIssue]


def test_same_product_in_two_colours_is_not_a_duplicate_of_one():
    both = server._order_fingerprint(_order([_item('Red'), _item('Black')]))
    single = server._order_fingerprint(_order([_item('Red')]))
    assert both != single


def test_identical_orders_still_fingerprint_the_same():
    a = server._order_fingerprint(_order([_item('Red', 2)]))
    b = server._order_fingerprint(_order([_item('  red ', 2)]))
    assert a == b
