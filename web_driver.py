from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import os
import subprocess
from logScript import logger

# создание виртуального дисплея
def setup_virtual_display():
    """
    Настройка виртуального дисплея через Xvfb.
    """
    try:
        # Запуск Xvfb
        xvfb_process = subprocess.Popen(['Xvfb', ':107', '-screen', '0', '1920x1080x24', '-nolisten', 'tcp'])
        # Установка переменной окружения DISPLAY
        os.environ["DISPLAY"] = ":107"
        logger.info("Виртуальный дисплей успешно настроен с использованием Xvfb.")
        return xvfb_process
    except Exception as e:
        logger.error(f"Ошибка при настройке виртуального дисплея: {e}")
        return None

# создание веб драйвера с виртуальным дисплем
def create_webdriver_with_display():
    """
    Создает WebDriver с виртуальным дисплеем.
    """
    try:
        # Настройка виртуального дисплея
        xvfb_process = setup_virtual_display()
        if not xvfb_process:
            raise RuntimeError("Не удалось настроить виртуальный дисплей.")

        # Настройка WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_service = Service(ChromeDriverManager().install())

        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
        driver.xvfb_process = xvfb_process  # Сохраняем процесс для последующего завершения
        return driver
    except Exception as e:
        logger.error(f"Ошибка при создании WebDriver: {e}")
        return None

# очистка виртуального дисплея
def cleanup_virtual_display(driver):
    """
    Завершает процесс Xvfb.
    """
    if hasattr(driver, "xvfb_process") and driver.xvfb_process:
        driver.xvfb_process.terminate()
        logger.info("Процесс Xvfb завершен.")

# Функция для перезапуска драйвера
def restart_driver(driver):
    try:
        cleanup_virtual_display(driver)
        driver.quit()  # Завершаем текущую сессию
    except Exception as e:
        logger.error(f"Ошибка при завершении WebDriver: {e}")
    return create_webdriver_with_display()

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