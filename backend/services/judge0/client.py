"""
Judge0 API Client for code execution.
Provides production-grade code execution with comprehensive error handling.
"""
import logging
import httpx
from typing import Dict, Optional, Any
from django.conf import settings

logger = logging.getLogger(__name__)

# Judge0 API Configuration
JUDGE0_API_URL = getattr(settings, "JUDGE0_API_URL", "https://judge0-ce.p.rapidapi.com")
JUDGE0_API_KEY = getattr(settings, "JUDGE0_API_KEY", "")
JUDGE0_API_HOST = getattr(settings, "JUDGE0_API_HOST", "judge0-ce.p.rapidapi.com")

# Timeout settings
SUBMISSION_TIMEOUT = 30  # seconds for initial submission
RESULT_TIMEOUT = 60  # seconds to wait for results
MAX_RETRIES = 3

# Supported languages
LANGUAGE_MAP = {
    "python": 71,  # Python 3
    "python3": 71,
    "javascript": 63,  # JavaScript (Node.js)
    "java": 62,  # Java
    "cpp": 54,  # C++ (GCC 9.4.0)
    "c": 50,  # C (GCC 9.4.0)
    "csharp": 51,  # C# (Mono 6.12.0)
    "go": 60,  # Go (1.18.5)
    "rust": 73,  # Rust (1.73.0)
    "php": 68,  # PHP (8.2.8)
    "ruby": 72,  # Ruby (3.2.2)
    "sql": 86,  # SQL (SQLite 3)
}


class Judge0Client:
    """Production-grade Judge0 API client with comprehensive error handling."""

    def __init__(self):
        """Initialize Judge0 client with production settings."""
        self.api_url = JUDGE0_API_URL
        self.api_key = JUDGE0_API_KEY
        self.api_host = JUDGE0_API_HOST
        
        if not self.api_key:
            logger.warning("Judge0 API key not configured. Code execution will not work.")
        
        # Configure HTTP client with production settings
        self.http_client = httpx.Client(
            timeout=SUBMISSION_TIMEOUT,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30,
            ),
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Judge0 API requests."""
        return {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
            "Content-Type": "application/json",
        }

    def submit_code(
        self,
        source_code: str,
        language_id: int,
        stdin: str = "",
        expected_output: Optional[str] = None,
        memory_limit: int = 256 * 1024 * 1024,  # 256 MB
        time_limit: int = 10,  # 10 seconds
    ) -> Dict[str, Any]:
        """
        Submit code for execution.
        
        Args:
            source_code: The code to execute
            language_id: Judge0 language ID
            stdin: Standard input for the program
            expected_output: Expected output for validation
            memory_limit: Memory limit in bytes
            time_limit: Time limit in seconds
            
        Returns:
            Dict with submission token and status
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Judge0 API key not configured",
                "status": "error"
            }

        try:
            payload = {
                "source_code": source_code,
                "language_id": language_id,
                "stdin": stdin,
                "expected_output": expected_output,
                "memory_limit": memory_limit,
                "time_limit": time_limit,
            }

            logger.info(f"Submitting code for execution (language_id={language_id})")
            
            response = self.http_client.post(
                f"{self.api_url}/submissions",
                json=payload,
                headers=self._get_headers(),
            )
            
            if response.status_code == 201:
                result = response.json()
                logger.info(f"Code submitted successfully, token: {result.get('token')}")
                return {
                    "success": True,
                    "token": result.get("token"),
                    "status": "submitted"
                }
            else:
                error_msg = response.text
                logger.error(f"Failed to submit code: {response.status_code} - {error_msg}")
                return {
                    "success": False,
                    "error": f"Failed to submit code: {error_msg}",
                    "status": "error"
                }
                
        except httpx.TimeoutError:
            logger.error("Timeout while submitting code to Judge0")
            return {
                "success": False,
                "error": "Timeout while submitting code",
                "status": "error"
            }
        except Exception as e:
            logger.exception("Error submitting code to Judge0")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }

    def get_submission_status(self, token: str) -> Dict[str, Any]:
        """
        Get the status of a code submission.
        
        Args:
            token: Submission token from submit_code
            
        Returns:
            Dict with submission status and results
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Judge0 API key not configured",
                "status": "error"
            }

        try:
            response = self.http_client.get(
                f"{self.api_url}/submissions/{token}",
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                result = response.json()
                status_id = result.get("status", {}).get("id")
                
                logger.info(f"Submission {token} status: {status_id}")
                
                # Map Judge0 status IDs to readable status
                status_map = {
                    1: "in_queue",
                    2: "processing",
                    3: "accepted",
                    4: "wrong_answer",
                    5: "time_limit_exceeded",
                    6: "compilation_error",
                    7: "runtime_error",
                    8: "internal_error",
                }
                
                return {
                    "success": True,
                    "token": token,
                    "status": status_map.get(status_id, "unknown"),
                    "status_id": status_id,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "compile_output": result.get("compile_output", ""),
                    "time": result.get("time"),
                    "memory": result.get("memory"),
                }
            else:
                error_msg = response.text
                logger.error(f"Failed to get submission status: {response.status_code} - {error_msg}")
                return {
                    "success": False,
                    "error": f"Failed to get status: {error_msg}",
                    "status": "error"
                }
                
        except Exception as e:
            logger.exception("Error getting submission status from Judge0")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }

    def execute_code(
        self,
        source_code: str,
        language: str,
        stdin: str = "",
        expected_output: Optional[str] = None,
        timeout: int = RESULT_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Execute code and wait for results (blocking).
        
        Args:
            source_code: The code to execute
            language: Programming language name (e.g., "python", "javascript")
            stdin: Standard input for the program
            expected_output: Expected output for validation
            timeout: Maximum time to wait for results in seconds
            
        Returns:
            Dict with execution results
        """
        # Map language name to Judge0 language ID
        language_id = LANGUAGE_MAP.get(language.lower())
        if not language_id:
            logger.warning(f"Unsupported language: {language}")
            return {
                "success": False,
                "error": f"Unsupported language: {language}",
                "status": "error"
            }

        # Submit code
        submit_result = self.submit_code(
            source_code=source_code,
            language_id=language_id,
            stdin=stdin,
            expected_output=expected_output,
        )

        if not submit_result["success"]:
            return submit_result

        token = submit_result["token"]

        # Poll for results
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status_result = self.get_submission_status(token)
            
            if not status_result["success"]:
                return status_result

            status = status_result["status"]
            
            # Check if execution is complete
            if status in ["accepted", "wrong_answer", "time_limit_exceeded", 
                           "compilation_error", "runtime_error", "internal_error"]:
                return status_result
            
            # Wait before polling again
            time.sleep(1)
        
        # Timeout waiting for results
        logger.warning(f"Timeout waiting for submission {token} results")
        return {
            "success": False,
            "error": "Timeout waiting for execution results",
            "status": "timeout"
        }

    def validate_code_output(
        self,
        stdout: str,
        expected_output: str,
        tolerance: float = 0.0
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
_judge0_client = None


def get_judge0_client() -> Judge0Client:
    """Get singleton Judge0 client instance."""
    global _judge0_client
    if _judge0_client is None:
        _judge0_client = Judge0Client()
    return _judge0_client
