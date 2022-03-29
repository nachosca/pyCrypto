import fastapi
import uvicorn
import requests
from datetime import datetime
import json

app = fastapi.FastAPI()

@app.get("/futures-convenience")
def index(name: str = '220624'):

    lst = json.loads(requests.get('https://dapi.binance.com/dapi/v1/premiumIndex').content)
    lst = [d for d in lst if name in d['symbol']]

    result = []
    for i in lst:
        d = {'name': i['symbol'], 'percentage': (float(i['markPrice']) * 100 / float(i['indexPrice'])) - 100,
             'spotPrice': i['indexPrice'], 'futurePrice': i['markPrice'],
             'daysToFinish': (datetime.strptime(name, '%y%m%d').date() - datetime.today().date()).days}
        result.append(d)

    return sorted(result, key=lambda d: d['percentage'], reverse=True)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
