from solaredge2mqtt.models.base import Component


class WallboxAPI(Component):
    COMPONENT = "wallbox"
    SOURCE = "api"

    power: float
    state: str
    vehicle_plugged: bool
    max_current: float

    def __init__(self, data: dict[str, str | int]):
        power = round(data["meter"]["totalActivePower"] / 1000)
        state = data["state"]
        vehicle_connected = bool(data["vehiclePlugged"])
        max_current = float(data["maxCurrent"])

        super().__init__(
            power=power,
            state=state,
            vehicle_plugged=vehicle_connected,
            max_current=max_current,
        )
