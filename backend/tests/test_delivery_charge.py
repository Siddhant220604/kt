import asyncio
import logging
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')

import server


class _FakeAddress:
    def __init__(self, address_line1='123 Test St', address_line2='', city='Lucknow', state='Uttar Pradesh', pincode='226001'):
        self.address_line1 = address_line1
        self.address_line2 = address_line2
        self.city = city
        self.state = state
        self.pincode = pincode


class _FakeSettingsCollection:
    def __init__(self, settings_doc):
        self._doc = settings_doc

    async def find_one(self, *args, **kwargs):
        return dict(self._doc)


class _FakeDB:
    def __init__(self, settings_doc):
        self.settings = _FakeSettingsCollection(settings_doc)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


SHOP_LAT = 26.8467
SHOP_LNG = 80.9462

DEFAULT_SETTINGS = {
    'shop_lat': SHOP_LAT,
    'shop_lng': SHOP_LNG,
    'shipping_flat': 100.0,
    'free_shipping_above': 2000.0,
}


def _install_fake_db(monkeypatch, settings_doc=None):
    monkeypatch.setattr(server, 'db', _FakeDB(settings_doc or DEFAULT_SETTINGS))


def _install_google_key(monkeypatch, key='test-key'):
    monkeypatch.setattr(server, 'GOOGLE_MAPS_API_KEY', key)


def test_normal_lucknow_address_calculates_driving_distance_charge(monkeypatch):
    _install_fake_db(monkeypatch)
    _install_google_key(monkeypatch)

    def fake_get(url, params=None, timeout=None):
        if 'geocode' in url:
            return _FakeResponse({
                'status': 'OK',
                'results': [{
                    'geometry': {'location': {'lat': 26.86, 'lng': 80.96}},
                    'address_components': [{'long_name': 'Lucknow', 'types': ['locality']}],
                }],
            })
        if 'distancematrix' in url:
            # 3.2km actual driving distance -> should be rounded up to 4km -> Rs 80.
            return _FakeResponse({
                'status': 'OK',
                'rows': [{'elements': [{'status': 'OK', 'distance': {'value': 3200}}]}],
            })
        raise AssertionError(f'unexpected URL: {url}')

    monkeypatch.setattr(server.requests, 'get', fake_get)

    async def scenario():
        return await server.calculate_delivery_charge(_FakeAddress())

    result = asyncio.run(scenario())

    assert result['delivery_allowed'] is True
    assert result['used_fallback'] is False
    assert result['reason'] is None
    assert result['distance_km'] == 3.2
    assert result['shipping'] == 80.0


def test_out_of_lucknow_address_is_rejected(monkeypatch):
    _install_fake_db(monkeypatch)
    _install_google_key(monkeypatch)

    def fake_get(url, params=None, timeout=None):
        # City check fails before any driving-distance lookup is needed.
        assert 'geocode' in url
        return _FakeResponse({
            'status': 'OK',
            'results': [{
                'geometry': {'location': {'lat': 28.7041, 'lng': 77.1025}},
                'address_components': [{'long_name': 'New Delhi', 'types': ['locality']}],
            }],
        })

    monkeypatch.setattr(server.requests, 'get', fake_get)

    async def scenario():
        return await server.calculate_delivery_charge(_FakeAddress(city='New Delhi', state='Delhi', pincode='110001'))

    result = asyncio.run(scenario())

    assert result['delivery_allowed'] is False
    assert result['reason'] == server.DELIVERY_UNAVAILABLE_MESSAGE
    assert result['shipping'] == 0.0


def test_25km_radius_backstop_rejects_far_address_even_if_city_matches(monkeypatch):
    # Guards against an ambiguous/wrong geocode match that reports "Lucknow" for a locality
    # that is actually far outside city limits.
    _install_fake_db(monkeypatch)
    _install_google_key(monkeypatch)

    def fake_get(url, params=None, timeout=None):
        assert 'geocode' in url
        return _FakeResponse({
            'status': 'OK',
            'results': [{
                'geometry': {'location': {'lat': 27.9, 'lng': 82.0}},  # ~150km from the shop
                'address_components': [{'long_name': 'Lucknow', 'types': ['locality']}],
            }],
        })

    monkeypatch.setattr(server.requests, 'get', fake_get)

    async def scenario():
        return await server.calculate_delivery_charge(_FakeAddress())

    result = asyncio.run(scenario())

    assert result['delivery_allowed'] is False
    assert result['reason'] == server.DELIVERY_UNAVAILABLE_MESSAGE
    assert result['distance_km'] > server.MAX_DELIVERY_RADIUS_KM


def test_haversine_fallback_when_distance_matrix_fails(monkeypatch, caplog):
    _install_fake_db(monkeypatch)
    _install_google_key(monkeypatch)

    def fake_get(url, params=None, timeout=None):
        if 'geocode' in url:
            return _FakeResponse({
                'status': 'OK',
                'results': [{
                    'geometry': {'location': {'lat': 26.86, 'lng': 80.96}},
                    'address_components': [{'long_name': 'Lucknow', 'types': ['locality']}],
                }],
            })
        if 'distancematrix' in url:
            raise Exception('simulated network failure')
        raise AssertionError(f'unexpected URL: {url}')

    monkeypatch.setattr(server.requests, 'get', fake_get)

    async def scenario():
        return await server.calculate_delivery_charge(_FakeAddress())

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(scenario())

    assert result['delivery_allowed'] is True
    assert result['used_fallback'] is True
    assert result['distance_km'] > 0
    assert result['shipping'] == math.ceil(result['distance_km']) * server.DELIVERY_RATE_PER_KM
    assert 'Falling back to Haversine distance' in caplog.text
