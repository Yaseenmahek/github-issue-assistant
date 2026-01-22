"""
FastAPI application for GitHub Issue Assistant.

This module defines the main FastAPI application with endpoints for
issue analysis and health checks, along with middleware and error handling.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .models import AnalyzeRequest, AnalyzeResponse, HealthResponse, IssueAnalysis
from .github_client import (
    GitHubClient,
    GitHubClientError,
    GitHubURLError,
    GitHubNotFoundError,
    GitHubForbiddenError,
    GitHubRateLimitError
)
from .llm_service import LLMAnalyzer, LLMServiceError
from .cache import AnalysisCache
from . import __version__
import time


logger = logging.getLogger(__name__)


# Lifespan context manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup and shutdown)."""
    # Startup
    logger.info("Starting GitHub Issue Assistant API")
    logger.info(f"Version: {__version__}")
    
    # Initialize settings to validate environment variables
    settings = get_settings()
    logger.info("Configuration loaded successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down GitHub Issue Assistant API")


# Create FastAPI application
app = FastAPI(
    title="GitHub Issue Assistant API",
    description="AI-powered GitHub issue analysis using OpenAI GPT models",
    version=__version__,
    lifespan=lifespan
)


# Configure CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",  # Streamlit default port
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    """Log all incoming requests and responses."""
    logger.info(f"Request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        logger.info(
            f"Response: {request.method} {request.url.path} - "
            f"Status: {response.status_code}"
        )
        return response
    except Exception as e:
        logger.error(
            f"Request failed: {request.method} {request.url.path} - "
            f"Error: {str(e)}"
        )
        raise


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.
    
    Returns:
        Health status and version information
    """
    return HealthResponse(
        status="healthy",
        version=__version__
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_issue(request: AnalyzeRequest):
    """Analyze a GitHub issue using AI.
    
    This endpoint fetches issue data from GitHub, analyzes it using
    OpenAI GPT, and returns structured insights. Results are cached
    for 24 hours to improve performance.
    
    Args:
        request: Analysis request with repo URL and issue number
        
    Returns:
        Structured analysis of the issue with metrics
        
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    settings = get_settings()
    start_time = time.time()
    
    # Initialize clients
    github_client = GitHubClient(settings.GITHUB_TOKEN)
    llm_analyzer = LLMAnalyzer(settings.OPENAI_API_KEY)
    cache = AnalysisCache()
    
    try:
        # Parse repository URL
        try:
            owner, repo = github_client.parse_repo_url(request.repo_url)
        except GitHubURLError as e:
            logger.warning(f"Invalid URL: {request.repo_url}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid GitHub URL",
                    "message": str(e),
                    "suggestion": "Please provide a valid GitHub repository URL like: https://github.com/owner/repo"
                }
            )
        
        # Construct issue URL for response
        issue_url = f"https://github.com/{owner}/{repo}/issues/{request.issue_number}"
        
        # Check cache first
        cached_result = cache.get(owner, repo, request.issue_number)
        if cached_result:
            analysis_time = time.time() - start_time
            logger.info(f"Returning cached result for {owner}/{repo}#{request.issue_number}")
            return AnalyzeResponse(
                success=True,
                data=IssueAnalysis(**cached_result),
                issue_url=issue_url,
                cached=True,
                analysis_time_seconds=round(analysis_time, 2)
            )
        
        # Fetch issue data from GitHub
        try:
            issue_data = github_client.fetch_issue(owner, repo, request.issue_number)
            logger.info(f"Fetched issue data: {owner}/{repo}#{request.issue_number}")
        except GitHubNotFoundError as e:
            logger.warning(f"Issue not found: {owner}/{repo}#{request.issue_number}")
            return AnalyzeResponse(
                success=False,
                issue_url=issue_url,
                error=str(e)
            )
        except GitHubForbiddenError as e:
            logger.warning(f"Access forbidden: {owner}/{repo}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Access Forbidden",
                    "message": str(e),
                    "suggestion": "Ensure your GitHub token has access to this repository"
                }
            )
        except GitHubRateLimitError as e:
            logger.error(f"Rate limit exceeded")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate Limit Exceeded",
                    "message": str(e),
                    "suggestion": "Please wait a few minutes before trying again"
                }
            )
        except GitHubClientError as e:
            logger.error(f"GitHub client error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "GitHub API Error",
                    "message": str(e)
                }
            )
        
        # Analyze issue with LLM
        try:
            analysis = llm_analyzer.analyze_issue(issue_data, owner, repo)
            analysis_time = time.time() - start_time
            
            logger.info(f"Successfully analyzed issue: {owner}/{repo}#{request.issue_number}")
            
            # Cache the result
            cache.set(owner, repo, request.issue_number, analysis.model_dump())
            
            return AnalyzeResponse(
                success=True,
                data=analysis,
                issue_url=issue_url,
                cached=False,
                analysis_time_seconds=round(analysis_time, 2)
            )
            
        except LLMServiceError as e:
            logger.error(f"LLM service error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "AI Analysis Failed",
                    "message": str(e),
                    "suggestion": "Please try again. If the issue persists, check your OpenAI API key and quota."
                }
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred while processing your request.",
                "suggestion": "Please try again or contact support if the issue persists."
            }
        )


# Custom exception handler for better error responses
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.exception(f"Unhandled exception: {str(exc)}")
    settings = get_settings()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.LOG_LEVEL == "DEBUG" else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
