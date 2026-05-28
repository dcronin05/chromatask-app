import datetime
import uuid
from abc import ABC, abstractmethod

class Entity(ABC):
    """
    Abstract base entity that defines metadata common to all domain entities.
    """
    def __init__(self, entity_id=None, created_at=None, updated_at=None):
        self.id = entity_id or str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    @abstractmethod
    def to_dict(self):
        """Serialize entity to a dictionary."""
        pass


class Task(Entity):
    """
    Represents a task within the task manager.
    """
    def __init__(self, 
                 task_id=None, 
                 title="", 
                 description="", 
                 status="TODO", 
                 priority="HIGH", 
                 created_at=None, 
                 updated_at=None,
                 due_date=None, 
                 completed_at=None,
                 is_deleted=False,
                 deleted_at=None,
                 collaborators=None, 
                 attachment_type=None, 
                 media_metadata=None,
                 task_specific_tags=None, 
                 curated_video_bookmarks=None, 
                 app_features_placeholder=None):
        
        # Call base constructor using task_id if provided
        super().__init__(entity_id=task_id, created_at=created_at, updated_at=updated_at)
        
        self.title = title
        self.description = description
        self.status = status
        self.priority = priority
        self.due_date = due_date
        self.completed_at = completed_at
        self.is_deleted = is_deleted
        self.deleted_at = deleted_at
        self.collaborators = collaborators or []
        self.attachment_type = attachment_type
        self.media_metadata = media_metadata
        self.task_specific_tags = task_specific_tags or []
        self.curated_video_bookmarks = curated_video_bookmarks or []
        self.app_features_placeholder = app_features_placeholder or {}

    @property
    def task_id(self):
        return self.id

    def to_dict(self):
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
            "app_features_placeholder": self.app_features_placeholder
        }

    @classmethod
    def from_dict(cls, data):
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
            app_features_placeholder=data.get("app_features_placeholder", {})
        )

    def update_fields(self, new_data):
        """
        Updates task fields and returns a list of differences for audit logs.
        Format: [{'field': name, 'old': old_val, 'new': new_val}]
        """
        diffs = []
        trackable_fields = [
            "title", "description", "status", "priority", 
            "due_date", "collaborators", "task_specific_tags", "curated_video_bookmarks"
        ]

        for field in trackable_fields:
            if field in new_data:
                old_val = getattr(self, field)
                new_val = new_data[field]
                
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

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.updated_at = self.deleted_at

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()


class HistoryLog(Entity):
    """
    Represents an audit event log for a specific task.
    """
    def __init__(self, history_id=None, task_id="", action="CREATED", timestamp=None, details=None):
        super().__init__(entity_id=history_id, created_at=timestamp, updated_at=timestamp)
        self.task_id = task_id
        self.action = action
        self.details = details or {}

    @property
    def history_id(self):
        return self.id

    @property
    def timestamp(self):
        return self.created_at

    def to_dict(self):
        return {
            "history_id": self.history_id,
            "task_id": self.task_id,
            "action": self.action,
            "timestamp": self.timestamp,
            "details": self.details
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            history_id=data.get("history_id"),
            task_id=data.get("task_id", ""),
            action=data.get("action", "CREATED"),
            timestamp=data.get("timestamp"),
            details=data.get("details", {})
        )
