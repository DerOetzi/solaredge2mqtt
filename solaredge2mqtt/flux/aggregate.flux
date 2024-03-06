import "date"

// Definieren der Start- und Stoppzeit
stopTime = date.truncate(t: now(), unit: 1h)
startTime = date.sub(from: stopTime, d: 2h)

bucket = "{{BUCKET_NAME}}"

exclude = ["inverter_power", "grid_power", "battery_power"]

power =
    from(bucket: bucket)
        |> range(start: startTime)
        |> filter(fn: (r) => r._measurement == "powerflow_raw")
        |> filter(fn: (r) => not contains(value: r._field, set: exclude))
        |> set(key: "_measurement", value: "powerflow")

power
    |> aggregateWindow(every: 1h, fn: max, createEmpty: false)
    |> set(key: "agg_type", value: "max")
    |> to(bucket: bucket)

power
    |> aggregateWindow(every: 1h, fn: min, createEmpty: false)
    |> set(key: "agg_type", value: "min")
    |> to(bucket: bucket)

power
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    |> set(key: "agg_type", value: "mean")
    |> to(bucket: bucket)

needed = ["pv_production", "consumer_used_production", "grid_delivery"]

power
    |> aggregateWindow(
        every: 1h,
        fn: (tables=<-, column) =>
            tables
                |> integral(unit: 1h)
                |> map(fn: (r) => ({r with _value: r._value / 1000.0})),
    )
    |> set(key: "_measurement", value: "energy")
    |> to(bucket: bucket)

battery =
    from(bucket: bucket)
        |> range(start: startTime)
        |> filter(fn: (r) => r._measurement == "battery_raw")
        |> set(key: "_measurement", value: "battery")

battery
    |> aggregateWindow(every: 1h, fn: max, createEmpty: false)
    |> set(key: "agg_type", value: "max")
    |> to(bucket: bucket)

battery
    |> aggregateWindow(every: 1h, fn: min, createEmpty: false)
    |> set(key: "agg_type", value: "min")
    |> to(bucket: bucket)

battery
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    |> set(key: "agg_type", value: "mean")
    |> to(bucket: bucket)