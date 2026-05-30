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


class FlaskAPITests(unittest.TestCase):
    """
    Integration tests for the Flask API endpoints.
    Uses app.test_client() to verify REST responses.
    """
    def setUp(self) -> None:
        """Sets up a temporary database and overrides server task_service."""
        import server
        self.original_service = server.task_service
        self.db_path = "db_api_integration_test.json"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        # Create a new service instance pointing to the integration test database
        server.task_service = TaskService(self.db_path)
        self.client = server.app.test_client()

    def tearDown(self) -> None:
        """Restores the original task_service and cleans up integration db."""
        import server
        server.task_service = self.original_service
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_get_tasks_endpoint(self) -> None:
        """Verifies GET /api/tasks returns a success status code and task list."""
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)

    def test_create_task_endpoint(self) -> None:
        """Verifies POST /api/tasks creates a task and returns 201."""
        payload = {"title": "API Test Task", "description": "API Test Desc"}
        response = self.client.post("/api/tasks", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIsNotNone(data.get("task_id"))
        self.assertEqual(data.get("title"), "API Test Task")

    def test_update_task_endpoint(self) -> None:
        """Verifies PUT /api/tasks/<task_id> updates fields and returns 200."""
        # Create a task first
        payload = {"title": "API Test Task To Update"}
        create_resp = self.client.post("/api/tasks", json=payload)
        task_id = create_resp.get_json()["task_id"]

        # Update the task
        update_payload = {"title": "Updated API Title", "priority": "LOW"}
        response = self.client.put(f"/api/tasks/{task_id}", json=update_payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("title"), "Updated API Title")
        self.assertEqual(data.get("priority"), "LOW")

    def test_get_docs_health_endpoint(self) -> None:
        """Verifies GET /api/docs/health returns the codebase quality health report."""
        response = self.client.get("/api/docs/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("score", data)
        self.assertIn("warnings", data)
        self.assertIsInstance(data.get("score"), (int, float))


class CodebaseQualityTests(unittest.TestCase):
    """
    Integration tests that combine DocService (linter) with the test suite
    to audit JS, CSS, and HTML codebase quality.
    """
    def setUp(self) -> None:
        """Registers frontend language analyzers on DocService for audits."""
        from doc_service import DocService, JSCodeAnalyzer, CSSCodeAnalyzer, HTMLCodeAnalyzer
        self.doc_service = DocService()
        self.doc_service.register_analyzer(".js", JSCodeAnalyzer)
        self.doc_service.register_analyzer(".css", CSSCodeAnalyzer)
        self.doc_service.register_analyzer(".html", HTMLCodeAnalyzer)

    def test_javascript_quality(self) -> None:
        """Runs lint checks on src/main.js and validates metadata parsing."""
        js_file = "src/main.js"
        report = self.doc_service.analyze_project([js_file])
        stats = report.get("stats", {})
        
        # Verify analyzer parsed files and returned valid metrics
        self.assertEqual(report.get("files_scanned"), 1)
        self.assertGreater(stats.get("lines", 0), 0)
        self.assertIn("warnings", report)
        self.assertIsInstance(report.get("score"), int)

    def test_css_quality(self) -> None:
        """Runs lint checks on src/style.css and validates metadata parsing."""
        css_file = "src/style.css"
        report = self.doc_service.analyze_project([css_file])
        stats = report.get("stats", {})
        
        self.assertEqual(report.get("files_scanned"), 1)
        self.assertGreater(stats.get("lines", 0), 0)
        self.assertIn("warnings", report)
        self.assertIsInstance(report.get("score"), int)

    def test_html_quality(self) -> None:
        """Runs lint checks on index.html and validates metadata parsing."""
        html_file = "index.html"
        report = self.doc_service.analyze_project([html_file])
        stats = report.get("stats", {})
        
        self.assertEqual(report.get("files_scanned"), 1)
        self.assertGreater(stats.get("lines", 0), 0)
        self.assertIn("warnings", report)
        self.assertIsInstance(report.get("score"), int)


class AnalyzerStrategyTests(unittest.TestCase):
    """
    Unit tests for the AST/regex-based language analyzers (JS, CSS, HTML).
    """
    def setUp(self) -> None:
        """Creates temporary files for in-memory analyzer parsing audits."""
        self.js_path: str = "temp_test_js.js"
        self.css_path: str = "temp_test_css.css"
        self.html_path: str = "temp_test_html.html"

    def tearDown(self) -> None:
        """Removes the temporary test files from the workspace."""
        for path in (self.js_path, self.css_path, self.html_path):
            if os.path.exists(path):
                os.remove(path)

    def test_js_analyzer_violations(self) -> None:
        """Verifies JSCodeAnalyzer detects naming, JSDoc, console.log, and eval warnings."""
        js_code: str = (
            "// Simple comment\n"
            "console.log('debug');\n"
            "eval('1+1');\n"
            "\n\n\n\n\n"
            "function bad_naming_style() {\n"
            "  const x = 1;\n"
            "  const y = 2;\n"
            "  const z = 3;\n"
            + "\n".join("  console.log(x + y + z);" for _ in range(60)) + "\n"
            "  return 42;\n"
            "}\n"
        )
        with open(self.js_path, "w", encoding="utf-8") as f:
            f.write(js_code)

        from doc_service import JSCodeAnalyzer
        analyzer: JSCodeAnalyzer = JSCodeAnalyzer(self.js_path)
        report: Dict[str, Any] = analyzer.analyze()
        warnings: List[Dict[str, Any]] = report["health"]["warnings"]
        issues: List[str] = [w["issue"] for w in warnings]

        self.assertIn("Console log left in code.", issues)
        self.assertIn("Avoid using eval() for security reasons.", issues)
        self.assertTrue(any("naming convention" in iss for iss in issues))
        self.assertTrue(any("missing descriptive comments" in iss for iss in issues))
        self.assertLess(report["health"]["score"], 100)

    def test_css_analyzer_violations(self) -> None:
        """Verifies CSSCodeAnalyzer detects hardcoded colors and !important rules."""
        css_code: str = (
            "/* CSS comment */\n"
            ".btn-primary {\n"
            "  background-color: #ff00ff !important;\n"
            "  color: white;\n"
            "}\n"
        )
        with open(self.css_path, "w", encoding="utf-8") as f:
            f.write(css_code)

        from doc_service import CSSCodeAnalyzer
        analyzer: CSSCodeAnalyzer = CSSCodeAnalyzer(self.css_path)
        report: Dict[str, Any] = analyzer.analyze()
        warnings: List[Dict[str, Any]] = report["health"]["warnings"]
        issues: List[str] = [w["issue"] for w in warnings]

        self.assertTrue(any("!important overrides" in iss for iss in issues))
        self.assertTrue(any("Hardcoded color value found" in iss for iss in issues))
        self.assertLess(report["health"]["score"], 100)

    def test_html_analyzer_violations(self) -> None:
        """Verifies HTMLCodeAnalyzer detects inline styles, missing alt attributes, and duplicate IDs."""
        html_code: str = (
            "<!-- HTML comment -->\n"
            "<div id='dup-id' style='margin: 10px; color: red;'>\n"
            "  <img src='logo.png' />\n"
            "  <span id='dup-id'>Hello</span>\n"
            "</div>\n"
        )
        with open(self.html_path, "w", encoding="utf-8") as f:
            f.write(html_code)

        from doc_service import HTMLCodeAnalyzer
        analyzer: HTMLCodeAnalyzer = HTMLCodeAnalyzer(self.html_path)
        report: Dict[str, Any] = analyzer.analyze()
        warnings: List[Dict[str, Any]] = report["health"]["warnings"]
        issues: List[str] = [w["issue"] for w in warnings]

        self.assertTrue(any("inline styles" in iss for iss in issues))
        self.assertTrue(any("missing an alt accessibility" in iss for iss in issues))
        self.assertTrue(any("Duplicate element ID" in iss for iss in issues))
        self.assertLess(report["health"]["score"], 100)


class DocServiceTests(unittest.TestCase):
    """
    Unit tests for the DocService orchestration and metrics aggregation.
    """
    def test_doc_service_registration_and_analysis(self) -> None:
        """Verifies custom analyzer registration and project analysis metrics."""
        from doc_service import DocService, BaseCodeAnalyzer

        class DummyAnalyzer(BaseCodeAnalyzer):
            def analyze(self) -> Dict[str, Any]:
                return {
                    "metadata": {
                        "file_name": os.path.basename(self.file_path),
                        "classes": [],
                        "stats": {"lines": 10, "comments": 2}
                    },
                    "health": {"score": 95, "warnings": [{"line": 1, "severity": "WARNING", "scope": "Dummy", "issue": "Dummy warning"}]}
                }

        service = DocService()
        service.register_analyzer(".dummy", DummyAnalyzer)

        # Create a temp file to scan
        temp_path = "temp_dummy.dummy"
        with open(temp_path, "w") as f:
            f.write("dummy content")

        try:
            report = service.analyze_project([temp_path])
            self.assertEqual(report["files_scanned"], 1)
            self.assertEqual(report["score"], 95)
            self.assertEqual(report["stats"]["lines"], 10)
            self.assertEqual(report["stats"]["comments"], 2)
            self.assertEqual(len(report["warnings"]), 1)
            self.assertEqual(report["warnings"][0]["issue"], "Dummy warning")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_js_code_analyzer_parsing(self) -> None:
        """Verifies JSCodeAnalyzer parses classes, JSDocs, and standalones."""
        from doc_service import JSCodeAnalyzer
        code = (
            "/**\n"
            " * A test class.\n"
            " */\n"
            "class Calculator {\n"
            "  /**\n"
            "   * Adds two numbers.\n"
            "   */\n"
            "  add(x, y) {\n"
            "    return x + y;\n"
            "  }\n"
            "}\n"
            "// Standalone sum\n"
            "function sum(a, b) {\n"
            "  return a + b;\n"
            "}\n"
            "const arrowMultiply = (m, n) => m * n;\n"
        )
        temp_path = "temp_test_js_parser.js"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            analyzer = JSCodeAnalyzer(temp_path)
            report = analyzer.analyze()
            classes = report["metadata"]["classes"]
            self.assertEqual(len(classes), 2)
            calc = next(c for c in classes if c["name"] == "Calculator")
            self.assertEqual(calc["docstring"], "A test class.")
            self.assertEqual(len(calc["methods"]), 1)
            self.assertEqual(calc["methods"][0]["name"], "add")
            self.assertEqual(calc["methods"][0]["args"], ["x", "y"])
            self.assertEqual(calc["methods"][0]["docstring"], "Adds two numbers.")
            module_class = next(c for c in classes if c["name"] == "temp_test_js_parser.js Module")
            self.assertEqual(len(module_class["methods"]), 2)
            s_fn = next(m for m in module_class["methods"] if m["name"] == "sum")
            self.assertEqual(s_fn["docstring"], "Standalone sum")
            self.assertEqual(s_fn["args"], ["a", "b"])
            arrow_fn = next(m for m in module_class["methods"] if m["name"] == "arrowMultiply")
            self.assertEqual(arrow_fn["args"], ["m", "n"])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestRunnerServiceTests(unittest.TestCase):
    """
    Unit tests for the TestRunnerService suite execution and cache state.
    """
    def test_test_runner_cache_and_scope(self) -> None:
        """Verifies TestRunnerService test discovery, caching, and scoped execution."""
        from test_service import TestRunnerService
        runner = TestRunnerService()

        # Run tests matching only TaskModelTests
        report = runner.run_tests(scope="TaskModelTests")
        self.assertEqual(report["scope"], "TaskModelTests")
        self.assertGreater(report["stats"]["total"], 0)

        # Check that only TaskModelTests items are run (others remain PENDING or not updated)
        # and matching items are not PENDING anymore
        results = report["results"]
        task_model_results = [r for r in results if r["class"] == "TaskModelTests"]
        self.assertTrue(all(r["status"] != "PENDING" for r in task_model_results))


class FlaskAPIAdditionalTests(FlaskAPITests):
    """
    Comprehensive integration tests for all additional Flask API endpoints.
    """
    def test_get_task_by_id_endpoint(self) -> None:
        """Verifies GET /api/tasks/<task_id> returns 200 for existing and 404 for missing."""
        # Test 404 for missing task
        response_404 = self.client.get("/api/tasks/non-existent-id")
        self.assertEqual(response_404.status_code, 404)

        # Create a task
        create_resp = self.client.post("/api/tasks", json={"title": "Single Task"})
        task_id = create_resp.get_json()["task_id"]

        # Test 200 for existing task
        response_200 = self.client.get(f"/api/tasks/{task_id}")
        self.assertEqual(response_200.status_code, 200)
        self.assertEqual(response_200.get_json()["title"], "Single Task")

    def test_delete_and_restore_endpoints(self) -> None:
        """Verifies DELETE /api/tasks/<task_id> and restore endpoints work correctly."""
        # Create a task
        create_resp = self.client.post("/api/tasks", json={"title": "Delete Restore Task"})
        task_id = create_resp.get_json()["task_id"]

        # Soft-delete the task
        del_resp = self.client.delete(f"/api/tasks/{task_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.get_json()["is_deleted"])

        # Restore the task
        restore_resp = self.client.post(f"/api/tasks/{task_id}/restore")
        self.assertEqual(restore_resp.status_code, 200)
        self.assertFalse(restore_resp.get_json()["is_deleted"])

    def test_task_history_endpoint(self) -> None:
        """Verifies GET /api/tasks/<task_id>/history returns audit log entries."""
        # Create a task
        create_resp = self.client.post("/api/tasks", json={"title": "History Task"})
        task_id = create_resp.get_json()["task_id"]

        # Get history logs
        hist_resp = self.client.get(f"/api/tasks/{task_id}/history")
        self.assertEqual(hist_resp.status_code, 200)
        data = hist_resp.get_json()
        self.assertGreater(len(data), 0)
        self.assertEqual(data[0]["action"], "CREATED")

    def test_reset_database_endpoint(self) -> None:
        """Verifies POST /api/reset clears all tasks from the service database."""
        # Create a task first
        self.client.post("/api/tasks", json={"title": "To Be Reset"})

        # Reset database
        reset_resp = self.client.post("/api/reset")
        self.assertEqual(reset_resp.status_code, 200)

        # Confirm tasks list is empty
        list_resp = self.client.get("/api/tasks")
        self.assertEqual(len(list_resp.get_json()), 0)

    def test_get_docs_commits_endpoint(self) -> None:
        """Verifies GET /api/docs/commits returns recent git commits metadata."""
        response = self.client.get("/api/docs/commits")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)

    def test_get_docs_metadata_endpoint(self) -> None:
        """Verifies GET /api/docs/metadata returns workspace static metadata analysis."""
        response = self.client.get("/api/docs/metadata")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("files", data)
        self.assertIsInstance(data["files"], list)

    def test_get_docs_guides_endpoints(self) -> None:
        """Verifies GET /api/docs/guides lists guides and retrieves markdown content."""
        # Test guides list
        list_resp = self.client.get("/api/docs/guides")
        self.assertEqual(list_resp.status_code, 200)
        guides = list_resp.get_json()
        self.assertIn("architecture", guides)
        self.assertIn("database", guides)
        self.assertIn("time_travel", guides)
        self.assertIn("testing", guides)

        # Test specific guide retrieval (e.g. database guide) and that it contains metadata & ROLLBACK
        guide_resp = self.client.get("/api/docs/guides/database")
        self.assertEqual(guide_resp.status_code, 200)
        db_data = guide_resp.get_json()
        self.assertEqual(db_data["name"], "database")
        self.assertIn("content", db_data)
        db_content = db_data["content"]
        self.assertIn("metadata", db_content)
        self.assertIn("ROLLBACK", db_content)

        # Test architecture guide contains Display Config, Dynamic Schema Engine, and AST API Route Parser documentation
        arch_resp = self.client.get("/api/docs/guides/architecture")
        self.assertEqual(arch_resp.status_code, 200)
        arch_content = arch_resp.get_json()["content"]
        self.assertIn("TASK_DISPLAY_CONFIG", arch_content)
        self.assertIn("syncDynamicFields", arch_content)
        self.assertIn("Glassmorphic Sidebar", arch_content)
        self.assertIn("localStorage", arch_content)
        self.assertIn("btn-toggle-sidebar", arch_content)
        self.assertIn("nav-counter", arch_content)
        self.assertIn("AST API Route Parser", arch_content)

        # Test testing guide contains JSDoc comment/function length thresholds, CSS/HTML audits, and endpoint routes documentation
        test_resp = self.client.get("/api/docs/guides/testing")
        self.assertEqual(test_resp.status_code, 200)
        test_content = test_resp.get_json()["content"]
        self.assertIn("JSCodeAnalyzer", test_content)
        self.assertIn("150 lines", test_content)
        self.assertIn("60 lines", test_content)
        self.assertIn("CSSCodeAnalyzer", test_content)
        self.assertIn("/api/docs/endpoints", test_content)
        self.assertIn("/api/docs/sync", test_content)

        # Test time travel guide contains list diff and null value timeline logs formatting checks
        tt_resp = self.client.get("/api/docs/guides/time_travel")
        self.assertEqual(tt_resp.status_code, 200)
        tt_content = tt_resp.get_json()["content"]
        self.assertIn("collaborators", tt_content)
        self.assertIn("Null Value Formatting", tt_content)

    def test_test_suite_and_metrics_endpoints(self) -> None:
        """Verifies test suite runs and individual metrics endpoints are accessible."""
        # Trigger test suite run via POST
        run_resp = self.client.post("/api/docs/tests/run", json={"scope": "TaskModelTests"})
        self.assertEqual(run_resp.status_code, 200)
        self.assertEqual(run_resp.get_json()["scope"], "TaskModelTests")

        # Get last test results via GET
        get_resp = self.client.get("/api/docs/tests")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.get_json()["scope"], "TaskModelTests")

        # Poll total metric endpoint
        total_resp = self.client.get("/api/docs/tests/metrics/total")
        self.assertEqual(total_resp.status_code, 200)
        self.assertIn("total", total_resp.get_json())
        self.assertIsInstance(total_resp.get_json()["total"], int)

        # Poll passed metric endpoint
        passed_resp = self.client.get("/api/docs/tests/metrics/passed")
        self.assertEqual(passed_resp.status_code, 200)
        self.assertIn("passed", passed_resp.get_json())

        # Poll invalid metric endpoint
        invalid_resp = self.client.get("/api/docs/tests/metrics/invalid-name")
        self.assertEqual(invalid_resp.status_code, 400)

    def test_reconstruction_and_rollback_endpoints(self) -> None:
        """Verifies task state reconstructed playback and rollback REST endpoints."""
        # Create a task
        create_resp = self.client.post("/api/tasks", json={"title": "Original"})
        task = create_resp.get_json()
        task_id = task["task_id"]

        # Get task history to retrieve creation event ID
        hist_resp = self.client.get(f"/api/tasks/{task_id}/history")
        history_id = hist_resp.get_json()[0]["history_id"]

        # Update the task title
        self.client.put(f"/api/tasks/{task_id}", json={"title": "Updated"})

        # Get reconstructed state at creation event
        recon_resp = self.client.get(f"/api/tasks/{task_id}/history/{history_id}")
        self.assertEqual(recon_resp.status_code, 200)
        self.assertEqual(recon_resp.get_json()["reconstructed"]["title"], "Original")

        # Perform rollback to creation event
        rollback_resp = self.client.post(f"/api/tasks/{task_id}/rollback/{history_id}")
        self.assertEqual(rollback_resp.status_code, 200)
        self.assertEqual(rollback_resp.get_json()["title"], "Original")

    def test_sync_dynamic_docs_endpoint(self) -> None:
        """Verifies POST /api/docs/sync executes the dynamic document compiler."""
        # Call the sync endpoint
        sync_resp = self.client.post("/api/docs/sync")
        self.assertEqual(sync_resp.status_code, 200)
        self.assertEqual(sync_resp.get_json()["status"], "success")

        # Fetch architecture guide to verify API Reference structural summary was compiled
        arch_resp = self.client.get("/api/docs/guides/architecture")
        self.assertEqual(arch_resp.status_code, 200)
        arch_content = arch_resp.get_json()["content"]
        self.assertIn("Programmatic API Reference", arch_content)
        self.assertIn("Codebase Structural Summary", arch_content)
        self.assertIn("Scanned Modules", arch_content)
        self.assertIn("Total Methods/Functions", arch_content)

        # Fetch testing guide to verify Code Health scorecard was compiled
        test_resp = self.client.get("/api/docs/guides/testing")
        self.assertEqual(test_resp.status_code, 200)
        test_content = test_resp.get_json()["content"]
        self.assertIn("Codebase Health & Test Execution Scorecard", test_content)
        self.assertIn("Code Health Scorecard", test_content)
        self.assertIn("Code Quality Score", test_content)
        self.assertIn("Unit Tests Success Rate", test_content)

    def test_get_api_endpoints_endpoint(self) -> None:
        """Verifies GET /api/docs/endpoints dynamically parses and returns routes."""
        resp = self.client.get("/api/docs/endpoints")
        self.assertEqual(resp.status_code, 200)
        endpoints = resp.get_json()
        self.assertIsInstance(endpoints, list)
        
        # Check that standard routes exist in the response
        paths = [e["path"] for e in endpoints]
        self.assertIn("/api/tasks", paths)
        self.assertIn("/api/docs/endpoints", paths)
        self.assertIn("/api/docs/health", paths)

    def test_permanent_deletion_endpoint(self) -> None:
        """Verifies DELETE /api/tasks/<id>/permanent purges task and history logs."""
        create_resp = self.client.post("/api/tasks", json={"title": "Temp Task"})
        task_id = create_resp.get_json()["task_id"]
        
        # Soft delete first
        self.client.delete(f"/api/tasks/{task_id}")
        
        # Purge permanently
        purge_resp = self.client.delete(f"/api/tasks/{task_id}/permanent")
        self.assertEqual(purge_resp.status_code, 200)
        
        # Verify task is gone
        get_resp = self.client.get(f"/api/tasks/{task_id}")
        self.assertEqual(get_resp.status_code, 404)
        
        # Verify history logs are purged
        hist_resp = self.client.get(f"/api/tasks/{task_id}/history")
        self.assertEqual(len(hist_resp.get_json()), 0)

    def test_ai_task_analyzer_sync(self) -> None:
        """Verifies synchronous creation runs analyzer heuristics based on title."""
        payload = {"title": "caffeine coffee run tomorrow urgent #work"}
        create_resp = self.client.post("/api/tasks", json=payload)
        self.assertEqual(create_resp.status_code, 201)
        
        task = create_resp.get_json()
        self.assertEqual(task["priority"], "HIGH")
        self.assertIn("Beverage", task["task_specific_tags"])
        self.assertIn("Caffeine", task["task_specific_tags"])
        self.assertIn("Work", task["task_specific_tags"])
        self.assertIsNotNone(task["due_date"])
        self.assertGreater(len(task["description"]), 0)
        
        # Verify metadata and raw AI data storage
        self.assertIn("metadata", task)
        self.assertIn("ai_data", task["metadata"])
        ai_data = task["metadata"]["ai_data"]
        self.assertEqual(ai_data["priority"], "HIGH")
        self.assertIn("Beverage", ai_data["tags"])
        self.assertIn("Caffeine", ai_data["tags"])

    def test_ai_task_analyzer_async_service(self) -> None:
        """Verifies AiTaskAnalyzerService background scanner detects pending tasks."""
        from services import AiTaskAnalyzerService
        test_db = "db_unit_test.json"
        
        # Seed test task
        with DatabaseContext(test_db) as db:
            db._tasks.clear()
            db._history.clear()
            task = Task(title="urgent backup plex server today")
            db.tasks.add(task)
            
        analyzer = AiTaskAnalyzerService(test_db)
        analyzer.analyze_pending_tasks()
        
        # Verify task was processed and updated
        with DatabaseContext(test_db) as db:
            updated = db.tasks.get(task.task_id)
            self.assertEqual(updated.priority, "HIGH")
            self.assertIn("Plex", updated.task_specific_tags)
            self.assertIsNotNone(updated.due_date)
            self.assertTrue(updated.metadata.get("ai_analyzed"))
            
        import os
        if os.path.exists(test_db):
            os.remove(test_db)




