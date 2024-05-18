from pydantic import BaseModel, Field, SecretStr


class MQTTSettings(BaseModel):
    client_id: str = Field("solaredge2mqtt")
    broker: str
    port: int = Field(1883)
    username: str
    password: SecretStr
    topic_prefix: str = Field("solaredge")
