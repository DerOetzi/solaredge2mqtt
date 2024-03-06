import "date"
import "timezone"
import "experimental/date/boundaries"

option location = timezone.location(name: "{{TIMEZONE}}")

week = boundaries.week(week_offset: 1)

startTime = if "{{UNIT}}" == "1w" then week.start else date.add(to: date.truncate(t: now(), unit: {{UNIT}}), d: {{UNIT}})
stopTime = if "{{UNIT}}" == "1w" then week.stop else date.add(to: startTime, d: {{UNIT}})

from(bucket: "{{BUCKET_NAME}}")
    |> range(start: startTime, stop: stopTime)
    |> filter(fn: (r) => r._measurement == "{{MEASUREMENT}}")
    |> sum()
    |> pivot(rowKey: ["_measurement"], columnKey: ["_field"], valueColumn: "_value")