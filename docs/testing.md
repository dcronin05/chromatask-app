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
- **Endpoints Discovery**: `GET /api/docs/endpoints`
  - Returns a dynamically compiled JSON list of all REST routes, HTTP verbs, and descriptions extracted from `server.py` using AST.
- **Sync Documentation**: `POST /api/docs/sync`
  - Triggers a manual synchronization of dynamic documentation placeholders.

---

## 4. Codebase Health & Test Execution Scorecard

<!-- DYNAMIC_HEALTH_SCORECARD_START -->
### 🛡️ Code Health Scorecard
- **Code Quality Score**: **100%**
- **Active Linter Warnings**: 1 active warnings
- **Unit Tests Success Rate**: **100%** (37/37 Passed, 0 Failed)
- **Test Execution Duration**: 0.3127s

*Documentation compiled from Git HEAD:* `9ddcf80` (Daniel Cronin on 2026-05-29)
<!-- DYNAMIC_HEALTH_SCORECARD_END -->

