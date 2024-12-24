from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import time
from selenium.webdriver.support import expected_conditions as EC
from logScript import logger


def parse_message_page(data, driver):
    try:
        url = data['сообщение_ссылка']
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

        # Основная информация
        table_main = soup.find('table', class_='headInfo')
        if table_main:
            rows = table_main.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) == 2:
                    field = cells[0].text.strip()
                    value = cells[1].text.strip()
                    data[field] = value

            # Данные о должнике
        debtor_section = soup.find('div', string="Должник")
        if debtor_section:
            debtor_table = debtor_section.find_next('table')
            if debtor_table:
                debtor_rows = debtor_table.find_all('tr')
                for row in debtor_rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        field = cells[0].text.strip()
                        value = cells[1].text.strip()
                        data[field] = value

        # Информация об арбитражном управляющем
        arbiter_section = soup.find('div', string="Кем опубликовано")
        if arbiter_section:
            arbiter_table = arbiter_section.find_next('table')
            if arbiter_table:
                arbiter_rows = arbiter_table.find_all('tr')
                for row in arbiter_rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        field = cells[0].text.strip()
                        value = cells[1].text.strip()
                        data[field] = value

        text_section = soup.find_all('div', class_='msg')
        data['текст'] = "; ".join(text.text.strip() for text in text_section if text.text.strip())

        file_links = []
        # doc need pard\
        pinned_files = soup.find_all('a', class_='Reference')
        if pinned_files:
            for file in pinned_files:
                file_link = file['href'].replace("&amp;", "&")
                file_links.append(f'https://old.bankrot.fedresurs.ru/{file_link}')
        else:
            file_links.append("Нет файлов")

        data.update({'файлы': " ".join(file_links)})

        return data
    except Exception as e:
        logger.error(f'Не удалось спарсить содержимое сообщения: {e}')
        return None
