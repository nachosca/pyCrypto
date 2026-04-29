import time
import hashlib
import hmac
from urllib.parse import urlencode


with open("binance_secrets.txt", encoding="UTF-8") as filedata:
    data = eval(filedata.read())

api_key = data["API_Key"]
api_secret = data["Secret_Key"]


# Get current timestamp
ts = int(time.time() * 1000)

# Set timestamp in environment variable
environment["timestamp"] = ts

# Initialize empty parameters object
paramsObject = {}

# Get Binance API secret from environment variable
binance_api_secret = environment.get("binance-api-secret")

# Get request parameters
parameters = request.url.query

# Iterate over parameters
for param in parameters:
    if param.key != 'signature' and not is_empty(param.value) and not is_disabled(param.disabled):
        paramsObject[param.key] = param.value

# Add timestamp to parameters object
paramsObject['timestamp'] = ts

# If Binance API secret is available, generate signature
if api_secret:
    # Create query string
    query_string = "&".join([f"{key}={paramsObject[key]}" for key in sorted(paramsObject)])

    # Generate signature
    signature = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

    # Set signature in environment variable
    environment["signature"] = signature

def is_disabled(str):
    return str == True

def is_empty(str):
    if str is None or str.strip() == '':
        return True
    else:
        return False
