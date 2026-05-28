import json
import os
import fcntl  # standard library lock for unix/macos
from abc import ABC, abstractmethod
from models import Task, HistoryLog

class BaseRepository(ABC):
    """
    Abstract interface for repository operations (CRUD).
    """
    @abstractmethod
    def get(self, entity_id):
        pass

    @abstractmethod
    def get_all(self):
        pass

    @abstractmethod
    def add(self, entity):
        pass

    @abstractmethod
    def delete(self, entity_id):
        pass


class JSONTaskRepository(BaseRepository):
    """
    Concrete task repository handling JSON-backed data.
    """
    def __init__(self, tasks_dict):
        self._tasks = tasks_dict

    def get(self, task_id):
        return self._tasks.get(task_id)

    def get_all(self, include_deleted=False):
        all_tasks = list(self._tasks.values())
        if not include_deleted:
            return [t for t in all_tasks if not t.is_deleted]
        return all_tasks

    def add(self, task):
        self._tasks[task.task_id] = task

    def update(self, task):
        # In-memory updates are handled via object references,
        # but we maintain interface consistency here.
        self._tasks[task.task_id] = task

    def delete(self, task_id):
        """Soft-deletes the task."""
        task = self.get(task_id)
        if task:
            task.soft_delete()


class JSONHistoryRepository(BaseRepository):
    """
    Concrete history log repository handling JSON-backed audit logs.
    """
    def __init__(self, history_list):
        self._history = history_list

    def get(self, history_id):
        for h in self._history:
            if h.history_id == history_id:
                return h
        return None

    def get_all(self, task_id=None):
        if task_id:
            return [h for h in self._history if h.task_id == task_id]
        return self._history

    def add(self, history_log):
        self._history.append(history_log)

    def delete(self, history_id):
        # We don't support deleting audit logs for security
        pass


class DatabaseContext:
    """
    Context manager (Unit of Work) coordinating file storage transactions.
    Ensures safe concurrent access using Unix flock.
    """
    def __init__(self, file_path="db.json"):
        self.file_path = file_path
        self._file_handle = None
        self._tasks = {}
        self._history = []
        
        # Public repositories exposed inside context block
        self.tasks = None
        self.history = None

    def __enter__(self):
        # Open file in read/write + create mode
        self._file_handle = open(self.file_path, "a+")
        
        # Acquire exclusive lock (blocks until lock is free)
        fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_EX)
        
        # Seek back to start and read
        self._file_handle.seek(0)
        content = self._file_handle.read().strip()
        
        data = {}
        if content:
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # If file is corrupted, initialize empty
                data = {}

        # Deserialize tasks
        raw_tasks = data.get("tasks", [])
        self._tasks = {t["task_id"]: Task.from_dict(t) for t in raw_tasks}

        # Deserialize history
        raw_history = data.get("history", [])
        self._history = [HistoryLog.from_dict(h) for h in raw_history]

        # Bind to repositories
        self.tasks = JSONTaskRepository(self._tasks)
        self.history = JSONHistoryRepository(self._history)
        
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # If no exceptions occurred during execution, commit changes
        if exc_type is None:
            self.commit()
            
        # Release the lock and close file descriptor
        if self._file_handle:
            fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
            self._file_handle.close()

    def commit(self):
        """Writes memory repository states back to database file."""
        if not self._file_handle:
            return

        data = {
            "tasks": [t.to_dict() for t in self._tasks.values()],
            "history": [h.to_dict() for h in self._history]
        }

        # Truncate and write
        self._file_handle.seek(0)
        self._file_handle.truncate()
        json.dump(data, self._file_handle, indent=2)
        self._file_handle.flush()
