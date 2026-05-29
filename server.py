import os
import json
from typing import Any, Dict, List, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from services import TaskService
from doc_service import DocService, PythonCodeAnalyzer, JSCodeAnalyzer, CSSCodeAnalyzer, HTMLCodeAnalyzer
from test_service import TestRunnerService

app: Flask = Flask(__name__)
# Enable CORS for cross-origin local testing if needed
CORS(app)

DB_FILE: str = "db.json"
SEED_FILE: str = "gemini-code-1780008469746.json"

task_service: TaskService = TaskService(DB_FILE)
test_runner_service: TestRunnerService = TestRunnerService()

# Initialize DocService and register language analyzers
code_doc_service: DocService = DocService(os.path.dirname(os.path.abspath(__file__)))
code_doc_service.register_analyzer(".py", PythonCodeAnalyzer)
code_doc_service.register_analyzer(".js", JSCodeAnalyzer)
code_doc_service.register_analyzer(".css", CSSCodeAnalyzer)
code_doc_service.register_analyzer(".html", HTMLCodeAnalyzer)
CODEBASE_FILES: List[str] = [
    "models.py", "repositories.py", "services.py", "server.py", "doc_service.py",
    "src/main.js", "src/style.css", "index.html"
]

# ==========================================
# DATABASE INITIALIZATION
# ==========================================
def initialize_database() -> None:
    """
    Initializes the database if db.json is missing or empty.
    Creates a basic JSON structure with empty lists for tasks and history.
    """
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        print(f"[{DB_FILE}] not found or empty. Initializing empty database...")
        try:
            with open(DB_FILE, "w") as f:
                json.dump({"tasks": [], "history": []}, f, indent=2)
            print("Database initialized empty.")
        except Exception as e:
            print(f"Critical error during database initialization: {e}")

# ==========================================
# API ROUTE CONTROLLERS
# ==========================================

@app.route("/api/tasks", methods=["GET"])
def get_tasks() -> Any:
    """
    Retrieves all active or archived tasks.
    Supports a query parameter 'include_deleted' (default: false).
    """
    include_deleted: bool = request.args.get("include_deleted", "false").lower() == "true"
    try:
        tasks: List[Dict[str, Any]] = task_service.get_all_tasks(include_deleted)
        return jsonify(tasks), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task(task_id: str) -> Any:
    """
    Retrieves a single task by its unique identifier.
    Returns a 404 error if the task is not found.
    """
    try:
        task: Optional[Dict[str, Any]] = task_service.get_task_by_id(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks", methods=["POST"])
def create_task() -> Any:
    """
    Creates a new task.
    Requires 'title' in the JSON body request payload.
    """
    try:
        task_data: Optional[Dict[str, Any]] = request.json
        if not task_data or not task_data.get("title"):
            return jsonify({"error": "Missing required field: title"}), 400
            
        created: Dict[str, Any] = task_service.create_task(task_data)
        return jsonify(created), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>", methods=["PUT"])
def update_task(task_id: str) -> Any:
    """
    Updates properties of an existing task.
    Requires a JSON body containing fields to be updated.
    """
    try:
        update_data: Optional[Dict[str, Any]] = request.json
        if not update_data:
            return jsonify({"error": "No update fields provided"}), 400
            
        updated: Dict[str, Any] = task_service.update_task(task_id, update_data)
        return jsonify(updated), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id: str) -> Any:
    """
    Soft-deletes a task by setting its 'is_deleted' flag to True.
    """
    try:
        deleted: Dict[str, Any] = task_service.delete_task(task_id)
        return jsonify(deleted), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>/restore", methods=["POST"])
def restore_task(task_id: str) -> Any:
    """
    Restores a soft-deleted task, setting its 'is_deleted' flag back to False.
    """
    try:
        restored: Dict[str, Any] = task_service.restore_task(task_id)
        return jsonify(restored), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>/history", methods=["GET"])
def get_task_history(task_id: str) -> Any:
    """
    Retrieves the chronological audit log for a task (newest first).
    """
    try:
        history: List[Dict[str, Any]] = task_service.get_task_history(task_id)
        return jsonify(history), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def reset_database() -> Any:
    """
    Resets the database by clearing all tasks and audit history logs.
    """
    try:
        task_service.reset_database()
        return jsonify({"message": "Database reset completed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================================
# DEVELOPER DOCS & QUALITY API
# ==========================================

@app.route("/api/docs/commits", methods=["GET"])
def get_docs_commits() -> Any:
    """
    Retrieves the list of recent Git commits for version selection.
    """
    try:
        commits = code_doc_service.get_recent_commits()
        return jsonify(commits), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/docs/metadata", methods=["GET"])
def get_docs_metadata() -> Any:
    """
    Retrieves high-level metadata (classes, methods, file stats) for codebase files.
    Supports an optional 'commit' query parameter to inspect historical revisions.
    """
    commit_hash = request.args.get("commit")
    try:
        report: Dict[str, Any] = code_doc_service.analyze_project(CODEBASE_FILES, commit_hash)
        metadata: Dict[str, Any] = {
            "files": [
                {
                    "file_name": f["metadata"]["file_name"],
                    "classes": f["metadata"]["classes"],
                    "stats": f["metadata"]["stats"]
                }
                for f in report["files_reports"]
            ]
        }
        return jsonify(metadata), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/docs/health", methods=["GET"])
def get_docs_health() -> Any:
    """
    Retrieves static analysis code health report details (score, stats, active warnings).
    Supports an optional 'commit' query parameter to inspect historical revisions.
    """
    commit_hash = request.args.get("commit")
    try:
        report: Dict[str, Any] = code_doc_service.analyze_project(CODEBASE_FILES, commit_hash)
        health: Dict[str, Any] = {
            "score": report["score"],
            "files_scanned": report["files_scanned"],
            "stats": report["stats"],
            "warnings": report["warnings"]
        }
        return jsonify(health), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/docs/guides", methods=["GET"])
def get_guides_list() -> Any:
    """
    Retrieves a list of available system documentation markdown guides.
    """
    guides: List[str] = ["architecture", "database", "time_travel"]
    return jsonify(guides), 200


@app.route("/api/docs/guides/<name>", methods=["GET"])
def get_guide(name: str) -> Any:
    """
    Retrieves content of a specific system guide by name.
    Supports an optional 'commit' query parameter to inspect historical revisions.
    """
    commit_hash = request.args.get("commit")
    try:
        content: str = code_doc_service.get_markdown_guide(name, commit_hash)
        if not content:
            return jsonify({"error": "Guide not found"}), 404
        return jsonify({"name": name, "content": content}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/docs/tests", methods=["GET"])
def get_test_results() -> Any:
    """
    Retrieves results of the last unit test suite execution.
    If no test run exists, performs an initial run of all tests.
    """
    try:
        results = test_runner_service.get_last_results()
        if not results:
            results = test_runner_service.run_tests()
        return jsonify(results), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/docs/tests/run", methods=["POST"])
def run_test_suite() -> Any:
    """
    Runs the unit test suite on-demand.
    Accepts an optional JSON payload specifying a 'scope' parameter.
    Example: {"scope": "TaskModelTests"} or {"scope": "TaskModelTests.test_task_serialization"}
    """
    try:
        scope = None
        if request.is_json:
            payload = request.json
            if payload:
                scope = payload.get("scope")
        results = test_runner_service.run_tests(scope)
        return jsonify(results), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>/history/<history_id>", methods=["GET"])
def get_task_reconstructed_state(task_id: str, history_id: str) -> Any:
    """
    Retrieves a reconstructed task state at the moment after a specified history event.
    """
    try:
        data: Dict[str, Any] = task_service.get_reconstructed_task(task_id, history_id)
        return jsonify(data), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>/rollback/<history_id>", methods=["POST"])
def rollback_task_to_state(task_id: str, history_id: str) -> Any:
    """
    Rolls back a task state to the moment after the specified history event.
    """
    try:
        updated_task: Dict[str, Any] = task_service.rollback_task(task_id, history_id)
        return jsonify(updated_task), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    initialize_database()
    # Run server locally on port 5000
    app.run(host="127.0.0.1", port=5000, debug=True)
