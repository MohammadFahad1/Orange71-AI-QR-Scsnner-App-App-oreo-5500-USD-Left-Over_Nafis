from woocommerce import API
from django.conf import settings


def get_wc_api():
    url = settings.WOOCOMMERCE_URL
    key = settings.WOOCOMMERCE_CONSUMER_KEY
    secret = settings.WOOCOMMERCE_CONSUMER_SECRET
    if not all([url, key, secret]):
        return None
    return API(
        url=url,
        consumer_key=key,
        consumer_secret=secret,
        version="wc/v3",
        timeout=20,
    )
