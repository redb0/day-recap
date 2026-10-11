"""Файлы, которые входят в пакет `app`."""

from importlib.resources import files


class PackageAssetError(Exception):
    """В пакете нет файла, который команда должна скопировать.

    Печатается без машинного кода: это дыра поставки, не статус источника.

    Attributes:
        message: Что случилось.
        hint: Что сделать человеку.
    """

    def __init__(self, message: str, hint: str) -> None:
        """Запомнить сообщение и подсказку.

        Args:
            message: Что случилось.
            hint: Что сделать человеку.
        """
        self.message = message
        self.hint = hint
        super().__init__(message)


def read_package_text(name: str, message: str, hint: str) -> str:
    """Прочитать файл из пакета `app`.

    Args:
        name: Имя файла в пакете.
        message: Текст, если файла нет.
        hint: Что сделать человеку.

    Returns:
        Содержимое в UTF-8.

    Raises:
        PackageAssetError: Файла нет в поставке.
    """
    resource = files("app").joinpath(name)
    if not resource.is_file():
        raise PackageAssetError(message, hint)
    return resource.read_text(encoding="utf-8")
