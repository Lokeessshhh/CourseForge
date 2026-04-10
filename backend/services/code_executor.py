"""
Local Code Execution Service.
Supports Python, JavaScript, Java, and C++ without external API dependencies.
Uses subprocess for secure code execution with timeouts and output capture.
"""
import logging
import subprocess
import tempfile
import os
import shutil
from pathlib import Path
from typing import Dict, Optional, Any
from django.conf import settings

logger = logging.getLogger(__name__)

# Execution limits
EXECUTION_TIMEOUT = 10  # seconds
MEMORY_LIMIT_MB = 256

# Language configurations
LANGUAGE_CONFIG = {
    "python": {
        "command": ["python", "-u"],
        "file_extension": ".py",
        "compile": False,
        "run_directly": True,
    },
    "python3": {
        "command": ["python", "-u"],
        "file_extension": ".py",
        "compile": False,
        "run_directly": True,
    },
    "javascript": {
        "command": ["node"],
        "file_extension": ".js",
        "compile": False,
        "run_directly": True,
    },
    "java": {
        "command": ["java", "-cp", "{temp_dir}", "{class_name}"],
        "file_extension": ".java",
        "compile": True,
        "compile_command": ["javac"],
        "run_directly": False,
    },
    "cpp": {
        "command": ["{exe_path}"],
        "file_extension": ".cpp",
        "compile": True,
        "compile_command": ["g++", "-o", "{exe_path}", "{source_file}"],
        "run_directly": False,
    },
}


class CodeExecutor:
    """Local code executor supporting multiple languages with subprocess."""

    def __init__(self):
        """Initialize code executor."""
        self.timeout = getattr(settings, "CODE_EXECUTION_TIMEOUT", EXECUTION_TIMEOUT)
        self.memory_limit_mb = MEMORY_LIMIT_MB

    def execute_code(
        self,
        source_code: str,
        language: str,
        stdin: str = "",
        expected_output: Optional[str] = None,
        timeout: int = EXECUTION_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Execute code locally and return results.

        Args:
            source_code: The code to execute
            language: Programming language (python, javascript, java, cpp)
            stdin: Standard input for the program
            expected_output: Expected output for validation
            timeout: Maximum execution time in seconds

        Returns:
            Dict with execution results matching Judge0 format
        """
        language_lower = language.lower()
        if language_lower not in LANGUAGE_CONFIG:
            logger.warning(f"Unsupported language: {language}")
            return {
                "success": False,
                "error": f"Unsupported language: {language}. Supported: python, javascript, java, cpp",
                "status": "error",
                "stdout": "",
                "stderr": "",
                "compile_output": "",
                "time": 0,
                "memory": 0,
            }

        config = LANGUAGE_CONFIG[language_lower]
        temp_dir = None

        try:
            # Create temporary directory for execution
            temp_dir = tempfile.mkdtemp(prefix=f"code_exec_{language_lower}_")

            # Write source code to temporary file
            class_name = self._extract_java_class_name(source_code) if language_lower == "java" else "Main"
            file_name = f"{class_name}{config['file_extension']}"
            source_file = os.path.join(temp_dir, file_name)

            with open(source_file, "w", encoding="utf-8") as f:
                f.write(source_code)

            logger.info(f"Created temporary {language} file: {source_file}")
            logger.info("=" * 60)
            logger.info(f"📝 EXECUTING {language.upper()} CODE:")
            logger.info("=" * 60)
            for i, line in enumerate(source_code.split('\n'), 1):
                logger.info(f"  {i:3d} | {line}")
            logger.info("=" * 60)

            # Compile if needed (Java, C++)
            if config.get("compile"):
                logger.info(f"🔨 Compiling {language_lower} code...")
                compile_result = self._compile_code(source_file, config, temp_dir, language_lower)
                if not compile_result["success"]:
                    logger.error(f"❌ Compilation failed: {compile_result.get('compile_output', '')}")
                    return compile_result
                else:
                    logger.info(f"✅ Compilation successful")

            # Execute the code
            if language_lower in ["python", "python3", "javascript"]:
                # Direct execution
                cmd = config["command"] + [source_file]
            elif language_lower == "java":
                # Java execution
                cmd = ["java", "-cp", temp_dir, class_name]
            elif language_lower == "cpp":
                # C++ execution
                exe_path = compile_result.get("exe_path", "")
                if not exe_path or not os.path.exists(exe_path):
                    return {
                        "success": False,
                        "error": "Compilation failed: executable not found",
                        "status": "error",
                        "stdout": "",
                        "stderr": compile_result.get("compile_output", ""),
                        "compile_output": compile_result.get("compile_output", ""),
                        "time": 0,
                        "memory": 0,
                    }
                cmd = [exe_path]
            else:
                return {
                    "success": False,
                    "error": f"Unsupported language: {language}",
                    "status": "error",
                }

            # Run the code with timeout
            start_time = self._get_time_ms()

            logger.info(f"🚀 Running command: {' '.join(cmd)}")
            if stdin:
                logger.info(f"📥 Standard input: {stdin}")

            try:
                result = subprocess.run(
                    cmd,
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=temp_dir,
                )

                end_time = self._get_time_ms()
                execution_time = (end_time - start_time) / 1000.0  # Convert to seconds

                stdout = result.stdout or ""
                stderr = result.stderr or ""
                compile_output = ""

                # Determine status
                if result.returncode == 0:
                    status = "accepted"
                    logger.info(f"✅ Execution completed successfully in {execution_time:.3f}s")
                elif result.returncode == -9 or result.returncode == 137:
                    status = "time_limit_exceeded"
                    logger.error(f"⏱️  Time limit exceeded after {timeout}s")
                elif result.returncode == 1 or result.returncode == 255:
                    status = "runtime_error"
                    logger.error(f"❌ Runtime error (exit code {result.returncode})")
                else:
                    status = "runtime_error"
                    logger.error(f"❌ Runtime error (exit code {result.returncode})")

                # Log outputs
                logger.info("-" * 60)
                logger.info(f"📤 STDOUT:")
                if stdout:
                    for i, line in enumerate(stdout.split('\n'), 1):
                        logger.info(f"  {i:3d} | {line}")
                else:
                    logger.info("  (empty)")
                logger.info("-" * 60)

                if stderr:
                    logger.error(f"⚠️  STDERR:")
                    for i, line in enumerate(stderr.split('\n'), 1):
                        logger.error(f"  {i:3d} | {line}")
                    logger.error("-" * 60)

                if compile_output:
                    logger.info(f"🔧 COMPILE OUTPUT:")
                    for i, line in enumerate(compile_output.split('\n'), 1):
                        logger.info(f"  {i:3d} | {line}")
                    logger.info("-" * 60)

                # Validate output if expected
                if expected_output:
                    is_correct = self.validate_code_output(stdout, expected_output)
                    logger.info(f"{'✅' if is_correct else '❌'} Output validation: {'PASSED' if is_correct else 'FAILED'}")
                    if expected_output != stdout:
                        logger.info(f"📋 Expected output:")
                        for i, line in enumerate(expected_output.split('\n'), 1):
                            logger.info(f"  {i:3d} | {line}")

                logger.info("=" * 60)

                return {
                    "success": True,
                    "status": status,
                    "status_id": self._status_to_id(status),
                    "stdout": stdout,
                    "stderr": stderr,
                    "compile_output": compile_output,
                    "time": round(execution_time, 3),
                    "memory": 0,  # Not tracked for local execution
                    "token": "",
                }

            except subprocess.TimeoutExpired:
                logger.warning(f"⏱️  Code execution timed out after {timeout}s")
                return {
                    "success": False,
                    "error": f"Execution timed out after {timeout} seconds",
                    "status": "time_limit_exceeded",
                    "status_id": 5,
                    "stdout": "",
                    "stderr": "Time limit exceeded",
                    "compile_output": "",
                    "time": timeout,
                    "memory": 0,
                }

        except FileNotFoundError as e:
            error_msg = str(e)
            language_cmd = LANGUAGE_CONFIG.get(language_lower, {}).get("command", [language_lower])[0]
            logger.error(f"❌ {language_cmd} not found: {error_msg}")
            return {
                "success": False,
                "error": f"{language_cmd} is not installed on this system. Please install it to run {language} code.",
                "status": "error",
                "status_id": 8,
                "stdout": "",
                "stderr": "",
                "compile_output": f"{language_cmd} not found: {error_msg}",
                "time": 0,
                "memory": 0,
            }

        except Exception as e:
            logger.exception(f"❌ Error executing {language} code")
            return {
                "success": False,
                "error": str(e),
                "status": "error",
                "status_id": 8,
                "stdout": "",
                "stderr": str(e),
                "compile_output": "",
                "time": 0,
                "memory": 0,
            }

        finally:
            # Cleanup temporary directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info(f"🧹 Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temporary directory: {e}")

    def _compile_code(
        self,
        source_file: str,
        config: dict,
        temp_dir: str,
        language: str,
    ) -> Dict[str, Any]:
        """
        Compile code for languages that require compilation (Java, C++).

        Args:
            source_file: Path to source file
            config: Language configuration
            temp_dir: Temporary directory path
            language: Language name

        Returns:
            Dict with compilation result
        """
        try:
            if language == "java":
                # Java compilation
                cmd = ["javac", source_file]
            elif language == "cpp":
                # C++ compilation
                exe_name = "main.exe" if os.name == "nt" else "main"
                exe_path = os.path.join(temp_dir, exe_name)
                cmd = ["g++", "-o", exe_path, source_file]
                return self._compile_with_cmd(cmd, source_file, temp_dir, language, exe_path)
            else:
                return {
                    "success": False,
                    "error": f"Compilation not supported for {language}",
                    "compile_output": "",
                }

            return self._compile_with_cmd(cmd, source_file, temp_dir, language)

        except FileNotFoundError as e:
            compiler = cmd[0] if 'cmd' in locals() else language
            return {
                "success": False,
                "error": f"{compiler} is not installed. Please install it to compile {language} code.",
                "status": "error",
                "status_id": 6,
                "stdout": "",
                "stderr": "",
                "compile_output": f"Compiler not found: {compiler}",
                "time": 0,
                "memory": 0,
            }

    def _compile_with_cmd(
        self,
        cmd: list,
        source_file: str,
        temp_dir: str,
        language: str,
        exe_path: str = "",
    ) -> Dict[str, Any]:
        """Execute compilation command and return result."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=EXECUTION_TIMEOUT,
                cwd=temp_dir,
            )

            compile_output = result.stdout + result.stderr

            if result.returncode == 0:
                logger.info(f"Compilation successful for {language}")
                result_dict = {
                    "success": True,
                    "compile_output": compile_output,
                }
                if exe_path:
                    result_dict["exe_path"] = exe_path
                return result_dict
            else:
                logger.warning(f"Compilation failed for {language}: {compile_output}")
                return {
                    "success": False,
                    "error": f"Compilation failed",
                    "status": "compilation_error",
                    "status_id": 6,
                    "stdout": "",
                    "stderr": "",
                    "compile_output": compile_output,
                    "time": 0,
                    "memory": 0,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Compilation timed out",
                "status": "error",
                "status_id": 8,
                "stdout": "",
                "stderr": "",
                "compile_output": "Compilation timed out",
                "time": 0,
                "memory": 0,
            }

        except Exception as e:
            logger.exception(f"Error during compilation")
            return {
                "success": False,
                "error": str(e),
                "status": "error",
                "status_id": 8,
                "stdout": "",
                "stderr": "",
                "compile_output": str(e),
                "time": 0,
                "memory": 0,
            }

    def _extract_java_class_name(self, source_code: str) -> str:
        """Extract public class name from Java source code."""
        import re
        match = re.search(r"public\s+class\s+(\w+)", source_code)
        if match:
            return match.group(1)
        return "Main"

    def _get_time_ms(self) -> float:
        """Get current time in milliseconds."""
        import time
        return time.time() * 1000

    def _status_to_id(self, status: str) -> int:
        """Map status string to Judge0-compatible status ID."""
        status_map = {
            "accepted": 3,
            "wrong_answer": 4,
            "time_limit_exceeded": 5,
            "compilation_error": 6,
            "runtime_error": 7,
            "internal_error": 8,
            "error": 8,
        }
        return status_map.get(status, 8)

    def validate_code_output(
        self,
        stdout: str,
        expected_output: str,
        tolerance: float = 0.0,
    ) -> bool:
        """
        Validate if output matches expected output.

        Args:
            stdout: Actual output from code execution
            expected_output: Expected output
            tolerance: Tolerance for numerical comparisons

        Returns:
            True if output matches expected, False otherwise
        """
        if not stdout or not expected_output:
            return False

        # Normalize outputs (strip whitespace, convert to lowercase)
        stdout_normalized = stdout.strip().lower()
        expected_normalized = expected_output.strip().lower()

        # Exact match
        if stdout_normalized == expected_normalized:
            return True

        # Numerical comparison with tolerance
        try:
            stdout_num = float(stdout_normalized)
            expected_num = float(expected_normalized)
            return abs(stdout_num - expected_num) <= tolerance
        except ValueError:
            pass

        return False


# Singleton instance
_executor = None


def get_code_executor() -> CodeExecutor:
    """Get singleton CodeExecutor instance."""
    global _executor
    if _executor is None:
        _executor = CodeExecutor()
    return _executor
