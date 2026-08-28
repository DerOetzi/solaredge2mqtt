"""Tests for the daily database backup."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from solaredge2mqtt.core.storage.backup import (
    LAST_BACKUP_KEY,
    LOCAL_TZ,
    backup_path,
    create_backup,
    existing_backups,
    maybe_create_backup,
    prune_backups,
)

NOW = datetime(2026, 8, 19, 12, 30, tzinfo=timezone.utc)

LOCAL_NOON = datetime(2026, 8, 19, 12, 0, tzinfo=LOCAL_TZ)

LOCAL_NIGHT = datetime(2026, 8, 19, 1, 0, tzinfo=LOCAL_TZ)


def count_points(path):
    """Count the points of a database file without the storage service."""
    connection = sqlite3.connect(path)
    try:
        return connection.execute("SELECT COUNT(*) FROM point").fetchone()[0]
    finally:
        connection.close()


def touch_backups(db_path, moments):
    """Create empty backup files for the given moments."""
    paths = []
    for moment in moments:
        path = backup_path(db_path, moment)
        path.touch()
        paths.append(path)

    return paths


class TestDefaults:
    """Tests for the settings a fresh installation runs with."""

    def test_backs_up_early_and_keeps_two(self, storage_settings):
        """The daily copy lands before the usual nightly backup of a host."""
        assert storage_settings.daily_backups is True
        assert storage_settings.backup_hour == 3
        assert storage_settings.keep_backups == 2


class TestCreateBackup:
    """Tests for writing a single backup."""

    @pytest.mark.asyncio
    async def test_writes_a_readable_copy(self, storage, seed):
        """The backup holds the same history as the database it came from."""
        await seed("energy", "pv_production", {}, [(NOW, 1.0)])

        backup = await create_backup(storage, NOW)

        assert backup is not None
        assert backup == backup_path(storage.db_path, NOW)
        assert count_points(backup) == count_points(storage.db_path)

    @pytest.mark.asyncio
    async def test_restricts_the_backup_to_the_owner(self, storage):
        """The copy carries the same history, so it carries the same mode."""
        backup = await create_backup(storage, NOW)

        assert backup is not None
        assert backup.stat().st_mode & 0o777 == 0o600

    @pytest.mark.asyncio
    async def test_keeps_an_existing_file(self, storage):
        """A second backup within the same second must not overwrite the first."""
        existing = backup_path(storage.db_path, NOW)
        existing.write_bytes(b"keep me")

        assert await create_backup(storage, NOW) is None
        assert existing.read_bytes() == b"keep me"

    @pytest.mark.asyncio
    async def test_skips_without_free_disk_space(self, storage, monkeypatch):
        """A filesystem too small for a second copy is reported, not attempted."""
        monkeypatch.setattr(
            "solaredge2mqtt.core.storage.backup.has_room_for_backup", lambda _: False
        )

        assert await create_backup(storage, NOW) is None
        assert existing_backups(storage.db_path) == []

    @pytest.mark.asyncio
    async def test_removes_the_target_after_a_failure(self, storage, monkeypatch):
        """A half written backup is worse than none at all."""

        async def fail(target):
            target.touch()
            raise sqlite3.OperationalError("disk I/O error")

        monkeypatch.setattr(storage, "vacuum_into", fail)

        assert await create_backup(storage, NOW) is None
        assert existing_backups(storage.db_path) == []


class TestPruneBackups:
    """Tests for the retention of the backup files."""

    def test_keeps_the_newest_ones(self, storage):
        """Only the configured number of backups survives."""
        moments = [NOW - timedelta(days=offset) for offset in range(4)]
        paths = touch_backups(storage.db_path, moments)

        removed = prune_backups(storage.db_path, keep=2)

        assert removed == paths[2:]
        assert existing_backups(storage.db_path) == paths[:2]

    def test_keeps_everything_without_a_limit(self, storage):
        """A limit of zero disables the pruning."""
        paths = touch_backups(storage.db_path, [NOW, NOW - timedelta(days=1)])

        assert prune_backups(storage.db_path, keep=0) == []
        assert existing_backups(storage.db_path) == paths

    def test_ignores_a_foreign_database(self, storage):
        """Backups of another database in the same directory stay untouched."""
        foreign = storage.db_path.with_name("other.db.backup.20260819123000")
        foreign.touch()
        touch_backups(storage.db_path, [NOW, NOW - timedelta(days=1)])

        prune_backups(storage.db_path, keep=1)

        assert foreign.exists()


class TestDailyBackup:
    """Tests for the once a day scheduling on a fixed local hour."""

    @pytest.mark.asyncio
    async def test_runs_on_the_first_pass_after_the_hour(self, storage):
        """Without a recorded run the backup is due as soon as the hour is up."""
        backup = await maybe_create_backup(storage, now=LOCAL_NOON)

        assert backup is not None
        assert await storage.read_meta(LAST_BACKUP_KEY) == str(
            int(LOCAL_NOON.timestamp())
        )

    @pytest.mark.asyncio
    async def test_waits_for_the_configured_hour(self, storage):
        """Before backup_hour the day's backup is not written yet."""
        assert await maybe_create_backup(storage, now=LOCAL_NIGHT) is None
        assert existing_backups(storage.db_path) == []

    @pytest.mark.asyncio
    async def test_skips_the_rest_of_the_day(self, storage):
        """Ten minute passes must not produce a backup every time."""
        await maybe_create_backup(storage, now=LOCAL_NOON)

        later = LOCAL_NOON + timedelta(hours=11)

        assert await maybe_create_backup(storage, now=later) is None
        assert len(existing_backups(storage.db_path)) == 1

    @pytest.mark.asyncio
    async def test_runs_again_on_the_next_day(self, storage):
        """The next local day gets its own backup."""
        await maybe_create_backup(storage, now=LOCAL_NOON)

        assert await maybe_create_backup(storage, now=LOCAL_NOON + timedelta(days=1))
        assert len(existing_backups(storage.db_path)) == 2

    @pytest.mark.asyncio
    async def test_runs_shortly_after_a_late_hour(self, storage):
        """A backup late on one day does not block the next morning."""
        storage.settings.backup_hour = 3
        await maybe_create_backup(storage, now=LOCAL_NOON.replace(hour=23))

        morning = LOCAL_NOON.replace(hour=4) + timedelta(days=1)

        assert await maybe_create_backup(storage, now=morning)

    @pytest.mark.asyncio
    async def test_applies_the_backup_retention(self, storage):
        """The oldest backups go once the limit is reached."""
        storage.settings.keep_backups = 1
        await maybe_create_backup(storage, now=LOCAL_NOON)

        await maybe_create_backup(storage, now=LOCAL_NOON + timedelta(days=1))

        assert existing_backups(storage.db_path) == [
            backup_path(storage.db_path, LOCAL_NOON + timedelta(days=1))
        ]

    @pytest.mark.asyncio
    async def test_disabled_by_setting(self, storage):
        """Nothing is written and nothing is recorded when it is switched off."""
        storage.settings.daily_backups = False

        assert await maybe_create_backup(storage, now=LOCAL_NOON) is None
        assert existing_backups(storage.db_path) == []
        assert await storage.read_meta(LAST_BACKUP_KEY) is None

    @pytest.mark.asyncio
    async def test_retries_after_a_failed_backup(self, storage, monkeypatch):
        """A failure must not count as the run of the day."""
        monkeypatch.setattr(
            "solaredge2mqtt.core.storage.backup.has_room_for_backup", lambda _: False
        )

        assert await maybe_create_backup(storage, now=LOCAL_NOON) is None
        assert await storage.read_meta(LAST_BACKUP_KEY) is None
