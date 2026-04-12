"""
Code Content Parser - Production-grade parser for LLM-generated code sections.

Parses raw markdown code content into structured JSON with:
- Multiple code examples with titles, descriptions, code blocks, explanations, outputs, common mistakes
- Practice exercises with descriptions and expected outputs

Handles edge cases gracefully:
- Missing sections
- Malformed markdown
- Multiple code blocks per example
- Empty content
"""
import re
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class CodeContentParser:
    """
    Parses LLM-generated code content into structured format.
    
    Expected input format (from LLM):
    ```markdown
    ## Example 1: Title Here
    
    Description text here...
    
    ```python
    code here
    ```
    
    **Explanation:**
    - point 1
    - point 2
    
    **Output:**
    ```
    output here
    ```
    
    **Common Mistakes:**
    - mistake 1
    
    ## Example 2: ...
    
    ### Practice Exercise
    
    Exercise description...
    
    **Expected Output:**
    ```
    expected output
    ```
    ```
    
    Returns structured JSON:
    ```json
    {
        "examples": [
            {
                "title": "Example 1: Title Here",
                "description": "Description text here...",
                "code": "code here",
                "language": "python",
                "explanation": ["point 1", "point 2"],
                "output": "output here",
                "common_mistakes": ["mistake 1"]
            }
        ],
        "practice_exercise": {
            "description": "Exercise description...",
            "expected_output": "expected output",
            "hints": []
        }
    }
    ```
    """
    
    # Regex patterns for parsing
    EXAMPLE_HEADER_PATTERN = re.compile(
        r'^##\s+Example\s+\d+[:.]\s*(.+?)(?=\n|$)',
        re.MULTILINE | re.IGNORECASE
    )
    
    PRACTICE_HEADER_PATTERN = re.compile(
        r'^#{1,3}\s+(?:Practice\s+(?:Exercise|Problem)|Try\s+this\s+yourself|Exercise)[:.]?\s*$',
        re.MULTILINE | re.IGNORECASE
    )
    
    CODE_BLOCK_PATTERN = re.compile(
        r'```(\w*)\n(.*?)```',
        re.DOTALL
    )
    
    EXPLANATION_PATTERN = re.compile(
        r'\*\*Explanation:\*\*\s*\n(.*?)(?=\n\*\*|\n##|\Z)',
        re.DOTALL | re.IGNORECASE
    )
    
    OUTPUT_PATTERN = re.compile(
        r'\*\*Output:\*\*\s*\n(.*?)(?=\n\*\*|\n##|\Z)',
        re.DOTALL | re.IGNORECASE
    )
    
    COMMON_MISTAKES_PATTERN = re.compile(
        r'\*\*Common\s+Mistakes:\*\*\s*\n(.*?)(?=\n\*\*|\n##|\Z)',
        re.DOTALL | re.IGNORECASE
    )
    
    EXPECTED_OUTPUT_PATTERN = re.compile(
        r'\*\*(?:Expected\s+Output|Output):\*\*\s*\n(.*?)(?=\n\*\*|\n##|\Z)',
        re.DOTALL | re.IGNORECASE
    )
    
    BULLET_POINT_PATTERN = re.compile(
        r'^-\s+(.+?)$',
        re.MULTILINE
    )
    
    @classmethod
    def parse(cls, raw_content: str) -> Dict[str, Any]:
        """
        Parse raw code content into structured format.
        
        Args:
            raw_content: Raw markdown string from LLM
            
        Returns:
            Dict with 'examples' and 'practice_exercise' keys
        """
        if not raw_content or not raw_content.strip():
            return cls._empty_result()
        
        try:
            result = {
                "examples": [],
                "practice_exercise": None
            }
            
            # Split into examples by ## Example headers
            examples_raw = cls._split_examples(raw_content)
            
            for example_text in examples_raw:
                example = cls._parse_example(example_text)
                if example:
                    result["examples"].append(example)
            
            # Extract practice exercise if present
            practice = cls._extract_practice_exercise(raw_content)
            if practice:
                result["practice_exercise"] = practice
            
            # If no examples were found but we have content, create a single example
            if not result["examples"] and raw_content.strip():
                result["examples"].append(cls._parse_as_single_example(raw_content))
            
            return result
            
        except Exception as e:
            logger.error(f"Code content parsing failed: {e}", exc_info=True)
            # Return raw content as a single example on error
            return {
                "examples": [cls._parse_as_single_example(raw_content)],
                "practice_exercise": None
            }
    
    @classmethod
    def _split_examples(cls, content: str) -> List[str]:
        """Split content by ## Example headers."""
        # Find all example header positions
        matches = list(cls.EXAMPLE_HEADER_PATTERN.finditer(content))
        
        if not matches:
            return [content]
        
        examples = []
        for i, match in enumerate(matches):
            start = match.start()
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                # Find where practice exercise starts (if any)
                practice_match = cls.PRACTICE_HEADER_PATTERN.search(content, match.end())
                end = practice_match.start() if practice_match else len(content)
            
            examples.append(content[start:end])
        
        return examples
    
    @classmethod
    def _parse_example(cls, text: str) -> Optional[Dict[str, Any]]:
        """Parse a single example section."""
        if not text or not text.strip():
            return None
        
        # Extract title from header
        title_match = cls.EXAMPLE_HEADER_PATTERN.match(text)
        title = f"Example: {title_match.group(1).strip()}" if title_match else "Code Example"
        
        # Extract description (text before first code block)
        first_code_match = cls.CODE_BLOCK_PATTERN.search(text)
        description = text[:first_code_match.start()].strip() if first_code_match else text.strip()
        
        # Remove the title from description if present
        if title_match:
            description = description[title_match.end():].strip()
        
        # Extract code blocks
        code_blocks = cls._extract_code_blocks(text)
        
        # Use the first code block as the main code
        main_code = ""
        language = ""
        if code_blocks:
            main_code = code_blocks[0]["code"].strip()
            language = code_blocks[0].get("language", "")
        
        # Extract explanation
        explanation = cls._extract_bullet_points(text, cls.EXPLANATION_PATTERN)
        
        # Extract output
        output = cls._extract_output(text)
        
        # Extract common mistakes
        common_mistakes = cls._extract_bullet_points(text, cls.COMMON_MISTAKES_PATTERN)
        
        return {
            "title": title,
            "description": description,
            "code": main_code,
            "language": language or "python",
            "explanation": explanation,
            "output": output,
            "common_mistakes": common_mistakes
        }
    
    @classmethod
    def _extract_code_blocks(cls, text: str) -> List[Dict[str, str]]:
        """Extract all code blocks from text."""
        blocks = []
        for match in cls.CODE_BLOCK_PATTERN.finditer(text):
            language = match.group(1).strip() or "python"
            code = match.group(2).strip()
            if code:
                blocks.append({
                    "language": language,
                    "code": code
                })
        return blocks
    
    @classmethod
    def _extract_bullet_points(cls, text: str, pattern: re.Pattern) -> List[str]:
        """Extract bullet points from a section."""
        match = pattern.search(text)
        if not match:
            return []
        
        section_text = match.group(1).strip()
        points = cls.BULLET_POINT_PATTERN.findall(section_text)
        
        # Clean up points
        cleaned_points = []
        for point in points:
            point = point.strip().rstrip('-').strip()
            if point:
                cleaned_points.append(point)
        
        return cleaned_points
    
    @classmethod
    def _extract_output(cls, text: str) -> str:
        """Extract output from output section."""
        match = cls.OUTPUT_PATTERN.search(text)
        if not match:
            return ""
        
        output_text = match.group(1).strip()
        
        # If output is in a code block, extract it
        code_match = cls.CODE_BLOCK_PATTERN.search(output_text)
        if code_match:
            return code_match.group(2).strip()
        
        return output_text
    
    @classmethod
    def _extract_practice_exercise(cls, content: str) -> Optional[Dict[str, Any]]:
        """Extract practice exercise section."""
        match = cls.PRACTICE_HEADER_PATTERN.search(content)
        if not match:
            return None
        
        # Get text after practice header
        practice_text = content[match.end():].strip()
        
        if not practice_text:
            return None
        
        # Extract description (text before expected output)
        expected_output_match = cls.EXPECTED_OUTPUT_PATTERN.search(practice_text)
        
        description = ""
        expected_output = ""
        hints = []
        
        if expected_output_match:
            description = practice_text[:expected_output_match.start()].strip()
            output_section = expected_output_match.group(1).strip()
            
            # Extract expected output from code block if present
            code_match = cls.CODE_BLOCK_PATTERN.search(output_section)
            if code_match:
                expected_output = code_match.group(2).strip()
            else:
                expected_output = output_section
        else:
            description = practice_text
        
        # Extract hints if present
        hints_section = re.search(
            r'\*\*Hints?:\*\*\s*\n(.*?)(?=\n\*\*|\Z)',
            description,
            re.DOTALL | re.IGNORECASE
        )
        if hints_section:
            hints = cls.BULLET_POINT_PATTERN.findall(hints_section.group(1))
            hints = [h.strip() for h in hints if h.strip()]
        
        return {
            "description": description,
            "expected_output": expected_output,
            "hints": hints
        }
    
    @classmethod
    def _parse_as_single_example(cls, content: str) -> Dict[str, Any]:
        """Parse content as a single example when no ## Example headers found."""
        code_blocks = cls._extract_code_blocks(content)
        
        main_code = ""
        language = "python"
        if code_blocks:
            main_code = code_blocks[0]["code"]
            language = code_blocks[0].get("language", "python")
        
        # Extract any explanations or mistakes present
        explanation = cls._extract_bullet_points(content, cls.EXPLANATION_PATTERN)
        common_mistakes = cls._extract_bullet_points(content, cls.COMMON_MISTAKES_PATTERN)
        output = cls._extract_output(content)
        
        return {
            "title": "Code Examples",
            "description": content[:500].strip() if len(content) > 500 else content.strip(),
            "code": main_code,
            "language": language,
            "explanation": explanation,
            "output": output,
            "common_mistakes": common_mistakes
        }
    
    @classmethod
    def _empty_result(cls) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "examples": [],
            "practice_exercise": None
        }


# Convenience function for direct use
def parse_code_content(raw_content: str) -> Dict[str, Any]:
    """
    Parse raw code content into structured format.
    
    Args:
        raw_content: Raw markdown string from LLM
        
    Returns:
        Structured dict with examples and practice exercise
    """
    return CodeContentParser.parse(raw_content)
