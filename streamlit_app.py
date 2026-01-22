"""
AI-Powered GitHub Issue Assistant - Streamlit Cloud Ready
Author: Yaseen Mahek
Project: Seedling Labs Engineering Internship

This is a single-file Streamlit application that can be deployed to Streamlit Cloud.
It analyzes GitHub issues using OpenAI GPT models and provides structured insights.
"""

import streamlit as st
import requests
import json
import re
import os
import warnings
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import base64
import csv
import io

# Suppress Streamlit secrets file warnings
warnings.filterwarnings("ignore", message=".*secrets.*")

# Load .env for local development (silent if not available)
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)  # Don't override existing env vars
except ImportError:
    pass  # dotenv not installed, using environment variables directly


# ============================================================================
# SECURE SECRETS MANAGEMENT - Hybrid Loading (Best Practice)
# ============================================================================

def _secrets_file_exists() -> bool:
    """Check if Streamlit secrets.toml file exists."""
    import pathlib
    
    # Check both possible locations for secrets.toml
    possible_paths = [
        pathlib.Path.home() / ".streamlit" / "secrets.toml",
        pathlib.Path.cwd() / ".streamlit" / "secrets.toml",
    ]
    
    return any(p.exists() for p in possible_paths)


def get_secret(key: str, default: str = "") -> str:
    """
    Securely retrieve a secret value using hybrid loading strategy.
    
    Priority order:
    1. Streamlit Secrets (st.secrets) - for Streamlit Cloud deployment
    2. Environment Variables (os.environ) - for local development via .env
    3. Default value - fallback
    
    This approach:
    - Works seamlessly in both local and cloud environments
    - Never logs or prints secret values
    - Fails gracefully without exposing internals
    - Does NOT access st.secrets if secrets.toml doesn't exist (prevents UI errors)
    
    Args:
        key: The name of the secret/environment variable
        default: Fallback value if secret is not found
        
    Returns:
        The secret value or default
    """
    # Strategy 1: Try Streamlit Secrets ONLY if secrets file exists
    # This prevents the "No secrets files found" UI error
    if _secrets_file_exists():
        try:
            if key in st.secrets:
                return str(st.secrets[key])
        except Exception:
            pass  # Silently continue to next strategy
    
    # Strategy 2: Try Environment Variables (for local .env)
    env_value = os.environ.get(key)
    if env_value:
        return env_value
    
    # Strategy 3: Return default
    return default


def validate_required_secrets() -> Dict[str, bool]:
    """
    Validate that required secrets are configured.
    
    Returns:
        Dictionary with secret names as keys and availability as boolean values
    """
    return {
        "OPENAI_API_KEY": bool(get_secret("OPENAI_API_KEY")),
        "GITHUB_TOKEN": bool(get_secret("GITHUB_TOKEN"))
    }


# Page configuration
PAGE_TITLE = "🔍 GitHub Issue Assistant"
PAGE_ICON = "🔍"
GITHUB_API_BASE = "https://api.github.com"

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

if 'history' not in st.session_state:
    st.session_state.history = []
if 'stats' not in st.session_state:
    st.session_state.stats = {'total_analyses': 0, 'total_time': 0}


# ============================================================================
# CUSTOM CSS FOR PROFESSIONAL STYLING
# ============================================================================

st.markdown("""
    <style>
    .main-header {
        font-size: 2.8rem;
        font-weight: bold;
        background: linear-gradient(90deg, #1f77b4 0%, #2ca02c 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .success-box {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        padding: 1rem;
        border-radius: 8px;
        color: white;
        margin: 1rem 0;
    }
    .error-box {
        background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
        padding: 1rem;
        border-radius: 8px;
        color: white;
        margin: 1rem 0;
    }
    .confidence-bar {
        background: #e0e0e0;
        border-radius: 10px;
        height: 24px;
        overflow: hidden;
    }
    .confidence-fill {
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        transition: width 0.3s ease;
    }
    .label-tag {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 15px;
        margin: 0.2rem;
        display: inline-block;
        font-size: 0.9rem;
        font-weight: 500;
    }
    .info-card {
        background: #f8f9fa;
        border-left: 4px solid #1f77b4;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)


# ============================================================================
# GITHUB API CLIENT
# ============================================================================

class GitHubClient:
    """Client for interacting with GitHub REST API."""
    
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"token {token}" if token else "",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Issue-Assistant/1.0"
        }
    
    def parse_repo_url(self, url: str) -> Tuple[str, str]:
        """Parse GitHub repository URL to extract owner and repo name."""
        url = url.strip()
        url = re.sub(r'\.git$', '', url)
        
        patterns = [
            r'^https?://github\.com/([\w\-\.]+)/([\w\-\.]+)/?$',
            r'^github\.com/([\w\-\.]+)/([\w\-\.]+)/?$',
            r'^([\w\-\.]+)/([\w\-\.]+)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                return match.groups()
        
        raise ValueError(
            f"Invalid GitHub URL format: {url}. "
            "Expected format: https://github.com/owner/repo or owner/repo"
        )
    
    def fetch_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Fetch issue data from GitHub API."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 404:
                raise ValueError(
                    f"Repository '{owner}/{repo}' or issue #{issue_number} not found. "
                    "Please verify the URL and issue number."
                )
            elif response.status_code == 403:
                remaining = response.headers.get('X-RateLimit-Remaining', '0')
                if remaining == '0':
                    raise ValueError(
                        "GitHub API rate limit exceeded. Please wait a few minutes or add a GitHub token."
                    )
                raise ValueError(
                    f"Access forbidden to '{owner}/{repo}'. This may be a private repository."
                )
            elif response.status_code == 401:
                raise ValueError("GitHub authentication failed. Please check your GITHUB_TOKEN.")
            
            response.raise_for_status()
            data = response.json()
            
            # Fetch comments
            comments = self._fetch_comments(owner, repo, issue_number)
            
            return {
                "title": data.get('title', ''),
                "body": data.get('body') or 'No description provided.',
                "comments": comments,
                "labels": [label['name'] for label in data.get('labels', [])],
                "state": data.get('state', 'open'),
                "created_at": data.get('created_at', ''),
                "updated_at": data.get('updated_at', ''),
                "html_url": data.get('html_url', '')
            }
            
        except requests.Timeout:
            raise ValueError("Request to GitHub API timed out. Please try again.")
        except requests.RequestException as e:
            raise ValueError(f"Network error while fetching GitHub data: {str(e)}")
    
    def _fetch_comments(self, owner: str, repo: str, issue_number: int) -> List[str]:
        """Fetch comments for an issue."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        
        try:
            response = requests.get(
                url, 
                headers=self.headers, 
                params={'per_page': 50},
                timeout=10
            )
            response.raise_for_status()
            
            comments = []
            for comment in response.json():
                body = comment.get('body', '').strip()
                if body:
                    comments.append(body[:500])  # Limit comment length
            return comments[:10]  # Max 10 comments
            
        except:
            return []  # Don't fail if comments can't be fetched


# ============================================================================
# LLM ANALYZER (OpenAI GPT)
# ============================================================================

class LLMAnalyzer:
    """Analyzer for GitHub issues using OpenAI GPT models."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def analyze_issue(self, issue_data: Dict[str, Any], owner: str, repo: str) -> Dict[str, Any]:
        """Analyze a GitHub issue using OpenAI GPT."""
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            
            prompt = self._build_prompt(issue_data, owner, repo)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert GitHub issue analyst. Analyze issues and provide structured JSON output."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except ImportError:
            raise ValueError("OpenAI library not installed. Run: pip install openai")
        except Exception as e:
            raise ValueError(f"AI analysis failed: {str(e)}")
    
    def _build_prompt(self, issue_data: Dict[str, Any], owner: str, repo: str) -> str:
        """Build a comprehensive prompt for issue analysis."""
        title = issue_data.get('title', '')[:500]
        body = issue_data.get('body', '')[:2000]
        comments = issue_data.get('comments', [])
        comments_text = "\n".join([f"- {c[:300]}" for c in comments[:5]]) or "No comments"
        
        return f"""You are an expert AI system that produces machine-readable output.
Your response will be parsed directly using a JSON parser.

GITHUB ISSUE TO ANALYZE:
Repository: {owner}/{repo}
Title: {title}
State: {issue_data.get('state', 'open')}
Existing Labels: {', '.join(issue_data.get('labels', [])) or 'None'}

Description:
{body}

Comments:
{comments_text}

ABSOLUTE RULES (NO EXCEPTIONS):
1. Output ONLY a single JSON object.
2. Do NOT include any text outside the JSON.
3. Do NOT include markdown, headings, or explanations.
4. Use double quotes for all keys and string values.
5. Arrays MUST contain ONLY string values (no objects, no indexed keys).
6. Do NOT include trailing commas.

REQUIRED JSON SCHEMA (MATCH THIS EXACTLY):
{{
  "summary": "A one-sentence summary of the user's problem or request.",
  "type": "Classify as: bug, feature_request, documentation, question, or other",
  "priority_score": "A score from 1 (low) to 5 (critical), with a brief justification for the score.",
  "suggested_labels": ["An array of 2-3 relevant GitHub labels"],
  "potential_impact": "A brief sentence on the potential impact on users if the issue is a bug."
}}

EXAMPLE OUTPUT:
{{
  "summary": "Users cannot login due to authentication token expiration issue.",
  "type": "bug",
  "priority_score": "4 - High priority because it blocks user access to the application.",
  "suggested_labels": ["bug", "authentication", "high-priority"],
  "potential_impact": "Users are unable to access their accounts, leading to service disruption."
}}

OUTPUT: Return ONLY the JSON object matching this exact schema."""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_confidence_color(score: int) -> str:
    """Get color for confidence score."""
    if score >= 90: return "#28a745"
    elif score >= 70: return "#17a2b8"
    elif score >= 50: return "#ffc107"
    else: return "#dc3545"


def get_priority_emoji(priority) -> str:
    """Get emoji for priority level (handles both number and string formats)."""
    try:
        if isinstance(priority, (int, float)):
            priority_num = int(priority)
        else:
            priority_num = int(str(priority).split('-')[0].strip())
        return {1: "⚪", 2: "🟢", 3: "🟡", 4: "🟠", 5: "🔴"}.get(priority_num, "⚪")
    except:
        return "⚪"


def get_type_emoji(issue_type: str) -> str:
    """Get emoji for issue type."""
    return {
        "bug": "🐛", "feature": "✨", "feature_request": "✨", "question": "❓",
        "documentation": "📚", "enhancement": "🚀", "other": "📌"
    }.get(issue_type, "📌")


def create_download_link(data: dict, filename: str) -> str:
    """Create a download link for JSON data."""
    content = json.dumps(data, indent=2)
    b64 = base64.b64encode(content.encode()).decode()
    return f'<a href="data:application/json;base64,{b64}" download="{filename}.json" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.5rem 1rem; border-radius: 5px; text-decoration: none;">📥 Download JSON</a>'


# ============================================================================
# DISPLAY FUNCTIONS
# ============================================================================

def display_analysis(result: Dict[str, Any], issue_url: str) -> None:
    """Display the analysis results in a professional format."""
    
    # Success banner
    st.success("✅ Analysis completed successfully!")
    
    if issue_url:
        st.markdown(f"🔗 **[View Issue on GitHub]({issue_url})**")
    
    st.divider()
    
    # Main metrics row
    col1, col2 = st.columns(2)
    
    with col1:
        issue_type = result.get("type", "other")
        st.markdown(f"### {get_type_emoji(issue_type)} Issue Type")
        st.markdown(f"**{issue_type.replace('_', ' ').title()}**")
    
    with col2:
        priority = result.get("priority_score", "Unknown")
        st.markdown(f"### {get_priority_emoji(priority)} Priority Score")
        st.markdown(f"**{priority}**")
    
    st.divider()
    
    # Summary
    with st.expander("📝 Summary", expanded=True):
        st.write(result.get("summary", "No summary available"))
    
    # Potential Impact
    with st.expander("⚠️ Potential Impact", expanded=True):
        st.write(result.get("potential_impact", "No impact analysis available"))
    
    # Suggested Labels
    st.markdown("### 🏷️ Suggested Labels")
    labels = result.get("suggested_labels", [])
    if labels:
        labels_html = " ".join([f'<span class="label-tag">{label}</span>' for label in labels])
        st.markdown(labels_html, unsafe_allow_html=True)
    else:
        st.write("No labels suggested")
    
    st.divider()
    
    # Raw JSON Output
    st.markdown("### 📋 Raw JSON Output")
    json_output = json.dumps(result, indent=2, ensure_ascii=False)
    st.code(json_output, language="json")

    # CSV Download Button
    st.divider()
    
    # Create CSV in memory
    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer)
    
    # Write headers and data (Single row format)
    headers = ["summary", "type", "priority_score", "potential_impact", "suggested_labels"]
    csv_writer.writerow(headers)
    
    csv_writer.writerow([
        result.get("summary", ""),
        result.get("type", ""),
        result.get("priority_score", ""),
        result.get("potential_impact", ""),
        ", ".join(result.get("suggested_labels", []))
    ])
    
    st.download_button(
        label="📥 Download Analysis as CSV",
        data=csv_buffer.getvalue(),
        file_name=f"issue_analysis_{int(datetime.now().timestamp())}.csv",
        mime="text/csv",
        use_container_width=True
    )


def check_api_keys() -> Tuple[bool, bool]:
    """Check if required API keys are configured."""
    secrets_status = validate_required_secrets()
    return secrets_status["GITHUB_TOKEN"], secrets_status["OPENAI_API_KEY"]


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application function."""
    
    # Header
    st.markdown(f'<div class="main-header">{PAGE_ICON} GitHub Issue Assistant</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">AI-powered analysis for GitHub issues • By Yaseen Mahek</div>',
        unsafe_allow_html=True
    )
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ℹ️ About")
        st.markdown("""
        This tool analyzes GitHub issues using AI to provide:
        - 📊 Issue classification (Bug/Feature/Question)
        - 🎯 Priority assessment (1-5 scale)
        - 🔍 Root cause analysis
        - 💡 Suggested fixes
        - 🏷️ Label recommendations
        - 📈 Impact analysis
        """)
        
        st.divider()
        
        # API Key Status
        st.markdown("### 🔑 API Status")
        has_github, has_openai = check_api_keys()
        
        if has_github:
            st.success("✅ GitHub Token configured")
        else:
            st.warning("⚠️ GitHub Token not set (using public API)")
            st.caption("Add GITHUB_TOKEN for higher rate limits")
        
        if has_openai:
            st.success("✅ OpenAI API Key configured")
        else:
            st.error("❌ OpenAI API Key required")
            st.caption("Set OPENAI_API_KEY in secrets")
        
        st.divider()
        
        # Session Stats
        st.markdown("### 📊 Session Stats")
        stats = st.session_state.stats
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Analyses", stats['total_analyses'])
        with col2:
            avg_time = stats['total_time'] / max(stats['total_analyses'], 1)
            st.metric("Avg Time", f"{avg_time:.1f}s")
        
        st.divider()
        
        # Recent History
        if st.session_state.history:
            st.markdown("### 📜 Recent")
            for item in reversed(st.session_state.history[-3:]):
                st.caption(f"• {item['repo']} #{item['issue']}")
        
        st.divider()
        
        st.markdown("### 🎓 Project Info")
        st.markdown("""
        **Author:** Yaseen Mahek  
        **Project:** Engineering Internship  
        **Tech:** Python, Streamlit, OpenAI  
        """)
    
    # Main content
    st.markdown("### 🚀 Analyze an Issue")
    
    # Check if OpenAI key is available
    _, has_openai = check_api_keys()
    if not has_openai:
        st.error("""
        ⚠️ **OpenAI API Key Required**
        
        Please configure your OpenAI API key:
        - **Local:** Create a `.env` file with `OPENAI_API_KEY=your_key_here`
        - **Streamlit Cloud:** Add it to your app's Secrets
        """)
        st.stop()
    
    # Input form
    with st.form("analysis_form"):
        repo_url = st.text_input(
            "GitHub Repository URL",
            placeholder="facebook/react or https://github.com/facebook/react",
            help="Enter the repository in any format: owner/repo or full URL"
        )
        
        issue_number = st.number_input(
            "Issue Number",
            min_value=1,
            step=1,
            value=1,
            help="Enter the issue number to analyze"
        )
        
        submit_button = st.form_submit_button("🔍 Analyze Issue", use_container_width=True)
    
    # Process form submission
    if submit_button:
        if not repo_url or not repo_url.strip():
            st.error("❌ Please enter a GitHub repository URL")
            return
        
        # Get API keys securely
        github_token = get_secret("GITHUB_TOKEN")
        openai_key = get_secret("OPENAI_API_KEY")
        
        # Initialize clients
        github_client = GitHubClient(github_token)
        llm_analyzer = LLMAnalyzer(openai_key)
        
        try:
            # Parse URL
            with st.spinner("🔎 Parsing repository URL..."):
                owner, repo = github_client.parse_repo_url(repo_url.strip())
            
            # Fetch issue
            with st.spinner(f"📥 Fetching issue #{issue_number} from {owner}/{repo}..."):
                issue_data = github_client.fetch_issue(owner, repo, issue_number)
            
            issue_url = issue_data.get('html_url', f"https://github.com/{owner}/{repo}/issues/{issue_number}")
            
            # Analyze with AI
            with st.spinner("🤖 Analyzing issue with AI... (this may take 10-30 seconds)"):
                import time
                start_time = time.time()
                analysis = llm_analyzer.analyze_issue(issue_data, owner, repo)
                analysis_time = time.time() - start_time
            
            # Update stats
            st.session_state.stats['total_analyses'] += 1
            st.session_state.stats['total_time'] += analysis_time
            
            # Add to history
            st.session_state.history.append({
                'repo': f"{owner}/{repo}",
                'issue': issue_number,
                'timestamp': datetime.now().strftime("%H:%M:%S")
            })
            
            # Display results
            display_analysis(analysis, issue_url)
            
        except ValueError as e:
            st.error(f"❌ {str(e)}")
        except Exception as e:
            st.error(f"❌ An unexpected error occurred: {str(e)}")
    
    # Examples section
    st.divider()
    st.markdown("### 📚 Example Issues to Try")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **React - Bug Report**
        - URL: `facebook/react`
        - Issue: `1`
        """)
    
    with col2:
        st.markdown("""
        **VS Code - Feature**
        - URL: `microsoft/vscode`  
        - Issue: `167416`
        """)
    
    with col3:
        st.markdown("""
        **Python - Discussion**
        - URL: `python/cpython`
        - Issue: `100`
        """)


if __name__ == "__main__":
    main()
