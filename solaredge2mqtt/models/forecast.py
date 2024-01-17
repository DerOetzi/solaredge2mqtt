from solaredge2mqtt.models.base import Solaredge2MQTTBaseModel, EnumModel


class ForecastAccount(EnumModel):
    PUBLIC = "Public", 1
    PERSONAL = "Personal", 1
    PERSONAL_PLUS = "Personal Plus", 2
    PROFESSSIONAL = "Professional", 3
    PROFESSSIONAL_PLUS = "Professional Plus", 4

    def __init__(self, account_name: str, allowed_strings: int) -> None:
        self._account_name = account_name
        self._allowed_strings = allowed_strings

    @property
    def account_name(self) -> str:
        return self.account_name

    @property
    def allowed_strings(self) -> int:
        return self._allowed_strings


class ForecastAPIKeyInfo(Solaredge2MQTTBaseModel):
    account: ForecastAccount = ForecastAccount.PUBLIC

    model_config = {"extra": "ignore"}


class Forecast(Solaredge2MQTTBaseModel):
    watts: dict[str, int]
    watt_hours_period: dict[str, int]
    watt_hours: dict[str, int]
    watt_hours_day: dict[str, int]
