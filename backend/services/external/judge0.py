"""
Judge0 API integration for code execution and evaluation.
Supports multiple programming languages for code assessment.
"""
import logging
from typing import Optional, Dict, Any
import aiohttp
import asyncio
import base64

from django.conf import settings

logger = logging.getLogger(__name__)

JUDGE0_API_URL = "https://judge0-ce.p.rapidapi.com"
JUDGE0_RAPIDAPI_HOST = "judge0-ce.p.rapidapi.com"


class Judge0Service:
    """
    Judge0 code execution service.
    Used for evaluating and running user code submissions.
    """

    # Language ID mapping
    LANGUAGE_IDS = {
        "python": 71,
        "python3": 71,
        "javascript": 63,
        "nodejs": 63,
        "java": 62,
        "c": 50,
        "cpp": 54,
        "csharp": 51,
        "c#": 51,
        "go": 60,
        "rust": 73,
        "ruby": 72,
        "php": 68,
        "swift": 83,
        "kotlin": 78,
        "typescript": 74,
        "sql": 82,
        "bash": 46,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """
        Initialize Judge0 service.
        
        Args:
            api_key: RapidAPI key (defaults to settings.RAPIDAPI_KEY)
            api_url: Judge0 API URL
        """
        self.api_key = api_key or getattr(settings, "RAPIDAPI_KEY", None)
        self.api_url = api_url or getattr(settings, "JUDGE0_API_URL", JUDGE0_API_URL)
        
        if not self.api_key:
            logger.warning("RapidAPI key not configured for Judge0")

    def _get_headers(self) -> Dict[str, str]:
        """Get API headers."""
        return {
            "X-RapidAPI-Key": self.api_key or "",
            "X-RapidAPI-Host": JUDGE0_RAPIDAPI_HOST,
            "Content-Type": "application/json",
        }

    def get_language_id(self, language: str) -> Optional[int]:
        """
        Get Judge0 language ID from language name.
        
        Args:
            language: Language name (case-insensitive)
            
        Returns:
            Language ID or None
        """
        return self.LANGUAGE_IDS.get(language.lower())

    def execute_code(
        self,
        source_code: str,
        language: str = "python",
        stdin: str = "",
        expected_output: Optional[str] = None,
        cpu_time_limit: float = 2.0,
        memory_limit: int = 128000,  # KB
        wait: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute code synchronously.
        
        Args:
            source_code: Code to execute
            language: Programming language
            stdin: Standard input
            expected_output: Expected output for comparison
            cpu_time_limit: CPU time limit in seconds
            memory_limit: Memory limit in KB
            wait: Wait for execution to complete
            
        Returns:
            Execution result dict
        """
        return asyncio.run(self._async_execute(
            source_code=source_code,
            language=language,
            stdin=stdin,
            expected_output=expected_output,
            cpu_time_limit=cpu_time_limit,
            memory_limit=memory_limit,
            wait=wait,
        ))

    async def _async_execute(
        self,
        source_code: str,
        language: str,
        stdin: str,
        expected_output: Optional[str],
        cpu_time_limit: float,
        memory_limit: int,
        wait: bool,
    ) -> Dict[str, Any]:
        """Async code execution."""
        if not self.api_key:
            return {
                "success": False,
                "error": "Judge0 API key not configured",
            }

        language_id = self.get_language_id(language)
        if not language_id:
            return {
                "success": False,
                "error": f"Unsupported language: {language}",
            }

        # Encode source code
        encoded_source = base64.b64encode(source_code.encode()).decode()
        encoded_stdin = base64.b64encode(stdin.encode()).decode() if stdin else None

        payload = {
            "source_code": encoded_source,
            "language_id": language_id,
            "stdin": encoded_stdin,
            "cpu_time_limit": int(cpu_time_limit * 1000),  # Convert to ms
            "memory_limit": memory_limit,
        }

        if expected_output:
            payload["expected_output"] = base64.b64encode(expected_output.encode()).decode()

        try:
            async with aiohttp.ClientSession() as session:
                # Submit submission
                url = f"{self.api_url}/submissions"
                if wait:
                    url += "?wait=true"

                async with session.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        logger.error("Judge0 submission error: %s", error_text)
                        return {
                            "success": False,
                            "error": f"API error: {response.status}",
                        }

                    result = await response.json()
                    return self._format_result(result)

        except asyncio.TimeoutError:
            return {"success": False, "error": "Execution timed out"}
        except Exception as e:
            logger.exception("Judge0 execution failed: %s", e)
            return {"success": False, "error": str(e)}

    def _format_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format Judge0 result."""
        status_id = result.get("status", {}).get("id", 0)
        
        # Status codes: 1-3 = processing, 3 = accepted, 4-8 = errors
        success = status_id == 3
        
        # Decode outputs
        stdout = None
        if result.get("stdout"):
            try:
                stdout = base64.b64decode(result["stdout"]).decode()
            except Exception:
                stdout = result["stdout"]

        stderr = None
        if result.get("stderr"):
            try:
                stderr = base64.b64decode(result["stderr"]).decode()
            except Exception:
                stderr = result["stderr"]

        compile_output = None
        if result.get("compile_output"):
            try:
                compile_output = base64.b64decode(result["compile_output"]).decode()
            except Exception:
                compile_output = result["compile_output"]

        return {
            "success": success,
            "status": result.get("status", {}).get("description", "Unknown"),
            "status_id": status_id,
            "stdout": stdout,
            "stderr": stderr,
            "compile_output": compile_output,
            "time": result.get("time"),
            "memory": result.get("memory"),
            "exit_code": result.get("exit_code"),
            "token": result.get("token"),
        }

    def evaluate_quiz_code(
        self,
        source_code: str,
        language: str,
        test_cases: list,
    ) -> Dict[str, Any]:
        """
        Evaluate code against test cases.
        
        Args:
            source_code: Code to evaluate
            language: Programming language
            test_cases: List of {input, expected_output} dicts
            
        Returns:
            Evaluation result with pass/fail for each test case
        """
        results = []
        passed = 0

        for i, test in enumerate(test_cases):
            result = self.execute_code(
                source_code=source_code,
                language=language,
                stdin=test.get("input", ""),
                expected_output=test.get("expected_output"),
            )

            test_passed = result.get("success", False)
            if test_passed:
                passed += 1

            results.append({
                "test_case": i + 1,
                "passed": test_passed,
                "output": result.get("stdout"),
                "error": result.get("error") or result.get("stderr") or result.get("compile_output"),
            })

        return {
            "total_tests": len(test_cases),
            "passed": passed,
            "failed": len(test_cases) - passed,
            "score": round(passed / len(test_cases) * 100) if test_cases else 0,
            "results": results,
        }


def execute_code(source_code: str, language: str = "python", **kwargs) -> Dict[str, Any]:
    """
    Convenience function for code execution.
    
    Args:
        source_code: Code to execute
        language: Programming language
        **kwargs: Additional arguments
        
    Returns:
        Execution result
    """
    service = Judge0Service()
    return service.execute_code(source_code, language=language, **kwargs)
