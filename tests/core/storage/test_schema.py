"""Tests for the storage schema creation and migration."""

import aiosqlite
import pytest
from loguru import logger as loguru_logger

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.storage import StorageService
from solaredge2mqtt.core.storage.connection import (
    open_write_connection,
    supports_incremental_vacuum,
)
from solaredge2mqtt.core.storage.schema import (
    CREATE_SCHEMA_VERSION,
    SCHEMA_VERSION,
    migrate,
    read_schema_version,
)
from solaredge2mqtt.core.storage.settings import StorageSettings


class TestSchemaCreation:
    """Tests for a freshly created database file."""

    @pytest.mark.asyncio
    async def test_creates_all_tables(self, storage):
        """Every table the queries rely on exists after initialization."""
        rows = await storage.fetch_all(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        names = {row["name"] for row in rows}

        assert {"schema_version", "meta", "series", "series_tag", "point"} <= names

    @pytest.mark.asyncio
    async def test_records_schema_version(self, storage):
        """The applied version is recorded so upgrades can resume."""
        assert await read_schema_version(storage.write_connection) == SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_enables_wal(self, storage):
        """WAL is what lets a foreign reader attach while the service writes."""
        rows = await storage.fetch_all("PRAGMA journal_mode")

        assert rows[0][0] == "wal"

    @pytest.mark.asyncio
    async def test_enables_incremental_auto_vacuum(self, storage):
        """Incremental auto vacuum must be set before the first table exists."""
        assert await supports_incremental_vacuum(storage.write_connection) is True

    @pytest.mark.asyncio
    async def test_database_file_is_private(self, storage):
        """The database may contain consumption patterns, keep it owner-only."""
        assert storage.db_path.stat().st_mode & 0o777 == 0o600


class TestSchemaMigration:
    """Tests for reopening and version handling."""

    @pytest.mark.asyncio
    async def test_reopening_is_idempotent(self, tmp_path, storage_settings, prices):
        """A second start must not apply the migrations again."""
        first = StorageService(storage_settings, prices, config_dir=str(tmp_path))
        await first.async_init()
        await first.close()

        second = StorageService(storage_settings, prices, config_dir=str(tmp_path))
        await second.async_init()
        rows = await second.fetch_all("SELECT COUNT(*) FROM schema_version")
        await second.close()

        assert rows[0][0] == SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_reports_version_zero_without_table(self, tmp_path):
        """An empty file is treated as an unmigrated database."""
        connection = await aiosqlite.connect(tmp_path / "empty.db")
        try:
            assert await read_schema_version(connection) == 0
        finally:
            await connection.close()

    @pytest.mark.asyncio
    async def test_reports_version_zero_with_an_empty_table(self, tmp_path):
        """A run interrupted between the create and the insert leaves no row."""
        connection = await aiosqlite.connect(tmp_path / "halfway.db")
        try:
            await connection.execute(CREATE_SCHEMA_VERSION)

            assert await read_schema_version(connection) == 0
        finally:
            await connection.close()

    @pytest.mark.asyncio
    async def test_refuses_newer_schema(self, tmp_path):
        """A database written by a newer release must not be downgraded."""
        connection = await open_write_connection(tmp_path / "newer.db")
        try:
            await migrate(connection)
            await connection.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION + 1, 0),
            )

            with pytest.raises(ConfigurationException):
                await migrate(connection)
        finally:
            await connection.close()


class TestIncrementalVacuum:
    """Tests for the auto vacuum mode a database is opened with."""

    @pytest.mark.asyncio
    async def test_warns_about_a_database_without_incremental_vacuum(self, tmp_path):
        """A file from before the pragma keeps its pages, and says so on open."""
        db_path = tmp_path / "legacy.db"
        legacy = await aiosqlite.connect(db_path)
        await legacy.execute("PRAGMA auto_vacuum=NONE")
        await legacy.execute("CREATE TABLE marker (id INTEGER)")
        await legacy.close()

        messages = []
        sink_id = loguru_logger.add(lambda message: messages.append(str(message)))
        try:
            connection = await open_write_connection(db_path)
        finally:
            loguru_logger.remove(sink_id)

        try:
            assert await supports_incremental_vacuum(connection) is False
        finally:
            await connection.close()

        assert any("free pages are not returned" in message for message in messages)


class TestSettingsPath:
    """Tests for resolving the database location."""

    def test_uses_config_dir_by_default(self):
        """Without an explicit path the file lives next to the configuration."""
        settings = StorageSettings()

        assert settings.resolve_path("config").as_posix() == (
            "config/solaredge2mqtt.db"
        )

    def test_explicit_path_wins(self):
        """An absolute path overrides the config directory."""
        settings = StorageSettings(path="/data/history.db")

        assert settings.resolve_path("config").as_posix() == "/data/history.db"

    def test_disabled_storage_is_not_configured(self):
        """Setting enable to false is the escape hatch out of local storage."""
        assert StorageSettings(enable=False).is_configured is False
