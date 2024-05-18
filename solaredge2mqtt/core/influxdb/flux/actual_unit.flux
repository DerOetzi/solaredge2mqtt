import "date"
import "timezone"
import "experimental/date/boundaries"

option location = timezone.location(name: "{{TIMEZONE}}")

week = boundaries.week()

startTime = if "{{UNIT}}" == "1w" then week.start else date.truncate(t: now(), unit: {{UNIT}})
stopTime = if "{{UNIT}}" == "1w" then week.stop else date.add(to: startTime, d: {{UNIT}})

from(bucket: "{{BUCKET_NAME}}")
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r._measurement == "{{MEASUREMENT}}")
    |> sum()
    |> pivot(rowKey: ["_measurement"], columnKey: ["_field"], valueColumn: "_value")