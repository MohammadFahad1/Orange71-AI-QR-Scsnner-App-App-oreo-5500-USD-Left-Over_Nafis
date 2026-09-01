import requests
import base64
from decouple import config

wp_url = "https://amorerings.com/wp-json/wp/v2/users/me"
username = config("WP_USERNAME", default=None, cast=str)
app_password = config("WP_APP_PASSWORD", default=None, cast=str)

# --- METHOD A: Manual Base64 Header Construction ---
# Sometimes manually injecting the header bypasses naive server filters
credential_string = f"{username}:{app_password}"
encoded_credentials = base64.b64encode(credential_string.encode('utf-8')).decode('utf-8')

headers = {
    "Authorization": f"Basic {encoded_credentials}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"  # Mimic a real browser
}

res_a = requests.get(wp_url, headers=headers)
print(f"Method A (Manual Header) Status: {res_a.status_code}")
if res_a.status_code == 200:
    print("Success via Method A!")


# --- METHOD B: True WP Context Query Fallback ---
# If headers are stripped entirely, WordPress can accept authorization via standard context parameters
params = {
    "context": "edit",
    "username": username,
    "password": app_password
}
res_b = requests.get("https://amorerings.com/wp-json/wp/v2/users/me", params=params, headers={"User-Agent": "Mozilla/5.0"})
print(f"Method B (Query Context) Status: {res_b.status_code}")