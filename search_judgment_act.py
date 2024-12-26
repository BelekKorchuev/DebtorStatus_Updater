import time

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
def search_act(driver, list_dic):
    try:
        for dic in list_dic:
            # Открытие новой вкладки
            driver.switch_to.window(driver.window_handles[-1])

            link = dic.get('сообщение_ссылка', '')

            driver.get(link)
            logger.info(f'текущее сообщение: {link}')

            # Получение HTML-кода страницы
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

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

            act_status = dic.get('Судебный акт', '')
            if act_status == "об утверждении арбитражного управляющего":
                logger.info(f'первый акт про СМЕНУ АУ')
                continue

            if act_status not in list_of_status:
                logger.info(f'акт не тот, что нам нужен')
                continue

            dic['должник'] = dic.get('ФИО должника') or dic.get('Наименование должника')
            logger.info(f'НУЖНЫЙ акт')

            # Закрытие текущей вкладки
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[-1])  # Переключаемся на последнюю вкладку

            return dic


    except Exception as e:
        logger.error(f'НЕ удалось спарсить найденный акт у должника {list_dic[0]['должник_ссылка']}: {e}')
        driver.close()
        driver.switch_to.window(driver.window_handles[-1])
        return

# поиск 5 актов или имеющихся актов(из меньше 5)
def search_with_pagination(driver, link_debtor):
    """
    Парсинг всех сообщений из <tr> и переход на следующую страницу при наличии пагинации.
    """
    logger.info('началась поиск всех актов у должника')

    # Открываем новую вкладку
    driver.execute_script("window.open('');")
    new_tab = driver.window_handles[-1]  # Получаем хендл новой вкладки
    driver.switch_to.window(new_tab)  # Переключаемся на новую вкладку

    # Открываем указанный URL в новой вкладке
    driver.get(link_debtor)

    # Получаем HTML-код страницы
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    messages = []
    limit = 0
    checked_messages = set()
    visited_pages = set()
    needed_stop = False
    while not needed_stop:
        if limit == 5:
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
                    if len(cells) >= 4:
                        # Извлекаем данные из ячеек
                        date = cells[0].get_text(strip=True)
                        message_title = cells[1].get_text(strip=True)
                        tag = cells[1].find('a')
                        raw_link = tag['onclick'].split("'")[1]
                        link = f"https://old.bankrot.fedresurs.ru{raw_link}"

                        link_arbitr = cells[2].find("a")["href"] if cells[2].find("a") else None
                        published_by = cells[2].get_text(strip=True)

                        if link in checked_messages:
                            needed_stop = True
                            break

                        checked_messages.add(link)
                        logger.info(message_title)
                        if tag and 'onclick' in tag.attrs:  # Безопасная проверка наличия атрибута
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
                if 'pager' in row_class:
                    pager_table = row.find_next('table')
                    if not pager_table:
                        logger.info("Таблица пагинации не найдена")
                        return

                    page_elements = pager_table.find_all('a', href=True)
                    if not page_elements:
                        logger.info("Ссылки пагинации отсутствуют")
                        return

                    for page_element in page_elements:

                        href = page_element['href']
                        page_action = href.split("'")[3]  # Получаем 'Page$31'
                        logger.info(f"Обнаружено действие: {page_action}")

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
                                return
                    else:
                        logger.info("Дополнительных страниц для перехода не найдено")
                        return

    logger.info('закончил поиск актов')
    return messages
