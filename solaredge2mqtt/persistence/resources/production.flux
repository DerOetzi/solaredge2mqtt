import "date"
import "timezone"

option location = timezone.location(name: "{{TIMEZONE}}")

stopTime = date.truncate(t: now(), unit: 10m)
startTime = date.sub(from: stopTime, d: 10m)

power =
    from(bucket: "{{BUCKET_RAW}}")
        |> range(start: startTime, stop: stopTime)
        |> filter(fn: (r) => r._measurement == "powerflow")
        |> filter(fn: (r) => r._field == "pv_production")

energy =
    power
        |> aggregateWindow(
            every: 10m,
            fn: (tables=<-, column) =>
                tables
                    |> integral(unit: 1h)
                    |> map(fn: (r) => ({r with _value: r._value})),
        )

mean_power =
    power
        |> aggregateWindow(every: 10m, fn: mean)
        |> map(fn: (r) => ({r with _value: r._value}))

join(tables: {t1: energy, t2: mean_power}, on: ["_time"])
    |> map(fn: (r) => ({_time: r._time, energy: r._value_t1, power: r._value_t2}))