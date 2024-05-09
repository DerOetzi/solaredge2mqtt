import "date"

startTime = date.sub(from: date.truncate(t: now(), unit: 1y), d: 1y)
stopTime = date.add(to: date.truncate(t: now(), unit: 1h), d: 1d)

bucket = "solaredgedev"
price_in = 0.3644

from(bucket: bucket)
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r["_measurement"] == "energy")
    |> filter(fn: (r) => r["_field"] == "money_earnings")
    |> set(key: "_field", value: "money_delivered")
    |> to(bucket: bucket)

from(bucket: bucket)
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r["_measurement"] == "energy")
    |> filter(fn: (r) => r["_field"] == "money_savings")
    |> set(key: "_field", value: "money_saved")
    |> to(bucket: bucket)

from(bucket: bucket)
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r["_measurement"] == "energy")
    |> filter(fn: (r) => r["_field"] == "grid_consumption")
    |> map(fn: (r) => ({r with _value: r._value * price_in}))
    |> set(key: "_field", value: "money_consumed")
    |> to(bucket: bucket)