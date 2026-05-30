import json
import os
import fcntl  # standard library lock for unix/macos
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from models import Task, HistoryLog

class BaseRepository(ABC):
    """
    Abstract interface for repository operations (CRUD).
    """
    @abstractmethod
    def get(self, entity_id: str) -> Optional[Any]:
        """
        Retrieves a single entity by its identifier.
        """
        pass

    @abstractmethod
    def get_all(self) -> List[Any]:
        """
        Retrieves all entities stored in the repository.
        """
        pass

    @abstractmethod
    def add(self, entity: Any) -> None:
        """
        Adds a new entity to the repository.
        """
        pass

    @abstractmethod
    def delete(self, entity_id: str) -> None:
        """
        Deletes or soft-deletes an entity from the repository.
        """
        pass


class JSONTaskRepository(BaseRepository):
    """
    Concrete task repository handling JSON-backed data.
    """
    def __init__(self, tasks_dict: Dict[str, Task]) -> None:
        """
        Initializes the repository with a dictionary of Task objects.
        """
        self._tasks: Dict[str, Task] = tasks_dict

    def get(self, task_id: str) -> Optional[Task]:
        """
        Retrieves a Task object by its unique identifier.
        """
        return self._tasks.get(task_id)

    def get_all(self, include_deleted: bool = False) -> List[Task]:
        """
        Retrieves all active tasks, or all tasks (including deleted) if include_deleted is True.
        """
        all_tasks: List[Task] = list(self._tasks.values())
        if not include_deleted:
            return [t for t in all_tasks if not t.is_deleted]
        return all_tasks

    def add(self, task: Task) -> None:
        """
        Adds a new Task to the repository.
        """
        self._tasks[task.task_id] = task

    def update(self, task: Task) -> None:
        """
        Updates an existing Task. Since memory states use references, this maps state key.
        """
        self._tasks[task.task_id] = task

    def delete(self, task_id: str) -> None:
        """
        Soft-deletes the Task matching the given task identifier.
        """
        task: Optional[Task] = self.get(task_id)
        if task:
            task.soft_delete()

    def delete_permanently(self, task_id: str) -> None:
        """
        Permanently removes the task matching the given task identifier from memory.
        """
        if task_id in self._tasks:
            del self._tasks[task_id]


class JSONHistoryRepository(BaseRepository):
    """
    Concrete history log repository handling JSON-backed audit logs.
    """
    def __init__(self, history_list: List[HistoryLog]) -> None:
        """
        Initializes the repository with a list of HistoryLog objects.
        """
        self._history: List[HistoryLog] = history_list

    def get(self, history_id: str) -> Optional[HistoryLog]:
        """
        Retrieves a HistoryLog by its unique history identifier.
        """
        for h in self._history:
            if h.history_id == history_id:
                return h
        return None

    def get_all(self, task_id: Optional[str] = None) -> List[HistoryLog]:
        """
        Retrieves all history logs, filtered by a task identifier if provided.
        """
        if task_id:
            return [h for h in self._history if h.task_id == task_id]
        return self._history

    def add(self, history_log: HistoryLog) -> None:
        """
        Appends a new HistoryLog entry.
        """
        self._history.append(history_log)

    def delete(self, history_id: str) -> None:
        """
        Deletes a history log. Deletes are unsupported for history security logs.
        """
        pass


class DatabaseContext:
    """
    Context manager (Unit of Work) coordinating file storage transactions.
    Ensures safe concurrent access using Unix flock.
    """
    def __init__(self, file_path: str = "db.json") -> None:
        """
        Initializes the database context manager with the target file path.
        """
        self.file_path: str = file_path
        self._file_handle: Optional[Any] = None
        self._tasks: Dict[str, Task] = {}
        self._history: List[HistoryLog] = []
        
        # Public repositories exposed inside context block
        self.tasks: Optional[JSONTaskRepository] = None
        self.history: Optional[JSONHistoryRepository] = None

    def __enter__(self) -> "DatabaseContext":
        """
        Enters the context block, opens the database file, and acquires a file lock.
        Deserializes file data into model repositories.
        """
        # Open file in read/write + create mode
        self._file_handle = open(self.file_path, "a+")
        
        # Acquire exclusive lock (blocks until lock is free)
        fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_EX)
        
        # Seek back to start and read
        self._file_handle.seek(0)
        content: str = self._file_handle.read().strip()
        
        data: Dict[str, Any] = {}
        if content:
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # If file is corrupted, initialize empty
                data = {}

        # Deserialize tasks
        raw_tasks: List[Dict[str, Any]] = data.get("tasks", [])
        self._tasks = {t["task_id"]: Task.from_dict(t) for t in raw_tasks}

        # Deserialize history
        raw_history: List[Dict[str, Any]] = data.get("history", [])
        self._history = [HistoryLog.from_dict(h) for h in raw_history]

        # Bind to repositories
        self.tasks = JSONTaskRepository(self._tasks)
        self.history = JSONHistoryRepository(self._history)
        
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[Any]) -> None:
        """
        Exits the context block, committing pending changes if no exception was raised.
        Releases the lock and closes the file handler.
        """
        # If no exceptions occurred during execution, commit changes
        if exc_type is None:
            self.commit()
            
        # Release the lock and close file descriptor
        if self._file_handle:
            fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
            self._file_handle.close()

    def commit(self) -> None:
        """
        Writes memory repository states back to database file in JSON format.
        """
        if not self._file_handle:
            return

        data: Dict[str, Any] = {
            "tasks": [t.to_dict() for t in self._tasks.values()],
            "history": [h.to_dict() for h in self._history]
        }

        # Truncate and write
        self._file_handle.seek(0)
        self._file_handle.truncate()
        json.dump(data, self._file_handle, indent=2)
        self._file_handle.flush()
