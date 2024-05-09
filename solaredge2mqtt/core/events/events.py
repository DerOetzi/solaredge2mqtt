class BaseEvent:
    AWAIT = False

    @classmethod
    def event_key(cls) -> str:
        return cls.__name__.lower()
