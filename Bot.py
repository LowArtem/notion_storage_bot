import asyncio
import logging
import re
from typing import List, Dict, Tuple

import requests
import telebot
from bs4 import BeautifulSoup
from notion_client import APIResponseError
from telebot.async_telebot import AsyncTeleBot

from NotionItem import NotionItem
from NotionWorkNote import NotionWorkNote, NotionWorkNoteItem


class Bot:
    """
    Класс, управляющий telegram ботом, который сохраняет элементы в таблицу Notion
    """

    commands = {
        'start': 'старт бота',
        'help': 'справка по командам',
        'add': 'добавить элемент в таблицу Notion',
        'add_work_urg_imp': 'Срочная важная',
        'add_work_urg_unimp': 'Срочная неважная',
        'add_work_unurg_imp': 'Несрочная важная',
        'add_work_unurg_unimp': 'Несрочная неважная'
    }
    """список команд бота"""

    userStep = {}
    """текущее состояние пользователя при выполнении команды"""

    start_buttons = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    """начальные кнопки"""
    start_buttons.add(commands['help'], commands['add'], commands['add_work_urg_imp'], commands['add_work_urg_unimp'], commands['add_work_unurg_imp'],
                      commands['add_work_unurg_unimp'])

    category_buttons = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    """кнопки выбора категории"""

    content_type_buttons = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    """кнопки выбора типа контента"""

    hideBoard = telebot.types.ReplyKeyboardRemove()
    """удалить кнопки из клавиатуры"""

    cancel_buttons_text = 'Отменить'
    approve_buttons_text = 'Подтвердить'
    skip_buttons_text = 'Пропустить'

    approve_cancel_buttons = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    approve_cancel_buttons.add(approve_buttons_text, cancel_buttons_text)

    skip_cancel_buttons = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    skip_cancel_buttons.add(skip_buttons_text, cancel_buttons_text)

    cancel_buttons = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    cancel_buttons.add(cancel_buttons_text)

    start_message = 'Добро пожаловать в NotionStorageBot.\n\n' \
                    'Он позволяет сохранять полезные материалы, ссылки, заметки в таблицу Notion.\n\n' \
                    'Список доступных команд по команде /help'
    """сообщение при старте бота"""

    help_message = 'Список доступных команд:\n\n' \
                   '/start - старт бота\n' \
                   '/help - справка по командам\n' \
                   '/add - добавить элемент в таблицу Notion\n' \
                   '/add_work_urg_imp - добавить срочную важную задачу\n' \
                   '/add_work_urg_unimp - добавить срочную неважную задачу\n' \
                   '/add_work_unurg_imp - добавить несрочную важную задачу\n' \
                   '/add_work_unurg_unimp - добавить несрочную неважную задачу\n'
    """сообщение команды /help"""

    notionItem: Dict[int, NotionItem] = {}
    """ОБъект NotionItem для каждого пользователя"""

    notion_work_note_item: Dict[int, NotionWorkNoteItem] = {}

    content_types: List[str] = []
    """список типов контента"""

    categories: List[str] = []
    """список категорий"""

    bot: AsyncTeleBot
    """бот"""

    notion_work_note_client: NotionWorkNote
    """клиент для работы с рабочими заметками Notion"""

    def __init__(self, telegram_token: str, notion_token: str, database_id: str, admin_username: str, yandex_token: str,
                 notion_work_note_client: NotionWorkNote):
        """
        Создать бота
        :param telegram_token: токен telegram бота
        :param notion_token: токен для доступа к Notion
        :param database_id: ID таблицы Notion
        """
        # telebot.apihelper.ENABLE_MIDDLEWARE = True
        self.bot = AsyncTeleBot(token=telegram_token)
        # self.bot.setup_middleware(AlbumMiddleware(1))

        self.notion_work_note_client = notion_work_note_client

        # Должно быть самым первым, так как отменяет все процессы при запросе
        @self.bot.message_handler(func=lambda message: message.text == self.cancel_buttons_text)
        async def send_cancel(message: telebot.types.Message):
            self.userStep[message.chat.id] = 0
            await self.bot.send_message(message.chat.id, "Текущая операция отменена", reply_markup=self.start_buttons)

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

            await self.bot.send_message(message.chat.id, "Введите ссылку на материал (или нажмите Пропустить)", reply_markup=self.skip_cancel_buttons)

        @self.bot.message_handler(func=lambda message: message.text == self.commands['add_work_urg_imp'] or message.text == '/add_work_urg_imp')
        async def send_add_work_urgent_important(message: telebot.types.Message):
            self.userStep[message.chat.id] = 20
            await self.bot.send_message(message.chat.id, "Введите заголовок задачи", reply_markup=self.cancel_buttons)

        @self.bot.message_handler(func=lambda message: message.text == self.commands['add_work_urg_unimp'] or message.text == '/add_work_urg_unimp')
        async def send_add_work_urgent_unimportant(message: telebot.types.Message):
            self.userStep[message.chat.id] = 21
            await self.bot.send_message(message.chat.id, "Введите заголовок задачи", reply_markup=self.cancel_buttons)

        @self.bot.message_handler(func=lambda message: message.text == self.commands['add_work_unurg_imp'] or message.text == '/add_work_unurg_imp')
        async def send_add_work_unurgent_important(message: telebot.types.Message):
            self.userStep[message.chat.id] = 22
            await self.bot.send_message(message.chat.id, "Введите заголовок задачи", reply_markup=self.cancel_buttons)

        @self.bot.message_handler(func=lambda message: message.text == self.commands['add_work_unurg_unimp'] or message.text == '/add_work_unurg_unimp')
        async def send_add_work_unurgent_unimportant(message: telebot.types.Message):
            self.userStep[message.chat.id] = 23
            await self.bot.send_message(message.chat.id, "Введите заголовок задачи", reply_markup=self.cancel_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] in [20, 21, 22, 23])
        async def send_work_name(message: telebot.types.Message):
            self.userStep[message.chat.id] += 10

            self.notion_work_note_item[message.chat.id] = NotionWorkNoteItem()
            self.notion_work_note_item[message.chat.id].name = message.text

            await self.bot.send_message(message.chat.id, "Введите описание задачи (можно прикреплять изображения)", reply_markup=self.skip_cancel_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] in [30, 31, 32, 33], content_types=['text', 'photo'])
        async def send_work_description(message: telebot.types.Message):
            if message.text != self.skip_buttons_text:
                if message.photo is not None:
                    file_info = await self.bot.get_file(message.photo[-1].file_id)
                    file = await self.bot.download_file(file_info.file_path)

                    self.notion_work_note_item[message.chat.id].images = []
                    self.notion_work_note_item[message.chat.id].images.append(file)

                    if message.caption:
                        self.notion_work_note_item[message.chat.id].description = message.caption
                else:
                    self.notion_work_note_item[message.chat.id].images = None
                    self.notion_work_note_item[message.chat.id].description = message.text
            else:
                self.notion_work_note_item[message.chat.id].description = None

            match self.userStep[message.chat.id]:
                case 30:
                    self.notion_work_note_item[message.chat.id].is_urgent = True
                    self.notion_work_note_item[message.chat.id].is_important = True
                case 31:
                    self.notion_work_note_item[message.chat.id].is_urgent = True
                    self.notion_work_note_item[message.chat.id].is_important = False
                case 32:
                    self.notion_work_note_item[message.chat.id].is_urgent = False
                    self.notion_work_note_item[message.chat.id].is_important = True
                case 33:
                    self.notion_work_note_item[message.chat.id].is_urgent = False
                    self.notion_work_note_item[message.chat.id].is_important = False

            self.notion_work_note_item[message.chat.id].deadline = None

            # добавление элемента в таблицу Notion
            self.userStep[message.chat.id] = 0
            try:
                await self.notion_work_note_client.add_item_to_notion(self.notion_work_note_item[message.chat.id])
            except APIResponseError as e:
                logging.log(logging.ERROR, e)
                await self.bot.send_message(message.chat.id, "Ошибка добавления элемента в таблицу Notion", reply_markup=self.start_buttons)
            else:
                await self.bot.send_message(message.chat.id, "Задача добавлена в таблицу Notion", reply_markup=self.start_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 1)
        async def send_add_url(message: telebot.types.Message):
            self.userStep[message.chat.id] = 2
            self.notionItem[message.chat.id].url = message.text if message.text != self.skip_buttons_text else None

            await self.bot.send_message(message.chat.id, "Введите название материала", reply_markup=self.cancel_buttons)

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

            await self.bot.send_message(message.chat.id, "Введите описание материала (или нажмите Пропустить)", reply_markup=self.skip_cancel_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 5)
        async def send_add_description(message: telebot.types.Message):
            self.userStep[message.chat.id] = 0
            self.notionItem[message.chat.id].description = message.text if message.text != self.skip_buttons_text else None

            try:
                await self.notionItem[message.chat.id].add_item_to_notion(notion_token, database_id)
            except APIResponseError as e:
                logging.log(logging.ERROR, e)
                await self.bot.send_message(message.chat.id, "Ошибка добавления элемента в таблицу Notion", reply_markup=self.start_buttons)
            else:
                await self.bot.send_message(message.chat.id, "Элемент добавлен в таблицу Notion", reply_markup=self.start_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 11)
        async def send_multiple_links(message: telebot.types.Message):
            self.userStep[message.chat.id] = 10
            if message.text != self.skip_buttons_text and message.text != self.approve_buttons_text:
                self.notionItem[message.chat.id].url = message.text

            await send_forwarded_name_before(message)

        async def send_forwarded_name_before(message: telebot.types.Message):
            status, title, theses = _try_parse_post_theses(self.notionItem[message.chat.id].url)

            title = title.replace('\n', '').strip()

            if status:
                self.notionItem[message.chat.id].description = \
                    self.notionItem[message.chat.id].description + f'\n\n\nОсновные тезисы статьи:\n{theses}'

            if status and title != self.notionItem[message.chat.id].name:
                self.notionItem[message.chat.id].name_variant = title

                text = "Выберите или, при необходимости, исправьте название материала:\n\n" + \
                       f"1) '{self.notionItem[message.chat.id].name}'\n\n" + \
                       f"2) '{self.notionItem[message.chat.id].name_variant}'\n\n"

                variants_buttons = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
                variants_buttons.add('1', '2', self.cancel_buttons_text)

                await self.bot.send_message(message.chat.id, text, reply_markup=variants_buttons)
            else:
                text = "Подтвердите название материала или исправьте, если необходимо:\n\n" + \
                       f"'{self.notionItem[message.chat.id].name}'\n\n"

                await self.bot.send_message(message.chat.id, text, reply_markup=self.approve_cancel_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 10)
        async def send_forwarded_name(message: telebot.types.Message):
            self.userStep[message.chat.id] = 12
            if message.text == '2':
                self.notionItem[message.chat.id].name = self.notionItem[message.chat.id].name_variant
            elif message.text != '1' and message.text != self.approve_buttons_text and message.text != self.skip_buttons_text:
                self.notionItem[message.chat.id].name = message.text

            await self.bot.send_message(message.chat.id, "Введите описание материала (или нажмите Пропустить)", reply_markup=self.skip_cancel_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 12)
        async def send_forwarded_description(message: telebot.types.Message):
            self.userStep[message.chat.id] = 13
            if message.text != self.skip_buttons_text and message.text != self.approve_buttons_text:
                self.notionItem[message.chat.id].description = message.text

            await self.bot.send_message(message.chat.id, "Выберите тип контента", reply_markup=self.content_type_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 13)
        async def send_forwarded_add_content_type(message: telebot.types.Message):
            self.userStep[message.chat.id] = 14

            # валидация
            if self.content_types:
                if not self.content_types.__contains__(message.text):
                    self.userStep[message.chat.id] = 13
                    await self.bot.send_message(message.chat.id,
                                                "Данный тип контента не существует, попробуйте ещё раз",
                                                reply_markup=self.content_type_buttons)
                    return

            self.notionItem[message.chat.id].content_type = message.text

            await self.bot.send_message(message.chat.id, "Выберите категорию", reply_markup=self.category_buttons)

        @self.bot.message_handler(func=lambda message: self.userStep[message.chat.id] == 14)
        async def send_forwarded_add_category(message: telebot.types.Message):
            self.userStep[message.chat.id] = 0

            # валидация
            if self.categories:
                if not self.categories.__contains__(message.text):
                    self.userStep[message.chat.id] = 14
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

        # Должен быть самым последним обработчиком, так как он пытается обработать любое сообщение
        @self.bot.message_handler(content_types=['text', 'photo', 'document', 'animation', 'video'])
        async def forwarded_message(message: telebot.types.Message):
            self.userStep[message.chat.id] = 10
            notion_item, parsing_code = _parse_post(message)

            self.notionItem[message.chat.id] = notion_item

            await _get_variants(message.chat.id)

            if parsing_code == 1:
                self.userStep[message.chat.id] = 11
                await self.bot.send_message(message.chat.id, "Было обнаружено несколько ссылок.\n"
                                                             f"Выбрана: {notion_item.url}\n\n"
                                                             "Подтвердите выбор, или введите свой вариант",
                                            reply_markup=self.approve_cancel_buttons)
            else:
                await send_forwarded_name_before(message)

        def _parse_post(message: telebot.types.Message) -> Tuple[NotionItem, int]:
            """
            Парсер поста с полезной информацией
            :param message: сообщение пользователя
            :return: элемент таблицы Notion и статус код парсинга (0 - успешно, 1 - несколько ссылок)
            """
            text_html = message.html_text if message.html_text else message.html_caption
            text = message.text if message.text else message.caption

            url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
            urls = url_pattern.findall(text_html)

            try_youtube_name = _try_parse_video_link(urls[0] if urls else None)

            item = NotionItem()
            item.url = urls[0] if urls else None

            urls_text = [f'{i + 1}. {x}' for i, x in enumerate(urls)]
            item.description = text + '\n\n\nИспользуемые в материале ссылки:\n' + '\n'.join(urls_text)

            item.name = try_youtube_name if try_youtube_name else _parse_post_name(text)
            item.name = item.name.replace('\n', '')
            item.name = item.name.strip()

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
                    text = re.split('[?.!](?:\s|\n)', text)[0]
            except:
                text = '-'
            else:
                if text is None or len(text) == 0 or text.isspace():
                    text = '-'

            return text

        def _try_parse_video_link(link: str | None) -> str | None:
            """
            Парсер ссылки на видео (youtube)
            :param link: ссылка
            :return: название видео или None, если это не видео
            """
            if link is None:
                return None

            if link.__contains__('youtube') or link.__contains__('youtu.be'):
                r = requests.get(link)
                data = r.text
                soup = BeautifulSoup(data, 'html.parser')
                video_name = str(soup.find('title').text)
                return video_name.replace(' - YouTube', '')

            return None

        def _try_parse_post_theses(link: str) -> Tuple[bool, str, str]:
            """
            Парсер текста поста
            :param link: ссылка на пост
            :return: успешность, заголовок, основные тезисы материала
            """
            endpoint = 'https://300.ya.ru/api/sharing-url'
            response = requests.post(endpoint,
                                     json={'article_url': link},
                                     headers={'Authorization': f'OAuth {yandex_token}'})
            data = response.json()
            status = data['status']
            parsed_url = data['sharing_url'] if status == 'success' else None

            if status == 'success':
                r = requests.get(parsed_url)
                r.encoding = 'utf-8'
                data = r.text
                soup = BeautifulSoup(data, 'html.parser')

                try:
                    title = soup.find('meta', {'property': 'og:title'})
                    title = str(title.get('content')) if title else None
                    title = title.replace(' - Пересказ YandexGPT', '')
                except:
                    return False, '', ''

                theses = soup.find('meta', {'property': 'og:description'})
                theses = str(theses.get('content')) if theses else None

                return True, title, theses
            else:
                return False, '', ''

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
