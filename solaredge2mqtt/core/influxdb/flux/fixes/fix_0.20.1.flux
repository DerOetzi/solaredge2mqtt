import "date"

startTime = date.add(to: date.truncate(t: now(), unit: 1y), d: 13d)
stopTime = date.add(to: date.truncate(t: now(), unit: 1h), d: 1d)

bucket = "solaredgenew"
price_in = 0.3644
price_out = 0.082

from(bucket: bucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "energy" or r["_measurement"] == "powerflow")
  |> map(fn: (r) => ({r with _time: date.truncate(t: date.sub(from: r._time, d: 1s), unit: 1h)}))
  |> to(bucket: bucket)


energy = from(bucket: bucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "energy")

energy
    |> filter(fn: (r) => r._field == "consumer_used_production")
    |> map(fn: (r) => ({r with _value: r._value * price_in}))
    |> set(key: "_field", value: "money_savings")
    |> to(bucket: bucket)
    |> map(fn: (r) => ({r with _value: price_in}))
    |> set(key: "_field", value: "money_price_in")
    |> to(bucket: bucket)

energy
    |> filter(fn: (r) => r._field == "grid_delivery")
    |> map(fn: (r) => ({r with _value: r._value * price_out}))
    |> set(key: "_field", value: "money_earnings")
    |> to(bucket: bucket)
    |> map(fn: (r) => ({r with _value: price_out}))
    |> set(key: "_field", value: "money_price_out")
    |> to(bucket: bucket)