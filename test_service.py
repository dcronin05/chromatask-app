import unittest
import time
import datetime
from typing import Any, Dict, List, Optional

class JSONTestResult(unittest.TestResult):
    """
    Custom test result collector that stores execution results in a JSON-serializable structure.
    """
    def __init__(self, stream: Any = None, descriptions: Any = None, verbosity: Any = None) -> None:
        super().__init__(stream, descriptions, verbosity)
        self.results: List[Dict[str, Any]] = []
        self._start_times: Dict[str, float] = {}

    def startTest(self, test: unittest.TestCase) -> None:
        """
        Record the start time of the test case.
        """
        super().startTest(test)
        self._start_times[test.id()] = time.time()

    def addSuccess(self, test: unittest.TestCase) -> None:
        """
        Logs a passed test case into the results list.
        """
        super().addSuccess(test)
        duration = time.time() - self._start_times.get(test.id(), time.time())
        self.results.append({
            "name": test._testMethodName,
            "class": test.__class__.__name__,
            "status": "PASS",
            "duration": round(duration, 4),
            "message": "Passed successfully.",
            "last_run": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })

    def addFailure(self, test: unittest.TestCase, err: Any) -> None:
        """
        Logs a failed test case with the formatted traceback.
        """
        super().addFailure(test, err)
        duration = time.time() - self._start_times.get(test.id(), time.time())
        self.results.append({
            "name": test._testMethodName,
            "class": test.__class__.__name__,
            "status": "FAIL",
            "duration": round(duration, 4),
            "message": self._exc_info_to_string(err, test),
            "last_run": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })

    def addError(self, test: unittest.TestCase, err: Any) -> None:
        """
        Logs a test case execution error with the formatted traceback.
        """
        super().addError(test, err)
        duration = time.time() - self._start_times.get(test.id(), time.time())
        self.results.append({
            "name": test._testMethodName,
            "class": test.__class__.__name__,
            "status": "ERROR",
            "duration": round(duration, 4),
            "message": self._exc_info_to_string(err, test),
            "last_run": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })


class TestRunnerService:
    """
    Service that programmatically discovers, loads, and executes unit tests.
    Stores the results of the last test execution, preserving historical runs.
    """
    def __init__(self) -> None:
        self.last_results: Optional[Dict[str, Any]] = None
        self.all_tests_cache: Dict[str, Dict[str, Any]] = {}

    def _discover_all_tests(self) -> List[unittest.TestCase]:
        """
        Discovers all test cases from the tests module and returns them as a flat list.
        """
        import tests
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(tests)

        def flatten(suite_or_test: Any) -> List[unittest.TestCase]:
            test_cases = []
            if isinstance(suite_or_test, unittest.TestCase):
                test_cases.append(suite_or_test)
            else:
                for test in suite_or_test:
                    test_cases.extend(flatten(test))
            return test_cases

        return flatten(suite)

    def _refresh_test_cache(self) -> None:
        """
        Refreshes the internal test cache with newly discovered tests.
        Keeps previous execution results, appends new tests as PENDING,
        and removes test cases that no longer exist in tests.py.
        """
        try:
            test_cases = self._discover_all_tests()
        except Exception:
            return

        current_keys = set()
        for t in test_cases:
            class_name = t.__class__.__name__
            method_name = t._testMethodName
            key = f"{class_name}.{method_name}"
            current_keys.add(key)
            if key not in self.all_tests_cache:
                self.all_tests_cache[key] = {
                    "name": method_name,
                    "class": class_name,
                    "status": "PENDING",
                    "duration": 0.0,
                    "message": "Not run yet.",
                    "last_run": None
                }

        # Remove deleted tests from cache
        for key in list(self.all_tests_cache.keys()):
            if key not in current_keys:
                del self.all_tests_cache[key]

    def run_tests(self, scope: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs the unit tests under tests.py matching the given scope.
        Updates the cache with new results and returns the merged state of all tests.
        Scope can be a class name (e.g. 'TaskModelTests') or a specific test method.
        """
        # Ensure our cache structure is up to date
        self._refresh_test_cache()

        try:
            test_cases = self._discover_all_tests()
        except Exception as e:
            # Discovery error (e.g. syntax error in tests.py)
            return {
                "scope": scope or "ALL",
                "timestamp": time.time(),
                "duration": 0.0,
                "stats": {"total": 0, "passed": 0, "failed": 0, "success_rate": 0},
                "results": [{"name": "Error", "class": "Discovery", "status": "ERROR", "duration": 0.0, "message": str(e)}]
            }

        # Build custom suite with only matching tests
        suite = unittest.TestSuite()
        for t in test_cases:
            class_name = t.__class__.__name__
            method_name = t._testMethodName
            full_name = f"{class_name}.{method_name}"
            
            # If no scope, run everything. If scope matches class or full name, run it.
            if not scope or class_name == scope or full_name == scope:
                suite.addTest(t)

        result_collector = JSONTestResult()
        start_time = time.time()
        suite.run(result_collector)
        total_duration = time.time() - start_time

        # Update cache with new results
        for res in result_collector.results:
            key = f"{res['class']}.{res['name']}"
            if key in self.all_tests_cache:
                self.all_tests_cache[key].update({
                    "status": res["status"],
                    "duration": res["duration"],
                    "message": res["message"],
                    "last_run": res.get("last_run")
                })

        # Recalculate stats based on the latest cache state
        results_list = list(self.all_tests_cache.values())
        total = len(results_list)
        passed = sum(1 for r in results_list if r["status"] == "PASS")
        failed = sum(1 for r in results_list if r["status"] in ("FAIL", "ERROR"))
        success_rate = round((passed / total) * 100) if total > 0 else 100

        # Construct final report
        report = {
            "scope": scope or "ALL",
            "timestamp": time.time(),
            "duration": round(total_duration, 4),
            "stats": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "success_rate": success_rate
            },
            "results": results_list
        }

        # Cache last run results
        self.last_results = report
        return report

    def get_last_results(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves the report compiled during the last test execution,
        updated with any structural changes.
        """
        if self.last_results:
            self._refresh_test_cache()
            results_list = list(self.all_tests_cache.values())
            total = len(results_list)
            passed = sum(1 for r in results_list if r["status"] == "PASS")
            failed = sum(1 for r in results_list if r["status"] in ("FAIL", "ERROR"))
            success_rate = round((passed / total) * 100) if total > 0 else 100

            self.last_results["stats"] = {
                "total": total,
                "passed": passed,
                "failed": failed,
                "success_rate": success_rate
            }
            self.last_results["results"] = results_list
        return self.last_results
