import asyncio
from datetime import timezone
from pandas import read_csv, to_datetime

from solaredge2mqtt.models import (
    BatteryPowerflow,
    ConsumerPowerflow,
    GridPowerflow,
    InverterPowerflow,
    Powerflow,
)
from solaredge2mqtt.service.influxdb import InfluxDB, Point
from solaredge2mqtt.settings import LOCAL_TZ, service_settings

settings = service_settings()
STRINGS = 2


async def main():
    data = read_csv("data.csv")
    data["time"] = to_datetime(data["time"], format="%d.%m.%Y %H:%M").dt.tz_localize(
        LOCAL_TZ
    )

    for i in range(1, STRINGS + 1):
        data[f"string{i}"] = data[f"string{i}"].fillna(0)

    data["evcharger"] = data["evcharger"].fillna(0)

    data.info()

    points = []

    columns = data.columns.to_list()

    for _, row in data.iterrows():

        grid = GridPowerflow(
            power=round(row["grid_delivery"] - row["grid_consumption"])
        )

        if "battery_charge" in columns and "battery_discharge" in columns:
            battery = BatteryPowerflow(
                power=round(row["battery_charge"] - row["battery_discharge"])
            )
        else:
            battery = BatteryPowerflow(power=0)

        pv_production = 0.0
        for i in range(1, STRINGS + 1):
            pv_production += row[f"string{i}"]

        dc_power = pv_production - battery.power

        inverter = InverterPowerflow(
            power=round(row["inverter_production"]),
            dc_power=round(dc_power),
            battery_discharge=battery.discharge,
        )

        if "evcharger" in columns:
            evcharger = round(row["evcharger"])
        else:
            evcharger = 0

        consumer = ConsumerPowerflow(inverter=inverter, grid=grid, evcharger=evcharger)

        pv_production = round(pv_production)

        powerflow = Powerflow(
            pv_production=pv_production,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        print(
            f"Time: {row['time']}, PV: {pv_production} W, Inverter: {inverter.power} W, "
            + f"House: {consumer.house} W, Grid: {grid.power} W, "
            + f"Battery: {battery.power} W, Wallbox: {consumer.evcharger} W"
        )

        point = powerflow.prepare_point("powerflow_import")
        point.tag("agg_type", "mean")
        point.time(row["time"].astimezone(timezone.utc))
        points.append(point)

        point = powerflow.prepare_point_energy("energy_import", settings.prices)
        point.time(row["time"].astimezone(timezone.utc))
        points.append(point)

        if "battery_soc" in columns:
            point = Point("battery_import")
            point.field("state_of_charge", round(row["battery_soc"], 2))
            point.time(row["time"].astimezone(timezone.utc))
            point.tag("agg_type", "mean")
            points.append(point)

    influxdb = InfluxDB(settings.influxdb, settings.prices)
    await influxdb.write_points_async(points)


if __name__ == "__main__":
    asyncio.run(main())
