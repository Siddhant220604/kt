import logging
import os
from typing import Any, Dict, Optional

import requests

from config.whatsapp import WhatsAppConfig

logger = logging.getLogger(__name__)
WHATSAPP_DEFAULT_COUNTRY_CODE = os.environ.get('WHATSAPP_DEFAULT_COUNTRY_CODE', '+91')


def build_whatsapp_number(mobile: str, default_country_code: str) -> str:
    raw = mobile or ''
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if not digits:
        return ''

    # Remove leading zeros that may be present in local formatting
    digits = digits.lstrip('0')
    if len(digits) == 10:
        digits = default_country_code.lstrip('+') + digits
    if len(digits) < 10 or len(digits) > 15:
        return ''
    return digits


def send_whatsapp_message(
    config: WhatsAppConfig,
    to_number: str,
    message_type: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    if not config.is_valid:
        raise ValueError('WhatsApp configuration is incomplete')

    normalized_number = ''.join(ch for ch in to_number if ch.isdigit())
    if len(normalized_number) == 10:
        normalized_number = config.default_country_code.lstrip('+') + normalized_number
    if not normalized_number or len(normalized_number) < 10 or len(normalized_number) > 15:
        logger.warning('Invalid WhatsApp phone number after normalization: %s; message not sent', normalized_number)
        return {}

    to_number = normalized_number
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
    logger.info('Request URL: %s', config.api_url)
    logger.info('HTTP method: POST')
    logger.info('Request JSON payload: %s', data)
    logger.info('Recipient number: %s', to_number)

    template_name = None
    language = None
    template_parameters = None
    if message_type == 'template':
        template_name = payload.get('template', {}).get('name')
        language = payload.get('template', {}).get('language', {}).get('code')
        template_parameters = payload.get('template', {}).get('components')
        if template_parameters is not None:
            logger.info('Template name: %s', template_name)
            logger.info('Language: %s', language)
            logger.info('Template parameters: %s', template_parameters)

    try:
        resp = requests.post(config.api_url, headers=headers, json=data, timeout=15)
    except requests.RequestException as exc:
        logger.exception('WhatsApp API request failed for %s', to_number)
        logger.error('Full error response: %s', exc)
        raise

    logger.info('HTTP status code: %s', resp.status_code)
    logger.info('Full response JSON: %s', resp.text)

    try:
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.exception('WhatsApp API request failed for %s', to_number)
        logger.error('Full error response: %s', resp.text)
        raise

    response_payload = resp.json()
    message_id = None
    try:
        message_id = response_payload.get('messages', [{}])[0].get('id')
    except (AttributeError, IndexError, TypeError):
        message_id = None

    if message_id:
        logger.info('Message ID: %s', message_id)

    return response_payload


def send_text_message(config: WhatsAppConfig, to_number: str, text: str) -> Dict[str, Any]:
    return send_whatsapp_message(config, to_number, 'text', {'text': {'body': text}})


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
