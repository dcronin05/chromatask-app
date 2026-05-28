import datetime
from repositories import DatabaseContext
from models import Task, HistoryLog

class TaskService:
    """
    Service layer containing the business logic for task management.
    Coordinates between repositories and handles history tracking.
    """
    def __init__(self, db_file_path="db.json"):
        self.db_file_path = db_file_path

    def get_all_tasks(self, include_deleted=False):
        """Retrieves all active or archived tasks."""
        with DatabaseContext(self.db_file_path) as db:
            tasks = db.tasks.get_all(include_deleted)
            # Sort by creation time (newest first)
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            return [t.to_dict() for t in tasks]

    def get_task_by_id(self, task_id):
        """Retrieves a single task by ID."""
        with DatabaseContext(self.db_file_path) as db:
            task = db.tasks.get(task_id)
            return task.to_dict() if task else None

    def create_task(self, task_data):
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

    def update_task(self, task_id, update_data):
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

    def delete_task(self, task_id):
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

    def restore_task(self, task_id):
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

    def get_task_history(self, task_id):
        """Retrieves audit log events for a task (oldest first)."""
        with DatabaseContext(self.db_file_path) as db:
            logs = db.history.get_all(task_id=task_id)
            # Sort chronologically (oldest first)
            logs.sort(key=lambda l: l.timestamp)
            return [l.to_dict() for l in logs]

    def reset_database(self):
        """Resets the database, clearing all tasks and history."""
        with DatabaseContext(self.db_file_path) as db:
            # Clear all current memory records
            db._tasks.clear()
            db._history.clear()
            
            # DatabaseContext commits on exit automatically
            return True
