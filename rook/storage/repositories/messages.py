"""Message repository."""
from datetime import datetime
from typing import List

from rook.storage.database import Database
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class MessageRepository:
    """Repository for message data."""

    def __init__(self, database: Database):
        """Initialize repository.

        Args:
            database: Database instance
        """
        self.db = database

    async def save_message(
        self, session_id: str, role: str, content: str
    ) -> None:
        """Save a message.

        Args:
            session_id: Session ID
            role: Message role (user/assistant)
            content: Message content
        """
        conn = self.db.get_connection()
        await conn.execute(
            """
            INSERT INTO messages (session_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, content, datetime.now()),
        )
        await conn.commit()

    async def get_messages(self, session_id: str, limit: int = 100) -> List[dict]:
        """Get messages for a session.

        Args:
            session_id: Session ID
            limit: Maximum number of messages

        Returns:
            List of message dicts
        """
        conn = self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT role, content, timestamp
            FROM messages
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (session_id, limit),
        )

        rows = await cursor.fetchall()
        messages = []

        for row in rows:
            messages.append({"role": row[0], "content": row[1], "timestamp": row[2]})

        # Reverse to get chronological order
        messages.reverse()
        return messages
