from typing import Union, List, Tuple

from notion_client import APIResponseError
from notion_client import AsyncClient


class NotionItem:
    """
    Элемент таблицы Notion
    """

    def __int__(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.content_type = kwargs.get('content_type', 'Note')
        self.category = kwargs.get('category', 'Other')
        self.url = kwargs.get('url', None)
        self.description = kwargs.get('description', None)

    name: str
    """
    Название элемента
    """

    name_variant: str
    """
    Другой вариант названия элемента
    """

    content_type: str
    """
    Тип содержания элемента (статья, видео...)
    """

    category: str
    """
    Категория элемента (жизнь, программирование...)
    """

    url: Union[str, None]
    """
    Ссылка на материал (может отсутствовать)
    """

    description: Union[str, None]
    """
    Подробное описание элемента (может отсутствовать)
    """

    _notion_client: AsyncClient | None = None
    """
    Клиент Notion
    """

    def _get_notion_client(self, notion_token: str):
        """
        Получить клиент Notion
        :param notion_token: токен для доступа к Notion
        :return: клиент Notion
        """
        if self._notion_client is None:
            self._notion_client = AsyncClient(auth=notion_token)
        return self._notion_client

    async def add_item_to_notion(self, notion_token: str, database_id: str) -> None:
        """
        Сохраняет элемент в таблицу Notion

        :param database_id: ID таблицы Notion
        :param notion_token: токен для доступа к Notion
        :param item: элемент, который нужно сохранить в таблицу Notion
        :return: none
        :raises APIResponseError: если не удалось обратиться к Notion API
        """
        try:
            notion = self._get_notion_client(notion_token)
            await notion.pages.create(
                parent={
                    "type": "database_id",
                    "database_id": database_id
                },
                properties={
                    "name": {
                        "title": [
                            {
                                "text": {
                                    "content": self.name
                                }
                            }
                        ]
                    },
                    "content_type": {
                        "select": {
                            "name": self.content_type
                        }
                    },
                    "category": {
                        "select": {
                            "name": self.category
                        }
                    },
                    "url": {
                        "url": self.url if self.url else None
                    }
                },
                children=[
                    {
                        "object": "block",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "text": {
                                        "content": self.description if self.description else 'Нет контента'
                                    }
                                }
                            ],
                            "color": "default"
                        }
                    }
                ]
            )
        except APIResponseError as error:
            raise error

    async def get_content_types_and_categories(self, notion_token: str, database_id: str) -> Tuple[List[str], List[str]]:
        """
        Получить списки типов контента и категорий
        :param notion_token: токен для доступа к Notion
        :param database_id: id таблицы
        :return: кортеж с типами контента и категориями
        """
        notion = self._get_notion_client(notion_token)
        db_object = await notion.databases.retrieve(database_id)

        content_types = db_object['properties']['content_type']['select']['options']
        categories = db_object['properties']['category']['select']['options']

        return list(map(lambda x: x['name'], content_types)), list(map(lambda x: x['name'], categories))

