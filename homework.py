import logging
import os
import sys
import time
import telegram
import requests
from http import HTTPStatus
import json
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.info(f'Отправлено сообщение: {message}')
    except telegram.TelegramError:
        logger.error('Не удалось отправить сообщение.')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    При успехе возращается ответ API, приведённый к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    status = response.status_code
    if status == HTTPStatus.OK:
        try:
            return response.json()
        except json.decoder.JSONDecodeError:
            logger.error('Ошибка преобразования к типам данных Python')
    else:
        logger.error(
            f'Недоступность эндпоинта {ENDPOINT}. Код ответа API: {status}'
        )
        raise AssertionError


def check_response(response):
    """Проверяет ответ API на корректность.
    В качестве параметра получает ответ API, приведенный к типам данных Python.
    В случае успеха возвращает список домашних работ,
    доступный в ответе API по ключу 'homeworks'.
    """
    if type(response) is not dict:
        logger.error('Ответ API не является словарем.')
        raise TypeError

    if ('current_date' in response) and ('homeworks' in response):
        if type(response.get('homeworks')) is not list:
            logger.error('Ответ API не соответствует.')
            raise TypeError
        homeworks = response.get('homeworks')
        return homeworks
    else:
        logger.error('Ключи словаря не соответствуют ожиданиям.')
        raise KeyError


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра получает только один элемент из списка домашних работ.
    В случае успеха, возвращает один из вердиктов словаря HOMEWORK_STATUSES.
    """
    homework_name = homework.get('homework_name')
    if not homework_name:
        logger.error(f'Отсутствует или пустое поле: {homework_name}')
        raise KeyError
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        logger.error(f'Неизвестный статус: {homework_status}')
        raise KeyError
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения.
    Если отсутствует хотя бы одна переменная окружения —
    функция должна вернуть False, иначе — True.
    """
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует переменная окружения')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                for hw in homeworks:
                    message = parse_status(hw)
                    send_message(bot, message)
            else:
                logger.debug('Новые статусы в ответе отсутствуют')
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
