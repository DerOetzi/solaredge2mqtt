# Architecture Decisions

Records of decisions that shaped the project, written when the decision was made and kept
afterwards. They explain why something is the way it is, which the code itself cannot.

They are numbered sequentially and append-only. A decision that no longer holds is not edited or
deleted, it is superseded by a later one that says so.

| # | Decision | Status | In short |
|---|---|---|---|
| [0001](0001-pvlearn-extraction-wiring.md) | Wiring to the pvlearn forecast core | Accepted | The forecast regression test compares error metrics within a tolerance instead of exact predictions, and pvlearn errors are translated at the service boundary. |
| [0002](0002-canonical-weather-schema.md) | Speaking pvlearn's canonical weather schema | Partly superseded by [0007](0007-storage-holds-the-canonical-schema.md) | The OpenWeatherMap condition id is mapped onto WMO 4677, deliberately losing detail. |
| [0003](0003-weather-provider-as-a-feature.md) | The weather provider is stamped onto every row | Partly superseded by [0007](0007-storage-holds-the-canonical-schema.md) | The provider became a first-class field rather than an assumption. |
| [0004](0004-drop-armv7-support.md) | Build with uv, drop `arm/v7` | Accepted | The Docker build uses `uv sync --frozen` for reproducible pins, and 32-bit ARM images are no longer published. Includes a self-build recipe. |
| [0005](0005-install-wheel-in-docker.md) | Install the wheel in Docker | Accepted | The final image installs a built wheel instead of copying source, which fixes the missing generated version file. |
| [0006](0006-sqlite-storage-instead-of-influxdb.md) | A local SQLite file replaces InfluxDB | Accepted | The history moved into an embedded database in the configuration directory, removing a mandatory external service. |
| [0007](0007-storage-holds-the-canonical-schema.md) | The storage holds the canonical schema | Accepted | Training data is stored under the forecast model's own field names, translated once on write instead of on every read. |
| [0008](0008-the-weather-service-speaks-canonically.md) | The weather service hands out canonical snapshots | Accepted | The weather event and the published topic carry provider-independent field names. |
| [0009](0009-migration-consolidates-the-module-series.md) | The migration consolidates the module series | Accepted | The InfluxDB import merges duplicate module series, caused by a changed optimizer identifier, keyed by serial number. |
| [0010](0010-the-forecast-model-is-rebuilt-on-a-slower-cadence.md) | The forecast model is rebuilt on a slower cadence | Accepted | Training data is still written hourly, while the model, the hyperparameter search and their state on disk each follow their own interval. |
| [0011](0011-energy-classes-follow-home-assistant.md) | Stored energy and session energy get their own Home Assistant classes | Accepted | Battery capacities became `energy_storage` measurements, the EV charger session became a `total_increasing` energy counter, which costs a one-time statistics repair. |

## Writing a new one

Take the next free number, keep the file name in the `NNNN-kebab-case-title.md` shape, and add a
row to the table above. State the context, the decision, and the consequence you accepted. A
decision that only records what was done, without the alternatives that were rejected, is not
worth keeping.
