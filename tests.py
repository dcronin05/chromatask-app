import unittest
import os
from typing import Any, Dict, List, Optional
from models import Task, HistoryLog
from repositories import DatabaseContext, JSONTaskRepository, JSONHistoryRepository
from services import TaskService

class TaskModelTests(unittest.TestCase):
    """
    Unit tests for the Task and HistoryLog domain models.
    """
    def test_task_creation_and_defaults(self) -> None:
        """Verifies default values and fields on Task instantiation."""
        task = Task(title="Test Task")
        self.assertIsNotNone(task.task_id)
        self.assertEqual(task.title, "Test Task")
        self.assertEqual(task.status, "TODO")
        self.assertEqual(task.priority, "HIGH")
        self.assertFalse(task.is_deleted)
        self.assertEqual(task.collaborators, [])
        self.assertEqual(task.task_specific_tags, [])

    def test_task_serialization(self) -> None:
        """Verifies Task dictionary serialization and deserialization."""
        task_data: Dict[str, Any] = {
            "title": "Serial Task",
            "description": "Serial Desc",
            "priority": "LOW",
            "status": "IN_PROGRESS",
            "task_specific_tags": ["tag1", "tag2"]
        }
        task = Task.from_dict(task_data)
        self.assertEqual(task.title, "Serial Task")
        self.assertEqual(task.description, "Serial Desc")
        
        serialized = task.to_dict()
        self.assertEqual(serialized["title"], "Serial Task")
        self.assertEqual(serialized["status"], "IN_PROGRESS")
        self.assertEqual(serialized["task_specific_tags"], ["tag1", "tag2"])

    def test_task_field_update_diffs(self) -> None:
        """Verifies update_fields accurately calculates change diffs."""
        task = Task(title="Original Title", priority="LOW")
        update_data = {
            "title": "New Title",
            "priority": "HIGH",
            "description": "New Description"
        }
        diffs = task.update_fields(update_data)
        
        # Verify changes list
        fields_changed = [d["field"] for d in diffs]
        self.assertIn("title", fields_changed)
        self.assertIn("priority", fields_changed)
        self.assertIn("description", fields_changed)
        
        # Check actual values on task
        self.assertEqual(task.title, "New Title")
        self.assertEqual(task.priority, "HIGH")
        self.assertEqual(task.description, "New Description")

    def test_task_soft_delete_and_restore(self) -> None:
        """Verifies soft-deletion and restoration timestamps and flags."""
        task = Task(title="Delete Me")
        self.assertFalse(task.is_deleted)
        self.assertIsNone(task.deleted_at)
        
        task.soft_delete()
        self.assertTrue(task.is_deleted)
        self.assertIsNotNone(task.deleted_at)
        
        task.restore()
        self.assertFalse(task.is_deleted)
        self.assertIsNone(task.deleted_at)


class RepositoryTests(unittest.TestCase):
    """
    Unit tests for repository implementations and database context.
    """
    def setUp(self) -> None:
        self.db_path = "db_unit_test.json"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_database_context_locking_and_crud(self) -> None:
        """Verifies DatabaseContext reads, writes, commits, and locks file correctly."""
        with DatabaseContext(self.db_path) as db:
            self.assertIsNotNone(db.tasks)
            self.assertIsNotNone(db.history)
            
            task = Task(title="Repo Task")
            db.tasks.add(task)
            
            log = HistoryLog(task_id=task.task_id, action="CREATED")
            db.history.add(log)
            
            # Context exit commits automatically
        
        # Re-open database context to check if values are loaded
        with DatabaseContext(self.db_path) as db:
            loaded_task = db.tasks.get(task.task_id)
            self.assertIsNotNone(loaded_task)
            self.assertEqual(loaded_task.title, "Repo Task")
            
            loaded_history = db.history.get_all(task_id=task.task_id)
            self.assertEqual(len(loaded_history), 1)
            self.assertEqual(loaded_history[0].action, "CREATED")


class TaskServiceTests(unittest.TestCase):
    """
    Unit tests for the TaskService business logic and time-travel rollback.
    """
    def setUp(self) -> None:
        self.db_path = "db_service_unit_test.json"
        self.service = TaskService(self.db_path)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_and_update_task_service(self) -> None:
        """Verifies TaskService manages creations and logs history events."""
        task_data = {"title": "Service Task", "description": "Service Desc"}
        created = self.service.create_task(task_data)
        task_id = created["task_id"]
        
        # Check task retrieval
        task = self.service.get_task_by_id(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task["title"], "Service Task")
        
        # Check creation log
        history = self.service.get_task_history(task_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["action"], "CREATED")
        
        # Check update workflow
        self.service.update_task(task_id, {"title": "Updated Title"})
        updated_task = self.service.get_task_by_id(task_id)
        self.assertEqual(updated_task["title"], "Updated Title")
        
        # Check update log
        history = self.service.get_task_history(task_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["action"], "UPDATED")

    def test_time_travel_reconstruction_and_rollback(self) -> None:
        """Verifies state playback reconstruction and rollback triggers."""
        task = self.service.create_task({"title": "Initial Title", "priority": "LOW"})
        task_id = task["task_id"]
        
        # Get creation history ID
        hist1 = self.service.get_task_history(task_id)
        create_log_id = hist1[0]["history_id"]
        
        # Update title
        self.service.update_task(task_id, {"title": "Title V2"})
        hist2 = self.service.get_task_history(task_id)
        update_log_id = hist2[0]["history_id"]
        
        # Verify reconstruction at creation state
        reconstructed = self.service.get_reconstructed_task(task_id, create_log_id)
        self.assertEqual(reconstructed["reconstructed"]["title"], "Initial Title")
        self.assertEqual(reconstructed["reconstructed"]["priority"], "LOW")
        
        # Verify rollback
        self.service.rollback_task(task_id, create_log_id)
        live_task = self.service.get_task_by_id(task_id)
        self.assertEqual(live_task["title"], "Initial Title")
        
        # Verify rollback log
        history = self.service.get_task_history(task_id)
        self.assertEqual(len(history), 3) # Created + Updated + Rollback log
        self.assertEqual(history[0]["action"], "ROLLBACK")
