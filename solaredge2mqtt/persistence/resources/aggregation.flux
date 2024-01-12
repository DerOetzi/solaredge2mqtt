import "date"

option task = {name: "TASK_NAME", every: UNIT}

// Historical data
fullUnitTime = date.truncate(t: now(), unit: UNIT)
startTime = date.sub(from: fullUnitTime, d: UNIT)
stopTime = fullUnitTime

data =
    from(bucket: "BUCKET_RAW")
        |> range(start: startTime, stop: stopTime)
        |> filter(fn: (r) => r._measurement == "powerflow")
        |> keep(
            columns: [
                "_measurement",
                "_field",
                "_value",
                "_start",
                "_stop",
                "_time",
            ],
        )

data
    |> aggregateWindow(every: UNIT, fn: mean, createEmpty: false)
    |> set(key: "agg_type", value: "mean")
    |> to(bucket: "BUCKET_AGGREGATED")

data
    |> aggregateWindow(every: UNIT, fn: max, createEmpty: false)
    |> set(key: "agg_type", value: "max")
    |> to(bucket: "BUCKET_AGGREGATED")

data
    |> aggregateWindow(every: UNIT, fn: min, createEmpty: false)
    |> set(key: "agg_type", value: "min")
    |> to(bucket: "BUCKET_AGGREGATED")

exclude_fields = ["battery_power", "grid_power", "inverter_power"]

data
    |> filter(fn: (r) => contains(value: r._field, set: exclude_fields) == false)
    |> aggregateWindow(
        every: UNIT,
        fn: (tables=<-, column) =>
            tables
                |> integral(unit: 1h)
                |> map(fn: (r) => ({r with _value: r._value / 1000.0})),
    )
    |> keep(
        columns: [
            "_measurement",
            "_field",
            "_value",
            "_start",
            "_stop",
            "_time",
        ],
    )
    |> set(key: "_measurement", value: "energy")
    |> to(bucket: "BUCKET_AGGREGATED")

batteryfields = ["current", "state_of_charge", "state_of_health", "voltage"]

//battery data
dataBattery =
    from(bucket: "BUCKET_RAW")
        |> range(start: startTime, stop: stopTime)
        |> filter(fn: (r) => r._measurement == "component")
        |> filter(fn: (r) => r.component == "battery")
        |> filter(fn: (r) => contains(value: r._field, set: batteryfields))
        |> set(key: "_measurement", value: "battery")
        |> keep(
            columns: [
                "_measurement",
                "_field",
                "_value",
                "_start",
                "_stop",
                "_time",
            ],
        )

dataBattery
    |> aggregateWindow(every: UNIT, fn: mean, createEmpty: false)
    |> set(key: "agg_type", value: "mean")
    |> to(bucket: "BUCKET_AGGREGATED")

dataBattery
    |> aggregateWindow(every: UNIT, fn: max, createEmpty: false)
    |> set(key: "agg_type", value: "max")
    |> to(bucket: "BUCKET_AGGREGATED")

dataBattery
    |> aggregateWindow(every: UNIT, fn: min, createEmpty: false)
    |> set(key: "agg_type", value: "min")
    |> to(bucket: "BUCKET_AGGREGATED")