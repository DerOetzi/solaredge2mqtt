from pydantic import BaseModel, Field, SecretStr


class MQTTSettings(BaseModel):
    client_id: str = Field("solaredge2mqtt")
    broker: str
    port: int = Field(1883)
    username: str | None = Field(None)
    password: SecretStr | None = Field(None)
    topic_prefix: str = Field("solaredge")

    @property
    def kargs(self) -> dict[str, str]:
        args = {"identifier": self.client_id}

        if self.username is not None:
            args["username"] = self.username
        if self.password is not None:
            args["password"] = self.password.get_secret_value()

        return args
