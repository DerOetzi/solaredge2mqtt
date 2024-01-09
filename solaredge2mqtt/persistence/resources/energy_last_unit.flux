import "date"
import "timezone"

option location = timezone.location(name: "TIMEZONE")

stopTime = date.truncate(t: now(), unit: UNIT)
startTime = date.sub(from: stopTime, d: UNIT)

from(bucket: "BUCKET_AGGREGATED")
 |> range(start: startTime, stop: stopTime)
 |> filter(fn: (r) => r._measurement == "energy")
 |> sum()
 |> pivot(rowKey: ["_measurement"], columnKey: ["_field"], valueColumn: "_value")
