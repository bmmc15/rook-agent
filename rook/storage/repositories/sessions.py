"""Session repository."""
import uuid
from datetime import datetime
from typing import Optional

from rook.storage.database import Database
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class SessionRepository:
    """Repository for session data."""

    def __init__(self, database: Database):
        """Initialize repository.

        Args:
            database: Database instance
        """
        self.db = database

    async def create_session(self) -> str:
        """Create a new session.

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        now = datetime.now()

        conn = self.db.get_connection()
        await conn.execute(
            """
            INSERT INTO sessions (id, created_at, updated_at, status)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, now, now, "active"),
        )
        await conn.commit()

        logger.info(f"Created session: {session_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session data or None
        """
        conn = self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT id, created_at, updated_at, status
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        )

        row = await cursor.fetchone()
        if not row:
            return None

        return {
            "id": row[0],
            "created_at": row[1],
            "updated_at": row[2],
            "status": row[3],
        }
