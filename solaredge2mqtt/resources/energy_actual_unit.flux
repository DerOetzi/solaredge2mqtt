import "date"

startTime = date.truncate(t: now(), unit: UNIT)

bucket = if "UNIT" == "1h" then "BUCKET_RAW" else "BUCKET_AGGREGATED"

from(bucket: bucket)
    |> range(start: startTime)
    |> filter(fn: (r) => r._measurement == "energy")
    |> sum()
    |> pivot(rowKey: ["_start"], columnKey: ["_field"], valueColumn: "_value")