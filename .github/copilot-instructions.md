# Copilot Coding Agent Instructions for SolarEdge2MQTT

## Project Overview
- **Purpose:** Integrates SolarEdge inverters with MQTT for home automation, logging, and forecasting.
- **Major Components:**
  - `solaredge2mqtt/`: Core logic, service orchestration, and integrations.
    - `core/`: Event bus, logging, settings, MQTT, InfluxDB, timer, etc.
    - `services/`: Modular services (energy, forecast, homeassistant, modbus, monitoring, powerflow, wallbox, weather).
    - `__main__.py`: Entrypoint for CLI/console mode.
  - `examples/`: Example configs for Docker Compose, Grafana, etc.
  - `Dockerfile`, `docker-compose.yml`: Containerization and orchestration.

## Architecture & Data Flow
- **Event-driven:** Uses an internal event bus for cross-component communication (see `core/events` and `core/timer/events`).
- **Service boundaries:** Each service (e.g., Modbus, MQTT, Forecast) is isolated in its own module under `services/` and configured via Pydantic models.
- **Data flow:**
  - Data is collected from inverters (Modbus, Monitoring, Wallbox)
  - Aggregated, logged to InfluxDB, and published to MQTT
  - Forecasting uses historical and weather data

## Developer Workflows
- **Build:**
  - Standard: `pip install .[dev,forecast]` or `pip install -e .[dev,forecast]` (for editable/development mode)
  - For package builds: `pip install build && python -m build`
  - Docker: `docker build -t solaredge2mqtt .`
- **Run:**
  - Console: `python -m solaredge2mqtt` or `solaredge2mqtt` (after install)
  - Docker Compose: `docker compose up -d`
- **Test:**
  - (If tests exist) Use `pytest` or similar; test structure may be under `tests/` (not present in current tree)
- **Configuration:**
  - Environment variables (see `.env.example` in repo and README)
  - Pydantic models in `core/settings/models.py` and per-service `settings.py`

## Project-Specific Patterns & Conventions
- **Settings:**
  - Deeply nested, environment-variable-driven, using double underscores for nesting (e.g., `SE2MQTT_MODBUS__HOST`).
  - Secrets can be injected via Docker secrets (`/run/secrets`).
- **Events:**
  - Event classes in `core/events` and `core/timer/events` are used for decoupled communication.
- **Logging:**
  - Centralized via `core/logging`.
- **Forecasting:**
  - Machine learning pipeline in `services/forecast/` uses InfluxDB and weather data.
  - Caching and security for forecast pipeline handled in `services/forecast/settings.py`.
- **Extensibility:**
  - New services should be added under `services/` and registered in the main service logic.

## Integration Points
- **MQTT:** Publishes inverter and sensor data for home automation (see `core/mqtt/`).
- **InfluxDB:** Logs raw and aggregated data (see `core/influxdb/`).
- **Home Assistant:** Auto-discovery support (see `services/homeassistant/`).
- **Weather/Forecast:** Integrates with OpenWeatherMap and uses local cache for ML models.

## Examples
- See `examples/docker-compose-full-stack.yaml` for a full-stack deployment.
- See `README.md` for environment variable documentation and usage scenarios.

---

**If you are unsure about a workflow or integration, check the README and the relevant service's `settings.py` for configuration details.**

## (Coding) generation constraints
- Use syntax and language features for python >= 3.11 <= 3.13
- For diagrams use PlantUml
- As this is an international project, ensure all code comments and documentation are in English.
- Follow the project's directory structure and naming conventions.
- Ensure SonarQube code quality standards are met.