import ast
import re
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type

class BaseCodeAnalyzer(ABC):
    """
    Abstract Base Class for programming language source code analyzers.
    Follows Strategy Pattern to support future language extensions (JS, CSS, etc.).
    """
    def __init__(self, file_path: str, commit_hash: Optional[str] = None) -> None:
        """
        Initializes the analyzer with the target file path.
        """
        self.file_path: str = file_path
        self.commit_hash: Optional[str] = commit_hash

    @abstractmethod
    def analyze(self) -> Dict[str, Any]:
        """
        Runs code analysis.
        Returns a dict containing metadata and health score details.
        """
        pass


class PythonCodeAnalyzer(BaseCodeAnalyzer):
    """
    Concrete analyzer for Python codebase using standard library ast.
    Inspects syntax tree for OOP structures and validates lint standards.
    """
    def analyze(self) -> Dict[str, Any]:
        """
        Parses and runs visual code analysis on the target Python file.
        Returns a report detailing classes, functions, code lines, and issues.
        """
        if not os.path.exists(self.file_path):
            return {
                "metadata": {
                    "file_name": os.path.basename(self.file_path),
                    "classes": [],
                    "stats": {"lines": 0, "comments": 0}
                },
                "health": {"score": 100, "warnings": []}
            }

        content, total_lines, comment_lines = self._read_file_stats()
        
        try:
            tree = ast.parse(content, filename=self.file_path)
        except SyntaxError as e:
            return self._create_syntax_error_report(e, total_lines, comment_lines)

        classes_metadata: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        lines = content.splitlines()

        self._extract_nodes(tree, lines, classes_metadata, warnings)
        file_score = self._calculate_score(warnings)

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

    def _read_file_stats(self) -> Tuple[str, int, int]:
        """
        Reads the file content and counts lines and comment lines.
        If self.commit_hash is provided, it retrieves content via git.
        """
        if self.commit_hash:
            import subprocess
            rel_path = os.path.relpath(self.file_path)
            cmd = ["git", "show", f"{self.commit_hash}:{rel_path}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return "", 0, 0
            content = result.stdout
        else:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()

        lines = content.splitlines()
        total_lines = len(lines)
        comment_lines = sum(1 for l in lines if l.strip().startswith("#"))
        return content, total_lines, comment_lines

    def _create_syntax_error_report(self, e: SyntaxError, total_lines: int, comment_lines: int) -> Dict[str, Any]:
        """
        Generates a syntax error report.
        """
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

    def _extract_nodes(
        self, 
        tree: ast.AST, 
        lines: List[str], 
        classes_metadata: List[Dict[str, Any]], 
        warnings: List[Dict[str, Any]]
    ) -> None:
        """
        Iterates over child nodes in the tree to extract classes and global helper methods.
        """
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                class_info = self._analyze_class(node, lines, warnings)
                classes_metadata.append(class_info)
            elif isinstance(node, ast.FunctionDef):
                func_info = self._analyze_function(node, lines, warnings, parent_class=None)
                is_server = "server.py" in self.file_path
                global_class_name = "API Routes" if is_server else "Global Helpers"
                
                virtual_class = next((c for c in classes_metadata if c["name"] == global_class_name), None)
                if not virtual_class:
                    virtual_class = {
                        "name": global_class_name,
                        "docstring": f"Contains standalone functions in {os.path.basename(self.file_path)}.",
                        "methods": []
                    }
                    classes_metadata.append(virtual_class)
                virtual_class["methods"].append(func_info)

    def _calculate_score(self, warnings: List[Dict[str, Any]]) -> int:
        """
        Deducts scores for each warning (5 points for WARNING, 2 points for INFO).
        """
        file_score = 100
        for w in warnings:
            if w["severity"] == "WARNING":
                file_score -= 5
            elif w["severity"] == "INFO":
                file_score -= 2
        return max(0, file_score)

    def _analyze_class(self, node: ast.ClassDef, lines: List[str], warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Inspects class-level attributes, docstring, naming conventions, and methods.
        """
        class_name: str = node.name
        docstring: str = ast.get_docstring(node) or ""

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

        methods: List[Dict[str, Any]] = []
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                method_info = self._analyze_function(child, lines, warnings, parent_class=class_name)
                methods.append(method_info)

        return {
            "name": class_name,
            "docstring": docstring,
            "methods": methods
        }

    def _analyze_function(
        self, 
        node: ast.FunctionDef, 
        lines: List[str], 
        warnings: List[Dict[str, Any]], 
        parent_class: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Inspects function-level docstring, naming conventions, types, and lengths.
        """
        func_name: str = node.name
        docstring: str = ast.get_docstring(node) or ""
        scope: str = f"{parent_class}.{func_name}" if parent_class else func_name
        is_special: bool = func_name.startswith("__") and func_name.endswith("__")

        self._check_function_naming_and_docstring(func_name, docstring, scope, node.lineno, is_special, warnings)
        length = self._check_function_length(node, func_name, scope, warnings)
        self._check_function_type_hints(node, func_name, scope, is_special, warnings)

        args_list = [a.arg for a in node.args.args]
        return {
            "name": func_name,
            "docstring": docstring,
            "args": args_list,
            "line": node.lineno,
            "length": length
        }

    def _check_function_naming_and_docstring(
        self, 
        func_name: str, 
        docstring: str, 
        scope: str, 
        line_no: int, 
        is_special: bool, 
        warnings: List[Dict[str, Any]]
    ) -> None:
        """
        Checks missing docstring or bad naming formats in functions.
        """
        # 1. Missing Method Docstring
        if not docstring and not is_special:
            warnings.append({
                "line": line_no,
                "issue": f"Method '{func_name}' is missing a docstring description.",
                "severity": "WARNING",
                "scope": scope
            })

        # 2. Method Naming Convention (snake_case)
        if not is_special and not re.match(r"^[a-z_][a-z0-9_]*$", func_name):
            warnings.append({
                "line": line_no,
                "issue": f"Method '{func_name}' should use snake_case naming convention.",
                "severity": "WARNING",
                "scope": scope
            })

    def _check_function_length(
        self, 
        node: ast.FunctionDef, 
        func_name: str, 
        scope: str, 
        warnings: List[Dict[str, Any]]
    ) -> int:
        """
        Checks function length and flags a warning if it exceeds 50 lines.
        """
        func_start: int = node.lineno
        func_end: int = getattr(node, "end_lineno", func_start)
        length: int = func_end - func_start + 1
        if length > 50:
            warnings.append({
                "line": node.lineno,
                "issue": f"Method '{func_name}' is very long ({length} lines). Consider splitting it.",
                "severity": "INFO",
                "scope": scope
            })
        return length

    def _check_function_type_hints(
        self, 
        node: ast.FunctionDef, 
        func_name: str, 
        scope: str, 
        is_special: bool, 
        warnings: List[Dict[str, Any]]
    ) -> None:
        """
        Checks missing parameter or return type annotations.
        """
        missing_type_hints: List[str] = []
        for arg in node.args.args:
            if arg.arg in ("self", "cls"):
                continue
            if not arg.annotation:
                missing_type_hints.append(arg.arg)

        has_return_hint: bool = node.returns is not None

        if missing_type_hints or (not has_return_hint and not is_special):
            details: List[str] = []
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


class JSCodeAnalyzer(BaseCodeAnalyzer):
    """
    Concrete analyzer for JavaScript codebase using regex parsing.
    Validates function naming, JSDoc docstrings, method length, console.log, and eval.
    """
    def analyze(self) -> Dict[str, Any]:
        """
        Parses and runs visual code analysis on the target JS file.
        Returns a report detailing classes, functions, code lines, and issues.
        """
        if not os.path.exists(self.file_path):
            return {
                "metadata": {
                    "file_name": os.path.basename(self.file_path),
                    "classes": [],
                    "stats": {"lines": 0, "comments": 0}
                },
                "health": {"score": 100, "warnings": []}
            }

        content = self._read_content()
        lines = content.splitlines()
        comment_lines = self._count_comments(lines)
        warnings = self._scan_warnings(lines)
        score = self._calculate_score(warnings)

        return {
            "metadata": {
                "file_name": os.path.basename(self.file_path),
                "classes": [],
                "stats": {
                    "lines": len(lines),
                    "comments": comment_lines
                }
            },
            "health": {
                "score": score,
                "warnings": warnings
            }
        }

    def _read_content(self) -> str:
        """Reads file content from git commit or local filesystem."""
        if self.commit_hash:
            import subprocess
            rel_path = os.path.relpath(self.file_path)
            cmd = ["git", "show", f"{self.commit_hash}:{rel_path}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
            return ""
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _count_comments(self, lines: List[str]) -> int:
        """Counts block and inline comments in JavaScript source lines."""
        comment_lines = 0
        in_block = False
        for line in lines:
            line_strip = line.strip()
            if in_block:
                comment_lines += 1
                if "*/" in line_strip:
                    in_block = False
            else:
                if line_strip.startswith("//"):
                    comment_lines += 1
                elif line_strip.startswith("/*"):
                    comment_lines += 1
                    if "*/" not in line_strip:
                        in_block = True
        return comment_lines

    def _scan_warnings(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Scans lines for naming violations, length, and banned operators."""
        warnings: List[Dict[str, Any]] = []
        func_pattern = re.compile(
            r"(?:function\s+([a-zA-Z0-9_$]+)\s*\()|"
            r"(?:(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>)|"
            r"(?:^\s*(?!(?:if|for|while|switch|catch)\b)([a-zA-Z0-9_$]+)\s*\([^)]*\)\s*\{)"
        )
        for i, line in enumerate(lines):
            line_no = i + 1
            if "console.log(" in line:
                warnings.append({
                    "line": line_no, "issue": "Console log left in code.",
                    "severity": "INFO", "scope": "Global"
                })
            if "eval(" in line:
                warnings.append({
                    "line": line_no, "issue": "Avoid using eval() for security reasons.",
                    "severity": "WARNING", "scope": "Global"
                })

            match = func_pattern.search(line)
            if match:
                self._check_function(lines, i, match, warnings)
        return warnings

    def _check_function(self, lines: List[str], i: int, match: Any, warnings: List[Dict[str, Any]]) -> None:
        """Inspects single function declaration details."""
        func_name = match.group(1) or match.group(2) or match.group(3)
        if not func_name:
            return
        scope = f"Function {func_name}"
        line_no = i + 1

        self._check_naming(func_name, line_no, scope, warnings)
        self._check_jsdoc(lines, i, line_no, scope, func_name, warnings)
        self._check_length(lines, i, line_no, scope, func_name, warnings)

    def _check_naming(self, func_name: str, line_no: int, scope: str, warnings: List[Dict[str, Any]]) -> None:
        """Checks naming convention rules for constructor classes or regular camelCase functions."""
        if func_name[0].isupper():
            if not re.match(r"^[A-Z][a-zA-Z0-9]*$", func_name):
                warnings.append({
                    "line": line_no, "severity": "WARNING", "scope": scope,
                    "issue": f"Function '{func_name}' should use PascalCase for class constructors."
                })
        else:
            if not re.match(r"^[a-z][a-zA-Z0-9]*$", func_name):
                warnings.append({
                    "line": line_no, "severity": "WARNING", "scope": scope,
                    "issue": f"Function '{func_name}' should use camelCase naming convention."
                })

    def _check_jsdoc(self, lines: List[str], i: int, line_no: int, scope: str, func_name: str, warnings: List[Dict[str, Any]]) -> None:
        """Checks JSDoc descriptions on function signatures."""
        has_jsdoc = False
        for j in range(max(0, i - 5), i):
            prev = lines[j].strip()
            if "/**" in prev or "*/" in prev or prev.startswith("//") or prev.startswith("*"):
                has_jsdoc = True
                break
        if not has_jsdoc:
            warnings.append({
                "line": line_no, "severity": "WARNING", "scope": scope,
                "issue": f"Function '{func_name}' is missing descriptive comments."
            })

    def _check_length(self, lines: List[str], i: int, line_no: int, scope: str, func_name: str, warnings: List[Dict[str, Any]]) -> None:
        """Validates function code line lengths do not exceed limit."""
        func_lines = 0
        brace_count = 0
        started = False
        for k in range(i, len(lines)):
            func_lines += 1
            k_line = lines[k]
            if "{" in k_line:
                brace_count += k_line.count("{")
                started = True
            if "}" in k_line:
                brace_count -= k_line.count("}")
            if started and brace_count <= 0:
                break
        if func_lines > 50:
            warnings.append({
                "line": line_no, "severity": "WARNING", "scope": scope,
                "issue": f"Function '{func_name}' exceeds 50 lines ({func_lines} lines)."
            })

    def _calculate_score(self, warnings: List[Dict[str, Any]]) -> int:
        """Deducts score values based on severity of active warnings."""
        score = 100
        for w in warnings:
            if w["severity"] == "ERROR":
                score -= 5
            elif w["severity"] == "WARNING":
                score -= 3
            else:
                score -= 1
        return max(0, score)


class CSSCodeAnalyzer(BaseCodeAnalyzer):
    """
    Concrete analyzer for CSS stylesheets using regex parsing.
    Validates theme color variables usage, !important overrides, and style rules.
    """
    def analyze(self) -> Dict[str, Any]:
        """
        Parses and runs visual code analysis on the target CSS file.
        Returns a report detailing file stats and code quality warnings.
        """
        if not os.path.exists(self.file_path):
            return {
                "metadata": {
                    "file_name": os.path.basename(self.file_path),
                    "classes": [],
                    "stats": {"lines": 0, "comments": 0}
                },
                "health": {"score": 100, "warnings": []}
            }

        content = self._read_content()
        lines = content.splitlines()
        comment_lines = self._count_comments(lines)
        warnings = self._scan_warnings(lines)
        score = self._calculate_score(warnings)

        return {
            "metadata": {
                "file_name": os.path.basename(self.file_path),
                "classes": [],
                "stats": {
                    "lines": len(lines),
                    "comments": comment_lines
                }
            },
            "health": {
                "score": score,
                "warnings": warnings
            }
        }

    def _read_content(self) -> str:
        """Reads stylesheet file content."""
        if self.commit_hash:
            import subprocess
            rel_path = os.path.relpath(self.file_path)
            cmd = ["git", "show", f"{self.commit_hash}:{rel_path}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
            return ""
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _count_comments(self, lines: List[str]) -> int:
        """Counts comment lines in stylesheet."""
        comment_lines = 0
        in_block = False
        for line in lines:
            line_strip = line.strip()
            if in_block:
                comment_lines += 1
                if "*/" in line_strip:
                    in_block = False
            else:
                if line_strip.startswith("/*") or line_strip.endswith("*/"):
                    comment_lines += 1
                    if "*/" not in line_strip:
                        in_block = True
        return comment_lines

    def _scan_warnings(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Scans lines for override rules and hardcoded styling variables."""
        warnings: List[Dict[str, Any]] = []
        for i, line in enumerate(lines):
            line_no = i + 1
            line_strip = line.strip()
            if line_strip.startswith("/*") or line_strip.startswith("*") or not line_strip:
                continue

            if "!important" in line_strip:
                warnings.append({
                    "line": line_no, "severity": "WARNING", "scope": "Styles",
                    "issue": "Avoid using !important overrides in style rules."
                })

            if not line_strip.startswith("--"):
                # Matches hex colors
                hex_colors = re.findall(r"#([a-fA-F0-9]{3,8})\b", line_strip)
                color_funcs = re.findall(r"\b(rgb|rgba|hsl|hsla)\(", line_strip)
                color_words = re.findall(r"\b(color|background|border)\s*:\s*(red|blue|green|black|white)\b", line_strip)
                if hex_colors or color_funcs or color_words:
                    warnings.append({
                        "line": line_no, "severity": "WARNING", "scope": "Styles",
                        "issue": "Hardcoded color value found. Use CSS theme variables instead."
                    })
        return warnings

    def _calculate_score(self, warnings: List[Dict[str, Any]]) -> int:
        """Deducts score based on warning severity."""
        score = 100
        for w in warnings:
            if w["severity"] == "WARNING":
                score -= 3
            else:
                score -= 1
        return max(0, score)


class HTMLCodeAnalyzer(BaseCodeAnalyzer):
    """
    Concrete analyzer for HTML markup files using regex parsing.
    Validates inline styles, alt accessibility attributes, and unique IDs.
    """
    def analyze(self) -> Dict[str, Any]:
        """
        Parses and runs visual code analysis on the target HTML file.
        Returns a report detailing file stats and code quality warnings.
        """
        if not os.path.exists(self.file_path):
            return {
                "metadata": {
                    "file_name": os.path.basename(self.file_path),
                    "classes": [],
                    "stats": {"lines": 0, "comments": 0}
                },
                "health": {"score": 100, "warnings": []}
            }

        content = self._read_content()
        lines = content.splitlines()
        comment_lines = self._count_comments(lines)
        warnings = self._scan_warnings(lines)
        score = self._calculate_score(warnings)

        return {
            "metadata": {
                "file_name": os.path.basename(self.file_path),
                "classes": [],
                "stats": {
                    "lines": len(lines),
                    "comments": comment_lines
                }
            },
            "health": {
                "score": score,
                "warnings": warnings
            }
        }

    def _read_content(self) -> str:
        """Reads markup file content."""
        if self.commit_hash:
            import subprocess
            rel_path = os.path.relpath(self.file_path)
            cmd = ["git", "show", f"{self.commit_hash}:{rel_path}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
            return ""
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _count_comments(self, lines: List[str]) -> int:
        """Counts HTML comment lines."""
        comment_lines = 0
        in_comment = False
        for line in lines:
            line_strip = line.strip()
            if in_comment:
                comment_lines += 1
                if "-->" in line_strip:
                    in_comment = False
            else:
                if line_strip.startswith("<!--"):
                    comment_lines += 1
                    if "-->" not in line_strip:
                        in_comment = True
        return comment_lines

    def _scan_warnings(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Audits markup lines for accessibility, inline styles, and duplicate IDs."""
        warnings: List[Dict[str, Any]] = []
        observed_ids: Dict[str, int] = {}
        for i, line in enumerate(lines):
            line_no = i + 1
            line_strip = line.strip()

            if 'style="' in line_strip:
                warnings.append({
                    "line": line_no, "severity": "WARNING", "scope": "Markup",
                    "issue": "Avoid inline styles; use CSS classes to preserve styling themes."
                })

            if "<img" in line_strip and "alt=" not in line_strip:
                warnings.append({
                    "line": line_no, "severity": "WARNING", "scope": "Markup",
                    "issue": "Image element is missing an alt accessibility attribute."
                })

            ids = re.findall(r'\bid\s*=\s*["\']([^"\']+)["\']', line_strip)
            for element_id in ids:
                observed_ids[element_id] = observed_ids.get(element_id, 0) + 1
                if observed_ids[element_id] > 1:
                    warnings.append({
                        "line": line_no, "severity": "WARNING", "scope": "Markup",
                        "issue": f"Duplicate element ID '{element_id}' found in document."
                    })
        return warnings

    def _calculate_score(self, warnings: List[Dict[str, Any]]) -> int:
        """Deducts scores based on warning severity."""
        score = 100
        for w in warnings:
            if w["severity"] == "WARNING":
                score -= 3
            else:
                score -= 1
        return max(0, score)


class DocService:
    """
    Orchestrates codebase documentation parsing and analysis.
    Maintains Strategy pattern registrations for extension code analyzers.
    """
    def __init__(self, project_path: str = ".") -> None:
        """
        Initializes the DocService instance.
        """
        self.project_path: str = project_path
        self._analyzers: Dict[str, Type[BaseCodeAnalyzer]] = {}

    def register_analyzer(self, ext: str, analyzer_class: Type[BaseCodeAnalyzer]) -> None:
        """Registers a BaseCodeAnalyzer subclass for a specific file extension."""
        self._analyzers[ext] = analyzer_class

    def analyze_project(self, files_list: List[str], commit_hash: Optional[str] = None) -> Dict[str, Any]:
        """Runs the registered analyzers across the given list of files and aggregates stats."""
        reports = self._run_analyzers(files_list, commit_hash)
        return self._aggregate_metrics(reports)

    def _run_analyzers(self, files_list: List[str], commit_hash: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Runs registered analyzers on each file path in the list.
        """
        reports: List[Dict[str, Any]] = []
        for rel_path in files_list:
            file_path: str = os.path.join(self.project_path, rel_path)
            ext: str = os.path.splitext(file_path)[1]

            analyzer_class = self._analyzers.get(ext)
            if analyzer_class:
                analyzer = analyzer_class(file_path, commit_hash)
                report: Dict[str, Any] = analyzer.analyze()
                report["file_path"] = rel_path
                reports.append(report)
        return reports

    def _aggregate_metrics(self, reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregates classes, methods, lines, comments, and warnings across reports.
        """
        scanned_files: int = 0
        total_score: int = 0
        total_classes: int = 0
        total_methods: int = 0
        total_lines: int = 0
        total_comments: int = 0
        all_warnings: List[Dict[str, Any]] = []

        for r in reports:
            if not r:
                continue
            scanned_files += 1
            total_score += r.get("health", {}).get("score", 100)

            meta: Dict[str, Any] = r.get("metadata", {})
            stats: Dict[str, Any] = meta.get("stats", {})
            total_lines += stats.get("lines", 0)
            total_comments += stats.get("comments", 0)

            classes: List[Dict[str, Any]] = meta.get("classes", [])
            total_classes += len(classes)
            for c in classes:
                total_methods += len(c.get("methods", []))

            file_warnings: List[Dict[str, Any]] = r.get("health", {}).get("warnings", [])
            for w in file_warnings:
                w["file"] = r["file_path"]
                all_warnings.append(w)

        avg_score: int = round(total_score / scanned_files) if scanned_files > 0 else 100

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

    def get_markdown_guide(self, guide_name: str, commit_hash: Optional[str] = None) -> str:
        """Retrieves and reads a static markdown documentation guide."""
        docs_dir: str = os.path.join(self.project_path, "docs")
        # Sanitize filename
        safe_name: str = re.sub(r"[^a-zA-Z0-9_\-]", "", guide_name)
        file_path: str = os.path.join(docs_dir, f"{safe_name}.md")
        
        if commit_hash:
            import subprocess
            rel_path = os.path.relpath(file_path)
            cmd = ["git", "show", f"{commit_hash}:{rel_path}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
            return ""
        else:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            return ""

    def get_recent_commits(self, limit: int = 15) -> List[Dict[str, str]]:
        """
        Retrieves the list of recent Git commits.
        Returns a list of dicts: [{'hash': str, 'author': str, 'date': str, 'subject': str}]
        """
        import subprocess
        # Format string: hash (%h), author name (%an), author date short (%ad), subject (%s)
        cmd = ["git", "log", f"-n {limit}", "--pretty=format:%h|%an|%ad|%s", "--date=short"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return []
        
        commits = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "subject": parts[3]
                })
        return commits
