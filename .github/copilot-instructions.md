# Copilot Coding Agent Instructions for SolarEdge2MQTT

## Project Overview

- **Purpose:** Integrates SolarEdge inverters with MQTT for home automation, logging, and forecasting.
- **Language:** Python (>=3.11, <=3.13)
- **Package Manager:** pip with pyproject.toml
- **Major Components:**
  - `solaredge2mqtt/`: Core logic, service orchestration, and integrations.
    - `core/`: Event bus, logging, settings, MQTT, InfluxDB, timer, etc.
    - `services/`: Modular services (energy, forecast, homeassistant, modbus, monitoring, powerflow, wallbox, weather).
    - `__main__.py`: Entrypoint for CLI/console mode.
    - `service.py`: Main service orchestration logic.
  - `tests/`: Unit and integration tests mirroring the `solaredge2mqtt/` structure.
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

### Installation

```bash
# Standard installation with all development dependencies
pip install -e ".[dev,forecast]"

# For package builds
pip install build && python -m build
```

### Linting

```bash
# Run linter (ruff) to check for issues
ruff check .

# Auto-fix linting issues
ruff check . --fix

# Format code
ruff format .
```

### Testing

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=solaredge2mqtt --cov-report=xml:coverage.xml

# Run specific test file
pytest tests/path/to/test_file.py

# Run tests with verbose output
pytest -v --tb=short
```

### Running the Service

```bash
# Console mode (development)
python -m solaredge2mqtt
# or after installation:
solaredge2mqtt

# Docker
docker build -t solaredge2mqtt .
docker compose up -d
```

### Configuration

- Environment variables (see `.env.example` in repo and README)
- Pydantic models in `core/settings/models.py` and per-service `settings.py`
- Double underscores for nested settings (e.g., `SE2MQTT_MODBUS__HOST`)

## Testing Guidelines

- Test files should mirror the source structure under `tests/`
- Use `pytest` with async support (`pytest-asyncio`)
- Fixtures are defined in `tests/conftest.py`
- Test classes should be prefixed with `Test` and methods with `test_`
- Use mocks for external services (MQTT, InfluxDB, Modbus, HTTP APIs)
- Async tests use the `@pytest.mark.asyncio` decorator (auto mode enabled)

## Project-Specific Patterns & Conventions

### Settings

- Deeply nested, environment-variable-driven, using double underscores for nesting (e.g., `SE2MQTT_MODBUS__HOST`).
- Secrets can be injected via Docker secrets (`/run/secrets`).
- All settings models use Pydantic for validation.

### Events

- Event classes in `core/events` and `core/timer/events` are used for decoupled communication.
- Services subscribe to events via `event_bus.subscribe()` and emit via `event_bus.emit()`.

### Logging

- Centralized via `core/logging` using `loguru`.
- Use `logger.debug()`, `logger.info()`, `logger.warning()`, `logger.error()` consistently.

### Forecasting

- Machine learning pipeline in `services/forecast/` uses InfluxDB and weather data.
- Caching and security for forecast pipeline handled in `services/forecast/settings.py`.
- Not available for `arm/v7` architecture.

### Extensibility

- New services should be added under `services/` and registered in the main service logic (`service.py`).
- Each service should have its own `settings.py`, `models.py`, and `events.py` as needed.

## Integration Points

- **MQTT:** Publishes inverter and sensor data for home automation (see `core/mqtt/`).
- **InfluxDB:** Logs raw and aggregated data (see `core/influxdb/`).
- **Home Assistant:** Auto-discovery support (see `services/homeassistant/`).
- **Weather/Forecast:** Integrates with OpenWeatherMap and uses local cache for ML models.
- **Modbus:** Communicates with SolarEdge inverters via TCP/IP.

## Security Considerations

- Never commit secrets or credentials to the repository.
- Use environment variables or Docker secrets for sensitive configuration.
- Validate all external inputs through Pydantic models.
- Be cautious with user-provided data in MQTT messages.

## Code Quality Standards

- Code must pass `ruff check` linting.
- Follow PEP 8 style guidelines (enforced by ruff).
- Maximum line length: 88 characters.
- Use type hints for function signatures.
- Ensure SonarQube code quality standards are met.

## Examples

- See `examples/docker-compose-full-stack.yaml` for a full-stack deployment.
- See `README.md` for environment variable documentation and usage scenarios.

---

**If you are unsure about a workflow or integration, check the README and the relevant service's `settings.py` for configuration details.**

## Code Generation Constraints

- Use syntax and language features for Python >=3.11 and <=3.13
- For diagrams use PlantUML
- As this is an international project, ensure all code comments and documentation are in English
- Follow the project's directory structure and naming conventions
- Maintain consistency with existing code patterns and style