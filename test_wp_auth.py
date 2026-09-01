import os
import sys
import base64
import requests

# Set formatting helpers for colored output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def load_env(env_path=".env"):
    """Manually parse .env to avoid external dependencies like python-decouple/dotenv."""
    env_data = {}
    if not os.path.exists(env_path):
        print(f"{YELLOW}Warning: {env_path} not found. Reading from environment variables directly.{RESET}")
        return env_data
    
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                env_data[key.strip()] = val.strip()
    return env_data

def test_wordpress_app_password(url, username, password):
    print(f"\n{BOLD}=== Testing WordPress Application Password Authentication ==={RESET}")
    print(f"Target URL: {url}")
    print(f"Username:   {username}")
    print(f"App Pass:   {password[:4]}...{password[-4:] if len(password) > 8 else ''}")

    endpoint = f"{url.rstrip('/')}/wp-json/wp/v2/users/me"
    
    # 1. Test using HTTP Basic Authentication header (standard requests auth)
    print(f"\n{CYAN}[1/3] Testing standard Basic Authentication (Header)...{RESET}")
    try:
        response = requests.get(
            endpoint,
            auth=(username, password),
            headers={"User-Agent": "Orange71 Test Client/1.0"},
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            user_data = response.json()
            print(f"{GREEN}✔ Success! Authenticated as: {user_data.get('name')} (ID: {user_data.get('id')}){RESET}")
            return True
        else:
            print(f"{RED}✘ Failed with status code: {response.status_code}{RESET}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"{RED}Error connecting: {e}{RESET}")

    # 2. Test using manual Base64 Header (to bypass header stripping/filtering if any)
    print(f"\n{CYAN}[2/3] Testing manual Base64 Authorization Header injection...{RESET}")
    try:
        cred_str = f"{username}:{password}"
        encoded_creds = base64.b64encode(cred_str.encode('utf-8')).decode('utf-8')
        headers = {
            "Authorization": f"Basic {encoded_creds}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        response = requests.get(endpoint, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            user_data = response.json()
            print(f"{GREEN}✔ Success! Authenticated as: {user_data.get('name')} (ID: {user_data.get('id')}){RESET}")
            return True
        else:
            print(f"{RED}✘ Failed with status code: {response.status_code}{RESET}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"{RED}Error connecting: {e}{RESET}")

    # 3. Test using Query Parameters (WordPress fallback context if server strips headers)
    print(f"\n{CYAN}[3/3] Testing Query Parameters Auth Fallback...{RESET}")
    try:
        params = {
            "context": "edit",
            "username": username,
            "password": password
        }
        response = requests.get(
            endpoint, 
            params=params, 
            headers={"User-Agent": "Mozilla/5.0"}, 
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            user_data = response.json()
            print(f"{GREEN}✔ Success! Authenticated as: {user_data.get('name')} (ID: {user_data.get('id')}){RESET}")
            return True
        else:
            print(f"{RED}✘ Failed with status code: {response.status_code}{RESET}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"{RED}Error connecting: {e}{RESET}")

    print(f"\n{YELLOW}💡 Diagnostic Advice for WordPress Auth Failure:{RESET}")
    print("1. Ensure Wordfence -> Firewall -> Manage WAF -> Brute Force Protection -> 'Disable WordPress application passwords' is UNCHECKED.")
    print("2. Recreate the application password under Users -> Profile for username 'ringboss'. Make sure the name is copied exactly (excluding spaces).")
    print("3. If using Apache, make sure the .htaccess RewriteRules for HTTP:Authorization are present.")
    print("4. If using Nginx, ensure 'fastcgi_pass_header Authorization;' is added in your php block.")
    return False


def test_woocommerce_api(url, consumer_key, consumer_secret):
    print(f"\n{BOLD}=== Testing WooCommerce REST API Authentication ==={RESET}")
    print(f"Target URL: {url}")
    print(f"CK:         {consumer_key[:8]}...{consumer_key[-8:] if len(consumer_key) > 16 else ''}")
    print(f"CS:         {consumer_secret[:8]}...{consumer_secret[-8:] if len(consumer_secret) > 16 else ''}")

    endpoint = f"{url.rstrip('/')}/wp-json/wc/v3/products"
    
    # WooCommerce accepts Basic Authentication using CK as username and CS as password
    print(f"\n{CYAN}Testing WooCommerce products endpoint...{RESET}")
    try:
        response = requests.get(
            endpoint,
            auth=(consumer_key, consumer_secret),
            headers={"User-Agent": "Orange71 Test Client/1.0"},
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            products = response.json()
            print(f"{GREEN}✔ Success! Retrieved {len(products)} products from WooCommerce.{RESET}")
            return True
        else:
            print(f"{RED}✘ Failed with status code: {response.status_code}{RESET}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"{RED}Error connecting: {e}{RESET}")

    print(f"\n{YELLOW}💡 Diagnostic Advice for WooCommerce Failure:{RESET}")
    print("1. Check if SSL/TLS is fully configured and working properly on your server.")
    print("2. Verify that the REST API credentials (CK/CS) under WooCommerce -> Settings -> Advanced -> REST API have 'Read/Write' permissions and are active.")
    return False


if __name__ == "__main__":
    env = load_env()
    
    # Get values from env or current environment variables
    wp_url = env.get("WOOCOMMERCE_URL", os.getenv("WOOCOMMERCE_URL"))
    wp_username = env.get("WP_USERNAME", os.getenv("WP_USERNAME"))
    wp_app_password = env.get("WP_APP_PASSWORD", os.getenv("WP_APP_PASSWORD"))
    
    wc_consumer_key = env.get("WOOCOMMERCE_CONSUMER_KEY", os.getenv("WOOCOMMERCE_CONSUMER_KEY"))
    wc_consumer_secret = env.get("WOOCOMMERCE_CONSUMER_SECRET", os.getenv("WOOCOMMERCE_CONSUMER_SECRET"))
    
    errors = False
    
    if not wp_url or not wp_username or not wp_app_password:
        print(f"{RED}Error: Missing WordPress credentials in .env file (WOOCOMMERCE_URL, WP_USERNAME, WP_APP_PASSWORD).{RESET}")
        errors = True
        
    if not wc_consumer_key or not wc_consumer_secret:
        print(f"{RED}Error: Missing WooCommerce API credentials in .env file (WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET).{RESET}")
        errors = True
        
    if errors:
        sys.exit(1)
        
    # Execute Tests
    wp_success = test_wordpress_app_password(wp_url, wp_username, wp_app_password)
    wc_success = test_woocommerce_api(wp_url, wc_consumer_key, wc_consumer_secret)
    
    print(f"\n{BOLD}=== Summary ==={RESET}")
    if wp_success:
        print(f"WordPress App Pass: {GREEN}WORKING{RESET}")
    else:
        print(f"WordPress App Pass: {RED}FAILED{RESET}")
        
    if wc_success:
        print(f"WooCommerce API:    {GREEN}WORKING{RESET}")
    else:
        print(f"WooCommerce API:    {RED}FAILED{RESET}")
