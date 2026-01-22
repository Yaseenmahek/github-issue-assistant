"""
Pydantic models for request/response validation and data structures.

This module defines all data models used throughout the application,
ensuring type safety and validation.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
import re


class AnalyzeRequest(BaseModel):
    """Request model for issue analysis endpoint.
    
    Attributes:
        repo_url: Full GitHub repository URL (e.g., https://github.com/facebook/react)
        issue_number: Issue number to analyze (must be positive integer)
    """
    repo_url: str = Field(
        ...,
        description="GitHub repository URL",
        examples=["https://github.com/facebook/react"]
    )
    issue_number: int = Field(
        ...,
        gt=0,
        description="GitHub issue number (must be positive)",
        examples=[12345]
    )
    
    @field_validator('repo_url')
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Validate that the URL is a valid GitHub repository URL."""
        # Accept various GitHub URL formats
        patterns = [
            r'^https?://github\.com/[\w\-\.]+/[\w\-\.]+/?$',  # https://github.com/owner/repo
            r'^https?://github\.com/[\w\-\.]+/[\w\-\.]+\.git$',  # https://github.com/owner/repo.git
            r'^github\.com/[\w\-\.]+/[\w\-\.]+/?$',  # github.com/owner/repo
            r'^[\w\-\.]+/[\w\-\.]+$',  # owner/repo (simple format)
        ]
        
        if not any(re.match(pattern, v.strip()) for pattern in patterns):
            raise ValueError(
                'Invalid GitHub URL format. Expected formats: '
                'https://github.com/owner/repo OR owner/repo'
            )
        return v.strip()


class IssueAnalysis(BaseModel):
    """LLM-generated analysis of a GitHub issue.
    
    This model represents the structured output from the LLM service.
    
    Attributes:
        summary: Concise summary of the issue (2-3 sentences)
        type: Classification of the issue type
        priority_score: Priority rating (1-5) with justification
        suggested_labels: List of 2-3 relevant labels
        potential_impact: Description of the issue's potential impact
        confidence_score: AI confidence in the analysis (0-100)
    """
    summary: str = Field(
        ...,
        description="Concise summary of the issue",
        min_length=10,
        max_length=1000
    )
    type: Literal["bug", "feature_request", "question", "documentation", "enhancement", "other"] = Field(
        ...,
        description="Type of the issue"
    )
    priority_score: str = Field(
        ...,
        description="Priority score (1-5) with justification",
        examples=["4 - High priority because it affects many users"]
    )
    suggested_labels: List[str] = Field(
        ...,
        description="List of 2-3 suggested labels",
        min_length=1,
        max_length=5
    )
    potential_impact: str = Field(
        ...,
        description="Description of potential impact",
        min_length=10,
        max_length=1000
    )
    confidence_score: Optional[int] = Field(
        None,
        description="AI confidence in analysis (0-100)",
        ge=0,
        le=100
    )


class AnalyzeResponse(BaseModel):
    """Response model for issue analysis endpoint.
    
    Attributes:
        success: Whether the analysis was successful
        data: The analysis results (only present if success=True)
        issue_url: Full URL to the GitHub issue
        error: Error message (only present if success=False)
        cached: Whether result was from cache
        analysis_time_seconds: Time taken for analysis
        tokens_used: Number of tokens used (if available)
    """
    success: bool = Field(..., description="Whether the analysis succeeded")
    data: Optional[IssueAnalysis] = Field(
        None,
        description="Analysis results"
    )
    issue_url: str = Field(
        ...,
        description="URL to the GitHub issue",
        examples=["https://github.com/facebook/react/issues/12345"]
    )
    error: Optional[str] = Field(
        None,
        description="Error message if analysis failed"
    )
    cached: bool = Field(
        False,
        description="Whether this result was retrieved from cache"
    )
    analysis_time_seconds: Optional[float] = Field(
        None,
        description="Time taken for analysis in seconds"
    )
    tokens_used: Optional[int] = Field(
        None,
        description="Number of tokens used by LLM"
    )


class GitHubIssueData(BaseModel):
    """Internal model for GitHub issue data.
    
    This model represents the data fetched from GitHub API.
    
    Attributes:
        title: Issue title
        body: Issue body/description
        comments: List of comment texts
        labels: Existing labels on the issue
        state: Issue state (open/closed)
        created_at: ISO timestamp of creation
        updated_at: ISO timestamp of last update
    """
    title: str
    body: Optional[str] = ""
    comments: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    state: str = "open"
    created_at: str = ""
    updated_at: str = ""


class HealthResponse(BaseModel):
    """Response model for health check endpoint.
    
    Attributes:
        status: Service status
        version: Application version
    """
    status: Literal["healthy", "unhealthy"] = Field(
        ...,
        description="Service health status"
    )
    version: str = Field(
        ...,
        description="Application version",
        examples=["1.0.0"]
    )