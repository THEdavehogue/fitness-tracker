import os
from time import sleep
from bs4 import BeautifulSoup
from unidecode import unidecode
from selenium import webdriver

USERID = os.getenv('GARMIN_USERID')
PASSWORD = os.getenv('GARMIN_PASSWORD')


def scrape_activity(driver, url):
    driver.get(url)
    sleep(5)
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    bits = [unidecode(x.text) for x in soup.findAll('div', class_='data-bit')]
    labels = [unidecode(x.text) for x in soup.findAll('span', class_='data-label')]
    key_info = {l: b for l, b in zip(labels, bits[1:])}
    return key_info


if __name__ == '__main__':
    pass
