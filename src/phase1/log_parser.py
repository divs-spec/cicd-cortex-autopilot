import re
from typing import List, Optional
from .models import ErrorContext, StepRun


class LogParser:
    """Parses CI logs to extract error information"""
    
    # Common error patterns
    ERROR_PATTERNS = [
        # Python errors
        (r'(?P<type>\w+Error): (?P<message>.+)', 'python_error'),
        # Test failures
        (r'FAILED .+::(?P<test>\w+)', 'test_failure'),
        # Build errors
        (r'error: (?P<message>.+)', 'build_error'),
        # npm/node errors
        (r'npm ERR! (?P<message>.+)', 'npm_error'),
        # TypeScript errors
        (r'TS\d+: (?P<message>.+)', 'typescript_error'),
        # Generic error
        (r'Error: (?P<message>.+)', 'generic_error'),
    ]
    
    # Stack trace patterns
    STACK_TRACE_PATTERNS = [
        r'^\s+File "(?P<file>.+)", line (?P<line>\d+)',  # Python
        r'^\s+at .+ \((?P<file>.+):(?P<line>\d+)',      # JavaScript
        r'^\s+(?P<file>[\w/.-]+):(?P<line>\d+)',        # Generic
    ]
    
    def parse_step_logs(self, step: StepRun) -> List[ErrorContext]:
        """Extract error contexts from a failed step's logs"""
        if not step.log_content or step.conclusion != "failure":
            return []
        
        errors = []
        lines = step.log_content.split('\n')
        
        for i, line in enumerate(lines):
            # Try each error pattern
            for pattern, error_type in self.ERROR_PATTERNS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    error = self._extract_error_context(
                        lines, i, match, error_type
                    )
                    if error:
                        errors.append(error)
                    break
        
        return errors
    
    def _extract_error_context(
        self, 
        lines: List[str], 
        error_line_idx: int,
        match: re.Match,
        error_type: str
    ) -> Optional[ErrorContext]:
        """Extract detailed context around an error"""
        
        # Get error message
        error_message = match.group(0)
        
        # Try to extract file and line number from stack trace
        file_path = None
        line_number = None
        stack_trace = []
        
        # Look ahead for stack trace
        for i in range(error_line_idx + 1, min(error_line_idx + 20, len(lines))):
            line = lines[i]
            
            # Check if line is part of stack trace
            for pattern in self.STACK_TRACE_PATTERNS:
                stack_match = re.match(pattern, line)
                if stack_match:
                    stack_trace.append(line.strip())
                    if not file_path:  # Take first file/line as primary
                        file_path = stack_match.group('file')
                        line_number = int(stack_match.group('line'))
                    break
            
            # Stop if we hit an empty line or another error
            if not line.strip() or any(re.search(p[0], line, re.IGNORECASE) for p in self.ERROR_PATTERNS):
                break
        
        # Get surrounding context (5 lines before and after)
        context_start = max(0, error_line_idx - 5)
        context_end = min(len(lines), error_line_idx + 10)
        surrounding_context = lines[context_start:context_end]
        
        return ErrorContext(
            error_message=error_message,
            error_type=error_type,
            line_number=line_number,
            file_path=file_path,
            stack_trace=stack_trace,
            surrounding_context=[line.strip() for line in surrounding_context if line.strip()]
        )
    
    def extract_failure_summary(self, step: StepRun) -> str:
        """Generate a quick summary of what failed"""
        errors = self.parse_step_logs(step)
        
        if not errors:
            return f"Step '{step.name}' failed with no clear error message"
        
        error = errors[0]  # Focus on first error
        
        summary_parts = [f"Step '{step.name}' failed"]
        
        if error.error_type:
            summary_parts.append(f"({error.error_type})")
        
        if error.file_path:
            summary_parts.append(f"in {error.file_path}")
            if error.line_number:
                summary_parts[2] += f":{error.line_number}"
        
        summary_parts.append(f"- {error.error_message[:100]}")
        
        return " ".join(summary_parts)
