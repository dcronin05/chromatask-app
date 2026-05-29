# ChromaTask OOP Architectural Design Guide

ChromaTask operates on a modular, decoupled Object-Oriented Design (OOD) separating storage technology, application logic, and transportation layers.

---

## 1. Architectural Layers

The backend codebase is divided into four distinct components to enforce the **Separation of Concerns**:

```
+---------------------------------------------+
|               server.py (API)               |  <- Controller / Router (Flask)
+---------------------------------------------+
                       |
                       v
+---------------------------------------------+
|             services.py (Tasks)             |  <- Business Use Cases & Logic
+---------------------------------------------+
                       |
                       v
+---------------------------------------------+
|          repositories.py (Database)         |  <- Database Abstraction (flock Locked)
+---------------------------------------------+
                       |
                       v
+---------------------------------------------+
|              models.py (Domain)             |  <- Core Domain Entities
+---------------------------------------------+
```

### A. The Domain Model Layer (`models.py`)
- Defines the data entities that represent tasks and logs.
- Extends the abstract base class `Entity`, which automatically handles entity identifiers (UUIDs) and creation/update timestamps.
- The `Task` entity encapsulates task states and performs field comparison diff checks when properties are updated, returning detailed information for history logging.

### B. The Data Access Layer (`repositories.py`)
- Provides an abstract interface `BaseRepository` enforcing standard CRUD contracts.
- Decouples storage formats from business logic. The `JSONTaskRepository` and `JSONHistoryRepository` classes manipulate in-memory dictionary states.
- The `DatabaseContext` acts as the **Unit of Work** context manager. It manages opening the database file, acquiring an exclusive Unix lock (`flock`), parsing files into Domain Entity objects, and writing committed memory state back to disk on exit.

### C. The Business Service Layer (`services.py`)
- Exposes clean business methods like `create_task`, `update_task`, `soft_delete_task`, and `restore_task`.
- Coordinates operations inside `DatabaseContext` transactions.
- Automatically calculates differences on task edits and inserts chronological `HistoryLog` entries detailing changes.

### D. The Controller Route Layer (`server.py`)
- Maps HTTP REST paths to service actions.
- Instantiates the `TaskService` and handles JSON serialization/deserialization.
- Completely separate from backend logic; can be swapped for a command-line interface (CLI) or a different API framework without touching business code.

---

## 2. Dev Docs Strategy Pattern

The programmatic documentation and linter console uses the **Strategy Pattern** to ensure language extensibility:
- **`BaseCodeAnalyzer`**: Abstract base class requiring an `analyze()` implementation.
- **`PythonCodeAnalyzer`**: Analyzes Python source code syntax trees via the native `ast` module.
- **`JSCodeAnalyzer`**: Audits JavaScript source files using regex syntax checks.
- **`CSSCodeAnalyzer`**: Audits CSS stylesheets for theme and variable conformity.
- **`HTMLCodeAnalyzer`**: Audits HTML markup for accessibility and style conformance.
- **`DocService`**: Orchestrates scanning the project, mapping extensions (e.g. `.py` ➜ `PythonCodeAnalyzer`, `.js` ➜ `JSCodeAnalyzer`, etc.), and building a unified codebase dashboard.

---

## 3. Frontend Task Display & Dynamic Schema Engine

ChromaTask enforces a single source of truth for display structures, dynamically matching backend database configurations:

### A. Display Configurations (`TASK_DISPLAY_CONFIG`)
Located in `src/main.js`, this unified registry maps task properties (`title`, `description`, `status`, `priority`, `due_date`, `task_specific_tags`, `collaborators`, and `curated_video_bookmarks`). Each entry specifies:
- `key`: The JSON data property name.
- `label`: Friendly header/label text.
- `render()`: Standard formatting function for textual display.
- `equals()`: Equivalence checker for version comparing and diff tracking.
- `renderCard()` / `renderDetail()`: Dynamic DOM constructors for task card rendering and detail drawer input fields.

### B. Dynamic Schema Engine (`syncDynamicFields`)
To support ad-hoc metadata fields dynamically added to the database (or custom columns):
- scans all task records at runtime for unrecognized keys.
- dynamically injects a configuration entry into `TASK_DISPLAY_CONFIG` to build corresponding input fields and timeline descriptors.
- **Object Filtering**: Auto-registered fields skip nested object shapes (like `media_metadata`) by running pre-scan checks on all tasks to prevent formatting conflicts and invalid `[object Object]` rendering outputs.
- **Auto-Pruning**: Dynamically removes configuration entries from the active list if their database values are cleared or re-categorized as system-ignored keys.
