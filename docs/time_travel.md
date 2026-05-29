# Task Time-Travel & Audit Trail Rollback Guide

ChromaTask features an advanced Git-like time-travel system allowing developers and users to view historical task versions side-by-side, inspect details of changes, and roll back task data to any point in the audit trail.

---

## 1. Reverse-Playback State Reconstruction

To prevent storing duplicate copy snapshots in `db.json`, the state reconstruction algorithm runs dynamically **in-memory** on demand:

### State Reconstruction Flow
```
[ Current Live State ] 
          │
          ▼
[ Chronological Logs (Reverse Order) ]
          │  (Loop backwards)
          ├──► Revert UPDATE / ROLLBACK field changes (apply 'old' value)
          ├──► Revert DELETED actions (is_deleted = False)
          └──► Revert RESTORED actions (is_deleted = True)
          │
          ▼
[ Stop at target history_id ] ──► Returns Reconstructed Task State
```

- **Efficiency**: Only changes that occurred *after* the target event are undone.
- **Independence**: Reconstruction does not modify the live database state, making it completely read-only and safe for browsing.

---

## 2. Visual Diff Visualizations

The timeline console provides two distinct levels of visual diff inspection:

### A. Inline Diff Pane
Clicking the **Show Highlighted Diff** button on any timeline entry expands an inline grid showing the differences:
- **Red background (`.diff-deleted`)**: Represents removed values or old states.
- **Green background (`.diff-added`)**: Represents added values or new states.
- **Unchanged values (`.diff-unchanged`)**: Rendered in a muted neutral style.
- Handles list-based properties (like tags and collaborators) by diffing item differences.

### B. Time-Travel Version Inspector
Clicking the **Clock Icon** next to any timeline log opens a side-by-side split comparison:
- **Left Column**: Historical task properties immediately after the event took place.
- **Right Column**: Current live task state.
- Diff cards that vary between the two states are highlighted in gold to show exactly what changes a rollback would make.

---

## 3. Rollback Operations

Clicking **Rollback to this Version** in the Inspector overlay triggers a database transaction write:
1. Reconstructs the target state in-memory.
2. Calls the model's `update_fields()` method to diff the target state against the current live state.
3. Saves the modifications back to the repository.
4. Inserts a new `ROLLBACK` audit event into the task timeline history logs, documenting the reversion.
