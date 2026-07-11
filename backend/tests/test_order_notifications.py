import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')

import server


def test_send_order_notification_sends_customer_email(monkeypatch):
    monkeypatch.setattr(server, 'MAIL_HOST', 'smtp.example.com')
    monkeypatch.setattr(server, 'MAIL_PORT', 587)
    monkeypatch.setattr(server, 'MAIL_USE_TLS', True)
    monkeypatch.setattr(server, 'MAIL_USE_SSL', False)
    monkeypatch.setattr(server, 'MAIL_USERNAME', 'user')
    monkeypatch.setattr(server, 'MAIL_PASSWORD', 'pass')
    monkeypatch.setattr(server, 'MAIL_FROM', 'Kiran Traders <shop@example.com>')

    sent_messages = []

    class DummySMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            return None

        def starttls(self):
            return None

        def login(self, username, password):
            return None

        def send_message(self, msg):
            sent_messages.append(msg)

    monkeypatch.setattr(server.smtplib, 'SMTP', DummySMTP)
    monkeypatch.setattr(server.smtplib, 'SMTP_SSL', DummySMTP)

    order = {
        'id': 'KT20260708ABC123',
        'total': 499.0,
        'address': {
            'name': 'Alice',
            'email': 'alice@example.com',
            'mobile': '9999999999',
        },
        'items': [
            {'name': 'Test Product', 'quantity': 2, 'price': 249.5}
        ],
    }

    server.send_order_notification(order, {'business_name': 'Kiran Traders'})

    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg['To'] == 'alice@example.com'
    assert 'Order confirmed' in msg['Subject']
    assert 'KT20260708ABC123' in msg.get_content()


def test_send_order_whatsapp_sends_message(monkeypatch):
    monkeypatch.setattr(server, 'TWILIO_ACCOUNT_SID', 'AC123')
    monkeypatch.setattr(server, 'TWILIO_AUTH_TOKEN', 'token')
    monkeypatch.setattr(server, 'TWILIO_WHATSAPP_FROM', '+14155238886')
    monkeypatch.setattr(server, 'WHATSAPP_DEFAULT_COUNTRY_CODE', '+91')

    posted = []

    class DummyResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, data, auth, timeout):
        posted.append((url, data, auth, timeout))
        return DummyResponse()

    monkeypatch.setattr(server.requests, 'post', fake_post)

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

    assert len(posted) == 1
    url, data, auth, timeout = posted[0]
    assert 'Messages.json' in url
    assert data['To'] == 'whatsapp:+919999999999'
    assert 'KT20260708ABC123' in data['Body']
    assert auth == ('AC123', 'token')
    assert timeout == 15
