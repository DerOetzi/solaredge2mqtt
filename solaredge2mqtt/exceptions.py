from typing import Any


class ConfigurationException(Exception):
    def __init__(self, message: str, *args: Any) -> None:
        self.message = message
        super().__init__(*args)


class InvalidDataException(Exception):
    def __init__(self, message: str, *args: Any) -> Any:
        self.message = message

        super().__init__(*args)
