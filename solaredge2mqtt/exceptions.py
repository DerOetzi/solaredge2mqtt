class ConfigurationException(Exception):
    def __init__(self, component: str, message: str, *args: any) -> None:
        self.component = component
        self.message = message
        super().__init__(*args)


class InvalidDataException(Exception):
    def __init__(self, message: str, *args: any) -> None:
        self.message = message

        super().__init__(*args)
