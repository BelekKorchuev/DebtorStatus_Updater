from datetime import datetime
import os
import time
from logScript import logger
from dotenv import load_dotenv
import psycopg2
from psycopg2 import OperationalError

load_dotenv(dotenv_path='.env')

db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name2 = os.getenv('DB_NAME2')

# Функция для подключения к базе данных
def get_db1_connection():
    try:
        connection = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        return connection
    except OperationalError as e:
        logger.error(f"Ошибка при подключении: {e}")
        time.sleep(5)
        return get_db1_connection()

# Функция для подключения к базе данных
def get_db2_connection():
    try:
        connection = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name2,
            user=db_user,
            password=db_password
        )
        return connection
    except OperationalError as e:
        logger.error(f"Ошибка при подключении: {e}")
        time.sleep(5)
        return get_db2_connection()

# Функция для очистки текста
def clean_text(text):
    """Удаляет лишние символы из текста и приводит его в читаемый вид"""
    text = text.replace('\xa0', ' ').replace('\t', ' ').strip()
    # Убираем лишние пробелы, если они есть
    text = " ".join(text.split())
    return text

# Функция для подготовки данных для вставки в базу данных
def prepare_data_for_db(raw_data):
    """Приводит данные к нужному формату для вставки в базу данных"""

    # Общие данные для всех сообщений
    data = raw_data.get('дата', '')
    date = datetime.strptime(data, "%d.%m.%Y %H:%M:%S") if data else None
    debtor = clean_text(raw_data.get('должник', ''))
    debtor_link = raw_data.get('должник_ссылка', '')
    arbiter = clean_text(raw_data.get('арбитр', ''))
    arbiter_link = raw_data.get('арбитр_ссылка', '')
    message_link = raw_data.get('сообщение_ссылка', '')

    # Данные из содержимого сообщения
    judgment_act = clean_text(raw_data.get('Судебный акт', ''))

    # Данные о должнике
    debtor_name = clean_text(raw_data.get('Наименование должника', '') or raw_data.get('ФИО должника', ''))
    address = clean_text(raw_data.get('Адрес', ''))
    ogrn = clean_text(raw_data.get('ОГРН', ''))
    inn = clean_text(raw_data.get('ИНН', ''))
    case_number = clean_text(raw_data.get('№ дела', ''))
    birth_date = raw_data.get('Дата рождения', '')
    birth_place = clean_text(raw_data.get('Место рождения', ''))
    residence = clean_text(raw_data.get('Место жительства', ''))
    snils = clean_text(raw_data.get('СНИЛС', ''))

    # Данные об арбитраже
    arbiter_name = clean_text(raw_data.get('Арбитражный управляющий', ''))
    correspondence_address = clean_text(raw_data.get('Адрес для корреспонденции', ''))
    email = clean_text(raw_data.get('E-mail', ''))
    sro_au = clean_text(raw_data.get('СРО АУ', ''))
    sro_address = clean_text(raw_data.get('Адрес СРО АУ', ''))

    text = clean_text(raw_data.get('текст', ''))
    files_link = raw_data.get('файлы', '')


    # Подготовленные данные для вставки
    prepared_data = {
        'дата': date,
        'должник': debtor,
        'должник_ссылка': debtor_link,
        'арбитр': arbiter,
        'арбитр_ссылка': arbiter_link,
        'сообщение_ссылка': message_link,

        'cудебный_акт': judgment_act,
        'наименование_должника': debtor_name,
        'адрес ': address,
        'ОГРН': ogrn,
        'ИНН': inn,
        'номер_дела': case_number,
        'дата_рождения': birth_date,
        'место_рождения': birth_place,
        'место_жительства': residence,
        'СНИЛС': snils,

        'ФИО_АУ': arbiter_name,
        'адрес_корреспонденции': correspondence_address,
        'почта': email,
        'СРО_АУ': sro_au,
        'адрес_СРО_АУ': sro_address,
        'текст': text,
        'ссылка_файл': files_link
    }

    return prepared_data

# отправка данных в базу
def status_updating(data):
    try:
        conn_crm = get_db1_connection()
        conn_default = get_db2_connection()

        # Создаем курсор
        cursor_crm = conn_crm.cursor()
        cursor_default =conn_default.cursor()

        query_crm = '''
            INSERT INTO debtor_status_newau (
                дата, должник, должник_ссылка, сообщение_ссылка, текущий_статус,   
                наименование_должника, адрес, ОГРН, ИНН, номер_дела, дата_рождения, место_рождения,
                место_жительства, СНИЛС, текст, ссылка_файл
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            '''
        values_crm = (
            data['дата'], data['должник'],
            data["должник_ссылка"], data["сообщение_ссылка"],
            data["cудебный_акт"],
            data["наименование_должника"], data["адрес"], data["ОГРН"],
            data["ИНН"], data["номер_дела"], data["дата_рождения"], data['место_рождения'],
            data['место_жительства'], data['СНИЛС'], data['текст'], data['ссылка_файл']
        )
        cursor_crm.execute(query_crm, values_crm)


        # SQL-запрос для вставки данных
        query_default = '''
            UPDATE dolzhnik 
            SET текущий_статус = %s
            WHERE Инн_Должника = %s
            '''

        values_default = (
            data['cудебный_акт'], data['ИНН']
        )
        # Выполняем запрос с передачей данных из словаря
        cursor_default.execute(query_default, values_default)

        # Фиксируем изменения
        if conn_crm:
            conn_crm.rollback()
        if conn_default:
            conn_default.rollback()


        logger.info(f"Данные успешно добавлены в базу для {data['ИНН']}")
    except Exception as e:
        logger.error(f"Ошибка вставки данных в базу для {data['ИНН']}: {e}")
        conn_crm.rollback()
        conn_default.rollback()
    finally:
        if cursor_crm:
            cursor_crm.close()
        if cursor_default:
            cursor_default.close()
        if conn_crm:
            conn_crm.close()
        if conn_default:
            conn_default.close()

# отправка данных в базу
def status_au_updating(data):
    try:
        conn_crm = get_db1_connection()
        conn_default = get_db2_connection()

        # Создаем курсор
        cursor_crm = conn_crm.cursor()
        cursor_default =conn_default.cursor()

        query_crm = '''
            INSERT INTO debtor_status_newau (
                дата, должник, должник_ссылка, сообщение_ссылка, текущий_статус,   
                наименование_должника, адрес, ОГРН, ИНН, номер_дела, дата_рождения, место_рождения,
                место_жительства, СНИЛС, текст, ссылка_файл
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            '''
        values_crm = (
            data['дата'], data['должник'],
            data["должник_ссылка"], data["сообщение_ссылка"],
            data["cудебный_акт"],
            data["наименование_должника"], data["адрес"], data["ОГРН"],
            data["ИНН"], data["номер_дела"], data["дата_рождения"], data['место_рождения'],
            data['место_жительства'], data['СНИЛС'], data['текст'], data['ссылка_файл']
        )
        cursor_crm.execute(query_crm, values_crm)


        # SQL-запрос для вставки данных
        query_default = '''
            UPDATE dolzhnik 
            SET текущий_статус = %s
            WHERE Инн_Должника = %s
            '''

        values_default = (
            data['cудебный_акт'], data['ИНН']
        )
        # Выполняем запрос с передачей данных из словаря
        cursor_default.execute(query_default, values_default)

        # Фиксируем изменения
        if conn_crm:
            conn_crm.rollback()
        if conn_default:
            conn_default.rollback()


        logger.info(f"Данные успешно добавлены в базу для {data['ИНН']}")
    except Exception as e:
        logger.error(f"Ошибка вставки данных в базу для {data['ИНН']}: {e}")
        conn_crm.rollback()
        conn_default.rollback()
    finally:
        if cursor_crm:
            cursor_crm.close()
        if cursor_default:
            cursor_default.close()
        if conn_crm:
            conn_crm.close()
        if conn_default:
            conn_default.close()

# проверка статуса должника
def before_check(data):
    status = data['Судебный акт']

    list_of_status = {'о введении наблюдения', 'о признании обоснованным заявления о признании гражданина банкротом и введении реструктуризации его долгов',
                      'о признании должника банкротом и открытии конкурсного производства', 'о передаче дела на рассмотрение другого арбитражного суда об утверждении плана реструктуризации долгов гражданина',
                      'о признании должника банкротом и введении реализации имущества гражданина', 'о напременении в отношении гражданина правила об освобождении от исполнения обязательств',
                      'о завершении реализации имущества гражданина', 'о прекращении производства по делу'}

    changed_au = {'об утверждении арбитражного управляющего'}

    if status in list_of_status:
        status_updating(data)

    if status in changed_au:
        status_au_updating(data)




