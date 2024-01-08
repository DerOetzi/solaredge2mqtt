import "date"

fullTime = date.truncate(t: now(), unit: UNIT)
startTime = date.sub(from: fullTime, d: UNIT)
stopTime = date.sub(from: fullTime, d: 1s)

bucket = if "UNIT" == "1h" then "BUCKET_RAW" else "BUCKET_AGGREGATEDW"

from(bucket: bucket)
 |> range(start: startTime, stop: stopTime)
 |> filter(fn: (r) => r._measurement == "energy")
 |> sum()
 |> pivot(rowKey: ["_start"], columnKey: ["_field"], valueColumn: "_value")

