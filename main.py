import logging
import os
from Bot import Bot

NOTION_TOKEN = os.getenv('NOTION_TOKEN')
DATABASE_ID = os.getenv('DATABASE_ID')
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')


def main():
    if NOTION_TOKEN is None or DATABASE_ID is None or BOT_TOKEN is None or ADMIN_USERNAME is None:
        logging.log(logging.ERROR, 'Переменные окружения NOTION_TOKEN, DATABASE_ID, BOT_TOKEN, ADMIN_USERNAME не заданы')
        return

    bot = Bot(BOT_TOKEN, NOTION_TOKEN, DATABASE_ID, ADMIN_USERNAME)
    bot.run()


if __name__ == '__main__':
    main()
