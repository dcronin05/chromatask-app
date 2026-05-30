# ChromaTask Database & Concurrency Guide

ChromaTask uses a persistent, file-based JSON database (`db.json`) located in the root of the project.

---

## 1. Database Schema

The database contains two core top-level arrays: `tasks` and `history`.

### A. The Tasks Schema
Contains the active and archived tasks in the system:
* `task_id` (str): Unique UUID.
* `title` (str): Task title.
* `description` (str): Task detailed description.
* `status` (str): Current workflow column (`TODO`, `IN_PROGRESS`, `COMPLETED`).
* `priority` (str): Importance (`LOW`, `MEDIUM`, `HIGH`).
* `created_at` (str): ISO 8601 creation timestamp.
* `updated_at` (str): ISO 8601 last-modified timestamp.
* `due_date` (str | null): Optional ISO 8601 due date.
* `completed_at` (str | null): ISO 8601 completion timestamp (set when status is changed to `COMPLETED`).
* `is_deleted` (bool): Flag indicating if the task is soft-deleted.
* `deleted_at` (str | null): ISO 8601 timestamp representing when the task was deleted.
* `collaborators` (list): Array of dictionaries containing:
  - `user_id` (str)
  - `name` (str)
  - `role` (str)
  - `status` (str): Invitation status (`INVITED`, `JOINED`, `DECLINED`).
* `attachment_type` (str | null): Type of attachment (e.g. `"VIDEO_LINK"`).
* `media_metadata` (dict | null): Metadata for video links (video_id, title, views, platform, creator).
* `task_specific_tags` (list): String tags (e.g. `["Zoology", "Conservation"]`).
* `curated_video_bookmarks` (list): Chronologically sorted video bookmarks containing:
  - `timestamp` (str): Format `[MM:SS]` or `[HH:MM:SS]`.
  - `label` (str): Bookmark name.
  - `note` (str | null): Optional description notes.
* `app_features_placeholder` (dict): Placeholder dictionary for custom application features and metadata parameters.

### B. The History Schema (Audit Log)
Tracks every modification made to any task:
* `history_id` (str): Unique UUID.
* `task_id` (str): Reference to the modified task.
* `action` (str): Type of event (`CREATED`, `UPDATED`, `DELETED`, `RESTORED`, `ROLLBACK`).
* `timestamp` (str): ISO 8601 log timestamp.
* `details` (dict): Event metadata:
  - For `CREATED` and `DELETED` events: Contains `{"title": task_title}`.
  - For `UPDATED` events: Contains `{"changes": [{"field": name, "old": old_value, "new": new_value}]}` mapping exactly what properties were changed.
  - For `ROLLBACK` events: Contains `{"rollback_to_history_id": history_id, "changes": [{"field": name, "old": old_value, "new": new_value}]}` detailing the reverted changes.

---

## 2. Concurrency Control & File Locking

To prevent race conditions and write-collisions when multiple frontend requests or processes write to `db.json` simultaneously, ChromaTask implements **Exclusive Locking**:

* The `DatabaseContext` class handles file transactions using the Python standard library's `fcntl` module.
* Upon entering a `with DatabaseContext() as db:` block:
  1. The server opens the `db.json` file descriptor.
  2. It acquires an exclusive UNIX advisory lock: `fcntl.flock(fd, fcntl.LOCK_EX)`. This blocks other threads or processes from acquiring the lock until this block exits.
  3. Once the lock is acquired, the file is read and loaded into memory objects.
* During execution:
  - Modifying operations are kept in memory to minimize slow disk I/O.
* Upon exiting the `with` block:
  1. If no exception occurred, `db.commit()` runs, which serializes memory lists back to the file.
  2. The database lock is released: `fcntl.flock(fd, fcntl.LOCK_UN)`.
  3. The file descriptor is safely closed.
