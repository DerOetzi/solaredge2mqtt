from(bucket: "{{BUCKET_AGGREGATED}}")
    |> range(start: 2024-01-01T00:00:00Z)
    |> filter(fn: (r) => r["_measurement"] == "forecast_training")
    |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")