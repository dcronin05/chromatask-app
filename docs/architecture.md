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

---

## 4. Glassmorphic Sidebar Design & UI State Persistence

ChromaTask features a premium floating sidebar with dynamic navigation counters, hover tooltips, and robust state persistence.

### A. Sidebar Layout and Interactions (`index.html` & `src/style.css`)
- **Glassmorphic Theme**: Styled using `.app-sidebar` as a floating glassmorphic panel with borders and soft box-shadows.
- **Collapsible Toggle**: Managed via `#btn-toggle-sidebar`. When collapsed, the sidebar transitions from `280px` to `84px` wide. Labels, counters, and tags are hidden with transition opacity, while `#btn-reset-db` shrinks to an icon.
- **Frosted Tooltips**: Built using pure CSS `::after` tooltips on `.collapsed .nav-item` to display labels and counts on hover.

### B. Dynamic Navigation Counters (`src/main.js`)
- **Real-Time Calculation**: The `updateSidebarCounters(tasksList)` function calculates active task counts, archived counts, and specific priority counts (`high`, `medium`, `low`) directly from the client's current tasks list.
- **Sidebar Integration**: Counters are rendered in real-time in `.nav-counter` element pills within each navigation item.
- **Docs Health Badge**: Calculates the latest codebase quality health score dynamically and binds it to the `#counter-docs` element using the `.docs-badge` styling.

### C. UI State Persistence (`src/main.js`)
To prevent page reloads or server restarts from resetting the user's active context, key variables are serialized to and from `localStorage`:
- `currentView`: The active layout tab (e.g. Dashboard, Archive, Dev Docs).
- `activeFilters`: Selected priorities, search query text, or active tags.
- `currentDocsSubtab`: The active developer documentation sub-tab.
- `activeTaskId`: Automatically tracks the open task detail drawer to reopen it on reload.
- `chromatask_sidebar_collapsed`: Remembers whether the user preferred the collapsed or expanded sidebar state.
- **State Clearing**: All stored settings are wiped from `localStorage` whenever `apiResetDatabase` resets the task database.

---

## 5. Programmatic API Reference

<!-- DYNAMIC_API_REFERENCE_START -->
The following reference lists all modules, classes, and public functions detected programmatically via AST:

### 📂 [models.py](file:///Users/dcronin05/Library/Mobile Documents/com~apple~CloudDocs/app_development/todo_app/models.py)
- **Lines of Code**: 242 | **Comments**: 3

#### Class: `Entity`
> Abstract base entity that defines metadata common to all domain entities.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `(self, entity_id, created_at, updated_at)` | 11 | Initializes an entity with a unique identifier and timestamps. |
| `to_dict` | `(self)` | 5 | Serialize entity properties into a dictionary. |

#### Class: `Task`
> Represents a task within the task manager.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `(self, task_id, title, description, status, priority, created_at, updated_at, due_date, completed_at, is_deleted, deleted_at, collaborators, attachment_type, media_metadata, task_specific_tags, curated_video_bookmarks, app_features_placeholder)` | 37 | Initializes a task with title, priority, status, and related co-watching metadata. |
| `task_id` | `(self)` | 5 | Returns the unique identifier of the task. |
| `to_dict` | `(self)` | 23 | Serializes the task object into a dictionary for JSON representation. |
| `from_dict` | `(cls, data)` | 23 | Creates a Task instance from a dictionary. |
| `update_fields` | `(self, new_data)` | 41 | Updates task fields and returns a list of differences for audit logs. |
| `soft_delete` | `(self)` | 7 | Marks the task as soft-deleted and sets the deleted timestamp. |
| `restore` | `(self)` | 7 | Restores a soft-deleted task, removing the deleted flag and timestamp. |

#### Class: `HistoryLog`
> Represents an audit event log for a specific task.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `(self, history_id, task_id, action, timestamp, details)` | 13 | Initializes a history log event. |
| `history_id` | `(self)` | 5 | Returns the unique identifier for the history log. |
| `timestamp` | `(self)` | 5 | Returns the timestamp of when the event occurred. |
| `to_dict` | `(self)` | 11 | Serializes the history log object into a dictionary. |
| `from_dict` | `(cls, data)` | 11 | Creates a HistoryLog instance from a dictionary. |

---

### 📂 [repositories.py](file:///Users/dcronin05/Library/Mobile Documents/com~apple~CloudDocs/app_development/todo_app/repositories.py)
- **Lines of Code**: 212 | **Comments**: 11

#### Class: `BaseRepository`
> Abstract interface for repository operations (CRUD).

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `get` | `(self, entity_id)` | 5 | Retrieves a single entity by its identifier. |
| `get_all` | `(self)` | 5 | Retrieves all entities stored in the repository. |
| `add` | `(self, entity)` | 5 | Adds a new entity to the repository. |
| `delete` | `(self, entity_id)` | 5 | Deletes or soft-deletes an entity from the repository. |

#### Class: `JSONTaskRepository`
> Concrete task repository handling JSON-backed data.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `(self, tasks_dict)` | 5 | Initializes the repository with a dictionary of Task objects. |
| `get` | `(self, task_id)` | 5 | Retrieves a Task object by its unique identifier. |
| `get_all` | `(self, include_deleted)` | 8 | Retrieves all active tasks, or all tasks (including deleted) if include_deleted is True. |
| `add` | `(self, task)` | 5 | Adds a new Task to the repository. |
| `update` | `(self, task)` | 5 | Updates an existing Task. Since memory states use references, this maps state key. |
| `delete` | `(self, task_id)` | 7 | Soft-deletes the Task matching the given task identifier. |

#### Class: `JSONHistoryRepository`
> Concrete history log repository handling JSON-backed audit logs.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `(self, history_list)` | 5 | Initializes the repository with a list of HistoryLog objects. |
| `get` | `(self, history_id)` | 8 | Retrieves a HistoryLog by its unique history identifier. |
| `get_all` | `(self, task_id)` | 7 | Retrieves all history logs, filtered by a task identifier if provided. |
| `add` | `(self, history_log)` | 5 | Appends a new HistoryLog entry. |
| `delete` | `(self, history_id)` | 5 | Deletes a history log. Deletes are unsupported for history security logs. |

#### Class: `DatabaseContext`
> Context manager (Unit of Work) coordinating file storage transactions.
Ensures safe concurrent access using Unix flock.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `(self, file_path)` | 12 | Initializes the database context manager with the target file path. |
| `__enter__` | `(self)` | 36 | Enters the context block, opens the database file, and acquires a file lock. |
| `__exit__` | `(self, exc_type, exc_val, exc_tb)` | 13 | Exits the context block, committing pending changes if no exception was raised. |
| `commit` | `(self)` | 17 | Writes memory repository states back to database file in JSON format. |

---

### 📂 [services.py](file:///Users/dcronin05/Library/Mobile Documents/com~apple~CloudDocs/app_development/todo_app/services.py)
- **Lines of Code**: 213 | **Comments**: 18

#### Class: `TaskService`
> Service layer containing the business logic for task management.
Coordinates between repositories and handles history tracking.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `(self, db_file_path)` | 5 | Initializes the TaskService with a database file path. |
| `get_all_tasks` | `(self, include_deleted)` | 7 | Retrieves all active or archived tasks, sorted by creation date. |
| `get_task_by_id` | `(self, task_id)` | 5 | Retrieves a single task by ID. |
| `create_task` | `(self, task_data)` | 18 | Creates a new task and logs the creation event. |
| `update_task` | `(self, task_id, update_data)` | 23 | Updates a task, diffs fields, and logs a detailed update history event. |
| `delete_task` | `(self, task_id)` | 18 | Soft-deletes a task and logs the deletion event. |
| `restore_task` | `(self, task_id)` | 18 | Restores a soft-deleted task and logs the restoration event. |
| `get_task_history` | `(self, task_id)` | 7 | Retrieves audit log events for a task (newest first). |
| `_reconstruct_task_dict_at` | `(self, task_id, history_id, db)` | 37 | Reconstructs the task dictionary state immediately after a history event. |
| `get_reconstructed_task` | `(self, task_id, history_id)` | 15 | Retrieves a reconstructed task state at the moment after the specified history event. |
| `rollback_task` | `(self, task_id, history_id)` | 30 | Rolls back a task to its state immediately after the specified history event. |
| `reset_database` | `(self)` | 9 | Resets the database, clearing all tasks and history. |

---

### 📂 [server.py](file:///Users/dcronin05/Library/Mobile Documents/com~apple~CloudDocs/app_development/todo_app/server.py)
- **Lines of Code**: 376 | **Comments**: 12

#### Class: `API Routes`
> Contains standalone functions in server.py.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `initialize_database` | `()` | 13 | Initializes the database if db.json is missing or empty. |
| `get_tasks` | `()` | 11 | Retrieves all active or archived tasks. |
| `get_task` | `(task_id)` | 12 | Retrieves a single task by its unique identifier. |
| `create_task` | `()` | 14 | Creates a new task. |
| `update_task` | `(task_id)` | 16 | Updates properties of an existing task. |
| `delete_task` | `(task_id)` | 11 | Soft-deletes a task by setting its 'is_deleted' flag to True. |
| `restore_task` | `(task_id)` | 11 | Restores a soft-deleted task, setting its 'is_deleted' flag back to False. |
| `get_task_history` | `(task_id)` | 9 | Retrieves the chronological audit log for a task (newest first). |
| `reset_database` | `()` | 9 | Resets the database by clearing all tasks and audit history logs. |
| `get_docs_commits` | `()` | 9 | Retrieves the list of recent Git commits for version selection. |
| `get_docs_metadata` | `()` | 21 | Retrieves high-level metadata (classes, methods, file stats) for codebase files. |
| `get_docs_health` | `()` | 17 | Retrieves static analysis code health report details (score, stats, active warnings). |
| `get_guides_list` | `()` | 6 | Retrieves a list of available system documentation markdown guides. |
| `get_guide` | `(name)` | 13 | Retrieves content of a specific system guide by name. |
| `get_test_results` | `()` | 13 | Retrieves results of the last unit test suite execution. |
| `run_test_suite` | `()` | 17 | Runs the unit test suite on-demand. |
| `sync_docs_endpoint` | `()` | 9 | Forces a manual synchronization of dynamic documentation sections. |
| `get_test_metric` | `(metric_name)` | 27 | Retrieves a single test metric from the last test run. |
| `get_task_reconstructed_state` | `(task_id, history_id)` | 11 | Retrieves a reconstructed task state at the moment after a specified history event. |
| `rollback_task_to_state` | `(task_id, history_id)` | 11 | Rolls back a task state to the moment after the specified history event. |
| `add_header` | `(response)` | 6 | Disable caching for all API responses. |

---

### 📂 [doc_service.py](file:///Users/dcronin05/Library/Mobile Documents/com~apple~CloudDocs/app_development/todo_app/doc_service.py)
- **Lines of Code**: 1092 | **Comments**: 14

#### Class: `BaseCodeAnalyzer`
> Abstract Base Class for programming language source code analyzers.
Follows Strategy Pattern to support future language extensions (JS, CSS, etc.).

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `(self, file_path, commit_hash)` | 6 | Initializes the analyzer with the target file path. |
| `analyze` | `(self)` | 6 | Runs code analysis. |

#### Class: `PythonCodeAnalyzer`
> Concrete analyzer for Python codebase using standard library ast.
Inspects syntax tree for OOP structures and validates lint standards.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `analyze` | `(self)` | 43 | Parses and runs visual code analysis on the target Python file. |
| `_read_file_stats` | `(self)` | 21 | Reads the file content and counts lines and comment lines. |
| `_create_syntax_error_report` | `(self, e, total_lines, comment_lines)` | 20 | Generates a syntax error report. |
| `_extract_nodes` | `(self, tree, lines, classes_metadata, warnings)` | 28 | Iterates over child nodes in the tree to extract classes and global helper methods. |
| `_calculate_score` | `(self, warnings)` | 11 | Deducts scores for each warning (5 points for WARNING, 2 points for INFO). |
| `_analyze_class` | `(self, node, lines, warnings)` | 36 | Inspects class-level attributes, docstring, naming conventions, and methods. |
| `_analyze_function` | `(self, node, lines, warnings, parent_class)` | 27 | Inspects function-level docstring, naming conventions, types, and lengths. |
| `_check_function_naming_and_docstring` | `(self, func_name, docstring, scope, line_no, is_special, warnings)` | 29 | Checks missing docstring or bad naming formats in functions. |
| `_check_function_length` | `(self, node, func_name, scope, warnings)` | 21 | Checks function length and flags a warning if it exceeds 50 lines. |
| `_check_function_type_hints` | `(self, node, func_name, scope, is_special, warnings)` | 33 | Checks missing parameter or return type annotations. |

#### Class: `JSCodeAnalyzer`
> Concrete analyzer for JavaScript codebase using regex parsing.
Validates function naming, JSDoc docstrings, method length, console.log, and eval.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `analyze` | `(self)` | 35 | Parses and runs visual code analysis on the target JS file. |
| `_read_content` | `(self)` | 12 | Reads file content from git commit or local filesystem. |
| `_count_comments` | `(self, lines)` | 18 | Counts block and inline comments in JavaScript source lines. |
| `_scan_warnings` | `(self, lines)` | 25 | Scans lines for naming violations, length, and banned operators. |
| `_check_function` | `(self, lines, i, match, warnings)` | 18 | Inspects single function declaration details. |
| `_get_function_length` | `(self, lines, i)` | 16 | Calculates function lines length. |
| `_check_naming` | `(self, func_name, line_no, scope, warnings)` | 14 | Checks naming convention rules for constructor classes or regular camelCase functions. |
| `_check_jsdoc` | `(self, lines, i, line_no, scope, func_name, warnings)` | 13 | Checks JSDoc descriptions on function signatures. |
| `_calculate_score` | `(self, warnings)` | 11 | Deducts score values based on severity of active warnings. |

#### Class: `CSSCodeAnalyzer`
> Concrete analyzer for CSS stylesheets using regex parsing.
Validates theme color variables usage, !important overrides, and style rules.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `analyze` | `(self)` | 35 | Parses and runs visual code analysis on the target CSS file. |
| `_read_content` | `(self)` | 12 | Reads stylesheet file content. |
| `_count_comments` | `(self, lines)` | 16 | Counts comment lines in stylesheet. |
| `_scan_warnings` | `(self, lines)` | 86 | Scans lines for override rules and hardcoded styling variables. |
| `_calculate_score` | `(self, warnings)` | 9 | Deducts score based on warning severity. |

#### Class: `HTMLCodeAnalyzer`
> Concrete analyzer for HTML markup files using regex parsing.
Validates inline styles, alt accessibility attributes, and unique IDs.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `analyze` | `(self)` | 35 | Parses and runs visual code analysis on the target HTML file. |
| `_read_content` | `(self)` | 12 | Reads markup file content. |
| `_count_comments` | `(self, lines)` | 16 | Counts HTML comment lines. |
| `_scan_warnings` | `(self, lines)` | 33 | Audits markup lines for accessibility, inline styles, and duplicate IDs. |
| `_calculate_score` | `(self, warnings)` | 9 | Deducts scores based on warning severity. |

#### Class: `DocService`
> Orchestrates codebase documentation parsing and analysis.
Maintains Strategy pattern registrations for extension code analyzers.

| Method / Function | Arguments | Lines | Description |
| :--- | :--- | :--- | :--- |
| `__init__` | `(self, project_path)` | 7 | Initializes the DocService instance. |
| `register_analyzer` | `(self, ext, analyzer_class)` | 3 | Registers a BaseCodeAnalyzer subclass for a specific file extension. |
| `analyze_project` | `(self, files_list, commit_hash)` | 4 | Runs the registered analyzers across the given list of files and aggregates stats. |
| `_run_analyzers` | `(self, files_list, commit_hash)` | 16 | Runs registered analyzers on each file path in the list. |
| `_aggregate_metrics` | `(self, reports)` | 47 | Aggregates classes, methods, lines, comments, and warnings across reports. |
| `_generate_api_reference_md` | `(self, report)` | 39 | Generates API Reference markdown from codebase static analysis report. |
| `_append_warnings_md` | `(self, md_lines, warnings)` | 20 | Appends active warnings list formatted as a markdown table to md_lines. |
| `_append_test_results_md` | `(self, md_lines, test_results)` | 29 | Appends unit test execution scorecard and results table to md_lines. |
| `_generate_health_scorecard_md` | `(self, report, test_results)` | 13 | Generates markdown scorecard summarizing code quality score, active warnings, and test runs. |
| `_replace_placeholder_in_file` | `(self, file_path, start_marker, end_marker, content)` | 13 | Replaces text between start and end markers inside a file with new content. |
| `_fetch_cached_test_results` | `(self)` | 18 | Queries TestRunnerService to fetch the last run test results. |
| `_get_current_git_commit` | `(self)` | 10 | Returns the current git HEAD commit hash. |
| `sync_dynamic_docs` | `(self, test_results)` | 31 | Regenerates API Reference and Health Scorecard markdown and writes them to placeholder markers. |
| `get_markdown_guide` | `(self, guide_name, commit_hash)` | 26 | Retrieves and reads a static markdown documentation guide. |
| `get_recent_commits` | `(self, limit)` | 23 | Retrieves the list of recent Git commits. |

---

### 📂 [main.js](file:///Users/dcronin05/Library/Mobile Documents/com~apple~CloudDocs/app_development/todo_app/src/main.js)
- **Lines of Code**: 2544 | **Comments**: 133

*No classes or global helper functions detected in this file.*

### 📂 [style.css](file:///Users/dcronin05/Library/Mobile Documents/com~apple~CloudDocs/app_development/todo_app/src/style.css)
- **Lines of Code**: 2503 | **Comments**: 60

*No classes or global helper functions detected in this file.*

### 📂 [index.html](file:///Users/dcronin05/Library/Mobile Documents/com~apple~CloudDocs/app_development/todo_app/index.html)
- **Lines of Code**: 568 | **Comments**: 43

*No classes or global helper functions detected in this file.*

<!-- DYNAMIC_API_REFERENCE_END -->

