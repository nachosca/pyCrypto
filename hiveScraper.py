from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import datetime

try:

    options = Options()
    options.BinaryLocation = "/usr/bin/chromium-browser"
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument("--window-size=1920x1080")
    options.add_argument("start-maximized")
    options.add_argument("enable-automation")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-browser-side-navigation")
    options.add_argument("--disable-gpu")

    driver_path = "/usr/lib/chromium-browser/chromedriver"
    driver = webdriver.Chrome(service=Service(driver_path), options=options)

    driver.get("https://hiveon.net")
    page = driver.page_source
    soup = BeautifulSoup(''.join(page), 'html.parser').body

    txt = soup.find_all("div", {"class": "value-box-module--value--hd1d6"})[1].text.split()

    datem = datetime.datetime.utcnow()

    data = datem.strftime("%D")
    for t in txt:
        data += ';'+ t

    try:
        with open(datem.strftime("%y%m") + "ethValue.txt", 'a', encoding="UTF-8") as filedata:
            filedata.write(data+"\n")
            filedata.close()
    except:
        pass

except Exception as e:
    print("error trayendo datos.")
    print(e)
