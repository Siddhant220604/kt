import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')

import server


def test_send_order_notification_sends_whatsapp(monkeypatch):
    sent = {}

    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'

    def fake_get_whatsapp_config():
        return DummyConfig()

    def fake_send_text_message(config, to_number, text):
        sent['to_number'] = to_number
        sent['text'] = text
        return {'messages': [{'id': 'msgid'}]}

    monkeypatch.setattr(server, 'get_whatsapp_config', fake_get_whatsapp_config)
    monkeypatch.setattr(server, 'send_text_message', fake_send_text_message)

    order = {
        'id': 'KT20260708ABC123',
        'total': 499.0,
        'address': {
            'name': 'Alice',
            'mobile': '9999999999',
        },
        'items': [
            {'name': 'Test Product', 'quantity': 2, 'price': 249.5}
        ],
    }

    server.send_order_notification(order, {'business_name': 'Kiran Traders'})

    assert sent['to_number'] == '919999999999'
    assert 'KT20260708ABC123' in sent['text']
    assert 'has been received' in sent['text']


def test_send_order_whatsapp_sends_message(monkeypatch):
    sent = {}

    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'

    def fake_get_whatsapp_config():
        return DummyConfig()

    def fake_send_text_message(config, to_number, text):
        sent['to_number'] = to_number
        sent['text'] = text
        return {'messages': [{'id': 'msgid'}]}

    monkeypatch.setattr(server, 'get_whatsapp_config', fake_get_whatsapp_config)
    monkeypatch.setattr(server, 'send_text_message', fake_send_text_message)

    order = {
        'id': 'KT20260708ABC123',
        'total': 499.0,
        'address': {
            'name': 'Alice',
            'mobile': '9999999999',
        },
        'items': [
            {'name': 'Test Product', 'quantity': 2, 'price': 249.5}
        ],
    }

    server.send_order_whatsapp(order, {'business_name': 'Kiran Traders'})

    assert sent['to_number'] == '919999999999'
    assert 'KT20260708ABC123' in sent['text']
    assert 'has been received' in sent['text']


def test_send_order_status_update_whatsapp_sends_message(monkeypatch):
    sent = {}

    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'

    def fake_get_whatsapp_config():
        return DummyConfig()

    def fake_send_text_message(config, to_number, text):
        sent['to_number'] = to_number
        sent['text'] = text
        return {'messages': [{'id': 'msgid'}]}

    monkeypatch.setattr(server, 'get_whatsapp_config', fake_get_whatsapp_config)
    monkeypatch.setattr(server, 'send_text_message', fake_send_text_message)

    order = {
        'id': 'KT20260708ABC123',
        'address': {
            'name': 'Alice',
            'mobile': '9999999999',
        },
    }

    server.send_order_status_update_whatsapp(order, 'processing', {'business_name': 'Kiran Traders'})

    assert sent['to_number'] == '919999999999'
    assert 'now Processing' in sent['text']


def test_build_whatsapp_number_normalizes_to_e164():
    assert server.build_whatsapp_number('99999 99999', '+91') == '919999999999'
    assert server.build_whatsapp_number('+91-99999-99999', '+91') == '919999999999'
    assert server.build_whatsapp_number('(999)999-9999', '+91') == '919999999999'
    assert server.build_whatsapp_number('00919999999999', '+91') == '919999999999'
    assert server.build_whatsapp_number('12345', '+91') == ''
