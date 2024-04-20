import "date"
import "timezone"

option location = timezone.location(name: "Europe/Berlin")

startTime = date.truncate(t: now(), unit: 1d)
stopTime = date.add(to: startTime, d: 2d)

from(bucket: "{{BUCKET_NAME}}")
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r._measurement == "forecast")
    |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")