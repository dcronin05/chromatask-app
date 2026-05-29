import ast
import re
import os
from abc import ABC, abstractmethod

class BaseCodeAnalyzer(ABC):
    """
    Abstract Base Class for programming language source code analyzers.
    Follows Strategy Pattern to support future language extensions (JS, CSS, etc.).
    """
    def __init__(self, file_path):
        self.file_path = file_path

    @abstractmethod
    def analyze(self) -> dict:
        """
        Runs code analysis.
        Returns a dict: {
            "metadata": { "file_name": str, "classes": list, "stats": dict },
            "health": { "score": int, "warnings": list }
        }
        """
        pass


class PythonCodeAnalyzer(BaseCodeAnalyzer):
    """
    Concrete analyzer for Python codebase using standard library ast.
    Inspects syntax tree for OOP structures and validates lint standards.
    """
    def analyze(self) -> dict:
        if not os.path.exists(self.file_path):
            return {
                "metadata": {"file_name": os.path.basename(self.file_path), "classes": [], "stats": {"lines": 0, "comments": 0}},
                "health": {"score": 100, "warnings": []}
            }

        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines()
        total_lines = len(lines)
        comment_lines = sum(1 for l in lines if l.strip().startswith("#"))

        try:
            tree = ast.parse(content, filename=self.file_path)
        except SyntaxError as e:
            return {
                "metadata": {
                    "file_name": os.path.basename(self.file_path),
                    "classes": [],
                    "stats": {"lines": total_lines, "comments": comment_lines}
                },
                "health": {
                    "score": 0,
                    "warnings": [{
                        "line": e.lineno or 1,
                        "issue": f"Syntax Error: {e.msg}",
                        "severity": "ERROR",
                        "scope": "File Syntax"
                    }]
                }
            }

        classes_metadata = []
        warnings = []

        # Iterate top-level nodes in file
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                class_info = self._analyze_class(node, lines, warnings)
                classes_metadata.append(class_info)
            elif isinstance(node, ast.FunctionDef):
                # Analyze top-level functions (like Flask route controller functions)
                func_info = self._analyze_function(node, lines, warnings, parent_class=None)
                # Group these under a virtual class "Global Endpoints" if it's the server file
                is_server = "server.py" in self.file_path
                global_class_name = "API Routes" if is_server else "Global Helpers"
                
                # Check if we already have the virtual class in our list
                virtual_class = next((c for c in classes_metadata if c["name"] == global_class_name), None)
                if not virtual_class:
                    virtual_class = {
                        "name": global_class_name,
                        "docstring": f"Contains standalone functions in {os.path.basename(self.file_path)}.",
                        "methods": []
                    }
                    classes_metadata.append(virtual_class)
                virtual_class["methods"].append(func_info)

        # Health score math (deduct from 100)
        file_score = 100
        for w in warnings:
            if w["severity"] == "WARNING":
                file_score -= 5
            elif w["severity"] == "INFO":
                file_score -= 2
        file_score = max(0, file_score)

        return {
            "metadata": {
                "file_name": os.path.basename(self.file_path),
                "classes": classes_metadata,
                "stats": {
                    "lines": total_lines,
                    "comments": comment_lines
                }
            },
            "health": {
                "score": file_score,
                "warnings": warnings
            }
        }

    def _analyze_class(self, node, lines, warnings) -> dict:
        class_name = node.name
        docstring = ast.get_docstring(node) or ""

        # 1. Missing Class Docstring
        if not docstring:
            warnings.append({
                "line": node.lineno,
                "issue": f"Class '{class_name}' is missing a docstring description.",
                "severity": "WARNING",
                "scope": class_name
            })

        # 2. Class Naming Convention (PascalCase)
        if not re.match(r"^[A-Z][a-zA-Z0-9]*$", class_name):
            warnings.append({
                "line": node.lineno,
                "issue": f"Class '{class_name}' should use PascalCase naming convention.",
                "severity": "WARNING",
                "scope": class_name
            })

        methods = []
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                method_info = self._analyze_function(child, lines, warnings, parent_class=class_name)
                methods.append(method_info)

        return {
            "name": class_name,
            "docstring": docstring,
            "methods": methods
        }

    def _analyze_function(self, node, lines, warnings, parent_class=None) -> dict:
        func_name = node.name
        docstring = ast.get_docstring(node) or ""
        scope = f"{parent_class}.{func_name}" if parent_class else func_name

        is_special = func_name.startswith("__") and func_name.endswith("__")

        # 1. Missing Method Docstring
        if not docstring and not is_special:
            warnings.append({
                "line": node.lineno,
                "issue": f"Method '{func_name}' is missing a docstring description.",
                "severity": "WARNING",
                "scope": scope
            })

        # 2. Method Naming Convention (snake_case)
        if not is_special and not re.match(r"^[a-z_][a-z0-9_]*$", func_name):
            warnings.append({
                "line": node.lineno,
                "issue": f"Method '{func_name}' should use snake_case naming convention.",
                "severity": "WARNING",
                "scope": scope
            })

        # 3. Method Complexity / Body Length
        func_start = node.lineno
        func_end = getattr(node, "end_lineno", func_start)
        length = func_end - func_start + 1
        if length > 50:
            warnings.append({
                "line": node.lineno,
                "issue": f"Method '{func_name}' is very long ({length} lines). Consider splitting it.",
                "severity": "INFO",
                "scope": scope
            })

        # 4. Missing Parameter & Return Type Hints
        missing_type_hints = []
        for arg in node.args.args:
            if arg.arg in ("self", "cls"):
                continue
            if not arg.annotation:
                missing_type_hints.append(arg.arg)

        has_return_hint = node.returns is not None

        if missing_type_hints or (not has_return_hint and not is_special):
            details = []
            if missing_type_hints:
                details.append(f"parameters: {', '.join(missing_type_hints)}")
            if not has_return_hint and not is_special:
                details.append("return hint")

            warnings.append({
                "line": node.lineno,
                "issue": f"Method '{func_name}' is missing type annotations ({'; '.join(details)}).",
                "severity": "INFO",
                "scope": scope
            })

        args_list = [a.arg for a in node.args.args]

        return {
            "name": func_name,
            "docstring": docstring,
            "args": args_list,
            "line": node.lineno,
            "length": length
        }


class DocService:
    """
    Orchestrates codebase documentation parsing and analysis.
    Maintains Strategy pattern registrations for extension code analyzers.
    """
    def __init__(self, project_path="."):
        self.project_path = project_path
        self._analyzers = {}

    def register_analyzer(self, ext, analyzer_class):
        """Registers a BaseCodeAnalyzer subclass for a specific file extension."""
        self._analyzers[ext] = analyzer_class

    def analyze_project(self, files_list) -> dict:
        """Runs the registered analyzers across the given list of files and aggregates stats."""
        reports = []
        for rel_path in files_list:
            file_path = os.path.join(self.project_path, rel_path)
            ext = os.path.splitext(file_path)[1]

            analyzer_class = self._analyzers.get(ext)
            if analyzer_class:
                analyzer = analyzer_class(file_path)
                report = analyzer.analyze()
                report["file_path"] = rel_path
                reports.append(report)

        # Aggregate report calculations
        scanned_files = 0
        total_score = 0
        total_classes = 0
        total_methods = 0
        total_lines = 0
        total_comments = 0
        all_warnings = []

        for r in reports:
            if not r:
                continue
            scanned_files += 1
            total_score += r.get("health", {}).get("score", 100)

            meta = r.get("metadata", {})
            stats = meta.get("stats", {})
            total_lines += stats.get("lines", 0)
            total_comments += stats.get("comments", 0)

            classes = meta.get("classes", [])
            total_classes += len(classes)
            for c in classes:
                total_methods += len(c.get("methods", []))

            file_warnings = r.get("health", {}).get("warnings", [])
            for w in file_warnings:
                w["file"] = r["file_path"]
                all_warnings.append(w)

        avg_score = round(total_score / scanned_files) if scanned_files > 0 else 100

        return {
            "score": avg_score,
            "files_scanned": scanned_files,
            "stats": {
                "classes": total_classes,
                "methods": total_methods,
                "lines": total_lines,
                "comments": total_comments
            },
            "warnings": all_warnings,
            "files_reports": reports
        }

    def get_markdown_guide(self, guide_name) -> str:
        """Retrieves and reads a static markdown documentation guide."""
        docs_dir = os.path.join(self.project_path, "docs")
        # Sanitize filename
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "", guide_name)
        file_path = os.path.join(docs_dir, f"{safe_name}.md")
        
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""
