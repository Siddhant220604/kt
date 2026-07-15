import logging
import os
from typing import Any, Dict, List, Optional

import requests

from config.whatsapp import WhatsAppConfig, get_whatsapp_config

logger = logging.getLogger(__name__)
WHATSAPP_DEFAULT_COUNTRY_CODE = os.environ.get('WHATSAPP_DEFAULT_COUNTRY_CODE', '+91')

# Meta requires business-initiated WhatsApp messages to use a pre-approved template (outside the
# 24-hour customer-service reply window, plain "text" messages are rejected). All templates used
# in this project were approved in Meta WhatsApp Manager with this language code.
DEFAULT_TEMPLATE_LANGUAGE_CODE = 'en'

# Expected body-parameter count for each approved template, exactly as defined in Meta WhatsApp
# Manager. Used only to log/flag mismatches before sending (Meta's Cloud API rejects a send with
# error #132000 if the count sent doesn't match the approved template) - it never changes what
# gets sent. Update this when a template's approved body variables change.
WHATSAPP_TEMPLATE_PARAM_COUNTS: Dict[str, int] = {
    'order_pending': 3,
    'order_confirmation': 3,
    'order_packed': 2,
    'order_out_for_dilivery': 2,
    'order_delivered': 2,
    'order_cancelled': 3,
    'invoice_ready': 3,
    'review_request': 2,
}


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
    except requests.RequestException:
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
    """Free-form text message. Only valid inside Meta's 24-hour customer-service window (e.g.
    an admin replying to a customer who messaged first). Order lifecycle notifications should
    use send_template_message() instead, which is required for business-initiated messages."""
    return send_whatsapp_message(config, to_number, 'text', {'text': {'body': text}})


def _build_template_components(
    body_parameters: Optional[List[Any]] = None,
    header_document: Optional[Dict[str, str]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Builds the `components` array of a WhatsApp template payload.

    - header_document, if given, becomes a `header` component with a document parameter
      (e.g. the invoice_ready template's PDF attachment).
    - body_parameters, if given, becomes a `body` component with one text parameter per
      value, in the same order as the template's {{1}}, {{2}}, ... placeholders.
    """
    components: List[Dict[str, Any]] = []
    if header_document:
        components.append({
            'type': 'header',
            'parameters': [{
                'type': 'document',
                'document': {
                    'link': header_document['link'],
                    'filename': header_document.get('filename', 'document.pdf'),
                },
            }],
        })
    if body_parameters:
        components.append({
            'type': 'body',
            'parameters': [{'type': 'text', 'text': str(value)} for value in body_parameters],
        })
    return components or None


def send_template_message(
    phone: str,
    template_name: str,
    body_parameters: Optional[List[Any]] = None,
    header_document: Optional[Dict[str, str]] = None,
    config: Optional[WhatsAppConfig] = None,
    language_code: str = DEFAULT_TEMPLATE_LANGUAGE_CODE,
) -> Optional[Dict[str, Any]]:
    """Reusable helper for sending an approved Meta WhatsApp Utility Template message.

    This is the single place that builds the Cloud API "template" payload - every order
    lifecycle notification (order_confirmation, order_packed, order_out_for_dilivery,
    order_delivered, invoice_ready, review_request) calls this instead of building its own
    payload, so the payload shape only has to be correct in one place.

    Args:
        phone: destination WhatsApp number (normalization happens inside send_whatsapp_message,
            same as send_text_message - callers don't need to pre-normalize).
        template_name: exact template name approved in Meta WhatsApp Manager
            (e.g. "order_confirmation", "invoice_ready").
        body_parameters: ordered values for the template body's {{1}}, {{2}}, ... placeholders.
            For this project's templates that's always [customer_name, order_id].
        header_document: optional {"link": <public PDF URL>, "filename": <str>}; when given,
            a document header component is attached (used by invoice_ready for the invoice PDF).
            Omit (or pass None) to send a template with no document header.
        config: WhatsAppConfig to reuse if the caller already has one; defaults to
            get_whatsapp_config() so existing call sites don't need to fetch it themselves.
        language_code: template language code; defaults to "en" per the approved templates.

    Returns:
        The parsed Graph API JSON response, or None if the send was skipped (WhatsApp not
        configured) or failed - the same soft-fail style as the rest of this module, so a
        notification failure never raises into the caller's order/business logic.
    """
    config = config or get_whatsapp_config()
    if not config.is_valid:
        logger.warning('WhatsApp Cloud API not configured; template "%s" not sent to %s', template_name, phone)
        return None

    actual_param_count = len(body_parameters) if body_parameters else 0
    expected_param_count = WHATSAPP_TEMPLATE_PARAM_COUNTS.get(template_name)
    logger.info(
        'WhatsApp template debug - Template Name: %s | Expected Parameters: %s | Actual Parameters: %s | Parameter Values: %s',
        template_name,
        expected_param_count if expected_param_count is not None else 'unknown',
        actual_param_count,
        body_parameters,
    )
    if expected_param_count is not None and actual_param_count != expected_param_count:
        logger.warning(
            'WhatsApp template "%s" parameter count mismatch: expected %s, got %s (values=%s) - Meta will reject this send with #132000',
            template_name, expected_param_count, actual_param_count, body_parameters,
        )

    payload: Dict[str, Any] = {
        'template': {
            'name': template_name,
            'language': {'code': language_code},
        }
    }
    components = _build_template_components(body_parameters, header_document)
    if components:
        payload['template']['components'] = components

    try:
        return send_whatsapp_message(config, phone, 'template', payload)
    except Exception:
        logger.exception('Failed to send WhatsApp template "%s" to %s', template_name, phone)
        return None
