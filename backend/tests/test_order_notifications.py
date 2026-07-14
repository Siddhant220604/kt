import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')

import pytest

import server
from services import whatsapp_service


@pytest.fixture(autouse=True)
def _no_real_whatsapp_event_recording(monkeypatch):
    """record_whatsapp_message_sent writes to Mongo via its own small sync client for
    delivery-status correlation - tests must never touch a real database, so replace it with
    a no-op everywhere in this file (nothing here asserts on its behavior)."""
    monkeypatch.setattr(server, 'record_whatsapp_message_sent', lambda *a, **kw: None)


def test_send_order_notification_sends_whatsapp(monkeypatch):
    # Order placement now sends the approved order_confirmation Utility Template (Meta requires
    # business-initiated WhatsApp messages to use pre-approved templates), not free-form text.
    sent = {}

    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'

    def fake_get_whatsapp_config():
        return DummyConfig()

    def fake_send_template_message(phone, template_name, body_parameters=None, header_document=None, config=None, language_code='en'):
        sent['phone'] = phone
        sent['template_name'] = template_name
        sent['body_parameters'] = body_parameters
        return {'messages': [{'id': 'msgid'}]}

    monkeypatch.setattr(server, 'get_whatsapp_config', fake_get_whatsapp_config)
    monkeypatch.setattr(server, 'send_template_message', fake_send_template_message)

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

    assert sent['phone'] == '919999999999'
    assert sent['template_name'] == server.WHATSAPP_TEMPLATE_ORDER_CONFIRMATION
    assert sent['body_parameters'] == ['Alice', 'KT20260708ABC123', '499.00']


def test_send_order_whatsapp_sends_message(monkeypatch):
    sent = {}

    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'

    def fake_get_whatsapp_config():
        return DummyConfig()

    def fake_send_template_message(phone, template_name, body_parameters=None, header_document=None, config=None, language_code='en'):
        sent['phone'] = phone
        sent['template_name'] = template_name
        sent['body_parameters'] = body_parameters
        return {'messages': [{'id': 'msgid'}]}

    monkeypatch.setattr(server, 'get_whatsapp_config', fake_get_whatsapp_config)
    monkeypatch.setattr(server, 'send_template_message', fake_send_template_message)

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

    assert sent['phone'] == '919999999999'
    assert sent['template_name'] == server.WHATSAPP_TEMPLATE_ORDER_CONFIRMATION
    assert sent['body_parameters'] == ['Alice', 'KT20260708ABC123', '499.00']


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


def test_send_order_status_update_whatsapp_uses_template_for_mapped_statuses(monkeypatch):
    # Statuses with an approved template (confirmed/packed/out for delivery/delivered) must go
    # through send_template_message, not the free-form text fallback used for other statuses.
    sent = {}

    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'

    monkeypatch.setattr(server, 'get_whatsapp_config', lambda: DummyConfig())

    def fake_send_template_message(phone, template_name, body_parameters=None, header_document=None, config=None, language_code='en'):
        sent['phone'] = phone
        sent['template_name'] = template_name
        sent['body_parameters'] = body_parameters
        return {'messages': [{'id': 'msgid'}]}

    def fail_if_called(*args, **kwargs):
        raise AssertionError('send_text_message should not be called for a templated status')

    monkeypatch.setattr(server, 'send_template_message', fake_send_template_message)
    monkeypatch.setattr(server, 'send_text_message', fail_if_called)

    order = {'id': 'KT20260708ABC123', 'total': 499.0, 'address': {'name': 'Alice', 'mobile': '9999999999'}}

    for status, expected_template, expected_params in [
        # order_confirmation is a 3-parameter template (customer name, order id, total amount);
        # the other three mapped statuses are still 2-parameter templates.
        ('confirmed', server.WHATSAPP_TEMPLATE_ORDER_CONFIRMATION, ['Alice', 'KT20260708ABC123', '499.00']),
        ('packed', server.WHATSAPP_TEMPLATE_ORDER_PACKED, ['Alice', 'KT20260708ABC123']),
        ('out for delivery', server.WHATSAPP_TEMPLATE_ORDER_OUT_FOR_DELIVERY, ['Alice', 'KT20260708ABC123']),
        ('delivered', server.WHATSAPP_TEMPLATE_ORDER_DELIVERED, ['Alice', 'KT20260708ABC123']),
    ]:
        sent.clear()
        server.send_order_status_update_whatsapp(order, status, {'business_name': 'Kiran Traders'})
        assert sent['template_name'] == expected_template
        assert sent['body_parameters'] == expected_params


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
    assert 'Recipient number: 919999999999' in caplog.text
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


def test_send_template_message_builds_body_only_payload(monkeypatch):
    # No header_document -> payload should have a body component but no header component.
    captured = {}

    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'
        default_country_code = '+91'

    def fake_send_whatsapp_message(config, to_number, message_type, payload):
        captured['to_number'] = to_number
        captured['message_type'] = message_type
        captured['payload'] = payload
        return {'messages': [{'id': 'msgid'}]}

    monkeypatch.setattr(whatsapp_service, 'send_whatsapp_message', fake_send_whatsapp_message)

    result = whatsapp_service.send_template_message(
        '9999999999', 'order_confirmation', body_parameters=['Alice', 'KT2026001'], config=DummyConfig(),
    )

    assert result == {'messages': [{'id': 'msgid'}]}
    assert captured['message_type'] == 'template'
    template = captured['payload']['template']
    assert template['name'] == 'order_confirmation'
    assert template['language'] == {'code': 'en'}
    assert template['components'] == [
        {'type': 'body', 'parameters': [{'type': 'text', 'text': 'Alice'}, {'type': 'text', 'text': 'KT2026001'}]},
    ]


def test_send_template_message_with_document_header_matches_meta_payload_shape(monkeypatch):
    # invoice_ready: header_document must produce a document header component *before* the body
    # component, matching the exact Cloud API shape Meta expects.
    captured = {}

    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'
        default_country_code = '+91'

    def fake_send_whatsapp_message(config, to_number, message_type, payload):
        captured['payload'] = payload
        return {'messages': [{'id': 'msgid'}]}

    monkeypatch.setattr(whatsapp_service, 'send_whatsapp_message', fake_send_whatsapp_message)

    whatsapp_service.send_template_message(
        '9999999999',
        'invoice_ready',
        body_parameters=['Alice', 'KT2026001'],
        header_document={'link': 'https://example.com/invoice.pdf', 'filename': 'Invoice-KT2026001.pdf'},
        config=DummyConfig(),
    )

    components = captured['payload']['template']['components']
    assert components[0] == {
        'type': 'header',
        'parameters': [{
            'type': 'document',
            'document': {'link': 'https://example.com/invoice.pdf', 'filename': 'Invoice-KT2026001.pdf'},
        }],
    }
    assert components[1]['type'] == 'body'


def test_send_template_message_skipped_when_config_invalid():
    class InvalidConfig:
        is_valid = False

    result = whatsapp_service.send_template_message('9999999999', 'order_confirmation', config=InvalidConfig())
    assert result is None


def test_send_template_message_logs_expected_vs_actual_param_debug_info(monkeypatch, caplog):
    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'
        default_country_code = '+91'

    monkeypatch.setattr(whatsapp_service, 'send_whatsapp_message', lambda *a, **k: {'messages': [{'id': 'msgid'}]})

    with caplog.at_level(logging.INFO):
        whatsapp_service.send_template_message(
            '9999999999', 'order_confirmation', body_parameters=['Alice', 'KT2026001', '499.00'], config=DummyConfig(),
        )

    assert 'Template Name: order_confirmation' in caplog.text
    assert 'Expected Parameters: 3' in caplog.text
    assert 'Actual Parameters: 3' in caplog.text
    assert "Parameter Values: ['Alice', 'KT2026001', '499.00']" in caplog.text


def test_send_template_message_warns_on_param_count_mismatch(monkeypatch, caplog):
    class DummyConfig:
        is_valid = True
        access_token = 'token'
        api_url = 'https://graph.facebook.com/v23.0/123/messages'
        default_country_code = '+91'

    monkeypatch.setattr(whatsapp_service, 'send_whatsapp_message', lambda *a, **k: {'messages': [{'id': 'msgid'}]})

    with caplog.at_level(logging.WARNING):
        whatsapp_service.send_template_message(
            '9999999999', 'order_confirmation', body_parameters=['Alice', 'KT2026001'], config=DummyConfig(),
        )

    assert 'parameter count mismatch' in caplog.text
    assert 'expected 3, got 2' in caplog.text
