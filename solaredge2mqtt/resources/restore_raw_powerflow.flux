import "date"
import "math"

pv_production = (ac_power, dc_power, battery_power) => {
    pv_production_calc =
        if ac_power > 0 then
            math.round(x: dc_power + battery_power)
        else
            0.0

    pv_production =
        if pv_production_calc >= 0 then
            pv_production_calc
        else
            0.0

    return pv_production
}

inverter_battery_production = (production, discharge, dc_power) => {
    battery_factor =
        if production > 0 and discharge > 0 then
            discharge / dc_power
        else
            0.0

    battery_production =
        if battery_factor > 0 then
            math.mMin(x: math.round(x: battery_factor * production), y: production)
        else
            0.0

    return battery_production
}

items = ["power", "ac_power_actual", "dc_power", "power_actual"]

startTime = date.truncate(t: now(), unit: 1d)

data =
    from(bucket: "solaredge_raw")
        |> range(start: startTime)
        |> filter(fn: (r) => r["_measurement"] == "component")
        |> filter(fn: (r) => contains(value: r._field, set: items))
        |> group()
        |> pivot(rowKey: ["_time"], columnKey: ["component", "_field"], valueColumn: "_value")
        |> filter(fn: (r) => exists r.inverter_dc_power and exists r.inverter_ac_power_actual)
        |> map(
            fn: (r) =>
                ({
                    _time: r._time,
                    "inverter_dc_power": math.round(x: r.inverter_dc_power),
                    "inverter_power": math.round(x: r.inverter_ac_power_actual),
                    "battery_power": r.battery_power,
                    "battery_discharge": if r.battery_power < 0 then (-1.0) * r.battery_power else 0.0,
                    "battery_charge": if r.battery_power > 0 then r.battery_power else 0.0,
                    "grid_power": r.meter_power_actual,
                    "grid_consumption":
                        if r.meter_power_actual < 0 then math.round(x: (-1.0) * r.meter_power_actual) else 0.0,
                    "grid_delivery": if r.meter_power_actual > 0 then r.meter_power_actual else 0.0,
                    "inverter_consumption":
                        if r.inverter_ac_power_actual < 0 then
                            math.round(x: (-1.0) * r.inverter_ac_power_actual)
                        else
                            0.0,
                    "inverter_production": if r.inverter_ac_power_actual >= 0 then r.inverter_ac_power_actual else 0.0,
                    "consumer_evcharger": r.wallbox_power,
                }),
        )
        |> map(
            fn: (r) =>
                ({r with inverter_battery_production:
                        inverter_battery_production(
                            production: r.inverter_production,
                            discharge: r.battery_discharge,
                            dc_power: r.inverter_dc_power,
                        ),
                }),
        )
        |> map(
            fn: (r) =>
                ({r with inverter_pv_production:
                        if r.inverter_production > 0 then
                            r.inverter_production - r.inverter_battery_production
                        else
                            r.inverter_production,
                }),
        )
        |> map(
            fn: (r) =>
                ({r with pv_production:
                        pv_production(
                            ac_power: r.inverter_production,
                            dc_power: r.inverter_dc_power,
                            battery_power: r.battery_power,
                        ),
                }),
        )
        |> map(fn: (r) => ({r with consumer_house: math.round(x: math.abs(x: r.grid_power - r.inverter_power))}))
        |> map(
            fn: (r) =>
                ({r with consumer_evcharger:
                        if r.consumer_house > r.consumer_evcharger then r.consumer_evcharger else 0.0,
                }),
        )
        |> map(fn: (r) => ({r with consumer_house: r.consumer_house - r.consumer_evcharger}))
        |> map(fn: (r) => ({r with consumer_inverter: r.inverter_consumption}))
        |> map(fn: (r) => ({r with consumer_total: r.consumer_house + r.consumer_evcharger + r.consumer_inverter}))
        |> map(
            fn: (r) =>
                ({r with consumer_used_pv_production:
                        if r.inverter_pv_production > r.inverter_production - r.grid_delivery then
                            r.inverter_pv_production - r.grid_delivery
                        else
                            r.inverter_pv_production,
                }),
        )
        |> map(
            fn: (r) =>
                ({r with consumer_used_battery_production:
                        if r.inverter_battery_production > r.inverter_production - r.grid_delivery then
                            r.inverter_battery_production - r.grid_delivery
                        else
                            r.inverter_battery_production,
                }),
        )
        |> set(key: "_measurement", value: "powerflow")

data
    |> set(key: "_field", value: "pv_production")
    |> map(fn: (r) => ({r with _value: r.pv_production}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "inverter_power")
    |> map(fn: (r) => ({r with _value: r.inverter_power}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "inverter_consumption")
    |> map(fn: (r) => ({r with _value: r.inverter_consumption}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "inverter_production")
    |> map(fn: (r) => ({r with _value: r.inverter_production}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "inverter_pv_production")
    |> map(fn: (r) => ({r with _value: r.inverter_pv_production}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "inverter_battery_production")
    |> map(fn: (r) => ({r with _value: r.inverter_battery_production}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "battery_power")
    |> map(fn: (r) => ({r with _value: r.battery_power}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "battery_discharge")
    |> map(fn: (r) => ({r with _value: r.battery_discharge}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "battery_charge")
    |> map(fn: (r) => ({r with _value: r.battery_charge}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "grid_power")
    |> map(fn: (r) => ({r with _value: r.grid_power}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "grid_consumption")
    |> map(fn: (r) => ({r with _value: r.grid_consumption}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "grid_delivery")
    |> map(fn: (r) => ({r with _value: r.grid_delivery}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "consumer_house")
    |> map(fn: (r) => ({r with _value: r.consumer_house}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "consumer_evcharger")
    |> map(fn: (r) => ({r with _value: r.consumer_evcharger}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "consumer_inverter")
    |> map(fn: (r) => ({r with _value: r.consumer_inverter}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "consumer_total")
    |> map(fn: (r) => ({r with _value: r.consumer_total}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "consumer_used_pv_production")
    |> map(fn: (r) => ({r with _value: r.consumer_used_pv_production}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")

data
    |> set(key: "_field", value: "consumer_used_battery_production")
    |> map(fn: (r) => ({r with _value: r.consumer_used_battery_production}))
    |> keep(columns: ["_time", "_measurement", "_field", "_value"])
    |> to(bucket: "solaredge_raw")