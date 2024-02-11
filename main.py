import logging
import os
import time

import gevent

from Bot import Bot
import threading
import sched

from ImageStore import ImageStore
from NotionWorkNote import NotionWorkNote

NOTION_TOKEN = os.getenv('NOTION_TOKEN')
DATABASE_ID = os.getenv('DATABASE_ID')
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
YANDEX_TOKEN = os.getenv('YANDEX_TOKEN')
WORK_NOTES_DATABASE_ID = os.getenv('WORK_NOTES_DATABASE_ID')
IMAGE_KIT_PRIVATE_KEY = os.getenv('IMAGE_KIT_PRIVATE_KEY')
IMAGE_KIT_PUBLIC_KEY = os.getenv('IMAGE_KIT_PUBLIC_KEY')
IMAGE_KIT_ENDPOINT = os.getenv('IMAGE_KIT_ENDPOINT')

constants = [NOTION_TOKEN, DATABASE_ID, BOT_TOKEN, ADMIN_USERNAME, YANDEX_TOKEN, WORK_NOTES_DATABASE_ID, IMAGE_KIT_PRIVATE_KEY, IMAGE_KIT_PUBLIC_KEY,
             IMAGE_KIT_ENDPOINT]


def main():
    if any(constants) is False:
        logging.log(logging.ERROR, 'Переменные окружения не заданы')
        return

    image_store = ImageStore(IMAGE_KIT_PRIVATE_KEY, IMAGE_KIT_PUBLIC_KEY, IMAGE_KIT_ENDPOINT)
    notion_work_note_client = NotionWorkNote(NOTION_TOKEN, WORK_NOTES_DATABASE_ID, image_store)

    bot = Bot(BOT_TOKEN, NOTION_TOKEN, DATABASE_ID, ADMIN_USERNAME, YANDEX_TOKEN, notion_work_note_client)
    bot_thread = threading.Thread(target=bot.run)
    bot_thread.start()

    scheduler = sched.scheduler(time.time, gevent.sleep)
    scheduler.enter(3 * 30 * 24 * 60 * 60, 1, periodic_task, (scheduler, image_store))
    scheduler.run()


def periodic_task(scheduler: sched.scheduler, image_store: ImageStore) -> None:
    """
    Периодическая задача по удалению старых изображений
    :param scheduler: объект расписания
    :param image_store: объект хранения изображений
    :return: None
    """
    image_store.delete_outdated_images()
    print('Удалены старые изображения')

    scheduler.enter(3 * 30 * 24 * 60 * 60, 1, periodic_task, (scheduler, image_store))


if __name__ == '__main__':
    main()
