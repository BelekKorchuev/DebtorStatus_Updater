import time
from threading import Thread

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

from DBmanager import prepare_data_for_db, before_check
from logScript import logger
from queue import Queue

from monitoring import clear_form_periodically, fetch_and_parse_first_page, parse_all_pages_reverse
from pars_messageInfo import parse_message_page

# Конфигурация Chrome
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Функция для создания нового драйвера
def create_driver():
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

# Функция для перезапуска драйвера
def restart_driver(driver):
    try:
        driver.quit()  # Завершаем текущую сессию
    except Exception as e:
        logger.error(f"Ошибка при завершении WebDriver: {e}")
    return create_driver()

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

        time.sleep(5)  # Проверка каждые 5 секунд

# Функция проверки состояния браузера
def is_browser_alive(driver):
    """
    Проверяет, жив ли браузер.
    :param driver: WebDriver instance.
    :return: True, если браузер работает, иначе False.
    """
    try:
        driver.title  # Пробуем получить заголовок текущей страницы
        return True
    except Exception as e:
        logger.warning(f"Браузер не отвечает: {e}")
        return False


# Основной цикл программы
def main():
    driver = create_driver()  # Инициализация WebDriver

    # Очередь для перезапуска драйвера
    restart_queue = Queue()

    # Обход всех страниц при старте
    logger.info("Запускаем полный парсинг всех страниц.")
    parse_all_pages_reverse(driver)

    # Список потоков
    threads = []

    # Создаём потоки
    clear_thread = Thread(target=clear_form_periodically, args=(3, 1, restart_queue), daemon=True,
                          name="ClearFormThread")

    # Запускаем потоки
    threads.append(clear_thread)
    clear_thread.start()

    # Мониторим потоки
    monitor_thread = Thread(target=monitor_threads, args=(threads, restart_queue), daemon=True, name="MonitorThread")
    monitor_thread.start()

    while True:
        try:


            # Проверка, нужно ли перезапустить драйвер
            if not is_browser_alive(driver):
                logger.warning("Браузер перестал отвечать. Перезапуск...")
                driver = restart_driver(driver)

            # Проверка, нужно ли перезапустить драйвер
            if not restart_queue.empty():
                restart_signal = restart_queue.get()
                if restart_signal:
                    logger.info("Перезапуск сессии WebDriver.")
                    driver = restart_driver(driver)

            # Получаем новые сообщения
            new_messages = fetch_and_parse_first_page(driver)
            if new_messages is None:
                print("Новых сообщений нет, продолжаем проверку...\n\n")
                time.sleep(0.5)
                continue

            try:
                # Парсим содержимое сообщения
                parsed_data = parse_message_page(new_messages, driver)
                prepered_data = prepare_data_for_db(parsed_data)

                # метод для проверки статуса и отправки в базу данных
                before_check(driver, prepered_data)



            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения: {e}")
                continue

        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")
            driver = restart_driver(driver)  # Перезапустите WebDriver

        time.sleep(0.5)  # Задержка перед следующим циклом
        print("\n \n Ожидание 0.5 секунды для следующего обновления...")

if __name__ == "__main__":
    main()
