import unittest
import time
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
            "message": "Passed successfully."
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
            "message": self._exc_info_to_string(err, test)
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
            "message": self._exc_info_to_string(err, test)
        })


class TestRunnerService:
    """
    Service that programmatically discovers, loads, and executes unit tests.
    Stores the results of the last test execution.
    """
    def __init__(self) -> None:
        self.last_results: Optional[Dict[str, Any]] = None

    def run_tests(self, scope: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs the unit tests under tests.py matching the given scope.
        If scope is None, runs all tests.
        Scope can be a class name (e.g. 'TaskModelTests') or a specific test (e.g. 'TaskModelTests.test_task_serialization').
        """
        loader = unittest.TestLoader()
        
        # Determine target test suite to load
        if scope:
            try:
                # Load a specific class or method from tests.py
                suite = loader.loadTestsFromName(f"tests.{scope}")
            except Exception as e:
                # Fallback to empty suite on error
                suite = unittest.TestSuite()
        else:
            import tests
            suite = loader.loadTestsFromModule(tests)

        result_collector = JSONTestResult()
        
        start_time = time.time()
        suite.run(result_collector)
        total_duration = time.time() - start_time

        # Calculate statistics
        total = len(result_collector.results)
        passed = sum(1 for r in result_collector.results if r["status"] == "PASS")
        failed = total - passed
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
            "results": result_collector.results
        }

        # Cache last run results
        self.last_results = report
        return report

    def get_last_results(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves the report compiled during the last test execution.
        """
        return self.last_results
