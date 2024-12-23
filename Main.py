import time
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

from logScript import logger
from queue import Queue



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

    while True:
        try:
            # Проверка, нужно ли перезапустить драйвер
            if not is_browser_alive(driver):
                logger.warning("Браузер перестал отвечать. Перезапуск...")
                driver = restart_driver(driver)

            # Получаем новые сообщения
            new_messages = fetch_and_parse_first_page(driver)
            if new_messages is None:
                print("Новых сообщений нет, продолжаем проверку...\n\n")
                time.sleep(0.5)
                continue

            link = new_messages["сообщение_ссылка"]
            try:
                # # Парсим содержимое сообщения
                # message_content = parse_message_page(link, driver)
                # new_messages['message_content'] = message_content
                #
                # # Подготовка данных перед вставкой в БД
                # prepared_data = prepare_data_for_db(new_messages)
                # logger.info(f'Сырые сообщения: %s' , str(prepared_data))
                #
                # # добавление новых АУ и должников
                # au_debtorsDetecting(prepared_data)
                #
                # # Вставляем данные в БД и получаем ID
                # insert_message_to_db(prepared_data)
                #
                # # Форматируем данные
                # formatted_data = split_columns(prepared_data)
                #
                # # Проверяем отформатированные данные
                # lots_analyze(formatted_data)

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
