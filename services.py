import datetime
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
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
        self.ai_analyzer: "AiTaskAnalyzerService" = AiTaskAnalyzerService(db_file_path)

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
        """Creates a new task, runs instant AI analysis, and logs the creation event."""
        with DatabaseContext(self.db_file_path) as db:
            # Instantiate Entity
            task = Task.from_dict(task_data)
            
            # Run instant AI analysis pass before saving
            self.ai_analyzer.analyze_task(task, db, during_creation=True)
            
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
        """Updates a task, diffs fields, triggers AI analysis on title changes, and logs history."""
        with DatabaseContext(self.db_file_path) as db:
            task = db.tasks.get(task_id)
            if not task:
                raise ValueError(f"Task with ID {task_id} not found.")

            # Detect title changes to trigger AI re-analysis
            title_changing = "title" in update_data and update_data["title"] != task.title

            # Perform update and retrieve list of changes
            diffs = task.update_fields(update_data)
            
            if title_changing:
                self.ai_analyzer.analyze_task(task, db)
            
            if diffs or title_changing:
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

    def delete_task_permanently(self, task_id: str) -> None:
        """Permanently deletes a task and all history events associated with it."""
        with DatabaseContext(self.db_file_path) as db:
            db.tasks.delete_permanently(task_id)
            db._history[:] = [h for h in db._history if h.task_id != task_id]


class AiTaskAnalyzerService:
    """
    Background analyzer service that monitors tasks for title updates
    and dynamically populates task metadata using keyword heuristics.
    """
    def __init__(self, db_file_path: str = "db.json") -> None:
        """Initializes the background AI analyzer service."""
        self.db_file_path: str = db_file_path
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Launches the background daemon thread loop."""
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        """Stops the background loop thread execution."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _run_loop(self) -> None:
        """Executes the loop checking for pending tasks every 2 seconds."""
        while self.running:
            try:
                self.analyze_pending_tasks()
            except Exception as e:
                print(f"Error in AiTaskAnalyzerService background loop: {e}")
            time.sleep(2)

    def analyze_pending_tasks(self) -> None:
        """Scans db tasks and triggers analysis on unanalyzed titles."""
        with DatabaseContext(self.db_file_path) as db:
            for task in db.tasks.get_all(include_deleted=True):
                placeholder = task.app_features_placeholder or {}
                has_changed = placeholder.get("ai_analyzed_title") != task.title
                outdated_version = placeholder.get("ai_analyzed_version") != 2
                if has_changed or outdated_version:
                    self.analyze_task(task, db)
                    db.tasks.update(task)

    def _parse_priority(self, title_lower: str) -> Optional[str]:
        """Maps urgency keywords found in titles to priority values."""
        if any(w in title_lower for w in ["urgent", "asap", "immediate", "critical", "blocking", "emergency"]):
            return "HIGH"
        if any(w in title_lower for w in ["low priority", "later", "backlog", "low", "minor", "someday", "optional"]):
            return "LOW"
        if any(w in title_lower for w in ["medium", "normal", "moderate", "routine"]):
            return "MEDIUM"
        return None

    def _parse_tags(self, title_lower: str, current_tags: List[str]) -> List[str]:
        """Detects keyword markers and hashtags to build task tags list."""
        new_tags = list(current_tags)
        if any(w in title_lower for w in ["cheetah", "ccf", "wildlife", "zoology", "animal"]):
            for t in ["Wildlife Conservation", "Zoology", "CCF"]:
                if t not in new_tags:
                    new_tags.append(t)
        if any(w in title_lower for w in ["plex", "dexter", "backup", "tower", "server"]):
            for t in ["Plex", "Backup", "Server"]:
                if t not in new_tags:
                    new_tags.append(t)
        if any(w in title_lower for w in ["caffeine", "coffee", "drink", "tea"]):
            for t in ["Beverage", "Caffeine"]:
                if t not in new_tags:
                    new_tags.append(t)
        if any(w in title_lower for w in ["test", "unittest", "linter", "docs"]):
            for t in ["Testing", "DevDocs"]:
                if t not in new_tags:
                    new_tags.append(t)
        
        hashtags = re.findall(r"#(\w+)", title_lower)
        for tag in hashtags:
            formatted_tag = tag.capitalize()
            if formatted_tag not in new_tags:
                new_tags.append(formatted_tag)
        return new_tags

    def _parse_due_date(self, title_lower: str) -> Optional[str]:
        """Identifies relative date expressions and converts them to ISO deadlines."""
        now = datetime.datetime.now(datetime.timezone.utc)
        if "today" in title_lower:
            return now.replace(hour=18, minute=0, second=0, microsecond=0).isoformat()
        if "tomorrow" in title_lower:
            tomorrow = now + datetime.timedelta(days=1)
            return tomorrow.replace(hour=18, minute=0, second=0, microsecond=0).isoformat()
        if "next week" in title_lower:
            next_w = now + datetime.timedelta(days=7)
            return next_w.replace(hour=18, minute=0, second=0, microsecond=0).isoformat()
        return None

    def _parse_media_and_bookmarks(self, title_lower: str) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
        """Auto-attaches media metadata and timestamps for video co-watching tasks."""
        if "cheetah" in title_lower or "lindsay nikole" in title_lower:
            media = {
                "platform": "YouTube",
                "original_url": "https://youtu.be/TStDUEBNGCM?si=5cSDsE9M9U8vYaeH",
                "video_id": "TStDUEBNGCM",
                "title": "Saving Cheetahs | Returning to Cheetah Conservation Fund | Lindsay Nikole",
                "creator_or_channel": "Lindsay Nikole",
                "publish_date": "2025-08-28",
                "duration_iso_8601": "PT46M1S",
                "duration_seconds": 2761,
                "thumbnail_url": "https://i.ytimg.com/vi/TStDUEBNGCM/maxresdefault.jpg",
                "metrics_at_creation": {"view_count": 138052, "like_count": 15092}
            }
            bookmarks = [
                {"timestamp": "[00:04:55]", "label": "Interview with Dr. Laurie Marker (CCF Founder)", "note": "Discusses wild population."},
                {"timestamp": "[00:06:15]", "label": "The Livestock Guarding Dog Program", "note": "Livestock guarding dogs program details."},
                {"timestamp": "[00:08:25]", "label": "Three Core Rules of Livestock Management", "note": "Rules for local farmers."},
                {"timestamp": "[00:19:25]", "label": "Cheetah Meat Prep & 'Predator Powder'", "note": "Feeding orphan cheetahs cc."},
                {"timestamp": "[00:24:45]", "label": "Release Candidates Criteria", "note": "Atango and Zephyr release suitability."}
            ]
            return "VIDEO_LINK", media, bookmarks
        return None, None, None

    def _generate_description(self, title: str, update_data: Dict[str, Any]) -> str:
        """Synthesizes a descriptive text summary explaining the AI configurations applied."""
        desc_parts = [f"AI-generated details for: '{title}'."]
        if "priority" in update_data:
            desc_parts.append(f"Priority evaluated as {update_data['priority']}.")
        if "task_specific_tags" in update_data:
            tags_str = ", ".join(update_data["task_specific_tags"])
            desc_parts.append(f"Auto-tagged: {tags_str}.")
        if "due_date" in update_data:
            desc_parts.append("Set due date calendar reminder.")
        if "media_metadata" in update_data:
            desc_parts.append("Attached CCF cheetah co-watch video.")
        return " ".join(desc_parts)

    def _capitalize_sentences(self, text: str) -> str:
        """Capitalizes the first letter of each sentence in a text string."""
        if not text:
            return ""
        sentences = re.split(r'(\s*[\.\!\?]\s*)', text)
        result = []
        for part in sentences:
            if re.match(r'^\s*[\.\!\?]\s*$', part):
                result.append(part)
            else:
                stripped = part.lstrip()
                if stripped:
                    leading_whitespace = part[:len(part)-len(stripped)]
                    capitalized = stripped[0].upper() + stripped[1:]
                    result.append(leading_whitespace + capitalized)
                else:
                    result.append(part)
        return "".join(result)

    def analyze_task(self, task: Task, db: DatabaseContext, during_creation: bool = False) -> bool:
        """Main orchestrator parsing a task's title and applying fields changes."""
        title_lower = task.title.lower()
        update_data: Dict[str, Any] = {}

        cap_title = self._capitalize_sentences(task.title)
        if cap_title != task.title:
            update_data["title"] = cap_title

        priority = self._parse_priority(title_lower)
        if priority and task.priority != priority:
            update_data["priority"] = priority

        tags = self._parse_tags(title_lower, task.task_specific_tags)
        if tags != task.task_specific_tags:
            update_data["task_specific_tags"] = tags

        due = self._parse_due_date(title_lower)
        if due and task.due_date != due:
            update_data["due_date"] = due

        att_type, media, bookmarks = self._parse_media_and_bookmarks(title_lower)
        if att_type and not task.attachment_type:
            update_data["attachment_type"] = att_type
            update_data["media_metadata"] = media
            update_data["curated_video_bookmarks"] = bookmarks

        if not task.description or not task.description.strip():
            desc = self._generate_description(update_data.get("title", task.title), update_data)
            update_data["description"] = desc
        elif task.description:
            cap_desc = self._capitalize_sentences(task.description)
            if cap_desc != task.description:
                update_data["description"] = cap_desc

        placeholder = task.app_features_placeholder or {}
        placeholder["ai_analyzed_title"] = update_data.get("title", task.title)
        placeholder["ai_analyzed"] = True
        placeholder["ai_analyzed_version"] = 2
        task.app_features_placeholder = placeholder

        if update_data:
            diffs = task.update_fields(update_data)
            if diffs:
                if not during_creation:
                    log = HistoryLog(task_id=task.task_id, action="UPDATED", details={"changes": diffs, "ai_processed": True})
                    db.history.add(log)
                return True
        return False

