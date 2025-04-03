import time
from threading import Thread
from DBmanager import prepare_data_for_db, before_check
from logScript import logger
from queue import Queue

from monitoring import clear_form_periodically, selecting_message_type, parse_all_pages_reverse, \
    fetch_and_parse_first_page, pop_last_elem
from pars_messageInfo import parse_message_page
from web_driver import create_webdriver_with_display, is_browser_alive, restart_driver, cleanup_virtual_display


def monitor_threads(threads, restart_queue):
    """
    Мониторинг состояния потоков. Перезапускает поток, если он завершился.
    """
    while True:
        for i, thread in enumerate(threads):
            if not thread.is_alive():
                logger.error(f"Поток {thread.name} завершился. Перезапуск...")

                # Перезапуск потока
                if thread.name == "ClearFormThread":
                    new_thread = Thread(target=clear_form_periodically, args=(3, 1, restart_queue), daemon=True,
                                        name="ClearFormThread")
                else:
                    continue

                threads[i] = new_thread  # Заменяем завершившийся поток на новый
                new_thread.start()

        time.sleep(5)  # Проверка каждые 5 секун

# Основной цикл программы
def main():
    while True:
        driver = create_webdriver_with_display()  # Инициализация WebDriver

        # Очередь для перезапуска драйвера
        restart_queue = Queue()

        # Обход всех страниц при старте
        logger.info("Запускаем полный парсинг всех страниц.")
        error_from_pars_all_pages = parse_all_pages_reverse(driver)
        if error_from_pars_all_pages is False:
            pop_last_elem()
            cleanup_virtual_display(driver)
            driver.quit()
            continue


        # Список потоков
        threads = []

        # Создаём потоки
        clear_thread = Thread(target=clear_form_periodically, args=(17, 00, restart_queue), daemon=True,
                              name="ClearFormThread")

        # Запускаем потоки
        threads.append(clear_thread)
        clear_thread.start()

        # Мониторим потоки
        monitor_thread = Thread(target=monitor_threads, args=(threads, restart_queue), daemon=True, name="MonitorThread")
        monitor_thread.start()

        while True:
            try:
                driver.refresh()
                current_url = driver.current_url
                if 'https://old.bankrot.fedresurs.ru/cookie-js-info.html' in current_url:
                    cleanup_virtual_display(driver)
                    driver.quit()
                    break

                # Проверка, нужно ли перезапустить драйвер
                if not is_browser_alive(driver):
                    logger.warning("Браузер перестал отвечать. Перезапуск...")
                    driver = restart_driver(driver)

                # Проверка, нужно ли перезапустить драйвер
                if not restart_queue.empty():
                    restart_signal = restart_queue.get()
                    if restart_signal:
                        logger.info("Перезапуск сессии WebDriver.")
                        cleanup_virtual_display(driver)
                        driver.quit()
                        break

                # Получаем новые сообщения
                new_messages = fetch_and_parse_first_page(driver)
                if new_messages is None:
                    logger.info("Новых сообщений нет, продолжаем проверку...\n\n")
                    time.sleep(0.5)
                    continue

                try:
                    # Парсим содержимое сообщения
                    parsed_data = parse_message_page(new_messages)
                    logger.info(f'инфа из париснга сообщения {parsed_data}')
                    if parsed_data is None:
                        pop_last_elem()
                        cleanup_virtual_display(driver)
                        driver.quit()
                        break

                    prepared_data = prepare_data_for_db(parsed_data)
                    logger.info(f'данные очищенныеф: {prepared_data}')

                    # метод для проверки статуса и отправки в базу данных
                    check_point = before_check(driver, prepared_data)
                    if check_point is None:
                        logger.error(f'Какая та ошибка в методе before_check: {prepared_data.get("должник_ссылка")}')
                        break

                except Exception as e:
                    logger.error(f"Ошибка при обработке сообщения: {e}")
                    continue

            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                driver = restart_driver(driver)  # Перезапустите WebDriver

            time.sleep(0.5)  # Задержка перед следующим циклом
            logger.info("Ожидание 0.5 секунды для следующего обновления...\n\n")

if __name__ == "__main__":
    main()
