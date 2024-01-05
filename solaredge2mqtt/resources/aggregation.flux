import "date"

option task = {name: "TASK_NAME", every: 1m}

// energy actual hour so far
from(bucket: "BUCKET_RAW")
    |> range(start: -task.every)
    |> filter(fn: (r) => r._measurement == "powerflow")
    |> aggregateWindow(
        every: 1m,
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
    |> to(bucket: "BUCKET_RAW")

// Historical data
fullHourTime = date.truncate(t: now(), unit: 1h)
startTime = date.sub(from: fullHourTime, d: 1h)
stopTime = date.sub(from: fullHourTime, d: 1s)

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
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    |> set(key: "agg_type", value: "mean")
    |> to(bucket: "BUCKET_AGGREGATED")

data
    |> aggregateWindow(every: 1h, fn: max, createEmpty: false)
    |> set(key: "agg_type", value: "max")
    |> to(bucket: "BUCKET_AGGREGATED")

data
    |> aggregateWindow(every: 1h, fn: min, createEmpty: false)
    |> set(key: "agg_type", value: "min")
    |> to(bucket: "BUCKET_AGGREGATED")

data
    |> aggregateWindow(
        every: 1h,
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