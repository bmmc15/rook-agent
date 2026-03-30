"""Database connection and migration."""
import aiosqlite
from pathlib import Path
from typing import Optional

from rook.core.config import Config
from rook.utils.exceptions import StorageError
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class Database:
    """Async SQLite database manager."""

    def __init__(self, config: Config):
        """Initialize database.

        Args:
            config: Application configuration
        """
        self.config = config
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Connect to database and run migrations."""
        logger.info(f"Connecting to database: {self.config.database_path}")

        try:
            # Ensure directory exists
            self.config.database_path.parent.mkdir(parents=True, exist_ok=True)

            # Connect
            self._conn = await aiosqlite.connect(str(self.config.database_path))

            # Enable foreign keys
            await self._conn.execute("PRAGMA foreign_keys = ON")

            # Run migrations
            await self._run_migrations()

            logger.info("Database connected")

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise StorageError(f"Database connection failed: {e}")

    async def disconnect(self) -> None:
        """Disconnect from database."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database disconnected")

    async def _run_migrations(self) -> None:
        """Run database migrations."""
        logger.info("Running database migrations...")

        # Read schema file
        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text()

        # Execute schema
        await self._conn.executescript(schema)
        await self._conn.commit()

        logger.info("Migrations complete")

    def get_connection(self) -> aiosqlite.Connection:
        """Get database connection.

        Returns:
            Database connection

        Raises:
            StorageError: If not connected
        """
        if not self._conn:
            raise StorageError("Not connected to database")
        return self._conn
