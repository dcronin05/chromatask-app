# ChromaTask

A premium, programmatic Kanban task manager built with a modular, decoupled Object-Oriented Design (OOD) in Python (Flask) and a responsive, glassmorphic Vanilla JS/CSS frontend (Vite).

ChromaTask features concurrent-safe database transaction locking, a chronological activity audit logging timeline, and an interactive **Developer Docs & Code Health Console** driven by native Python AST parsing.

---

## 🏗️ Architectural System Design

ChromaTask enforces a strict **Separation of Concerns** using four distinct design layers:

1. **Domain Model Layer (`models.py`)**: Defines core entities (e.g., `Task`, `HistoryLog`) extending a base `Entity` class. Keeps track of state modifications and compiles detailed diff audits on update.
2. **Data Access Layer (`repositories.py`)**: Abstract repository patterns decoupled from actual storage. Manages SQLite/JSON transactions through `DatabaseContext` (the Unit of Work pattern) which handles concurrent file reads and writes using Unix-level file locking (`flock`).
3. **Business Service Layer (`services.py`)**: Implements application use cases. Interacts with repositories and automatically calculates/records history logs for all mutations.
4. **API Controller Layer (`server.py`)**: Maps HTTP paths to service endpoints and handles JSON serialization. No business logic or database state manipulation lives here.

---

## 🛠️ Developer Docs & Code Health Linter

The codebase is self-monitoring and includes a programmatic developer dashboard:
- **Strategy Pattern Engine**: Utilizes a registration interface (`BaseCodeAnalyzer`) in `doc_service.py` mapping extensions to custom code scanners. This allows future lint support for JS, CSS, or HTML to be registered dynamically.
- **Python AST Inspection**: Runs zero-dependency syntax tree analysis on Python files, checks for naming conventions, computes a localized file quality score, and lists warnings for:
  - Missing class/method docstrings.
  - Casing convention errors (PascalCase for classes, snake_case for methods).
  - Long methods (>50 lines).
  - Missing parameters and return type annotations.

---

## 🤖 AI Coding Assistant & Developer Instructions

> [!IMPORTANT]
> If you are an AI agent or LLM coding assistant editing this codebase, you **must** adhere to the following rules:

### 1. Architectural Integrity
- **Do not bypass layers**: Never query the database or access files directly from the controller (`server.py`) or domain model (`models.py`) layers. All database queries must be requested via `TaskService` inside `services.py`.
- **Unit of Work Concurrency**: All database read/write actions must be wrapped inside a `DatabaseContext` block:
  ```python
  with DatabaseContext(self.db_file) as ctx:
      # Perform repository operations (ctx.tasks, ctx.history)
  ```
  This ensures the Unix `flock` file locking is acquired and released safely to prevent concurrency collisions.

### 2. Coding Standards & Linter Checks
The Dev Docs console automatically audits code changes. Ensure all code modifications satisfy the following:
- **Naming Conventions**: Classes must be named in `PascalCase`. Functions and methods must be named in `snake_case`.
- **Documentation**: Every class and public method **must** have a descriptive docstring.
- **Method Length**: Keep methods focused and short; any method exceeding 50 lines will trigger a code health warning.
- **Type Annotations**: Provide explicit type hints for all method arguments (excluding `self` and `cls`) and return statements.
  - *Example*: `def create_task(self, task_data: dict) -> dict:`

---

## 🚀 Setup & Execution

### 1. Prerequisites
- Python 3.8+
- Node.js (v18+)

### 2. Installation
Clone the repository and install developer dependencies:
```bash
npm install
```

### 3. Local Development Run
To run both the Python Flask backend and Vite client server concurrently:
```bash
npm run dev
```
- **Backend API**: Starts at `http://127.0.0.1:5000`
- **Vite Frontend**: Starts on a fixed port at `http://localhost:6000` (configured in `vite.config.js`)

### 4. Database Setup
The local database state is maintained in `db.json`.
- `db.json` is excluded from git versioning to prevent committing PII.
- If missing, the Flask server will automatically initialize a fresh, empty database on start.

---

## 📝 Licensing & Copyright Notice

This repository is public for demonstration purposes. The author does not claim copyright ownership or associate any formal software licenses (such as MIT or Apache) with the code at this stage. It remains a work in progress.
