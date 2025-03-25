import time

import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from logScript import logger

list_of_status = {'о введении наблюдения',
                  'о признании обоснованным заявления о признании гражданина банкротом и введении реструктуризации его долгов',
                  'о признании должника банкротом и открытии конкурсного производства',
                  'о передаче дела на рассмотрение другого арбитражного суда об утверждении плана реструктуризации долгов гражданина',
                  'о признании должника банкротом и введении реализации имущества гражданина',
                  'о напременении в отношении гражданина правила об освобождении от исполнения обязательств',
                  'о завершении реализации имущества гражданина', 'о прекращении производства по делу',
                  'о признании гражданина банкротом и введении реализации имущества гражданина'}

# метод для определения нужного акта для парсига
def search_act(driver, list_dic, data):
    try:

        # Список ключей, которые нужно извлечь
        keys_to_extract = ["ФИО_АУ", "адрес_корреспонденции", "почта", "СРО_АУ", "адрес_СРО_АУ", "арбитр", "арбитр_ссылка"]

        # Новый словарь
        target_dict = {key: data[key] for key in keys_to_extract if key in data}

        # Сопоставление старых и новых названий ключей
        key_mapping = {
            "ФИО_АУ": "Арбитражный управляющий",
            "адрес_корреспонденции": "Адрес для корреспонденции",
            "почта": "E-mail",
            "СРО_АУ": "СРО АУ",
            "адрес_СРО_АУ": "Адрес СРО АУ"
        }

        # Переименование ключей
        renamed_data = {key_mapping.get(k, k): v for k, v in target_dict.items()}
        logger.info(f'словарь с переименованными ключами: {renamed_data}')

        if len(list_dic) == 1:
            for dic in list_dic:
                # Открытие новой вкладки
                link = dic.get('сообщение_ссылка', '')
                response = requests.post(link)
                logger.info(f'текущее сообщение: {link}')

                soup = BeautifulSoup(response.text, 'html.parser')

                # Основная информация
                table_main = soup.find('table', class_='headInfo')
                if table_main:
                    rows = table_main.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            field = cells[0].text.strip()
                            value = cells[1].text.strip()
                            dic[field] = value

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
                                dic[field] = value

                text_section = soup.find_all('div', class_='msg')
                dic['текст'] = "; ".join(text.text.strip() for text in text_section if text.text.strip())

                file_links = []
                pinned_files = soup.find_all('a', class_='Reference')
                if pinned_files:
                    for file in pinned_files:
                        file_link = file['href'].replace("&amp;", "&")
                        file_links.append(f'https://old.bankrot.fedresurs.ru/{file_link}')
                else:
                    file_links.append("Нет файлов")

                dic['файлы'] = "&&& ".join(file_links)

                # act_status = dic.get('Судебный акт', '')

                dic['должник'] = dic.get('ФИО должника') or dic.get('Наименование должника')
                logger.info(f'НУЖНЫЙ акт')

                dic.update(renamed_data)

                return dic

        for dic in list_dic:
            link = dic.get('сообщение_ссылка', '')

            response = requests.post(link)
            logger.info(f'текущее сообщение: {link}')

            soup = BeautifulSoup(response.text, 'html.parser')

            # Основная информация
            table_main = soup.find('table', class_='headInfo')
            if table_main:
                rows = table_main.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        field = cells[0].text.strip()
                        value = cells[1].text.strip()
                        dic[field] = value

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
                            dic[field] = value


            text_section = soup.find_all('div', class_='msg')
            dic['текст'] = "; ".join(text.text.strip() for text in text_section if text.text.strip())

            # file_links = []
            # pinned_files = soup.find_all('a', class_='Reference')
            # if pinned_files:
            #     for file in pinned_files:
            #         file_link = file['href'].replace("&amp;", "&")
            #         file_links.append(f'https://old.bankrot.fedresurs.ru/{file_link}')
            # else:
            #     file_links.append("Нет файлов")
            #
            # dic['файлы'] = "&&& ".join(file_links)

            act_status = dic.get('Судебный акт', '')
            if act_status == "об утверждении арбитражного управляющего":
                logger.info(f'первый акт про СМЕНУ АУ')
                continue

            if act_status not in list_of_status:
                logger.info(f'акт не тот, что нам нужен')
                continue

            dic['должник'] = dic.get('ФИО должника') or dic.get('Наименование должника')
            logger.info(f'НУЖНЫЙ акт')

            dic.update(renamed_data)

            return dic

    except Exception as e:
        logger.error(f"НЕ удалось спарсить найденный акт у должника {list_dic[0]['должник_ссылка']}: {e}")
        return None

# поиск 5 актов или имеющихся актов(из меньше 5)
def search_with_pagination(driver, link_debtor):
    """
    Парсинг всех сообщений из <tr> и переход на следующую страницу при наличии пагинации.
    """
    logger.info('началась поиск всех актов у должника')

    # Открываем новую вкладку
    driver.execute_script(f"window.open('{link_debtor}');")
    new_tab = driver.window_handles[-1]
    driver.switch_to.window(new_tab)

    # Получаем HTML-код страницы
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    messages = []
    limit = 0
    checked_messages = set()
    visited_pages = set()
    needed_stop = False
    while not needed_stop:
        if limit == 10:
            needed_stop = True

        table = soup.find('table', class_='bank')
        if table:
            logger.info('нашел таблицу')
            rows = table.find_all('tr')
            for row in rows:
                logger.info('нашел строки')
                row_class = row.get('class', [])
                if not row_class or 'row' in row_class:
                    # Если это строка с данными сообщения
                    cells = row.find_all('td')
                    if len(cells) == 4:
                        # Извлекаем данные из ячеек
                        date = cells[0].get_text(strip=True)
                        message_title = cells[1].get_text(strip=True)
                        tag = cells[1].find('a')['href'] if cells[1].find("a") else None

                        link = f"https://old.bankrot.fedresurs.ru{tag}"

                        if "javascript:__doPostBa" in link:
                            logger.info(f'это ссылка пагинации')
                            continue

                        link_arbitr = cells[2].find("a")["href"] if cells[2].find("a") else None
                        published_by = cells[2].get_text(strip=True)

                        if link in checked_messages:
                            needed_stop = True
                            break

                        checked_messages.add(link)
                        logger.info(message_title)
                        if link:
                            logger.info(f"Ссылка на сообщение: {link}")
                            if "Сообщение о судебном акте" in message_title:
                                logger.info(f'нашел {message_title}')

                                message_face = {
                                    "дата": date,
                                    "тип_сообщения": message_title,
                                    "должник": '',
                                    "должник_ссылка": link_debtor if link else "Нет ссылки",
                                    "арбитр": published_by,
                                    "арбитр_ссылка": f"https://old.bankrot.fedresurs.ru{link_arbitr}" if link_arbitr else "Нет ссылки",
                                    "сообщение_ссылка": link,
                                }
                                limit += 1
                                messages.append(message_face)

            # Если это строка с пагинацией
            pager_row = table.find('tr', class_='pager')
            if not pager_row:
                logger.info("Больше нет страниц для перехода.")
                break
            logger.info("Обнаружена таблица пагинации")

            pager_table = pager_row.find_next('table')
            if not pager_table:
                logger.info("Таблица пагинации не найдена")
                return

            page_elements = pager_table.find_all('a', href=True)
            if not page_elements:
                logger.info("Ссылки пагинации отсутствуют")
                return

            for page_element in page_elements:

                href = page_element['href']
                logger.info(f'ссылка погинации {href}')
                page_action = href.split("'")[3]  # Получаем 'Page$31'
                logger.info(f"Обнаружено действие: {page_action}")

                if page_action == 'Page$1':
                    logger.info('уже проверял первую страницу')
                    visited_pages.add(page_action)
                    continue

                if page_action in visited_pages:
                    logger.info(f"Страница {page_action} уже обработана, пропускаем")
                    continue

                # Проверяем, начинается ли href с нужного JavaScript
                if "javascript:__doPostBack" in href:
                    try:
                        script = """
                            var theForm = document.forms['aspnetForm'];
                            if (!theForm) {
                                theForm = document.aspnetForm;
                            }
                            if (!theForm.onsubmit || (theForm.onsubmit() != false)) {
                                theForm.__EVENTTARGET.value = arguments[0];
                                theForm.__EVENTARGUMENT.value = arguments[1];
                                theForm.submit();
                            }
                            """
                        logger.info(f"Клик по элементу пагинации: {page_action}")
                        driver.execute_script(script, 'ctl00$cphBody$gvMessages', page_action)

                        # element.click()  # Кликаем по элементу
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, 'html'))
                        )
                        time.sleep(3)  # Ожидание загрузки новой страницы

                        # Обновляем soup для новой страницы и продолжаем обработку
                        soup = BeautifulSoup(driver.page_source, 'html.parser')


                        visited_pages.add(page_action)
                        break
                    except Exception as e:
                        logger.error(f"Ошибка при клике на элемент пагинации: {e}")

            else:
                logger.info("Дополнительных страниц для перехода не найдено")

    # Закрытие текущей вкладки
    if len(driver.window_handles) == 2:
        driver.close()
        driver.switch_to.window(driver.window_handles[0])  # Переключаемся на последнюю вкладку
    elif len(driver.window_handles) > 2:
        for handle in driver.window_handles[1:][::-1]:
            driver.switch_to.window(handle)
            driver.close()
        driver.switch_to.window(driver.window_handles[0])

    logger.info('закончил поиск актов')
    return messages
