import requests
from decouple import config

WP_URL = "https://amorerings.com/wp-json/wp/v2/users"
USERNAME = config("WP_USERNAME", default="oreoagency", cast=str)
APP_PASSWORD = config("WP_APP_PASSWORD", default=None, cast=str)





def fetch_users(user_email):
    params = {
    "search": user_email,
    "context": "edit"  
    }
    try:
        response = requests.get(WP_URL, params=params, auth=(USERNAME, APP_PASSWORD))
        print(response)
        
        if response.status_code == 200:
            results = response.json()
            target_user = None
            
            for user in results:
                if user.get("email").lower() == user_email.lower():
                    target_user = user
                    break
            
            if target_user:
                return target_user
            else:
                print("No user found with the provided email.")
                return "not_found"
        else:
            return None

    except requests.exceptions.RequestException as e:
        print("Connection Error:", e)
        return None