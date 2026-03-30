"""Tests for task states and manager."""
import pytest
from datetime import datetime

from rook.tasks.states import Task, TaskState
from rook.tasks.manager import TaskManager
from rook.core.events import EventBus


@pytest.mark.asyncio
async def test_create_task(event_bus):
    """Test task creation."""
    manager = TaskManager(event_bus)
    task = manager.create_task("Test task")

    assert task.id is not None
    assert task.description == "Test task"
    assert task.state == TaskState.PENDING
    assert task.progress == 0.0


@pytest.mark.asyncio
async def test_get_task(event_bus):
    """Test getting a task by ID."""
    manager = TaskManager(event_bus)
    task = manager.create_task("Test task")

    retrieved = manager.get_task(task.id)
    assert retrieved is not None
    assert retrieved.id == task.id


@pytest.mark.asyncio
async def test_list_tasks(event_bus):
    """Test listing all tasks."""
    manager = TaskManager(event_bus)
    task1 = manager.create_task("Task 1")
    task2 = manager.create_task("Task 2")

    tasks = manager.list_tasks()
    assert len(tasks) == 2


@pytest.mark.asyncio
async def test_update_task_state(event_bus):
    """Test updating task state."""
    manager = TaskManager(event_bus)
    task = manager.create_task("Test task")

    updated = manager.update_task_state(task.id, TaskState.RUNNING)
    assert updated.state == TaskState.RUNNING


@pytest.mark.asyncio
async def test_update_task_progress(event_bus):
    """Test updating task progress."""
    manager = TaskManager(event_bus)
    task = manager.create_task("Test task")

    updated = manager.update_task_progress(task.id, 0.5)
    assert updated.progress == 0.5


@pytest.mark.asyncio
async def test_cancel_task(event_bus):
    """Test canceling a task."""
    manager = TaskManager(event_bus)
    task = manager.create_task("Test task")

    cancelled = manager.cancel_task(task.id)
    assert cancelled.state == TaskState.CANCELLED


@pytest.mark.asyncio
async def test_cancel_all_tasks(event_bus):
    """Test canceling all tasks."""
    manager = TaskManager(event_bus)
    task1 = manager.create_task("Task 1")
    task2 = manager.create_task("Task 2")

    manager.update_task_state(task1.id, TaskState.RUNNING)

    manager.cancel_all_tasks()

    assert manager.get_task(task1.id).state == TaskState.CANCELLED
    assert manager.get_task(task2.id).state == TaskState.CANCELLED
