import os
import json
from typing import List
from anthropic import Anthropic
from .models import WorkflowRun, JobRun, ErrorContext, FailureAnalysis
from .log_parser import LogParser


class LLMAnalyzer:
    """Uses LLM to analyze CI failures and suggest fixes"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY env variable.")
        
        self.client = Anthropic(api_key=self.api_key)
        self.parser = LogParser()
    
    def analyze_workflow_failure(self, workflow_run: WorkflowRun) -> FailureAnalysis:
        """Analyze a failed workflow run and generate insights"""
        
        # Collect all errors from failed jobs
        all_errors = []
        failed_jobs = []
        failed_steps = []
        
        for job in workflow_run.jobs:
            if job.conclusion == "failure":
                failed_jobs.append(job.name)
                
                for step in job.steps:
                    if step.conclusion == "failure":
                        failed_steps.append(f"{job.name}/{step.name}")
                        errors = self.parser.parse_step_logs(step)
                        all_errors.extend(errors)
        
        # Build context for LLM
        context = self._build_analysis_context(workflow_run, failed_jobs, failed_steps, all_errors)
        
        # Get LLM analysis
        llm_response = self._query_llm(context)
        
        # Parse LLM response
        return self._parse_llm_response(
            workflow_run.id,
            failed_jobs,
            failed_steps,
            all_errors,
            llm_response
        )
    
    def _build_analysis_context(
        self,
        workflow_run: WorkflowRun,
        failed_jobs: List[str],
        failed_steps: List[str],
        errors: List[ErrorContext]
    ) -> str:
        """Build structured context for LLM analysis"""
        
        context_parts = [
            f"# CI Failure Analysis Request",
            f"",
            f"## Workflow Information",
            f"- Repository: {workflow_run.repository}",
            f"- Workflow: {workflow_run.name}",
            f"- Branch: {workflow_run.head_branch}",
            f"- Commit: {workflow_run.head_sha[:8]}",
            f"- Status: {workflow_run.conclusion}",
            f"",
            f"## Failed Jobs",
        ]
        
        for job in failed_jobs:
            context_parts.append(f"- {job}")
        
        context_parts.append("")
        context_parts.append("## Failed Steps")
        for step in failed_steps:
            context_parts.append(f"- {step}")
        
        context_parts.append("")
        context_parts.append("## Error Details")
        
        for i, error in enumerate(errors[:5], 1):  # Limit to first 5 errors
            context_parts.append(f"### Error {i}")
            context_parts.append(f"Type: {error.error_type}")
            context_parts.append(f"Message: {error.error_message}")
            
            if error.file_path:
                location = error.file_path
                if error.line_number:
                    location += f":{error.line_number}"
                context_parts.append(f"Location: {location}")
            
            if error.stack_trace:
                context_parts.append("Stack trace:")
                for line in error.stack_trace[:10]:
                    context_parts.append(f"  {line}")
            
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def _query_llm(self, context: str) -> str:
        """Send context to Claude and get analysis"""
        
        prompt = f"""{context}

Based on the above CI failure information, provide a comprehensive analysis in the following JSON format:

{{
  "summary": "One-sentence overview of what failed",
  "likely_cause": "Detailed explanation of the root cause",
  "suggested_actions": [
    "Specific action 1",
    "Specific action 2"
  ],
  "confidence": 0.85
}}

Focus on:
1. The most likely root cause based on error messages and stack traces
2. Actionable steps a developer can take to fix the issue
3. Any patterns or common issues you recognize

Respond ONLY with valid JSON, no additional text."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.content[0].text
    
    def _parse_llm_response(
        self,
        run_id: int,
        failed_jobs: List[str],
        failed_steps: List[str],
        errors: List[ErrorContext],
        llm_response: str
    ) -> FailureAnalysis:
        """Parse LLM JSON response into FailureAnalysis"""
        
        try:
            # Clean response (remove markdown code blocks if present)
            cleaned = llm_response.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:-1])
            
            data = json.loads(cleaned)
            
            return FailureAnalysis(
                workflow_run_id=run_id,
                summary=data.get("summary", "Analysis unavailable"),
                failed_jobs=failed_jobs,
                failed_steps=failed_steps,
                error_contexts=errors,
                likely_cause=data.get("likely_cause", "Unknown"),
                suggested_actions=data.get("suggested_actions", []),
                confidence=float(data.get("confidence", 0.5))
            )
        
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback if JSON parsing fails
            return FailureAnalysis(
                workflow_run_id=run_id,
                summary="Failed to parse LLM response",
                failed_jobs=failed_jobs,
                failed_steps=failed_steps,
                error_contexts=errors,
                likely_cause=llm_response[:500],
                suggested_actions=["Review logs manually"],
                confidence=0.0
            )
