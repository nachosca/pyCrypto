import requests
import json


with open("binance_secrets.txt", encoding="UTF-8") as filedata:
    data = eval(filedata.read())

api_key = data["API_Key"]
api_secret = data["Secret_Key"]

base_url = 'https://testnet.binance.vision/api/v3'
futures_url = 'https://testnet.binancefuture.com'
headers = {
    'X-MBX-APIKEY': api_key
}

def close_short_position(coin_symbol):
    # Close the short operation on COIN-M futures
    symbol = coin_symbol + 'USDT'
    try:
        # Fetch open orders
        open_orders = client.futures_get_open_orders(symbol=symbol)
        if len(open_orders) > 0:
            # Cancel open orders
            for order in open_orders:
                client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                print(f"Cancelled order {order['orderId']} successfully.")
        else:
            print("No open orders found.")

        # Close position
        client.futures_cancel_all_open_orders(symbol=symbol)
        print("Closed short position successfully.")
    except Exception as e:
        print("An error occurred:", e)

def send_to_spot_wallet(coin_symbol):
    # Send the coin to the spot wallet
    try:
        # Fetch coin balance from futures account
        coin_balance = float(client.futures_account_balance()[coin_symbol]['balance'])
        
        # Transfer to spot wallet
        if coin_balance > 0:
            client.futures_transfer(asset=coin_symbol, amount=coin_balance, type=2)  # Type 2: Transfer from futures to spot wallet
            print(f"Transferred {coin_balance} {coin_symbol} to spot wallet successfully.")
        else:
            print(f"No {coin_symbol} balance available.")
    except Exception as e:
        print("An error occurred:", e)

def exchange_to_usdt(coin_symbol):
    # Exchange the coin to USDT
    try:
        # Fetch coin balance from spot wallet
        coin_balance = float(client.get_asset_balance(asset=coin_symbol)['free'])
        
        if coin_balance > 0:
            # Market sell the coin to USDT
            order = client.create_order(
                symbol=coin_symbol + "USDT",
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=coin_balance
            )
            print(f"Exchanged {coin_balance} {coin_symbol} to USDT successfully.")
        else:
            print(f"No {coin_symbol} balance available.")
    except Exception as e:
        print("An error occurred:", e)

def check_futures_balance():
    try:
        url = f"{base_url}/fapi/v2/balance"
        response = requests.get(url, headers=headers)
        futures_balance = json.loads(response.text)
        print("Futures Account Balance:")
        for asset in futures_balance:
            print(f"{asset['asset']}: {asset['balance']}")
    except Exception as e:
        print("An error occurred:", e)

def check_spot_balance():
    try:
        url = f"{base_url}/account"
        response = requests.get(url, headers=headers)
        spot_balance = json.loads(response.text)
        print("Spot Wallet Balance:")
        for asset in spot_balance['balances']:
            print(f"{asset['asset']}: {asset['free']}")
    except Exception as e:
        print("An error occurred:", e)

if __name__ == "__main__":
    coin_symbol = 'BTC'
    
    #close_short_position(coin_symbol)
    #send_to_spot_wallet(coin_symbol)
    #exchange_to_usdt(coin_symbol)

    check_futures_balance()
    check_spot_balance()


def check_futures():
    lst = json.loads(requests.get('https://dapi.binance.com/dapi/v1/premiumIndex').content)
    lst = [d for d in lst if futuresDate in d['symbol']]

    result = []
    for i in lst:
        d = {'name': i['symbol'],
             'percentage': round((float(i['markPrice']) * 100 / float(i['indexPrice'])) - 100, 3)}
        result.append(d)

    return sorted(result, key=lambda d: d['percentage'], reverse=True)