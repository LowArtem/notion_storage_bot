import asyncio
import logging
from typing import List, Dict

import telebot
from notion_client import APIResponseError
from telebot.async_telebot import AsyncTeleBot

from NotionItem import NotionItem


class Bot:
    """
    Класс, управляющий telegram ботом, который сохраняет элементы в таблицу Notion
    """

    commands = {
        'start': 'старт бота',
        'help': 'справка по командам',
        'add': 'добавить элемент в таблицу Notion'
    }
    """список команд бота"""

    userStep = {}
    """текущее состояние пользователя при выполнении команды"""

    start_buttons = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    """начальные кнопки"""
    start_buttons.add(commands['help'], commands['add'])

    category_buttons = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    """кнопки выбора категории"""

    content_type_buttons = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    """кнопки выбора типа контента"""

    hideBoard = telebot.types.ReplyKeyboardRemove()
    """удалить кнопки из клавиатуры"""

    start_message = 'Добро пожаловать в NotionStorageBot.\n\n' \
                    'Он позволяет сохранять полезные материалы, ссылки, заметки в таблицу Notion.\n\n' \
                    'Список доступных команд по команде /help'
    """сообщение при старте бота"""

    help_message = 'Список доступных команд:\n\n' \
                   '/start - старт бота\n' \
                   '/help - справка по командам\n' \
                   '/add - добавить элемент в таблицу Notion'
    """сообщение команды /help"""

    notionItem: Dict[int, NotionItem] = {}

    content_types: List[str]
    """список типов контента"""

    categories: List[str]
    """список категорий"""

    bot: AsyncTeleBot
    """бот"""

    def __init__(self, telegram_token: str, notion_token: str, database_id: str, admin_username: str):
        """
        Создать бота
        :param telegram_token: токен telegram бота
        :param notion_token: токен для доступа к Notion
        :param database_id: ID таблицы Notion
        """
        self.bot = AsyncTeleBot(token=telegram_token)

        # /start handler
        @self.bot.message_handler(commands=['start'])
        async def send_start(message: telebot.types.Message):
            self.userStep[message.chat.id] = 0
            await self.bot.send_message(message.chat.id, self.start_message, reply_markup=self.start_buttons)

        @self.bot.message_handler(func=lambda message: message.text == self.commands['help'] or message.text == '/help')
        async def send_help(message: telebot.types.Message):
            self.userStep[message.chat.id] = 0
            await self.bot.send_message(message.chat.id, self.help_message, reply_markup=self.start_buttons)

        @self.bot.message_handler(func=lambda message: (message.text == self.commands[
            'add'] or message.text == '/add') and message.from_user.username == admin_username)
        async def send_add_beginning(message: telebot.types.Message):
            self.userStep[message.chat.id] = 1
            self.notionItem[message.chat.id] = NotionItem()

            self.content_types, self.categories = \
                await self.notionItem[message.chat.id].get_content_types_and_categories(notion_token, database_id)

            self.content_type_buttons.add(*self.content_types)
            self.category_buttons.add(*self.categories)

            await self.bot.send_message(message.chat.id, "Введите ссылку на материал (если ссылки нет, введие '-')",
                                        reply_markup=self.hideBoard)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 1)
        async def send_add_url(message: telebot.types.Message):
            self.userStep[message.chat.id] = 2
            self.notionItem[message.chat.id].url = message.text if message.text != '-' else None

            await self.bot.send_message(message.chat.id, "Введите название материала", reply_markup=self.hideBoard)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 2)
        async def send_add_name(message: telebot.types.Message):
            self.userStep[message.chat.id] = 3
            self.notionItem[message.chat.id].name = message.text

            await self.bot.send_message(message.chat.id, "Выберите тип контента",
                                        reply_markup=self.content_type_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 3)
        async def send_add_content_type(message: telebot.types.Message):
            self.userStep[message.chat.id] = 4

            # валидация
            if self.content_types:
                if not self.content_types.__contains__(message.text):
                    self.userStep[message.chat.id] = 3
                    await self.bot.send_message(message.chat.id,
                                                "Данный тип контента не существует, попробуйте ещё раз",
                                                reply_markup=self.content_type_buttons)
                    return

            self.notionItem[message.chat.id].content_type = message.text

            await self.bot.send_message(message.chat.id, "Выберите категорию", reply_markup=self.category_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 4)
        async def send_add_category(message: telebot.types.Message):
            self.userStep[message.chat.id] = 5

            # валидация
            if self.categories:
                if not self.categories.__contains__(message.text):
                    self.userStep[message.chat.id] = 4
                    await self.bot.send_message(message.chat.id,
                                                "Данная категория не существует, попробуйте ещё раз",
                                                reply_markup=self.category_buttons)
                    return

            self.notionItem[message.chat.id].category = message.text

            await self.bot.send_message(message.chat.id, "Введите описание материала (если описание нет, введите '-')",
                                        reply_markup=self.hideBoard)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 5)
        async def send_add_description(message: telebot.types.Message):
            self.userStep[message.chat.id] = 0
            self.notionItem[message.chat.id].description = message.text if message.text != '-' else None

            try:
                await self.notionItem[message.chat.id].add_item_to_notion(notion_token, database_id)
            except APIResponseError as e:
                logging.log(logging.ERROR, e)
                await self.bot.send_message(message.chat.id, "Ошибка добавления элемента в таблицу Notion",
                                            reply_markup=self.start_buttons)
            else:
                await self.bot.send_message(message.chat.id, "Элемент добавлен в таблицу Notion",
                                            reply_markup=self.start_buttons)

    def run(self):
        """Запустить бота"""
        return asyncio.run(self.bot.polling(non_stop=True))
