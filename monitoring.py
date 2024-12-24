import json
import os
from time import sleep

from bs4 import BeautifulSoup
import hashlib
import time
from collections import deque
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from DBmanager import prepare_data_for_db
from logScript import logger
from pars_messageInfo import parse_message_page

# Допустимые типы сообщений
valid_message_types = {
    'Сведения о заключении договора купли-продажи',
    'Сообщение о результатах торгов',
    'Объявление о проведении торгов',
    'Отчет оценщика об оценке имущества должника',
    'Сообщение об изменении объявления о проведении торгов'
}

# Файл для сохранения идентификаторов проверенных сообщений
CHECKED_MESSAGES_FILE = "checked_messages.json"

def load_checked_messages():
    """
    Загружает очередь из файла JSON. Если файл не существует или повреждён, создаёт новый файл с пустой очередью.
    """
    if os.path.exists(CHECKED_MESSAGES_FILE):
        try:
            with open(CHECKED_MESSAGES_FILE, "r") as file:
                data = json.load(file)
                logger.info(f"Файл {CHECKED_MESSAGES_FILE} успешно загружен.")
                return deque(data, maxlen=1000)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Ошибка при чтении {CHECKED_MESSAGES_FILE}: {e}. Инициализируем пустую очередь.")
            return initialize_checked_messages_file()
    else:
        logger.info(f"Файл {CHECKED_MESSAGES_FILE} не найден. Создаём новый.")
        return initialize_checked_messages_file()

def save_checked_messages(queue):
    """
    Сохраняет очередь в файл JSON.
    """
    try:
        with open(CHECKED_MESSAGES_FILE, "w") as file:
            json.dump(list(queue), file)
            logger.info(f"Очередь успешно сохранена в файл {CHECKED_MESSAGES_FILE}.")
    except IOError as e:
        logger.error(f"Ошибка при сохранении файла {CHECKED_MESSAGES_FILE}: {e}")

def initialize_checked_messages_file():
    """
    Создаёт новый файл с пустой очередью.
    """
    empty_queue = deque(maxlen=1000)
    save_checked_messages(empty_queue)
    return empty_queue

# Загружаем очередь из файла при старте программы
checked_messages = load_checked_messages()

def clear_form_periodically(target_hour=0, target_minute=2, restart_queue=None):
    """
    :param target_hour: Час запуска (по умолчанию 0 - полночь).
    :param target_minute: Минута запуска (по умолчанию 0).
    """
    while True:
        try:
            # Текущее время
            now = datetime.now()
            target_time = datetime.combine(now.date(), datetime.min.time()) + timedelta(
                hours=target_hour, minutes=target_minute
            )

            # Если текущее время уже прошло заданное, берём следующий день
            if now >= target_time:
                target_time += timedelta(days=1)

            # Вычисляем время до следующего запуска
            sleep_time = (target_time - now).total_seconds()
            logger.info(f"Следующее нажатие кнопки 'Очистить' запланировано на {target_time}. Спим {sleep_time:.2f} секунд.")

            # Спим до нужного времени
            time.sleep(sleep_time)

            # Здесь вместо выполнения нажатий, сигнализируем основной поток
            if restart_queue:
                logger.info("Перезапуск сессии требуется.")
                restart_queue.put(True)  # Отправляем сигнал в очередь

            return True

        except Exception as e:
            logger.error(f"Ошибка в функции clear_form_periodically: {e}")
            return False


def fetch_and_parse_first_page(driver):
    url = "https://old.bankrot.fedresurs.ru/Messages.aspx"
    logger.info(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Открытие основной страницы: {url}')

    try:
        # Открываем страницу
        driver.get(url)
        time.sleep(1)  # Ждем 1 секунду для загрузки контента

        search_message_type = driver.find_element(By.ID, "ctl00_cphBody_mdsMessageType_tbSelectedText")  # Очищаем поле
        search_message_type.click()
        message_type = driver.find_element(By.CLASS_NAME, "rtLI rtFirst")
        message_type.click()

        search_button = driver.find_element(By.CLASS_NAME, "ctl00_cphBody_ibMessagesSearch")
        search_button.click()

        # Получаем HTML-код страницы
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        table = soup.find('table', class_='bank')

        # Находим строки таблицы сообщений
        table_rows = table.select("tr")

        for row in reversed(table_rows):
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            # Извлекаем данные из ячеек
            date = cells[0].get_text(strip=True)
            message_type = cells[1].get_text(strip=True)
            debtor = cells[2].get_text(strip=True)
            published_by = cells[4].get_text(strip=True)
            link_messeges = cells[1].find("a")["href"] if cells[1].find("a") else None
            link_debtor = cells[2].find("a")["href"] if cells[2].find("a") else None
            link_arbitr = cells[4].find("a")["href"] if cells[4].find("a") else None


            # Проверка типа сообщения
            if message_type in valid_message_types:
                # Создаем уникальный идентификатор для строки
                msg_id = hashlib.md5((date + message_type + debtor).encode()).hexdigest()

                new_messages = {
                    "дата": date,
                    "тип_сообщения": message_type,
                    "должник": debtor,
                    "должник_ссылка": f"https://old.bankrot.fedresurs.ru{link_debtor}" if link_debtor else "Нет ссылки",
                    "арбитр": published_by,
                    "арбитр_ссылка": f"https://old.bankrot.fedresurs.ru{link_arbitr}" if link_arbitr else "Нет ссылки",
                    "сообщение_ссылка": f"https://old.bankrot.fedresurs.ru{link_messeges}" if link_messeges else "Нет ссылки",
                }

                # Проверяем, является ли сообщение новым
                if msg_id not in checked_messages:
                    checked_messages.append(msg_id)
                    logger.info('Найдено новое релевантное сообщение')
                    logger.debug(
                        f'Дата: {date}, Тип сообщения: {message_type}, Должник: {debtor}, Кем опубликовано: {published_by}')

                    # Сохраняем очередь
                    save_checked_messages(checked_messages)

                    return new_messages

    except Exception as e:
        logger.error(f'Ошибка при обработке страницы {url}: {e}')

    return None

# парсинг всех страниц снизу верх
def parse_all_pages_reverse(driver):
    """
    Парсинг всех страниц сообщений при запуске программы, начиная с последней страницы.
    """
    url = "https://old.bankrot.fedresurs.ru/Messages.aspx"

    visited_pages = set()  # Отслеживание уже обработанных страниц

    driver.get(url)

    search_message_type = driver.find_element(By.ID, 'ctl00_cphBody_mdsMessageType_tbSelectedText')  # Очищаем поле
    search_message_type.click()

    time.sleep(5)
    # # Ожидаем появления выпадающего списка
    message_type = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_BodyPlaceHolder_tbSearch"]'))
    )
    #
    # # Вводим текст в поле поиска типа сообщений
    # message_type.send_keys("Сообщение о судебном акте")

    # Вводим текст в поле поиска через JS
    # message_type = driver.find_element(By.ID, 'ctl00_BodyPlaceHolder_tbSearch')
    message_type.click()
    message_type.send_keys("Сообщение о судебном акте")

    # driver.execute_script("arguments[0].value = 'Сообщение о судебном акте';", message_type)

    time.sleep(5)
    buttom = driver.find_element(By.ID, 'ctl00_BodyPlaceHolder_btnSearch')
    buttom.click()

    time.sleep(5)
    search_button = driver.find_element(By.CLASS_NAME, "ctl00_cphBody_ibMessagesSearch")
    search_button.click()

    time.sleep(2)
    logger.info(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Начало обхода всех страниц (снизу вверх): {url}')
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    time.sleep(5)

    brige_page = "..."

    # Находим все ссылки пагинации
    page_link = soup.find('a', href=True, string=str(brige_page))
    if not page_link:
        logger.warning("Ссылки пагинации отсутствуют.")
        return

    driver.find_element(By.LINK_TEXT, brige_page).click()

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, 'html'))
    )

    time.sleep(5)
    page_numbers = ['20', '19', '18', '17', '16', '15', '14', '13', '12', '11',
                    '...', '9', '8', '7', '6', '5', '4', '3', '2', '1']

    for page_number in page_numbers:
        urlll = "https://old.bankrot.fedresurs.ru/Messages.aspx"
        driver.get(urlll)

        logger.info(f"Переход на страницу: {page_number}")
        try:
            # Находим ссылку на нужную страницу
            page_link = driver.find_element(By.LINK_TEXT, page_number)
            page_link.click()  # Эмулируем клик на элемент
            logger.info(f"Успешный переход на страницу: {page_number}")

            # Ожидание загрузки новой страницы
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'html'))
            )
            time.sleep(2)

            # Обновляем HTML и выполняем парсинг
            soup = BeautifulSoup(driver.page_source, 'html.parser')

        except Exception as e:
            logger.error(f"Ошибка при переходе на страницу {page_number}: {e}")
            continue

        logger.info("Парсинг всех страниц завершен.")

        # Помечаем страницу как обработанную
        visited_pages.add(str(page_number))

        # Обновляем содержимое страницы
        table = soup.find('table', class_='bank')
        if not table:
            logger.warning(f"Таблица сообщений не найдена на странице {page_number}")
            continue

        # Парсим строки
        rows = table.find_all('tr')
        for row in reversed(rows):  # Обрабатываем строки с конца
            row_class = row.get('class', [])
            if not row_class or 'row' in row_class:
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue

                # Извлекаем данные из ячеек
                date = cells[0].get_text(strip=True)
                message_type = cells[1].get_text(strip=True)
                debtor = cells[2].get_text(strip=True)
                published_by = cells[4].get_text(strip=True)
                link_messages = cells[1].find("a")["href"] if cells[1].find("a") else None
                link_arbitr = cells[4].find("a")["href"] if cells[4].find("a") else None
                link_debtor = cells[2].find("a")["href"] if cells[2].find("a") else None

                if message_type in valid_message_types:
                    msg_id = hashlib.md5((date + message_type + debtor).encode()).hexdigest()
                    new_message = {
                        "дата": date,
                        "тип_сообщения": message_type,
                        "должник": debtor,
                        "должник_ссылка": f"https://old.bankrot.fedresurs.ru{link_debtor}" if link_debtor else "Нет ссылки",
                        "арбитр": published_by,
                        "арбитр_ссылка": f"https://old.bankrot.fedresurs.ru{link_arbitr}" if link_arbitr else "Нет ссылки",
                        "сообщение_ссылка": f"https://old.bankrot.fedresurs.ru{link_messages}" if link_messages else "Нет ссылки",
                    }

                    if msg_id not in checked_messages:
                        checked_messages.append(msg_id)
                        logger.info('Найдено новое релевантное сообщение')
                        logger.debug(
                            f'Дата: {date}, Тип сообщения: {message_type}, Должник: {debtor}, Кем опубликовано: {published_by}')
                        save_checked_messages(checked_messages)
                        if new_message:
                            try:
                                parsed_data = parse_message_page(new_message, driver)
                                prepered_data = prepare_data_for_db(parsed_data)

                            except Exception as e:
                                logger.error(f"Ошибка при обработке сообщения: {e}")
                                continue

    logger.info("Обход всех страниц завершен.")
