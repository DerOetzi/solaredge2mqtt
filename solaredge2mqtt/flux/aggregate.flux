import "date"

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
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: bucket)

power
    |> aggregateWindow(every: 1h, fn: min, createEmpty: false)
    |> set(key: "agg_type", value: "min")
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: bucket)

power
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    |> set(key: "agg_type", value: "mean")
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: bucket)

energy = power
    |> aggregateWindow(
        every: 1h,
        fn: (tables=<-, column) =>
            tables
                |> integral(unit: 1h)
                |> map(fn: (r) => ({r with _value: r._value / 1000.0})),
    )
    |> set(key: "_measurement", value: "energy")
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: bucket)

energy
    |> filter(fn: (r) => r._field == "consumer_used_production")
    |> map(fn: (r) => ({r with _value: r._value * {{PRICE_IN}}}))
    |> set(key: "_field", value: "money_saved")
    |> to(bucket: bucket)
    |> map(fn: (r) => ({r with _value: {{PRICE_IN}}}))
    |> set(key: "_field", value: "money_price_in")
    |> to(bucket: bucket)

energy
    |> filter(fn: (r) => r._field == "grid_delivery")
    |> map(fn: (r) => ({r with _value: r._value * {{PRICE_OUT}}}))
    |> set(key: "_field", value: "money_delivered")
    |> to(bucket: bucket)
    |> map(fn: (r) => ({r with _value: {{PRICE_OUT}}}))
    |> set(key: "_field", value: "money_price_out")
    |> to(bucket: bucket)

energy
    |> filter(fn: (r) => r._field == "grid_consumption")
    |> map(fn: (r) => ({r with _value: r._value * {{PRICE_IN}}}))
    |> set(key: "_field", value: "money_consumed")
    |> to(bucket: bucket)



battery =
    from(bucket: bucket)
        |> range(start: startTime)
        |> filter(fn: (r) => r._measurement == "battery_raw")
        |> set(key: "_measurement", value: "battery")

battery
    |> aggregateWindow(every: 1h, fn: max, createEmpty: false)
    |> set(key: "agg_type", value: "max")
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: bucket)

battery
    |> aggregateWindow(every: 1h, fn: min, createEmpty: false)
    |> set(key: "agg_type", value: "min")
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: bucket)

battery
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    |> set(key: "agg_type", value: "mean")
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: bucket)