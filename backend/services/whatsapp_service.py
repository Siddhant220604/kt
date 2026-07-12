import logging
import os
from typing import Any, Dict, Optional

import requests

from config.whatsapp import WhatsAppConfig

logger = logging.getLogger(__name__)
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', '')
WHATSAPP_DEFAULT_COUNTRY_CODE = os.environ.get('WHATSAPP_DEFAULT_COUNTRY_CODE', '+91')


def build_whatsapp_number(mobile: str, default_country_code: str) -> str:
    raw = mobile or ''
    normalized = ''.join(ch for ch in raw if ch.isdigit() or ch == '+')
    if not normalized:
        return ''
    if normalized.startswith('+'):
        return normalized
    normalized = normalized.lstrip('0')
    if normalized.startswith(default_country_code.lstrip('+')):
        return f'+{normalized}'
    return f'{default_country_code}{normalized}'


def send_whatsapp_message(
    config: WhatsAppConfig,
    to_number: str,
    message_type: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    if not config.is_valid:
        raise ValueError('WhatsApp configuration is incomplete')
    to_number = to_number.lstrip('+')
    headers = {
        'Authorization': f'Bearer {config.access_token}',
        'Content-Type': 'application/json',
    }
    data = {
        'messaging_product': 'whatsapp',
        'to': to_number,
        'type': message_type,
        **payload,
    }
    logger.info('Sending WhatsApp message to %s via %s', to_number, config.api_url)
    resp = requests.post(config.api_url, headers=headers, json=data, timeout=15)
    try:
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.exception('WhatsApp API request failed: %s', exc)
        raise
    return resp.json()


def send_text_message(config: WhatsAppConfig, to_number: str, text: str) -> Dict[str, Any]:
    return send_whatsapp_message(config, to_number, 'text', {'text': {'body': text}})


def send_whatsapp_via_twilio(to_number: str, body: str) -> Dict[str, Any]:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_FROM:
        raise ValueError('Twilio WhatsApp credentials are not configured')
    payload = {
        'To': f'whatsapp:{to_number}',
        'From': TWILIO_WHATSAPP_FROM,
        'Body': body,
    }
    resp = requests.post(
        f'https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json',
        data=payload,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        timeout=15,
    )
    try:
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.exception('Twilio WhatsApp API request failed: %s', exc)
        raise
    return resp.json()


def send_template_message(config: WhatsAppConfig, to_number: str, template_name: str, language_code: str, components: Optional[list] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        'template': {
            'name': template_name,
            'language': {'code': language_code},
        }
    }
    if components is not None:
        payload['template']['components'] = components
    return send_whatsapp_message(config, to_number, 'template', payload)
