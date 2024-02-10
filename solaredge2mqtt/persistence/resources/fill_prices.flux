bucket = "solaredgedev"

data =
    from(bucket: bucket)
        |> range(start: 2000-01-01T00:00:00Z, stop: now())
        |> filter(fn: (r) => r["_measurement"] == "energy")
        |> filter(fn: (r) => r["_field"] == "pv_production")

data
    |> map(fn: (r) => ({_time: r._time, _field: "consumption", _value: 0.3644, _measurement: "prices"}))
    |> to(bucket: bucket)

data
    |> map(fn: (r) => ({_time: r._time, _field: "delivery", _value: 0.082, _measurement: "prices"}))
    |> to(bucket: bucket)