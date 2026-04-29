from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

try:

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    #driver = webdriver.Chrome(service=Service(driver_path), options=options)
    driver.implicitly_wait(20)
    driver.get("https://www.zonakids.com/productos/pack-promo-1-album-tapa-dura-100-sobres-de-figuritas-fifa-world-cup-qatar-2022/")
    page = driver.page_source
    soup = BeautifulSoup(''.join(page), 'html.parser').body
    txt = str(soup.find_all("input", {"class": "btn btn-primary full-width js-prod-submit-form js-addtocart nostock m-bottom-half"})[0])
    txt2 = str(soup.find_all("div", {"class": "js-addtocart js-addtocart-placeholder btn btn-primary full-width btn-transition m-bottom-half disabled"})[0])

    print(txt)
    print(txt2)

    if "Sin stock" in txt and "display: none" in txt2:
        print('No hay stock')
    else:
        print('hay stock')

except Exception as e:
    context.bot.send_message(chat_id=data["chatNacho"],
                                 text="Por las dudas checkea!! https://www.zonakids.com/productos/pack-promo-1-album-tapa-dura-100-sobres-de-figuritas-fifa-world-cup-qatar-2022/")
    print("error trayendo datos.")
    print(e)


try:  
    driver.get("https://www.zonakids.com/productos/pack-x-25-sobres-de-figuritas-fifa-world-cup-qatar-2022/")
    page = driver.page_source
    soup = BeautifulSoup(''.join(page), 'html.parser').body
    txt = str(soup.find_all("input", {"class": "btn btn-primary full-width js-prod-submit-form js-addtocart nostock m-bottom-half"})[0])
    txt2 = str(soup.find_all("div", {"class": "js-addtocart js-addtocart-placeholder btn btn-primary full-width btn-transition m-bottom-half disabled"})[0])

    if "Sin stock" in txt and "display: none" in txt2:
        print('No hay stock')
    else:
        print('hay stock')

    
except Exception as e:
    context.bot.send_message(chat_id=data["chatNacho"],
                                 text="Por las dudas checkea!! https://www.zonakids.com/productos/pack-x-25-sobres-de-figuritas-fifa-world-cup-qatar-2022/")
    print("error trayendo datos.")
    print(e)

