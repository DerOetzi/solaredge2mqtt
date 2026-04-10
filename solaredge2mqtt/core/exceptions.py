from typing import Any


class ConfigurationException(Exception):
    def __init__(self, component: str, message: str, *args: Any) -> None:
        self.component = component
        self.message = message
        super().__init__(message, *args)


class InvalidDataException(Exception):
    def __init__(self, message: str, *args: Any) -> None:
        self.message = message

        super().__init__(message, *args)
