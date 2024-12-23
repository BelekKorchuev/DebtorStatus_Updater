from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import time
from selenium.webdriver.support import expected_conditions as EC
from logScript import logger


def parse_message_page(url, driver):
    try:
        logger.info(f'Переход по ссылке: {url}')
        # Переход по ссылке
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'red_small'))
        )
        # Подождем несколько секунд, чтобы страница полностью загрузилась
        time.sleep(2)

        # Получение HTML-кода страницы
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Словарь для сохранения данных
        data = {}



    except Exception as e:
        logger.error('error')
