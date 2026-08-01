"""Query-string validation on the list endpoints.

These parameters reach Mongo's skip/limit and sort directly. Bounds on them are what stops a
query string from asking for the whole catalog in one response, or from reaching Motor with a
negative length, so they are worth a test rather than trust.

No database is needed: a rejected request never gets as far as a handler, and every case here
is a rejection. The one accepted case asserts only that validation let it through.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize('query', [
    'limit=100000',          # would have serialised the entire catalog
    'limit=0',
    'limit=-1',              # reached Motor's to_list(), which rejects a negative length
    'page=0',
    'page=-3',
    'sort=; drop',           # anything outside the sort_map is now refused, not silently ignored
    'search_in=description',
    'min_price=-5',
    'search=' + 'x' * 101,   # SEARCH_MAX_LEN
])
def test_product_list_rejects_out_of_range_query(query):
    assert client.get(f'/api/products?{query}').status_code == 422


def test_product_list_accepts_the_admin_grid_page_size():
    # 200 is MAX_PAGE_SIZE and what pages/admin/Products.js asks for; anything above is refused.
    assert client.get('/api/products?limit=200').status_code != 422
    assert client.get('/api/products?limit=201').status_code == 422


@pytest.mark.parametrize('query', ['status=not-a-status', 'limit=100000', 'page=0'])
def test_order_list_requires_auth_before_it_says_anything_about_the_query(query):
    # /orders is staff-only, and the auth dependency resolves first: an anonymous caller gets
    # 401 whether or not the query is well-formed. That ordering is the right way round - a 422
    # here would confirm the endpoint exists and that its parameters were understood. The bounds
    # themselves are covered above on /products, which is public and so observable directly.
    assert client.get(f'/api/orders?{query}').status_code == 401
