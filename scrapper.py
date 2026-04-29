from bs4 import BeautifulSoup
#from selenium import webdriver
#from selenium.webdriver.chrome.service import Service
#from selenium.webdriver.chrome.options import Options
#from webdriver_manager.chrome import ChromeDriverManager
import requests
import json
from urllib2 import urlopen, Request

try:
    #options = Options()
    #options.BinaryLocation = "/usr/bin/chromium-browser"
    #options.add_argument('--headless')
    #options.add_argument('--no-sandbox')
    #options.add_argument("--window-size=1920x1080")
    #options.add_argument("start-maximized")
    #options.add_argument("enable-automation")
    #options.add_argument("--headless")
    #options.add_argument("--no-sandbox")
    #options.add_argument("--disable-dev-shm-usage")
    #options.add_argument("--disable-browser-side-navigation")
    #options.add_argument("--disable-gpu")
    #driver_path = "/usr/lib/chromium-browser/chromedriver"
    #driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    #driver = webdriver.Chrome(service=Service(driver_path), options=options)
    
    asd=requests.get("https://www.adidas.com.ar/camiseta-titular-argentina-22-messi/HL8425.html").content.decode('utf8')
    print(str(asd))
    print('asd')
    #page = driver.page_source
    #soup = BeautifulSoup(''.join(page), 'html.parser').body
    #print(str(soup))
    #txt = str(soup.find_all("div", {"class": "sidebar___2C-EP"}))

    #print(txt)

    #if "Agotado" in txt:
    #    print('no hay')
    #else:
    #    print('si hay')

except Exception as e:
    print("error trayendo datos.")
    print(e)