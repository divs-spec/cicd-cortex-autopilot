import os
import requests
from typing import Optional, List
from github import Github, GithubException
from .models import WorkflowRun, JobRun, StepRun


class GitHubClient:
    """Client for interacting with GitHub Actions API"""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token required. Set GITHUB_TOKEN env variable.")
        
        self.github = Github(self.token)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        })
    
    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> WorkflowRun:
        """Fetch workflow run details"""
        try:
            repository = self.github.get_repo(f"{owner}/{repo}")
            run = repository.get_workflow_run(run_id)
            
            workflow_run = WorkflowRun(
                id=run.id,
                name=run.name,
                status=run.status,
                conclusion=run.conclusion,
                html_url=run.html_url,
                head_branch=run.head_branch,
                head_sha=run.head_sha,
                created_at=run.created_at.isoformat(),
                updated_at=run.updated_at.isoformat(),
                repository=f"{owner}/{repo}"
            )
            
            # Fetch jobs for this run
            workflow_run.jobs = self._get_jobs(owner, repo, run_id)
            
            return workflow_run
            
        except GithubException as e:
            raise Exception(f"Failed to fetch workflow run: {e}")
    
    def _get_jobs(self, owner: str, repo: str, run_id: int) -> List[JobRun]:
        """Fetch all jobs for a workflow run"""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        response = self.session.get(url)
        response.raise_for_status()
        
        jobs_data = response.json()
        jobs = []
        
        for job_data in jobs_data.get("jobs", []):
            job = JobRun(
                id=job_data["id"],
                name=job_data["name"],
                status=job_data["status"],
                conclusion=job_data.get("conclusion"),
                html_url=job_data["html_url"],
                started_at=job_data.get("started_at"),
                completed_at=job_data.get("completed_at")
            )
            
            # Parse steps
            for step_data in job_data.get("steps", []):
                step = StepRun(
                    name=step_data["name"],
                    status=step_data["status"],
                    conclusion=step_data.get("conclusion"),
                    number=step_data["number"],
                    started_at=step_data.get("started_at"),
                    completed_at=step_data.get("completed_at")
                )
                job.steps.append(step)
            
            # Fetch logs for failed jobs
            if job.conclusion == "failure":
                job_logs = self._get_job_logs(owner, repo, job.id)
                self._attach_logs_to_steps(job, job_logs)
            
            jobs.append(job)
        
        return jobs
    
    def _get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        """Fetch raw logs for a specific job"""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
        response = self.session.get(url)
        response.raise_for_status()
        return response.text
    
    def _attach_logs_to_steps(self, job: JobRun, logs: str):
        """Parse logs and attach to corresponding steps"""
        # Simple heuristic: split by step timestamps/markers
        # GitHub logs include markers like "##[group]Step name"
        current_step_idx = 0
        current_log_buffer = []
        
        for line in logs.split('\n'):
            # Check for step marker
            if '##[group]' in line and current_step_idx < len(job.steps):
                # Save previous step's logs
                if current_log_buffer and current_step_idx > 0:
                    job.steps[current_step_idx - 1].log_content = '\n'.join(current_log_buffer)
                current_log_buffer = []
                current_step_idx += 1
            
            current_log_buffer.append(line)
        
        # Attach final step's logs
        if current_log_buffer and current_step_idx > 0:
            job.steps[current_step_idx - 1].log_content = '\n'.join(current_log_buffer)
    
    def get_latest_failed_run(self, owner: str, repo: str) -> Optional[WorkflowRun]:
        """Get the most recent failed workflow run"""
        try:
            repository = self.github.get_repo(f"{owner}/{repo}")
            runs = repository.get_workflow_runs(status="completed", conclusion="failure")
            
            for run in runs[:1]:  # Get most recent
                return self.get_workflow_run(owner, repo, run.id)
            
            return None
            
        except GithubException as e:
            raise Exception(f"Failed to fetch latest run: {e}")
