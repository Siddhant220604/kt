import os
from dataclasses import dataclass

WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', '')
WHATSAPP_API_VERSION = os.environ.get('WHATSAPP_API_VERSION', 'v23.0')
WHATSAPP_DEFAULT_COUNTRY_CODE = os.environ.get('WHATSAPP_DEFAULT_COUNTRY_CODE', '+91')

@dataclass
class WhatsAppConfig:
    access_token: str
    phone_number_id: str
    verify_token: str
    api_version: str = 'v23.0'
    default_country_code: str = '+91'

    @property
    def is_valid(self) -> bool:
        return bool(self.access_token and self.phone_number_id)

    @property
    def api_url(self) -> str:
        return f'https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages'


def get_whatsapp_config() -> WhatsAppConfig:
    return WhatsAppConfig(
        access_token=WHATSAPP_ACCESS_TOKEN,
        phone_number_id=WHATSAPP_PHONE_NUMBER_ID,
        verify_token=WHATSAPP_VERIFY_TOKEN,
        api_version=WHATSAPP_API_VERSION,
        default_country_code=WHATSAPP_DEFAULT_COUNTRY_CODE,
    )
