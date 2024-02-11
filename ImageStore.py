import base64
from datetime import datetime

from imagekitio import ImageKit
from imagekitio.models.ListAndSearchFileRequestOptions import ListAndSearchFileRequestOptions
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
from imagekitio.models.results.UploadFileResult import UploadFileResult


class ImageStore:

    _image_kit: ImageKit | None
    """
    Клиент для сохранения изображений
    """

    def __init__(self, privateKey: str, publicKey: str, urlEndpoint: str):
        """
        Конструктор
        :param privateKey: приватный ключ
        :param publicKey: публичный ключ
        :param urlEndpoint: адрес
        """
        self._image_kit = None
        self._get_image_kit(privateKey, publicKey, urlEndpoint)

    def _get_image_kit(self, privateKey: str, publicKey: str, urlEndpoint: str) -> ImageKit:
        """
        Возвращает клиент для сохранения изображений
        :param privateKey: приватный ключ
        :param publicKey: публичный ключ
        :param urlEndpoint: адрес
        :return: клиент для сохранения изображений
        """
        if self._image_kit is None:
            self._image_kit = ImageKit(
                public_key=publicKey,
                private_key=privateKey,
                url_endpoint=urlEndpoint
            )
        return self._image_kit

    def upload_images(self, images: list[bytes]) -> list[str]:
        """
        Загружает все изображения
        :param images: список изображений
        :return: список ссылок на изображения
        """
        options = UploadFileRequestOptions(
            use_unique_file_name=True,
            tags=["image"],
            is_private_file=False
        )

        results: list[UploadFileResult] = []

        for image in images:
            encoded_file = base64.b64encode(image)

            results.append(self._image_kit.upload_file(
                file=encoded_file,
                file_name=self._generate_file_name(),
                options=options
            ))

        return list(map(lambda x: x.url, results))

    def delete_outdated_images(self) -> None:
        """
        Удаляет старые изображения
        """
        try:
            options = ListAndSearchFileRequestOptions(
                type='file',
                sort='ASC_CREATED',
                search_query="created_at >= '90d'",
                file_type='all',
            )
            find_result = self._image_kit.list_files(options)

            deleting_ids = [x.file_id for x in find_result.list]

            self._image_kit.bulk_file_delete(deleting_ids)
        except Exception as e:
            print('Delete outdated images error (maybe not found)', e)

    @staticmethod
    def _generate_file_name() -> str:
        """
        Генерирует имя для изображения
        :return: имя для изображения
        """
        file_name = "image_" + datetime.now().strftime('%Y_%m_%d_%H_%M_%S') + ".jpg"

        return file_name
