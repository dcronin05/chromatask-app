import datetime
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class Entity(ABC):
    """
    Abstract base entity that defines metadata common to all domain entities.
    """
    def __init__(self, 
                 entity_id: Optional[str] = None, 
                 created_at: Optional[str] = None, 
                 updated_at: Optional[str] = None) -> None:
        """
        Initializes an entity with a unique identifier and timestamps.
        """
        self.id: str = entity_id or str(uuid.uuid4())
        now: str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.created_at: str = created_at or now
        self.updated_at: str = updated_at or now

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize entity properties into a dictionary.
        """
        pass


class Task(Entity):
    """
    Represents a task within the task manager.
    """
    def __init__(self, 
                 task_id: Optional[str] = None, 
                 title: str = "", 
                 description: str = "", 
                 status: str = "TODO", 
                 priority: str = "HIGH", 
                 created_at: Optional[str] = None, 
                 updated_at: Optional[str] = None,
                 due_date: Optional[str] = None, 
                 completed_at: Optional[str] = None,
                 is_deleted: bool = False,
                 deleted_at: Optional[str] = None,
                 collaborators: Optional[List[Dict[str, Any]]] = None, 
                 attachment_type: Optional[str] = None, 
                 media_metadata: Optional[Dict[str, Any]] = None,
                 task_specific_tags: Optional[List[str]] = None, 
                 curated_video_bookmarks: Optional[List[Dict[str, Any]]] = None, 
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Initializes a task with title, priority, status, and related co-watching metadata.
        """
        super().__init__(entity_id=task_id, created_at=created_at, updated_at=updated_at)
        
        self.title: str = title
        self.description: str = description
        self.status: str = status
        self.priority: str = priority
        self.due_date: Optional[str] = due_date
        self.completed_at: Optional[str] = completed_at
        self.is_deleted: bool = is_deleted
        self.deleted_at: Optional[str] = deleted_at
        self.collaborators: List[Dict[str, Any]] = collaborators or []
        self.attachment_type: Optional[str] = attachment_type
        self.media_metadata: Optional[Dict[str, Any]] = media_metadata
        self.task_specific_tags: List[str] = task_specific_tags or []
        self.curated_video_bookmarks: List[Dict[str, Any]] = curated_video_bookmarks or []
        self.metadata: Dict[str, Any] = metadata or {}

    @property
    def task_id(self) -> str:
        """
        Returns the unique identifier of the task.
        """
        return self.id

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes the task object into a dictionary for JSON representation.
        """
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "due_date": self.due_date,
            "completed_at": self.completed_at,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "collaborators": self.collaborators,
            "attachment_type": self.attachment_type,
            "media_metadata": self.media_metadata,
            "task_specific_tags": self.task_specific_tags,
            "curated_video_bookmarks": self.curated_video_bookmarks,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """
        Creates a Task instance from a dictionary.
        """
        return cls(
            task_id=data.get("task_id"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", "TODO"),
            priority=data.get("priority", "HIGH"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            due_date=data.get("due_date"),
            completed_at=data.get("completed_at"),
            is_deleted=data.get("is_deleted", False),
            deleted_at=data.get("deleted_at"),
            collaborators=data.get("collaborators", []),
            attachment_type=data.get("attachment_type"),
            media_metadata=data.get("media_metadata"),
            task_specific_tags=data.get("task_specific_tags", []),
            curated_video_bookmarks=data.get("curated_video_bookmarks", []),
            metadata=data.get("metadata") or data.get("app_features_placeholder", {})
        )

    def update_fields(self, new_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Updates task fields and returns a list of differences for audit logs.
        Format: [{'field': name, 'old': old_val, 'new': new_val}]
        """
        diffs: List[Dict[str, Any]] = []
        trackable_fields: List[str] = [
            "title", "description", "status", "priority", 
            "due_date", "collaborators", "task_specific_tags", "curated_video_bookmarks"
        ]

        for field in trackable_fields:
            if field in new_data:
                old_val: Any = getattr(self, field)
                new_val: Any = new_data[field]
                
                # Check for equivalence (comparing serialized values for lists/dicts)
                if old_val != new_val:
                    # Specific date checks to ignore timezone mismatch differences in strings
                    if field == "due_date" and old_val and new_val:
                        if old_val[:16] == new_val[:16]:
                            continue
                            
                    diffs.append({
                        "field": field,
                        "old": old_val,
                        "new": new_val
                    })
                    setattr(self, field, new_val)

        if diffs:
            self.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Auto-handle completion date
            if "status" in new_data:
                if new_data["status"] == "COMPLETED":
                    self.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                else:
                    self.completed_at = None
                    
        return diffs

    def soft_delete(self) -> None:
        """
        Marks the task as soft-deleted and sets the deleted timestamp.
        """
        self.is_deleted = True
        self.deleted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.updated_at = self.deleted_at

    def restore(self) -> None:
        """
        Restores a soft-deleted task, removing the deleted flag and timestamp.
        """
        self.is_deleted = False
        self.deleted_at = None
        self.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()


class HistoryLog(Entity):
    """
    Represents an audit event log for a specific task.
    """
    def __init__(self, 
                 history_id: Optional[str] = None, 
                 task_id: str = "", 
                 action: str = "CREATED", 
                 timestamp: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None) -> None:
        """
        Initializes a history log event.
        """
        super().__init__(entity_id=history_id, created_at=timestamp, updated_at=timestamp)
        self.task_id: str = task_id
        self.action: str = action
        self.details: Dict[str, Any] = details or {}

    @property
    def history_id(self) -> str:
        """
        Returns the unique identifier for the history log.
        """
        return self.id

    @property
    def timestamp(self) -> str:
        """
        Returns the timestamp of when the event occurred.
        """
        return self.created_at

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes the history log object into a dictionary.
        """
        return {
            "history_id": self.history_id,
            "task_id": self.task_id,
            "action": self.action,
            "timestamp": self.timestamp,
            "details": self.details
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryLog":
        """
        Creates a HistoryLog instance from a dictionary.
        """
        return cls(
            history_id=data.get("history_id"),
            task_id=data.get("task_id", ""),
            action=data.get("action", "CREATED"),
            timestamp=data.get("timestamp"),
            details=data.get("details", {})
        )
