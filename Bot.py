import asyncio
import logging
import re
from typing import List, Dict, Tuple

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

    content_types: List[str] = []
    """список типов контента"""

    categories: List[str] = []
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

            await _get_variants(message.chat.id)

            await self.bot.send_message(message.chat.id, "Введите ссылку на материал (если ссылки нет, введите '-')", reply_markup=self.hideBoard)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 1)
        async def send_add_url(message: telebot.types.Message):
            self.userStep[message.chat.id] = 2
            self.notionItem[message.chat.id].url = message.text if message.text != '-' else None

            await self.bot.send_message(message.chat.id, "Введите название материала", reply_markup=self.hideBoard)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 2)
        async def send_add_name(message: telebot.types.Message):
            self.userStep[message.chat.id] = 3
            self.notionItem[message.chat.id].name = message.text

            await self.bot.send_message(message.chat.id, "Выберите тип контента", reply_markup=self.content_type_buttons)

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

            await self.bot.send_message(message.chat.id, "Введите описание материала (если описание нет, введите '-')", reply_markup=self.hideBoard)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 5)
        async def send_add_description(message: telebot.types.Message):
            self.userStep[message.chat.id] = 0
            self.notionItem[message.chat.id].description = message.text if message.text != '-' else None

            try:
                await self.notionItem[message.chat.id].add_item_to_notion(notion_token, database_id)
            except APIResponseError as e:
                logging.log(logging.ERROR, e)
                await self.bot.send_message(message.chat.id, "Ошибка добавления элемента в таблицу Notion", reply_markup=self.start_buttons)
            else:
                await self.bot.send_message(message.chat.id, "Элемент добавлен в таблицу Notion", reply_markup=self.start_buttons)

        @self.bot.message_handler(content_types=['text', 'photo', 'document', 'animation', 'video'],
                                  func=lambda message: message.forward_from is not None
                                                       or message.forward_from_chat is not None)
        async def forwarded_message(message: telebot.types.Message):
            self.userStep[message.chat.id] = 10
            notion_item, parsing_code = _parse_post(message)

            self.notionItem[message.chat.id] = notion_item

            await _get_variants(message.chat.id)

            if parsing_code == 1:
                self.userStep[message.chat.id] = 11
                await self.bot.send_message(message.chat.id, "Было обнаружено несколько ссылок.\n"
                                                             f"Выбрана: {notion_item.url}\n\n"
                                                             "Если вас устраивает выбор, введите '-', иначе, введите подходящую ссылку.",
                                            reply_markup=self.hideBoard)
            else:
                await send_forwarded_name_before(message)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 11)
        async def send_multiple_links(message: telebot.types.Message):
            self.userStep[message.chat.id] = 10
            if message.text != '-':
                self.notionItem[message.chat.id].url = message.text

            await send_forwarded_name_before(message)

        async def send_forwarded_name_before(message: telebot.types.Message):
            await self.bot.send_message(message.chat.id, "Проверьте и при необходимости исправьте название материала:\n\n"
                                                         f"'{self.notionItem[message.chat.id].name}'\n\n"
                                                         "Если вас устраивает выбор, введите '-', иначе, введите подходящее название",
                                        reply_markup=self.hideBoard)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 10)
        async def send_forwarded_name(message: telebot.types.Message):
            self.userStep[message.chat.id] = 12
            if message.text != '-':
                self.notionItem[message.chat.id].name = message.text

            await self.bot.send_message(message.chat.id, "Выберите тип контента", reply_markup=self.content_type_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 12)
        async def send_add_content_type(message: telebot.types.Message):
            self.userStep[message.chat.id] = 13

            # валидация
            if self.content_types:
                if not self.content_types.__contains__(message.text):
                    self.userStep[message.chat.id] = 12
                    await self.bot.send_message(message.chat.id,
                                                "Данный тип контента не существует, попробуйте ещё раз",
                                                reply_markup=self.content_type_buttons)
                    return

            self.notionItem[message.chat.id].content_type = message.text

            await self.bot.send_message(message.chat.id, "Выберите категорию", reply_markup=self.category_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 13)
        async def send_add_category(message: telebot.types.Message):
            self.userStep[message.chat.id] = 0

            # валидация
            if self.categories:
                if not self.categories.__contains__(message.text):
                    self.userStep[message.chat.id] = 13
                    await self.bot.send_message(message.chat.id,
                                                "Данная категория не существует, попробуйте ещё раз",
                                                reply_markup=self.category_buttons)
                    return

            self.notionItem[message.chat.id].category = message.text

            try:
                await self.notionItem[message.chat.id].add_item_to_notion(notion_token, database_id)
            except APIResponseError as e:
                logging.log(logging.ERROR, e)
                await self.bot.send_message(message.chat.id, "Ошибка добавления элемента в таблицу Notion", reply_markup=self.start_buttons)
            else:
                await self.bot.send_message(message.chat.id, "Элемент добавлен в таблицу Notion", reply_markup=self.start_buttons)

        def _parse_post(message: telebot.types.Message) -> Tuple[NotionItem, int]:
            """
            Парсер поста с полезной информацией
            :param message: сообщение пользователя
            :return: элемент таблицы Notion и статус код парсинга (0 - успешно, 1 - несколько ссылок)
            """
            text = message.html_text if message.html_text else message.html_caption

            url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
            urls = url_pattern.findall(text)

            item = NotionItem()
            item.url = urls[0] if urls else None
            item.description = text
            item.name = _parse_post_name(text)

            if len(urls) <= 1:
                return item, 0
            else:
                return item, 1

        def _parse_post_name(text: str) -> str:
            """
            Парсер названия материала из поста
            :param text: текст поста
            :return: название материала
            """
            try:
                if text.startswith('<b>'):
                    text = text.split('<b>')[1].split('</b>')[0]
                else:
                    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
                    text = re.sub(url_pattern, '', text)

                    text = text.split('\n')[0]
                    text = re.split('[?.!]', text)[0]
            except:
                text = '-'
            else:
                if text is None or len(text) == 0 or text.isspace():
                    text = '-'

            return text

        async def _get_variants(chat_id: int) -> None:
            """
            Получение списка вариантов категорий и типов контента
            :param chat_id: ID чата
            :return: None
            """
            self.content_types.clear()
            self.categories.clear()
            self.content_types, self.categories = \
                await self.notionItem[chat_id].get_content_types_and_categories(notion_token, database_id)

            self.content_type_buttons.keyboard.clear()
            self.category_buttons.keyboard.clear()

            self.content_type_buttons.add(*self.content_types)
            self.category_buttons.add(*self.categories)

    def run(self):
        """Запустить бота"""
        return asyncio.run(self.bot.polling(non_stop=True))
