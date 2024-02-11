from typing import Union, List, Tuple

from notion_client import APIResponseError
from notion_client import AsyncClient

from ImageStore import ImageStore


class NotionWorkNoteItem:
    """
    Структура рабочей заметки в Notion
    """

    name: str
    """Заголовок задачи"""

    description: Union[str, None]
    """Описание задачи"""

    images: Union[List[bytes], None]
    """Прикрепленные изображения"""

    is_urgent: bool
    """Срочность задачи"""

    is_important: bool
    """Важность задачи"""

    deadline: Union[str, None]
    """Крайний срок выполнения задачи (в формате ISO 8601, пока не используется)"""


class NotionWorkNote:
    """
    Рабочая заметка в Notion
    """

    _image_store: ImageStore

    _notion_client: AsyncClient | None
    """Клиент Notion"""

    _notion_token: str
    """Токен для доступа к Notion"""

    _database_id: str
    """Идентификатор базы данных Notion"""

    def __init__(self, notion_token: str, database_id: str, image_store: ImageStore):
        """
        Конструктор
        :param notion_token: токен для доступа к Notion
        """
        self._notion_client = None
        self._notion_token = notion_token
        self._database_id = database_id
        self._get_notion_client(notion_token)
        self._image_store = image_store

    def _get_notion_client(self, notion_token: str) -> AsyncClient:
        """
        Получить клиент Notion
        :param notion_token: токен для доступа к Notion
        :return: клиент Notion
        """
        if self._notion_client is None:
            self._notion_client = AsyncClient(auth=notion_token)
        return self._notion_client

    async def add_item_to_notion(self, item: NotionWorkNoteItem) -> None:
        """
        Добавить запись в базу данных Notion
        :param item: структура задачи
        :return: none
        """
        try:
            children = []

            if item.images is not None:
                images = self._get_images(item.images)
                if images is not None:
                    children.extend(images)

            if item.description is not None:
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": item.description
                                }
                            }
                        ],
                        "color": "default"
                    }
                })

            await self._notion_client.pages.create(
                parent={
                    "type": "database_id",
                    "database_id": self._database_id
                },
                icon={
                    "type": "emoji",
                    "emoji": "⚪"
                },
                properties={
                    "Task": {
                        "title": [
                            {
                                "text": {
                                    "content": item.name
                                }
                            }
                        ]
                    },
                    "Urgent": {
                        "checkbox": item.is_urgent
                    },
                    "Important": {
                        "checkbox": item.is_important
                    },
                    "Done": {
                        "checkbox": False
                    }
                },
                children=children
            )
        except APIResponseError as e:
            print("Notion work note add item error", e)
            raise e

    def _get_images(self, images: List[bytes] | None) -> List[dict] | None:
        """
        Получить изображения в формате Notion
        :param images: изображения
        :return: изображения в формате Notion
        """
        links = self._upload_images(images)
        if links is not None:
            return [
                {
                    "object": "block",
                    "type": "image",
                    "image": {
                        "type": "external",
                        "external": {
                            "url": link
                        }
                    }
                }
                for link in links
            ]
        else:
            return None

    def _upload_images(self, images: List[bytes] | None) -> List[str] | None:
        """
        Добавить изображения
        :param images: список изображений
        :return: none
        """
        if images is not None:
            try:
                return self._image_store.upload_images(images)
            except Exception as e:
                print("Notion work note upload images error", e)
                return None
        else:
            return None
