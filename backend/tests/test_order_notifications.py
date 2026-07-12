import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')

import server
from services import whatsapp_service


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


def test_send_whatsapp_logs_response_details(monkeypatch, caplog):
    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'
        default_country_code = '+91'

    class DummyResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception('bad request')

        def json(self):
            return self._payload

    def fake_post(url, headers, json, timeout):
        assert url == DummyConfig.api_url
        assert headers['Authorization'] == 'Bearer token'
        assert json['to'] == '919999999999'
        return DummyResponse(200, {'messages': [{'id': 'msg-123'}]})

    monkeypatch.setattr(whatsapp_service, 'requests', type('RequestsStub', (), {'post': staticmethod(fake_post)}))

    with caplog.at_level(logging.INFO):
        result = whatsapp_service.send_whatsapp_message(DummyConfig(), '9999999999', 'text', {'text': {'body': 'hello'}})

    assert result == {'messages': [{'id': 'msg-123'}]}
    assert 'Sending WhatsApp message to 919999999999 via https://graph.facebook.com/v23.0/123/messages' in caplog.text
    assert 'Request URL:' in caplog.text
    assert 'Request JSON payload:' in caplog.text
    assert 'Recipient phone number: 919999999999' in caplog.text
    assert 'HTTP status code:' in caplog.text
    assert 'Full response JSON:' in caplog.text
    assert 'Message ID: msg-123' in caplog.text


def test_send_whatsapp_logs_template_details(monkeypatch, caplog):
    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'
        default_country_code = '+91'

    class DummyResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception('bad request')

        def json(self):
            return self._payload

    def fake_post(url, headers, json, timeout):
        return DummyResponse(200, {'messages': [{'id': 'msg-template-123'}]})

    monkeypatch.setattr(whatsapp_service, 'requests', type('RequestsStub', (), {'post': staticmethod(fake_post)}))

    with caplog.at_level(logging.INFO):
        whatsapp_service.send_whatsapp_message(
            DummyConfig(),
            '9999999999',
            'template',
            {
                'template': {
                    'name': 'order_confirmation',
                    'language': {'code': 'en_US'},
                    'components': [
                        {'type': 'body', 'parameters': [{'type': 'text', 'text': 'Kiran Traders'}]}
                    ],
                }
            },
        )

    assert 'Template name: order_confirmation' in caplog.text
    assert 'Language: en_US' in caplog.text
    assert 'Template parameters:' in caplog.text
    assert 'Kiran Traders' in caplog.text
