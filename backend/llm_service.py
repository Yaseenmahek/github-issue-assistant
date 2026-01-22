"""
LLM service for analyzing GitHub issues using OpenAI GPT models.

This module handles prompt construction, LLM API calls, and response parsing
with comprehensive error handling and token management.
"""

import json
import logging
from typing import Dict, Any, List
from openai import OpenAI, OpenAIError, APIError, RateLimitError, APIConnectionError
from openai.types.chat import ChatCompletion

from .models import GitHubIssueData, IssueAnalysis


logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Base exception for LLM service errors."""
    pass


class LLMAnalyzer:
    """Analyzer for GitHub issues using OpenAI LLMs.
    
    This class constructs sophisticated prompts with few-shot examples
    and handles all aspects of LLM interaction.
    
    Attributes:
        client: OpenAI API client
        model: Model identifier (default: gpt-3.5-turbo-1106)
        max_tokens: Maximum tokens for response
    """
    
    # Model configuration
    DEFAULT_MODEL = "gpt-3.5-turbo-1106"  # Supports JSON mode
    MAX_RESPONSE_TOKENS = 1000
    MAX_INPUT_TOKENS = 3000  # Conservative limit for input truncation
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        """Initialize LLM analyzer.
        
        Args:
            api_key: OpenAI API key
            model: Model to use (must support JSON mode)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        logger.info(f"Initialized LLM analyzer with model: {model}")
    
    def analyze_issue(
        self,
        issue_data: GitHubIssueData,
        owner: str,
        repo: str
    ) -> IssueAnalysis:
        """Analyze a GitHub issue using LLM.
        
        Args:
            issue_data: GitHub issue data
            owner: Repository owner
            repo: Repository name
            
        Returns:
            IssueAnalysis with structured insights
            
        Raises:
            LLMServiceError: If analysis fails
        """
        try:
            # Construct the prompt
            prompt = self._build_prompt(issue_data, owner, repo)
            
            logger.info(f"Analyzing issue: {owner}/{repo} with {len(prompt)} chars prompt")
            
            # Call OpenAI API with JSON mode
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert GitHub issue analyst. You analyze issues and provide structured JSON output with insights about type, priority, impact, and suggested labels."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Lower temperature for more consistent output
                max_tokens=self.MAX_RESPONSE_TOKENS
            )
            
            # Parse and validate response
            analysis = self._parse_response(response)
            
            logger.info("Successfully analyzed issue")
            return analysis
            
        except RateLimitError as e:
            raise LLMServiceError(
                "OpenAI API rate limit exceeded. Please try again later."
            )
        except APIConnectionError as e:
            raise LLMServiceError(
                f"Failed to connect to OpenAI API: {str(e)}"
            )
        except APIError as e:
            raise LLMServiceError(
                f"OpenAI API error: {str(e)}"
            )
        except OpenAIError as e:
            raise LLMServiceError(
                f"OpenAI error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {str(e)}")
            raise LLMServiceError(
                f"Failed to analyze issue: {str(e)}"
            )
    
    def _build_prompt(
        self,
        issue_data: GitHubIssueData,
        owner: str,
        repo: str
    ) -> str:
        """Build a comprehensive prompt with few-shot examples.
        
        This is the critical component for accurate analysis. The prompt includes:
        - Clear task definition
        - Detailed rubrics for priority and type
        - Few-shot examples
        - Edge case handling instructions
        
        Args:
            issue_data: GitHub issue data
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Formatted prompt string
        """
        # Truncate input if needed to stay within token limits
        title = issue_data.title[:500]  # Max 500 chars for title
        body = self._truncate_text(issue_data.body or "No description provided.", 2000)
        comments_summary = self._summarize_comments(issue_data.comments)
        
        prompt = f"""You are an expert GitHub issue analyst. Analyze the following issue and provide structured insights.

ISSUE INFORMATION:
Repository: {owner}/{repo}
Title: {title}
State: {issue_data.state}
Existing Labels: {', '.join(issue_data.labels) if issue_data.labels else 'None'}

DESCRIPTION:
{body}

COMMENTS ({len(issue_data.comments)} total):
{comments_summary}

YOUR TASK:
Analyze this issue and generate a JSON object with the following fields:

1. **summary**: A concise 2-3 sentence summary of what the issue is about, its current status, and key points from discussion.

2. **type**: Classify the issue into ONE of these categories:
   - "bug": Software defects, errors, crashes, incorrect behavior
   - "feature_request": New functionality or enhancement requests
   - "question": User questions, how-to requests, clarifications
   - "documentation": Documentation improvements, typos, missing docs
   - "enhancement": Improvements to existing features (not new features)
   - "other": Anything that doesn't fit above categories

3. **priority_score**: A string in format "N - Explanation" where N is 1-5:
   - 1: Minor/cosmetic issues, very low impact (typos, small UI tweaks)
   - 2: Low priority, workarounds exist, affects few users
   - 3: Moderate priority, noticeable impact, affects some users
   - 4: High priority, significant impact, affects many users, no easy workaround
   - 5: Critical, blocks major functionality, security issues, data loss risk
   
   Provide clear justification based on:
   - Number of users affected
   - Severity of impact
   - Availability of workarounds
   - Business/security implications

4. **suggested_labels**: Array of 2-4 specific, relevant labels that would help categorize this issue. Examples: ["bug", "UI", "high-priority"], ["feature", "API", "needs-discussion"], ["documentation", "beginner-friendly"]

5. **potential_impact**: Describe the potential impact if this issue is not addressed. Consider user experience, system stability, security, and business implications.

6. **confidence_score**: An integer from 0-100 indicating your confidence in this analysis. Consider:
   - 90-100: Very confident, clear issue with sufficient context
   - 70-89: Confident, some ambiguity but main points are clear
   - 50-69: Moderate confidence, limited information or unclear intent
   - Below 50: Low confidence, insufficient information or highly ambiguous

PRIORITY SCORING EXAMPLES:
- "1 - Minor cosmetic issue with button alignment, no functional impact"
- "3 - Moderate priority feature request that would improve UX for some users"
- "5 - Critical security vulnerability allowing unauthorized data access"
- "4 - High priority bug causing crashes for users on mobile devices"

ISSUE TYPE EXAMPLES:
- Bug: "Application crashes when clicking submit button", "Memory leak in worker process"
- Feature Request: "Add dark mode support", "Export data to CSV functionality"
- Question: "How do I configure authentication?", "What's the difference between X and Y?"
- Documentation: "API reference missing parameters", "Installation guide outdated"

FEW-SHOT EXAMPLES:

Example 1 - Bug Issue:
Input: Title="App crashes on iOS 14 when opening camera", Body="The app immediately crashes when I try to access the camera feature on iOS 14.3. Works fine on iOS 15+", Comments=["I can reproduce this on iOS 14.2 as well", "Same issue here, iPhone 11"]
Output: {{
  "summary": "The application crashes when users attempt to access the camera feature specifically on iOS 14.x devices. Multiple users have confirmed the issue across different iOS 14 versions, though it works correctly on iOS 15 and later.",
  "type": "bug",
  "priority_score": "4 - High priority because it completely blocks camera functionality for iOS 14 users, affects multiple users, and has no workaround",
  "suggested_labels": ["bug", "iOS", "camera", "high-priority"],
  "potential_impact": "Users on iOS 14 devices cannot use camera features, leading to poor user experience and potential app abandonment. iOS 14 still has significant market share.",
  "confidence_score": 95
}}

Example 2 - Feature Request:
Input: Title="Add export to PDF functionality", Body="It would be great if users could export their reports as PDF files for sharing and archiving", Comments=["This would be very useful for our team", "Agree, we need this for client presentations"]
Output: {{
  "summary": "Users are requesting the ability to export reports in PDF format for easier sharing and archiving purposes. Multiple users have expressed interest, particularly for business and presentation use cases.",
  "type": "feature_request",
  "priority_score": "3 - Moderate priority as it would enhance functionality for business users, though current export options exist",
  "suggested_labels": ["feature-request", "export", "enhancement"],
  "potential_impact": "Without PDF export, users must use workarounds like print-to-PDF or screenshots, which is less professional. Adding this feature would improve professional use cases and user satisfaction.",
  "confidence_score": 92
}}

Example 3 - Question:
Input: Title="How to configure custom authentication?", Body="I'm trying to set up custom authentication but can't find clear documentation. Can someone point me in the right direction?", Comments=[]
Output: {{
  "summary": "User is seeking guidance on implementing custom authentication configuration, indicating a lack of clear documentation or examples for this feature.",
  "type": "question",
  "priority_score": "2 - Low priority as an individual question, but may indicate documentation gap if recurring",
  "suggested_labels": ["question", "authentication", "documentation"],
  "potential_impact": "If this is a common question, it suggests documentation needs improvement. Individual impact is low, but could indicate broader usability issues for developers.",
  "confidence_score": 88
}}

EDGE CASES TO HANDLE:
- If no comments: Focus analysis on title and body only
- If body is empty/minimal: Make best effort with title and any available context
- If non-English: Attempt analysis, note language if confidence is low
- If very technical: Still provide accessible summary and clear priority reasoning

OUTPUT FORMAT:
Return ONLY a valid JSON object with the six fields described above (summary, type, priority_score, suggested_labels, potential_impact, confidence_score). Do not include markdown formatting or any text outside the JSON object.

Now analyze the issue above and provide your structured analysis:"""
        
        return prompt
    
    def _truncate_text(self, text: str, max_chars: int) -> str:
        """Intelligently truncate text to fit within character limit.
        
        Keeps the beginning and end of text, truncating middle if needed.
        
        Args:
            text: Text to truncate
            max_chars: Maximum characters
            
        Returns:
            Truncated text
        """
        if len(text) <= max_chars:
            return text
        
        # Keep first 60% and last 20% of allowed chars
        keep_start = int(max_chars * 0.6)
        keep_end = int(max_chars * 0.2)
        
        truncated = (
            text[:keep_start] +
            f"\n\n[... truncated {len(text) - max_chars} characters ...]\n\n" +
            text[-keep_end:]
        )
        
        logger.debug(f"Truncated text from {len(text)} to ~{max_chars} chars")
        return truncated
    
    def _summarize_comments(self, comments: List[str]) -> str:
        """Summarize comments for inclusion in prompt.
        
        For many comments, includes first few and last few with count.
        
        Args:
            comments: List of comment texts
            
        Returns:
            Formatted comment summary
        """
        if not comments:
            return "No comments yet."
        
        # If few comments, include all
        if len(comments) <= 5:
            return "\n\n".join([
                f"Comment {i+1}: {self._truncate_text(c, 300)}"
                for i, c in enumerate(comments)
            ])
        
        # For many comments, show first 3 and last 2
        summary_parts = []
        
        # First 3 comments
        for i in range(3):
            summary_parts.append(
                f"Comment {i+1}: {self._truncate_text(comments[i], 300)}"
            )
        
        summary_parts.append(f"\n[... {len(comments) - 5} more comments ...]\n")
        
        # Last 2 comments
        for i in range(len(comments) - 2, len(comments)):
            summary_parts.append(
                f"Comment {i+1}: {self._truncate_text(comments[i], 300)}"
            )
        
        return "\n\n".join(summary_parts)
    
    def _parse_response(self, response: ChatCompletion) -> IssueAnalysis:
        """Parse and validate LLM response.
        
        Args:
            response: OpenAI API response
            
        Returns:
            Validated IssueAnalysis
            
        Raises:
            LLMServiceError: If response cannot be parsed or validated
        """
        try:
            # Extract content
            content = response.choices[0].message.content
            
            if not content:
                raise LLMServiceError("Empty response from LLM")
            
            # Parse JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {content[:200]}")
                raise LLMServiceError(
                    f"LLM returned invalid JSON: {str(e)}"
                )
            
            # Validate with Pydantic model
            analysis = IssueAnalysis(**data)
            
            return analysis
            
        except KeyError as e:
            raise LLMServiceError(
                f"Response missing required field: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error parsing response: {str(e)}")
            raise LLMServiceError(
                f"Failed to parse LLM response: {str(e)}"
            )
