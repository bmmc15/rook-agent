"""Task repository."""
from datetime import datetime
from typing import List, Optional

from rook.storage.database import Database
from rook.tasks.states import Task, TaskState
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class TaskRepository:
    """Repository for task data."""

    def __init__(self, database: Database):
        """Initialize repository.

        Args:
            database: Database instance
        """
        self.db = database

    async def save_task(self, task: Task, session_id: Optional[str] = None) -> None:
        """Save a task.

        Args:
            task: Task to save
            session_id: Optional session ID
        """
        conn = self.db.get_connection()
        await conn.execute(
            """
            INSERT OR REPLACE INTO tasks
            (id, session_id, description, state, progress, result, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                session_id,
                task.description,
                task.state.name,
                task.progress,
                task.result,
                task.error,
                task.created_at,
                task.updated_at,
            ),
        )
        await conn.commit()

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task or None
        """
        conn = self.db.get_connection()
        cursor = await conn.execute(
            """
            SELECT id, description, state, progress, result, error, created_at, updated_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        )

        row = await cursor.fetchone()
        if not row:
            return None

        return Task(
            id=row[0],
            description=row[1],
            state=TaskState[row[2]],
            progress=row[3],
            result=row[4],
            error=row[5],
            created_at=datetime.fromisoformat(row[6]),
            updated_at=datetime.fromisoformat(row[7]),
        )

    async def list_tasks(self, session_id: Optional[str] = None) -> List[Task]:
        """List tasks.

        Args:
            session_id: Optional session ID filter

        Returns:
            List of tasks
        """
        conn = self.db.get_connection()

        if session_id:
            cursor = await conn.execute(
                """
                SELECT id, description, state, progress, result, error, created_at, updated_at
                FROM tasks
                WHERE session_id = ?
                ORDER BY created_at DESC
                """,
                (session_id,),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT id, description, state, progress, result, error, created_at, updated_at
                FROM tasks
                ORDER BY created_at DESC
                """
            )

        rows = await cursor.fetchall()
        tasks = []

        for row in rows:
            tasks.append(
                Task(
                    id=row[0],
                    description=row[1],
                    state=TaskState[row[2]],
                    progress=row[3],
                    result=row[4],
                    error=row[5],
                    created_at=datetime.fromisoformat(row[6]),
                    updated_at=datetime.fromisoformat(row[7]),
                )
            )

        return tasks
