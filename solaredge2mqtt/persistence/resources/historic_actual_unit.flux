import "date"
import "timezone"

option location = timezone.location(name: "TIMEZONE")

startTime = date.truncate(t: now(), unit: UNIT)
stopTime = now()

from(bucket: "BUCKET_AGGREGATED")
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r._measurement == "MEASUREMENT")
    |> sum()
    |> pivot(rowKey: ["_measurement"], columnKey: ["_field"], valueColumn: "_value")