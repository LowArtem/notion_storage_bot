from typing import Union, List, Tuple

from notion_client import APIResponseError
from notion_client import AsyncClient

from ImageStore import ImageStore


class NotionWorkNote:
    """
    Рабочая заметка в Notion
    """

    _image_store: ImageStore

    _notion_client: AsyncClient
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

    async def add_item_to_notion(self, is_urgent: bool, is_important: bool, deadline: Union[str, None], name: str, description: Union[str, None],
                                 images: Union[List[bytes], None]) -> None:
        """
        Добавить запись в базу данных Notion
        :param is_urgent: срочность задачи
        :param is_important: важность задачи
        :param deadline: крайний срок выполнения задачи
        :param name: название задачи
        :param description: описание задачи
        :param images: прикрепленные изображения
        :return: none
        """
        try:
            children = []

            if images is not None:
                children.extend(self._get_images(images))

            if description is not None:
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": description
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
                properties={
                    "Task": {
                        "title": [
                            {
                                "text": {
                                    "content": name
                                }
                            }
                        ]
                    },
                    "Urgent": {
                        "checkbox": is_urgent
                    },
                    "Important": {
                        "checkbox": is_important
                    },
                    "Done": {
                        "checkbox": False
                    },
                    "Deadline": {
                        "date": {
                            "start": deadline if deadline is not None else ""
                        }
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
