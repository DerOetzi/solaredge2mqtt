import "date"
import "math"

startTime = date.add(to: date.truncate(t: now(), unit: 1y), d: 13d)
stopTime = date.truncate(t: now(), unit: 1h)

battery =
    from(bucket: "solaredge")
        |> range(start: startTime, stop: stopTime)
        |> filter(fn: (r) => r._measurement == "battery")

battery
    |> filter(fn: (r) => r.agg_type == "min")
    |> aggregateWindow(every: 1h, fn: min, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: "solaredgenew")

battery
    |> filter(fn: (r) => r.agg_type == "mean")
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: "solaredgenew")

battery
    |> filter(fn: (r) => r.agg_type == "max")
    |> aggregateWindow(every: 1h, fn: max, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: "solaredgenew")

from(bucket: "solaredge")
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r._measurement == "energy")
    |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: "solaredgenew")

training =
    from(bucket: "solaredge")
        |> range(start: startTime, stop: stopTime)
        |> filter(fn: (r) => r._measurement == "forecast_training")

training
    |> filter(fn: (r) => r._field == "energy")
    |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.sub(from: r._time, d: 1h)}))
    |> map(fn: (r) => ({r with _value: math.round(x: r._value * 100.0) / 100.0}))
    |> to(bucket: "solaredgenew")

training
    |> filter(fn: (r) => r._field == "power")
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.sub(from: r._time, d: 1h)}))
    |> map(fn: (r) => ({r with _value: int(v: math.round(x: r._value))}))
    |> to(bucket: "solaredgenew")

training
    |> filter(fn: (r) => r._field == "sun_altitude" or r._field == "sun_azimuth")
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.sub(from: r._time, d: 1h)}))
    |> map(fn: (r) => ({r with _value: math.round(x: r._value * 100.0) / 100.0}))
    |> to(bucket: "solaredgenew")

training
    |> filter(
        fn: (r) =>
            r._field != "power" and r._field != "energy" and r._field != "sun_altitude" and r._field != "sun_azimuth",
    )
    |> aggregateWindow(every: 1h, fn: first, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.sub(from: r._time, d: 1h)}))
    |> to(bucket: "solaredgenew")

money =
    from(bucket: "solaredge")
        |> range(start: startTime, stop: stopTime)
        |> filter(fn: (r) => r._measurement == "money")

money
    |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
    |> map(fn: (r) => ({r with _field: if r._field == "earnings" then "money_earnings" else "money_savings"}))
    |> set(key: "_measurement", value: "energy")
    |> to(bucket: "solaredgenew")

prices =
    from(bucket: "solaredge")
        |> range(start: startTime, stop: stopTime)
        |> filter(fn: (r) => r._measurement == "prices")

prices
    |> aggregateWindow(every: 1h, fn: last, createEmpty: false)
    |> map(fn: (r) => ({r with _field: if r._field == "consumption" then "money_price_in" else "money_price_out"}))
    |> set(key: "_measurement", value: "energy")
    |> to(bucket: "solaredgenew")

powerflow =
    from(bucket: "solaredge")
        |> range(start: startTime, stop: stopTime)
        |> filter(fn: (r) => r._measurement == "powerflow")

powerflow
    |> filter(fn: (r) => r.agg_type == "min")
    |> aggregateWindow(every: 1h, fn: min, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: "solaredgenew")

powerflow
    |> filter(fn: (r) => r.agg_type == "mean")
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: "solaredgenew")

powerflow
    |> filter(fn: (r) => r.agg_type == "max")
    |> aggregateWindow(every: 1h, fn: max, createEmpty: false)
    |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
    |> to(bucket: "solaredgenew")