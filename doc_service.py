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

        # Extract JS classes and standalone functions
        classes, standalones = self._scan_js_structures(lines)
        classes_metadata = self._build_js_metadata_report(classes, standalones)

        return {
            "metadata": {
                "file_name": os.path.basename(self.file_path),
                "classes": classes_metadata,
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

    def _clean_js_line(self, line: str) -> str:
        """Strips inline comments and string literals to normalize line."""
        line = re.sub(r"//.*$", "", line)
        line = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', line)
        line = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", line)
        line = re.sub(r"`[^`\\]*(?:\\.[^`\\]*)*`", "``", line)
        return line

    def _extract_jsdoc(self, lines: List[str], index: int) -> str:
        """Extracts docstring/comment block preceding index looking back up to 12 lines."""
        preceding_idx = index - 1
        if preceding_idx < 0:
            return ""
        prev_line = lines[preceding_idx].strip()
        is_cmt = prev_line.startswith("//") or prev_line.startswith("/*")
        is_cmt_cont = prev_line.startswith("*") or prev_line.endswith("*/")
        if not (is_cmt or is_cmt_cont):
            return ""
        start_idx = preceding_idx
        while start_idx >= max(0, index - 12):
            line = lines[start_idx].strip()
            line_is_cmt = line.startswith("//") or line.startswith("/*")
            line_is_cmt_cont = line.startswith("*") or line.endswith("*/") or "*/" in line
            if line_is_cmt or line_is_cmt_cont:
                start_idx -= 1
            else:
                break
        raw_lines = []
        for k in range(start_idx + 1, preceding_idx + 1):
            line = lines[k].strip()
            if line.startswith("/**"):
                line = line[3:]
            elif line.startswith("/*"):
                line = line[2:]
            if line.endswith("*/"):
                line = line[:-2]
            if line.startswith("*"):
                line = line[1:]
            if line.startswith("//"):
                line = line[2:]
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("@"):
                raw_lines.append(cleaned)
        return " ".join(raw_lines).strip()

    def _parse_js_class(self, line: str, line_no: int, lines: List[str]) -> Optional[Dict[str, Any]]:
        """Parses ES6 class definition and extracts class name and docstring."""
        match = re.search(r"\bclass\s+([a-zA-Z0-9_$]+)", line)
        if not match:
            return None
        class_name = match.group(1)
        docstring = self._extract_jsdoc(lines, line_no - 1)
        return {
            "name": class_name,
            "docstring": docstring,
            "methods": []
        }

    def _parse_js_method(self, line: str, line_no: int, lines: List[str]) -> Optional[Dict[str, Any]]:
        """Parses ES6 class method name, docstring, args, line, and length."""
        match = re.search(r"^\s*(?:async\s+|static\s+|\*\s*)*([a-zA-Z0-9_$]+)\s*\(([^)]*)\)", line)
        if not match:
            return None
        name = match.group(1)
        if name in ("if", "for", "while", "switch", "catch", "function", "return"):
            return None
        has_brace = False
        for idx in range(line_no - 1, min(len(lines), line_no + 3)):
            if "{" in lines[idx]:
                has_brace = True
                break
        if not has_brace:
            return None
        args = [a.strip() for a in match.group(2).split(",") if a.strip()]
        docstring = self._extract_jsdoc(lines, line_no - 1)
        length = self._get_function_length(lines, line_no - 1)
        return {
            "name": name,
            "docstring": docstring,
            "args": args,
            "line": line_no,
            "length": length
        }

    def _parse_standalone_function(self, line: str, line_no: int, lines: List[str]) -> Optional[Dict[str, Any]]:
        """Parses standalone or arrow function definitions."""
        match = re.search(r"\b(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)", line)
        if not match:
            match = re.search(r"\b(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>", line)
        if not match:
            match = re.search(r"\b(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?([a-zA-Z0-9_$]+)\s*=>", line)
            if match:
                name, args = match.group(1), [match.group(2).strip()]
            else:
                return None
        else:
            name, args = match.group(1), [a.strip() for a in match.group(2).split(",") if a.strip()]
        if name in ("if", "for", "while", "switch", "catch", "function", "return"):
            return None
        docstring = self._extract_jsdoc(lines, line_no - 1)
        length = self._get_function_length(lines, line_no - 1)
        return {
            "name": name,
            "docstring": docstring,
            "args": args,
            "line": line_no,
            "length": length
        }

    def _handle_non_class_line(
        self, line: str, line_no: int, lines: List[str], cleaned: str, brace_level: int,
        classes_metadata: List[Dict[str, Any]], standalone_functions: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """Handles line when outside class context, looking for class or standalone function."""
        class_info = self._parse_js_class(line, line_no, lines)
        if class_info:
            class_info["awaiting_brace"] = True
            classes_metadata.append(class_info)
            if "{" in cleaned:
                class_info["awaiting_brace"] = False
                class_info["start_brace_level"] = brace_level
                brace_level += cleaned.count("{") - cleaned.count("}")
            return class_info, brace_level
        func_info = self._parse_standalone_function(line, line_no, lines)
        if func_info:
            standalone_functions.append(func_info)
        return None, brace_level

    def _scan_js_structures(self, lines: List[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Scans JavaScript lines to extract actual classes and standalone functions."""
        classes_metadata = []
        standalone_functions = []
        current_class = None
        brace_level = 0
        in_block_comment = False
        for i, line in enumerate(lines):
            line_no = i + 1
            line_strip = line.strip()
            if in_block_comment:
                if "*/" in line_strip:
                    in_block_comment = False
                continue
            if line_strip.startswith("/*"):
                if "*/" not in line_strip:
                    in_block_comment = True
                continue
            if line_strip.startswith("//"):
                continue
            cleaned = self._clean_js_line(line)
            if current_class:
                opened, closed = cleaned.count("{"), cleaned.count("}")
                if current_class.get("awaiting_brace", True):
                    if "{" in cleaned:
                        current_class["awaiting_brace"] = False
                        current_class["start_brace_level"] = brace_level
                        brace_level += opened - closed
                    continue
                method_info = self._parse_js_method(line, line_no, lines)
                if method_info:
                    current_class["methods"].append(method_info)
                brace_level += opened - closed
                if brace_level <= current_class["start_brace_level"]:
                    current_class = None
            else:
                current_class, brace_level = self._handle_non_class_line(
                    line, line_no, lines, cleaned, brace_level, classes_metadata, standalone_functions
                )
        return classes_metadata, standalone_functions

    def _build_js_metadata_report(self, classes_metadata: List[Dict[str, Any]], standalone_functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Constructs list of metadata classes including a virtual module class for standalones."""
        for cls in classes_metadata:
            cls.pop("start_brace_level", None)
            cls.pop("awaiting_brace", None)
        if standalone_functions:
            filename = os.path.basename(self.file_path)
            virtual_class = {
                "name": f"{filename} Module",
                "docstring": f"Contains standalone functions in {filename}.",
                "methods": standalone_functions
            }
            classes_metadata.append(virtual_class)
        return classes_metadata

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

        func_lines = self._get_function_length(lines, i)
        self._check_naming(func_name, line_no, scope, warnings)
        if func_lines > 60:
            self._check_jsdoc(lines, i, line_no, scope, func_name, warnings)

        if func_lines > 150:
            warnings.append({
                "line": line_no, "severity": "WARNING", "scope": scope,
                "issue": f"Function '{func_name}' exceeds 150 lines ({func_lines} lines)."
            })

    def _get_function_length(self, lines: List[str], i: int) -> int:
        """Calculates function lines length."""
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
        return func_lines

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

    def _calculate_score(self, warnings: List[Dict[str, Any]]) -> int:
        """Deducts score values based on severity of active warnings."""
        score: float = 100.0
        for w in warnings:
            if w["severity"] == "ERROR":
                score -= 1.0
            elif w["severity"] == "WARNING":
                score -= 0.5
            else:
                score -= 0.2
        return max(0, round(score))


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
        
        # Design system brand colors (lowercase hex values)
        brand_colors = {
            "0b0f19", "0d121e", "161e31", "1e2943", "0f1626", "0f172a",
            "38bdf8", "a855f7", "2dd4bf", "fbbf24", "10b981", "f43f5e",
            "e11d48", "0ea5e9", "9333ea", "fda4af", "f1f5f9", "94a3b8",
            "64748b", "fff", "ffffff", "000", "000000",
            # Additional UI and hover palette shades (sky, purple, slate, ambers, emeralds, indigos)
            "c084fc", "7dd3fc", "6ee7b7", "34d399", "f87171", "a78bfa", "a7f3d0",
            "cbd5e1", "475569", "334155", "1e293b", "0f172a", "090d16", "1e1b4b",
            "2563eb", "3b82f6", "60a5fa", "93c5fd", "bfdbfe", "dbeafe", "eff6ff",
            "13131a", "1e293b", "334155", "0a0f1d", "111827", "1f2937", "374151",
            "4b5563", "9ca3af", "d1d5db", "e5e7eb", "f3f4f6", "f9fafb", "0d1321",
            "0d192d", "0d1322", "1e293b", "1e2942", "22304f", "30416b",
            "0ea5e9", "0284c7", "7dd3fc", "bae6fd", "e0f2fe", "f0f9ff", # sky
            "fbbf24", "f59e0b", "d97706", "b45309", "fcd34d", "fde68a", "fef3c7", # ambers
            "10b981", "059669", "047857", "34d399", "6ee7b7", "a7f3d0", "d1fae5", # greens
            "2dd4bf", "0d9488", "14b8a6", "99f6e4", "ccfbf1", "f0fdfa", # teals
            "a855f7", "9333ea", "7c3aed", "c084fc", "d8b4fe", "e9d5ff", "faf5ff", # purples
            "f43f5e", "e11d48", "be123c", "fb7185", "fca5a5", "fecaca", "fee2e2", # reds
            "1e1b4b", "312e81", "3730a3", "4338ca", "4f46e5", "6366f1", "818cf8", "a5b4fc" # indigos
        }
        
        # Allowed RGB/RGBA prefixes corresponding to brand colors and neutrals
        allowed_rgb_prefixes = (
            "0,0,0", "255,255,255", "56,189,248", "251,191,36", 
            "168,85,247", "45,212,191", "16,185,129", "244,63,94",
            "15,22,38", "15,23,42", "13,18,30", "22,30,49", "30,41,67",
            # Add general gray / slate values
            "100,116,139", "148,163,184", "241,245,249", "15,23,42",
            "13,19,33", "255,255,255", "0,0,0", "14,165,233", "147,51,234",
            # Additional brand-related rgb prefixes
            "33,27,49", "4,6,12", "192,132,252", "10,15,26"
        )

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
                non_neutral_hex = False
                for h in hex_colors:
                    h_lower = h.lower()
                    base_hex = h_lower
                    if len(h_lower) == 8:
                        base_hex = h_lower[:6]
                    elif len(h_lower) == 4:
                        base_hex = h_lower[:3]
                    
                    if base_hex not in brand_colors:
                        non_neutral_hex = True

                # Matches rgb/rgba/hsl/hsla functions
                color_funcs = re.findall(r"\b(rgb|rgba|hsl|hsla)\(([^)]+)\)", line_strip)
                has_non_neutral_func = False
                for name, params in color_funcs:
                    params_clean = "".join(params.split())
                    if "var(" in params_clean:
                        continue
                    
                    if any(params_clean.startswith(prefix) for prefix in allowed_rgb_prefixes):
                        continue
                    has_non_neutral_func = True

                # Matches simple literal colors
                color_words = re.findall(r"\b(color|background|border)\s*:\s*(red|blue|green)\b", line_strip)

                if non_neutral_hex or has_non_neutral_func or color_words:
                    warnings.append({
                        "line": line_no, "severity": "WARNING", "scope": "Styles",
                        "issue": "Hardcoded color value found. Use CSS theme variables instead."
                    })
        return warnings

    def _calculate_score(self, warnings: List[Dict[str, Any]]) -> int:
        """Deducts score based on warning severity."""
        score: float = 100.0
        for w in warnings:
            if w["severity"] == "WARNING":
                score -= 0.5
            else:
                score -= 0.2
        return max(0, round(score))


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

            if re.search(r'\bstyle\s*=\s*["\']', line_strip):
                style_match = re.search(r'\bstyle\s*=\s*["\']([^"\']+)["\']', line_strip)
                if style_match:
                    style_content = style_match.group(1)
                    if any(prop in style_content for prop in ("color", "background", "border", "font")):
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
        score: float = 100.0
        for w in warnings:
            if w["severity"] == "WARNING":
                score -= 0.5
            else:
                score -= 0.2
        return max(0, round(score))


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
        self.last_synced_commit: Optional[str] = None

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

    def _generate_git_footer_md(self) -> str:
        """
        Generates the Git HEAD version metadata footer line.
        """
        commits = self.get_recent_commits(limit=1)
        if commits:
            c = commits[0]
            return f"*Documentation compiled from Git HEAD:* `{c['hash']}` ({c['author']} on {c['date']})"
        return "*Documentation compiled from Git HEAD: unknown*"

    def _generate_api_reference_md(self, report: Dict[str, Any]) -> str:
        """
        Generates API Reference structural summary markdown.
        """
        stats = report.get("stats", {})
        md_lines = [
            "### 📊 Codebase Structural Summary",
            f"- **Scanned Modules**: {report.get('files_scanned', 0)} files",
            f"- **Detected Classes**: {stats.get('classes', 0)} classes",
            f"- **Total Methods/Functions**: {stats.get('methods', 0)} methods",
            f"- **Lines of Code**: {stats.get('lines', 0)} lines (Comments: {stats.get('comments', 0)} lines)",
            "",
            self._generate_git_footer_md()
        ]
        return "\n".join(md_lines)

    def _generate_health_scorecard_md(self, report: Dict[str, Any], test_results: Optional[Dict[str, Any]]) -> str:
        """
        Generates markdown scorecard summarizing codebase quality and test health.
        """
        score = report.get("score", 100)
        warnings = report.get("warnings", [])
        warnings_count = len(warnings)
        
        md_lines = [
            "### 🛡️ Code Health Scorecard",
            f"- **Code Quality Score**: **{score}%**",
            f"- **Active Linter Warnings**: {warnings_count} active warnings",
        ]
        
        if test_results:
            stats = test_results.get("stats", {})
            rate = stats.get("success_rate", 100)
            total = stats.get("total", 0)
            passed = stats.get("passed", 0)
            failed = stats.get("failed", 0)
            dur = test_results.get("duration", 0.0)
            md_lines.append(f"- **Unit Tests Success Rate**: **{rate}%** ({passed}/{total} Passed, {failed} Failed)")
            md_lines.append(f"- **Test Execution Duration**: {dur}s")
            
        md_lines.append("")
        md_lines.append(self._generate_git_footer_md())
        return "\n".join(md_lines)

    def _replace_placeholder_in_file(self, file_path: str, start_marker: str, end_marker: str, content: str) -> None:
        """
        Replaces text between start and end markers inside a file with new content.
        """
        if not os.path.exists(file_path):
            return
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
        replacement = f"{start_marker}\n{content}\n{end_marker}"
        new_content = re.sub(pattern, replacement, file_content, flags=re.DOTALL)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    def _fetch_cached_test_results(self) -> Optional[Dict[str, Any]]:
        """
        Queries TestRunnerService to fetch the last run test results.
        """
        try:
            from test_service import TestRunnerService
            runner = TestRunnerService()
            results = runner.get_last_results()
            if not results:
                runner._refresh_test_cache()
                results = {
                    "stats": {"total": len(runner.all_tests_cache), "passed": 0, "failed": 0, "success_rate": 0},
                    "duration": 0.0,
                    "results": list(runner.all_tests_cache.values())
                }
            return results
        except Exception:
            return None

    def _get_current_git_commit(self) -> Optional[str]:
        """
        Returns the current git HEAD commit hash.
        """
        import subprocess
        cmd = ["git", "rev-parse", "HEAD"]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_path)
        if res.returncode == 0:
            return res.stdout.strip()
        return None

    def get_api_endpoints(self) -> List[Dict[str, Any]]:
        """
        Parses server.py to dynamically extract all Flask API endpoints and docstrings.
        """
        server_path = os.path.join(self.project_path, "server.py")
        if not os.path.exists(server_path):
            return []
        with open(server_path, "r", encoding="utf-8") as f:
            content = f.read()
        try:
            tree = ast.parse(content, filename=server_path)
        except Exception:
            return []
        endpoints = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._check_route_decorator(node, endpoints)
        return endpoints

    def _check_route_decorator(self, node: ast.FunctionDef, endpoints: List[Dict[str, Any]]) -> None:
        """
        Helper to check if a function node has @app.route and extract endpoint details.
        """
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            is_route = (
                isinstance(func, ast.Attribute) and 
                isinstance(func.value, ast.Name) and 
                func.value.id == "app" and 
                func.attr == "route"
            )
            if not is_route:
                continue
            path = ""
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                path = decorator.args[0].value
            methods = ["GET"]
            for kw in decorator.keywords:
                if kw.arg == "methods" and isinstance(kw.value, ast.List):
                    methods = [el.value for el in kw.value.elts if isinstance(el, ast.Constant)]
            doc = ast.get_docstring(node) or ""
            desc = doc.strip().split("\n")[0] if doc else "No description available."
            for method in methods:
                endpoints.append({
                    "path": path,
                    "method": method,
                    "desc": desc
                })

    def sync_dynamic_docs(self, test_results: Optional[Dict[str, Any]] = None) -> None:
        """
        Regenerates API Reference and Health Scorecard markdown and writes them to placeholder markers.
        """
        files_list = [
            "models.py", "repositories.py", "services.py", "server.py", "doc_service.py",
            "src/main.js", "src/style.css", "index.html"
        ]
        report = self.analyze_project(files_list)
        arch_md = self._generate_api_reference_md(report)
        arch_path = os.path.join(self.project_path, "docs", "architecture.md")
        self._replace_placeholder_in_file(
            arch_path, 
            "<!-- DYNAMIC_API_REFERENCE_START -->", 
            "<!-- DYNAMIC_API_REFERENCE_END -->", 
            arch_md
        )
        if not test_results:
            test_results = self._fetch_cached_test_results()
        health_md = self._generate_health_scorecard_md(report, test_results)
        testing_path = os.path.join(self.project_path, "docs", "testing.md")
        self._replace_placeholder_in_file(
            testing_path, 
            "<!-- DYNAMIC_HEALTH_SCORECARD_START -->", 
            "<!-- DYNAMIC_HEALTH_SCORECARD_END -->", 
            health_md
        )
        try:
            self.last_synced_commit = self._get_current_git_commit()
        except Exception:
            pass

    def get_markdown_guide(self, guide_name: str, commit_hash: Optional[str] = None) -> str:
        """Retrieves and reads a static markdown documentation guide."""
        if not commit_hash:
            try:
                curr_hash = self._get_current_git_commit()
                if curr_hash and curr_hash != self.last_synced_commit:
                    self.sync_dynamic_docs()
            except Exception:
                pass
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
