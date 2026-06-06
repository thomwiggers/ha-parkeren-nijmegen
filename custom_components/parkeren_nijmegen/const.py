from datetime import timedelta

DOMAIN = "parkeren_nijmegen"

BASE_URL = "https://parkeerproducten.nijmegen.nl"
APP_BASE = "/DVSPortal"
API_BASE = "/DVSPortal/api"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PERMIT_ID = "permit_id"
CONF_PERMIT_MEDIA_CODE = "permit_media_code"
CONF_PERMIT_MEDIA_TYPE_ID = "permit_media_type_id"

SCAN_INTERVAL = timedelta(minutes=5)
