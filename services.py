import datetime
from typing import Any, Dict, List, Optional
from repositories import DatabaseContext
from models import Task, HistoryLog

class TaskService:
    """
    Service layer containing the business logic for task management.
    Coordinates between repositories and handles history tracking.
    """
    def __init__(self, db_file_path: str = "db.json") -> None:
        """
        Initializes the TaskService with a database file path.
        """
        self.db_file_path: str = db_file_path

    def get_all_tasks(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Retrieves all active or archived tasks, sorted by creation date."""
        with DatabaseContext(self.db_file_path) as db:
            tasks = db.tasks.get_all(include_deleted)
            # Sort by creation time (newest first)
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            return [t.to_dict() for t in tasks]

    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single task by ID."""
        with DatabaseContext(self.db_file_path) as db:
            task = db.tasks.get(task_id)
            return task.to_dict() if task else None

    def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a new task and logs the creation event."""
        with DatabaseContext(self.db_file_path) as db:
            # Instantiate Entity
            task = Task.from_dict(task_data)
            
            # Save task
            db.tasks.add(task)
            
            # Add History Log
            log = HistoryLog(
                task_id=task.task_id,
                action="CREATED",
                details={"title": task.title}
            )
            db.history.add(log)
            
            return task.to_dict()

    def update_task(self, task_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Updates a task, diffs fields, and logs a detailed update history event."""
        with DatabaseContext(self.db_file_path) as db:
            task = db.tasks.get(task_id)
            if not task:
                raise ValueError(f"Task with ID {task_id} not found.")

            # Perform update and retrieve list of changes
            diffs = task.update_fields(update_data)
            
            if diffs:
                # Save task changes
                db.tasks.update(task)
                
                # Add History Log detailing what fields changed
                log = HistoryLog(
                    task_id=task.task_id,
                    action="UPDATED",
                    details={"changes": diffs}
                )
                db.history.add(log)
                
            return task.to_dict()

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Soft-deletes a task and logs the deletion event."""
        with DatabaseContext(self.db_file_path) as db:
            task = db.tasks.get(task_id)
            if not task:
                raise ValueError(f"Task with ID {task_id} not found.")
                
            task.soft_delete()
            db.tasks.update(task)
            
            log = HistoryLog(
                task_id=task.task_id,
                action="DELETED",
                details={"title": task.title}
            )
            db.history.add(log)
            
            return task.to_dict()

    def restore_task(self, task_id: str) -> Dict[str, Any]:
        """Restores a soft-deleted task and logs the restoration event."""
        with DatabaseContext(self.db_file_path) as db:
            task = db.tasks.get(task_id)
            if not task:
                raise ValueError(f"Task with ID {task_id} not found.")
                
            task.restore()
            db.tasks.update(task)
            
            log = HistoryLog(
                task_id=task.task_id,
                action="RESTORED",
                details={"title": task.title}
            )
            db.history.add(log)
            
            return task.to_dict()

    def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
        """Retrieves audit log events for a task (newest first)."""
        with DatabaseContext(self.db_file_path) as db:
            logs = db.history.get_all(task_id=task_id)
            # Sort chronologically (newest first)
            logs.sort(key=lambda l: l.timestamp, reverse=True)
            return [l.to_dict() for l in logs]

    def _reconstruct_task_dict_at(self, task_id: str, history_id: str, db: DatabaseContext) -> Dict[str, Any]:
        """
        Reconstructs the task dictionary state immediately after a history event.
        Walks backward through history in reverse chronological order from current state.
        """
        task = db.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found.")

        # Clone current state
        reconstructed = task.to_dict()

        # Get all history logs for this task
        logs = db.history.get_all(task_id=task_id)
        # Sort by timestamp newest first
        logs.sort(key=lambda l: l.timestamp, reverse=True)

        # Loop through events in reverse chronological order
        for log in logs:
            if log.history_id == history_id:
                # Target history state reached (keep changes of this event, stop undoing prior events)
                break

            # Undo this log event's changes
            if log.action in ("UPDATED", "ROLLBACK"):
                changes = log.details.get("changes", [])
                for change in changes:
                    field = change["field"]
                    reconstructed[field] = change["old"]
            elif log.action == "DELETED":
                reconstructed["is_deleted"] = False
                reconstructed["deleted_at"] = None
            elif log.action == "RESTORED":
                reconstructed["is_deleted"] = True
                reconstructed["deleted_at"] = log.timestamp

        return reconstructed

    def get_reconstructed_task(self, task_id: str, history_id: str) -> Dict[str, Any]:
        """
        Retrieves a reconstructed task state at the moment after the specified history event.
        Returns a dict with reconstructed task state and the history log info.
        """
        with DatabaseContext(self.db_file_path) as db:
            log = db.history.get(history_id)
            if not log or log.task_id != task_id:
                raise ValueError(f"History log with ID {history_id} not found or task mismatch.")
            
            reconstructed = self._reconstruct_task_dict_at(task_id, history_id, db)
            return {
                "reconstructed": reconstructed,
                "log": log.to_dict()
            }

    def rollback_task(self, task_id: str, history_id: str) -> Dict[str, Any]:
        """
        Rolls back a task to its state immediately after the specified history event.
        Calculates differences and logs a ROLLBACK audit event.
        """
        with DatabaseContext(self.db_file_path) as db:
            task = db.tasks.get(task_id)
            if not task:
                raise ValueError(f"Task with ID {task_id} not found.")

            target_state_dict = self._reconstruct_task_dict_at(task_id, history_id, db)
            
            # Apply reconstructed properties using the existing diff mechanism
            diffs = task.update_fields(target_state_dict)

            if diffs:
                db.tasks.update(task)

                # Create audit trail for rollback
                log = HistoryLog(
                    task_id=task.task_id,
                    action="ROLLBACK",
                    details={
                        "rollback_to_history_id": history_id,
                        "changes": diffs
                    }
                )
                db.history.add(log)

            return task.to_dict()

    def reset_database(self) -> bool:
        """Resets the database, clearing all tasks and history."""
        with DatabaseContext(self.db_file_path) as db:
            # Clear all current memory records
            db._tasks.clear()
            db._history.clear()
            
            # DatabaseContext commits on exit automatically
            return True
