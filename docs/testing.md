# E2E Test Suite & Code Quality Verification Guide

ChromaTask integrates a comprehensive testing framework and code quality static analysis engine. This ensures the application remains robust, conforming to strict documentation and architectural standards.

---

## 1. Programmatic Test Runner (`test_service.py`)

The unit and integration test executions are managed by the `TestRunnerService` pattern:

- **`JSONTestResult`**: A customized `unittest.TestResult` collector. It captures execution success state (`PASS`, `FAIL`, `ERROR`), measures test duration, catches formatted stack tracebacks, and attaches an ISO UTC datetime stamp (`last_run`) for execution logging.
- **`TestRunnerService`**: 
  - Traverses the AST of the `tests` module to dynamically discover all defined test cases.
  - Maintains a persistent execution cache state (`self.all_tests_cache`). Any newly added test cases default to a `PENDING` status.
  - Supports scoped execution, allowing developers to execute either the entire test suite, a specific test case class (e.g. `TaskModelTests`), or an individual test method (e.g. `TaskModelTests.test_task_serialization`).
  - Merges execution results back into the cache and calculates total stats (passed, failed, duration, success rate).

---

## 2. Code Quality Static Analyzers (`doc_service.py`)

Concrete static code analyzers inspect source files inside the workspace to flag code quality issues:

### A. Python Code Analyzer (`PythonCodeAnalyzer`)
- Uses Python's native `ast` module to inspect syntax tree declarations.
- Enforces:
  - Descriptive docstrings for all classes and functions.
  - Casing standards (PascalCase for classes, snake_case for functions).
  - Explicit parameter and return type annotations/hints.
  - Function length constraints (warns if a function exceeds 50 lines).

### B. JavaScript Code Analyzer (`JSCodeAnalyzer`)
- Uses regex parsing to audit JS files.
- Enforces:
  - CamelCase naming for standard functions and PascalCase for class constructors.
  - JSDoc lookback check (warns if a function exceeding 60 lines is missing descriptive comments within the preceding lines).
  - Function length constraints (warns if a function exceeds 150 lines, accommodating longer Vanilla JS renderers).
  - Security and code hygiene checks (flags left-over `console.log()` and banned `eval()` functions).

### C. CSS Code Analyzer (`CSSCodeAnalyzer`)
- Audits stylesheets for consistency and theme isolation.
- Enforces:
  - Avoidance of raw hardcoded non-brand colors in favor of CSS variables (permits theme variables and ChromaTask custom brand palette colors).
  - Avoidance of stylesheet override flags (`!important`).

### D. HTML Code Analyzer (`HTMLCodeAnalyzer`)
- Audits markup for validation and accessibility.
- Enforces:
  - Alt attributes for image tags (`<img alt="...">`).
  - Unique element IDs (warns on duplicate IDs in the DOM).
  - Inline style audits (flags inline theme-breaking style overrides such as custom `color`, `background`, `border`, or `font`, while permitting functional layout overrides like `display: none;`).

---

## 3. Developer Integration & REST API Endpoints

The Dev Docs & Health console is backed by the following server routes:

- **Run Suite**: `POST /api/docs/tests/run`
  - Triggers test execution. Accepts optional JSON scope parameter: `{"scope": "TaskModelTests"}`.
- **Fetch Results**: `GET /api/docs/tests`
  - Retrieves the latest compiled test execution stats and results.
- **Metrics Polling**: `GET /api/docs/tests/metrics/<metric_name>`
  - Allows polling specific execution parameters individually: `total`, `passed`, `failed`, `success_rate`, `duration`, or `timestamp`.

---

## 4. Codebase Health & Test Execution Scorecard

<!-- DYNAMIC_HEALTH_SCORECARD_START -->
### 🛡️ Codebase Quality Score: **100%**
- **Files Scanned**: 8 files

#### Active Linter Warnings
| File | Line | Severity | Scope | Violation Details |
| :--- | :--- | :--- | :--- | :--- |
| `doc_service.py` | 561 | `INFO` | `CSSCodeAnalyzer._scan_warnings` | Method '_scan_warnings' is very long (86 lines). Consider splitting it. |

#### Unit & Integration Tests scorecard
- **Success Rate**: **100%** (33/33 passed, 0 failed)
- **Test Execution Duration**: 0.3951s

| Test Class | Test Case Method | Status | Duration | Message |
| :--- | :--- | :--- | :--- | :--- |
| `AnalyzerStrategyTests` | `test_css_analyzer_violations` | `PASS` | 0.0019s | Passed successfully. |
| `AnalyzerStrategyTests` | `test_html_analyzer_violations` | `PASS` | 0.0005s | Passed successfully. |
| `AnalyzerStrategyTests` | `test_js_analyzer_violations` | `PASS` | 0.001s | Passed successfully. |
| `CodebaseQualityTests` | `test_css_quality` | `PASS` | 0.0107s | Passed successfully. |
| `CodebaseQualityTests` | `test_html_quality` | `PASS` | 0.0025s | Passed successfully. |
| `CodebaseQualityTests` | `test_javascript_quality` | `PASS` | 0.007s | Passed successfully. |
| `DocServiceTests` | `test_doc_service_registration_and_analysis` | `PASS` | 0.0004s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_create_task_endpoint` | `PASS` | 0.0078s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_delete_and_restore_endpoints` | `PASS` | 0.0014s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_get_docs_commits_endpoint` | `PASS` | 0.0174s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_get_docs_guides_endpoints` | `PASS` | 0.0867s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_get_docs_health_endpoint` | `PASS` | 0.018s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_get_docs_metadata_endpoint` | `PASS` | 0.0243s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_get_task_by_id_endpoint` | `PASS` | 0.0017s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_get_tasks_endpoint` | `PASS` | 0.0004s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_reconstruction_and_rollback_endpoints` | `PASS` | 0.0021s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_reset_database_endpoint` | `PASS` | 0.0012s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_sync_dynamic_docs_endpoint` | `PASS` | 0.1255s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_task_history_endpoint` | `PASS` | 0.0014s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_test_suite_and_metrics_endpoints` | `PASS` | 0.0429s | Passed successfully. |
| `FlaskAPIAdditionalTests` | `test_update_task_endpoint` | `PASS` | 0.0027s | Passed successfully. |
| `FlaskAPITests` | `test_create_task_endpoint` | `PASS` | 0.0017s | Passed successfully. |
| `FlaskAPITests` | `test_get_docs_health_endpoint` | `PASS` | 0.0252s | Passed successfully. |
| `FlaskAPITests` | `test_get_tasks_endpoint` | `PASS` | 0.0009s | Passed successfully. |
| `FlaskAPITests` | `test_update_task_endpoint` | `PASS` | 0.0012s | Passed successfully. |
| `RepositoryTests` | `test_database_context_locking_and_crud` | `PASS` | 0.0004s | Passed successfully. |
| `TaskModelTests` | `test_task_creation_and_defaults` | `PASS` | 0.0s | Passed successfully. |
| `TaskModelTests` | `test_task_field_update_diffs` | `PASS` | 0.0s | Passed successfully. |
| `TaskModelTests` | `test_task_serialization` | `PASS` | 0.0s | Passed successfully. |
| `TaskModelTests` | `test_task_soft_delete_and_restore` | `PASS` | 0.0s | Passed successfully. |
| `TaskServiceTests` | `test_create_and_update_task_service` | `PASS` | 0.0018s | Passed successfully. |
| `TaskServiceTests` | `test_time_travel_reconstruction_and_rollback` | `PASS` | 0.0024s | Passed successfully. |
| `TestRunnerServiceTests` | `test_test_runner_cache_and_scope` | `PASS` | 0.0026s | Passed successfully. |

<!-- DYNAMIC_HEALTH_SCORECARD_END -->

