import "date"


startTime = date.sub(from: date.truncate(t: now(), unit: 1y), d: 1y)
stopTime = date.add(to: date.truncate(t: now(), unit: 1h), d: 1d)

bucket = "solaredgedev"

from(bucket: bucket)
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r["_measurement"] == "powerflow")
    |> set(key: "_measurement", value: "powerflow_import")
    |> to(bucket: bucket)

from(bucket: bucket)
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r["_measurement"] == "energy")
    |> set(key: "_measurement", value: "energy_import")
    |> to(bucket: bucket)

from(bucket: bucket)
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r["_measurement"] == "battery")
    |> set(key: "_measurement", value: "battery_import")
    |> to(bucket: bucket)

exclude = ["inverter_power", "grid_power", "battery_power"]

from(bucket: bucket)
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r["_measurement"] == "powerflow_import")
    |> filter(fn: (r) => not contains(value: r._field, set: exclude))
    |> set(key: "_measurement", value: "powerflow")
    |> to(bucket: bucket)

from(bucket: bucket)
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r["_measurement"] == "energy_import")
    |> filter(fn: (r) => not contains(value: r._field, set: exclude))
    |> set(key: "_measurement", value: "energy")
    |> to(bucket: bucket)

from(bucket: bucket)
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r["_measurement"] == "battery_import")
    |> set(key: "_measurement", value: "battery")
    |> to(bucket: bucket)