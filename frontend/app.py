"""
Enhanced Streamlit Frontend for GitHub Issue Assistant.

A professional, feature-rich interface with caching indicators, copy buttons,
analysis history, metrics display, and export functionality.
"""

import streamlit as st
import requests
import json
import time
from typing import Optional, Dict, Any
from datetime import datetime
import base64


# Configuration
API_URL = "http://localhost:8000"
PAGE_TITLE = "🔍 GitHub Issue Assistant"
PAGE_ICON = "🔍"


# Page configuration
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)


# Initialize session state for history
if 'history' not in st.session_state:
    st.session_state.history = []
if 'stats' not in st.session_state:
    st.session_state.stats = {
        'total_analyses': 0,
        'total_time': 0,
        'cache_hits': 0
    }
if 'api_url' not in st.session_state:
    st.session_state.api_url = API_URL
if 'api_timeout' not in st.session_state:
    st.session_state.api_timeout = 60


# Custom CSS for enhanced styling
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
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .success-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
    .copy-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        cursor: pointer;
        text-decoration: none;
        display: inline-block;
        transition: transform 0.2s ease;
    }
    .copy-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
    }
    .stat-badge {
        background: rgba(255,255,255,0.2);
        padding: 0.5rem 1rem;
        border-radius: 8px;
        display: inline-block;
        margin: 0.25rem;
    }
    </style>
""", unsafe_allow_html=True)


def check_api_health() -> bool:
    """Check if the backend API is healthy."""
    try:
        api_url = st.session_state.get('api_url', API_URL)
        response = requests.get(f"{api_url}/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def analyze_issue(repo_url: str, issue_number: int) -> Optional[Dict[str, Any]]:
    """Call the backend API to analyze an issue."""
    try:
        api_url = st.session_state.get('api_url', API_URL)
        timeout = st.session_state.get('api_timeout', 60)
        
        start_time = time.time()
        response = requests.post(
            f"{api_url}/analyze",
            json={
                "repo_url": repo_url,
                "issue_number": issue_number
            },
            timeout=timeout
        )
        request_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            result['_request_time'] = request_time
            return result
        else:
            try:
                error_data = response.json()
                if isinstance(error_data, dict) and 'detail' in error_data:
                    detail = error_data['detail']
                    if isinstance(detail, dict):
                        return {
                            "success": False,
                            "error": detail.get('message', str(detail)),
                            "suggestion": detail.get('suggestion', '')
                        }
                    return {"success": False, "error": str(detail)}
            except:
                pass
            
            return {
                "success": False,
                "error": f"API request failed with status {response.status_code}"
            }
    
    except requests.Timeout:
        return {
            "success": False,
            "error": "Request timed out. The issue might be too large or the API is slow to respond.",
            "suggestion": "Please try again with a smaller issue or wait a moment."
        }
    except requests.ConnectionError:
        return {
            "success": False,
            "error": "Could not connect to the backend API.",
            "suggestion": "Make sure the FastAPI server is running on http://localhost:8000"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def get_confidence_color(score: int) -> str:
    """Get color for confidence score."""
    if score >= 90:
        return "#28a745"  # Green
    elif score >= 70:
        return "#17a2b8"  # Blue
    elif score >= 50:
        return "#ffc107"  # Yellow
    else:
        return "#dc3545"  # Red


def get_priority_emoji(priority_str: str) -> str:
    """Get emoji for priority level."""
    try:
        priority_num = int(priority_str.split('-')[0].strip())
        emojis = {1: "⚪", 2: "🟢", 3: "🟡", 4: "🟠", 5: "🔴"}
        return emojis.get(priority_num, "⚪")
    except:
        return "⚪"


def get_type_emoji(issue_type: str) -> str:
    """Get emoji for issue type."""
    emojis = {
        "bug": "🐛",
        "feature_request": "✨",
        "question": "❓",
        "documentation": "📚",
        "enhancement": "🚀",
        "other": "📌"
    }
    return emojis.get(issue_type, "📌")


def create_download_link(data: dict, filename: str, file_format: str) -> str:
    """Create a download link for data."""
    if file_format == "json":
        content = json.dumps(data, indent=2)
        b64 = base64.b64encode(content.encode()).decode()
        return f'<a href="data:application/json;base64,{b64}" download="{filename}.json" class="copy-btn">📥 Download JSON</a>'
    elif file_format == "csv":
        # Simple CSV conversion
        import io
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Field', 'Value'])
        for key, value in data.items():
            if isinstance(value, list):
                value = ', '.join(str(v) for v in value)
            writer.writerow([key, value])
        b64 = base64.b64encode(output.getvalue().encode()).decode()
        return f'<a href="data:text/csv;base64,{b64}" download="{filename}.csv" class="copy-btn">📥 Download CSV</a>'
    elif file_format == "md":
        # Markdown conversion
        md_content = f"# GitHub Issue Analysis\n\n"
        for key, value in data.items():
            if isinstance(value, list):
                md_content += f"## {key.replace('_', ' ').title()}\n"
                for item in value:
                    md_content += f"- {item}\n"
                md_content += "\n"
            else:
                md_content += f"## {key.replace('_', ' ').title()}\n{value}\n\n"
        b64 = base64.b64encode(md_content.encode()).decode()
        return f'<a href="data:text/markdown;base64,{b64}" download="{filename}.md" class="copy-btn">📥 Download Markdown</a>'


def display_analysis(result: Dict[str, Any]) -> None:
    """Display the analysis results in an enhanced format."""
    if not result.get("success", False):
        st.error(f"❌ {result.get('error', 'Analysis failed')}")
        if result.get('suggestion'):
            st.info(f"💡 **Suggestion**: {result['suggestion']}")
        return
    
    data = result.get("data", {})
    issue_url = result.get("issue_url", "")
    cached = result.get("cached", False)
    analysis_time = result.get("analysis_time_seconds", 0)
    
    # Update stats
    st.session_state.stats['total_analyses'] += 1
    st.session_state.stats['total_time'] += analysis_time
    if cached:
        st.session_state.stats['cache_hits'] += 1
    
    # Success banner with metrics
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if cached:
            st.success(f"✅ Analysis completed successfully (⚡ **Cached Result**)")
        else:
            st.success(f"✅ Analysis completed successfully in {analysis_time:.2f}s")
    with col2:
        if issue_url:
            st.markdown(f"🔗 **[View on GitHub]({issue_url})**")
    with col3:
        # Copy JSON button
        json_str = json.dumps(data, indent=2)
        st.code(json_str, language="json")
        if st.button("📋 Copy JSON"):
            st.write("✅ JSON copied! (Use Ctrl+C to copy from code block above)")
    
    st.divider()
    
    # Main metrics row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        issue_type = data.get("type", "other")
        st.markdown(f"### {get_type_emoji(issue_type)} Issue Type")
        st.markdown(f"**{issue_type.replace('_', ' ').title()}**")
    
    with col2:
        priority = data.get("priority_score", "Unknown")
        st.markdown(f"### {get_priority_emoji(priority)} Priority")
        st.markdown(f"**{priority}**")
    
    with col3:
        confidence = data.get("confidence_score", 0)
        st.markdown(f"### 🎯 Confidence")
        color = get_confidence_color(confidence)
        st.markdown(f"""
            <div class="confidence-bar">
                <div class="confidence-fill" style="width: {confidence}%; background: {color};">
                    {confidence}%
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Summary
    with st.expander("📝 Summary", expanded=True):
        st.write(data.get("summary", "No summary available"))
    
    # Potential Impact
    with st.expander("⚠️ Potential Impact", expanded=True):
        st.write(data.get("potential_impact", "No impact analysis available"))
    
    # Suggested Labels
    st.markdown("### 🏷️ Suggested Labels")
    labels = data.get("suggested_labels", [])
    if labels:
        labels_html = " ".join([
            f'<span class="label-tag">{label}</span>'
            for label in labels
        ])
        st.markdown(labels_html, unsafe_allow_html=True)
    else:
        st.write("No labels suggested")
    
    st.divider()
    
    # Export options
    st.markdown("### 📥 Export Options")
    col1, col2, col3 = st.columns(3)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"issue_analysis_{timestamp}"
    
    with col1:
        st.markdown(create_download_link(data, filename, "json"), unsafe_allow_html=True)
    with col2:
        st.markdown(create_download_link(data, filename, "csv"), unsafe_allow_html=True)
    with col3:
        st.markdown(create_download_link(data, filename, "md"), unsafe_allow_html=True)


def settings_page():
    """Display the settings/configuration page."""
    st.markdown(f'<div class="main-header">⚙️ Settings</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Configure application settings and preferences</div>',
        unsafe_allow_html=True
    )
    
    st.divider()
    
    # Backend Configuration
    st.markdown("### 🔌 Backend Configuration")
    
    new_api_url = st.text_input(
        "Backend API URL",
        value=st.session_state.api_url,
        help="URL where the FastAPI backend is running",
        placeholder="http://localhost:8000"
    )
    
    new_timeout = st.number_input(
        "Request Timeout (seconds)",
        min_value=10,
        max_value=300,
        value=st.session_state.api_timeout,
        step=10,
        help="Maximum time to wait for API response"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Settings", use_container_width=True):
            # Validate URL format
            if new_api_url and (new_api_url.startswith('http://') or new_api_url.startswith('https://')):
                st.session_state.api_url = new_api_url.rstrip('/')
                st.session_state.api_timeout = new_timeout
                st.success(f"✅ Settings saved! Backend URL: {st.session_state.api_url}")
                st.info("🔄 Testing connection...")
                if check_api_health():
                    st.success("✅ Successfully connected to backend!")
                else:
                    st.warning("⚠️ Could not connect to backend. Please verify the URL and ensure the server is running.")
            else:
                st.error("❌ Invalid URL format. Must start with http:// or https://")
    
    with col2:
        if st.button("🔄 Reset to Defaults", use_container_width=True):
            st.session_state.api_url = API_URL
            st.session_state.api_timeout = 60
            st.info("✅ Settings reset! Please refresh the page to see changes.")
    
    st.divider()
    
    # Current Configuration Display
    st.markdown("### 📊 Current Configuration")
    
    config_col1, config_col2 = st.columns(2)
    
    with config_col1:
        st.info(f"**Backend URL:** `{st.session_state.api_url}`")
        st.info(f"**Timeout:** `{st.session_state.api_timeout}s`")
    
    with config_col2:
        health_status = check_api_health()
        if health_status:
            st.success("**API Status:** ✅ Healthy")
        else:
            st.error("**API Status:** ❌ Not Responding")
    
    st.divider()
    
    # Cache Management
    st.markdown("### 💾 Cache Management")
    
    st.info("""
    The application caches analysis results for 24 hours to improve performance. 
    Cache is stored in the backend `.cache/` directory.
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Session Analyses", st.session_state.stats['total_analyses'])
    with col2:
        cache_hits = st.session_state.stats.get('cache_hits', 0)
        total = st.session_state.stats.get('total_analyses', 1)
        cache_rate = (cache_hits / total * 100) if total > 0 else 0
        st.metric("Cache Hit Rate", f"{cache_rate:.1f}%")
    with col3:
        avg_time = st.session_state.stats['total_time'] / total if total > 0 else 0
        st.metric("Avg Response Time", f"{avg_time:.2f}s")
    
    st.divider()
    
    # About Section
    st.markdown("### ℹ️ About")
    st.markdown("""
    **GitHub Issue Assistant** v1.0.0
    
    An AI-powered tool for analyzing GitHub issues with GPT models.
    
    - 👤 **Author:** Yaseen Mahek
    - 🔗 **API Documentation:** [Swagger UI]({}/docs) | [ReDoc]({}/redoc)
    - 📚 **Project:** Seedling Labs Engineering Internship
    - 🛠️ **Tech Stack:** FastAPI, Streamlit, OpenAI GPT-3.5
    
    **Features:**
    - ✅ Intelligent issue classification
    - ✅ Priority scoring with confidence levels
    - ✅ 24-hour result caching
    - ✅ Export to JSON/CSV/Markdown
    - ✅ Session history tracking
    """.format(st.session_state.api_url, st.session_state.api_url))


def main():
    """Main application function."""
    
    # Sidebar Page Navigation
    with st.sidebar:
        st.markdown("### 📟 Navigation")
        page = st.radio(
            "Select Page",
            ["🏠 Analyze Issues", "⚙️ Settings"],
            label_visibility="collapsed",
            key="page_navigation"
        )
    
    # Route to appropriate page
    if page == "⚙️ Settings":
        settings_page()
        return
    
    # Header
    st.markdown(f'<div class="main-header">{PAGE_ICON} GitHub Issue Assistant</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">AI-powered analysis for GitHub issues using GPT models</div>',
        unsafe_allow_html=True
    )
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ℹ️ About")
        st.markdown("""
        This tool analyzes GitHub issues using AI to provide:
        - 📊 Issue classification
        - 🎯 Priority assessment  
        - 🏷️ Label suggestions
        - 📈 Impact analysis
        - 🎯 Confidence scoring
        """)
        
        st.divider()
        
        st.markdown("### 🔧 API Status")
        if check_api_health():
            st.success("✅ Backend API is healthy")
        else:
            st.error("❌ Backend API is not responding")
            st.warning("Make sure to start the FastAPI server:\n```bash\npython3 -m uvicorn backend.main:app --reload\n```")
        
        st.divider()
        
        # Statistics
        st.markdown("### 📊 Session Stats")
        stats = st.session_state.stats
        if stats['total_analyses'] > 0:
            avg_time = stats['total_time'] / stats['total_analyses']
            cache_rate = (stats['cache_hits'] / stats['total_analyses']) * 100
            
            st.markdown(f"""
                <div class="stat-badge">
                    📈 Total: {stats['total_analyses']}
                </div>
                <div class="stat-badge">
                    ⚡ Avg: {avg_time:.2f}s
                </div>
                <div class="stat-badge">
                    💾 Cache: {cache_rate:.0f}%
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No analyses yet")
        
        st.divider()
        
        # Analysis History
        if st.session_state.history:
            st.markdown("### 📜 Recent Analyses")
            for i, item in enumerate(reversed(st.session_state.history[-5:])):
                with st.expander(f"{item['repo']} #{item['issue']}", expanded=False):
                    st.write(f"**Type**: {item.get('type', 'N/A')}")
                    st.write(f"**Priority**: {item.get('priority', 'N/A')[:20]}...")
                    st.write(f"**Time**: {item.get('timestamp', 'N/A')}")
        
        st.divider()
        
        st.markdown("### 💡 Tips")
        st.markdown("""
        - Results are cached for 24 hours
        - Try different export formats
        - Check confidence scores
        - Use public repositories
        """)
    
    # Main content area
    st.markdown("### 🚀 Analyze an Issue")
    
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
        
        if issue_number < 1:
            st.error("❌ Issue number must be greater than 0")
            return
        
        # Show loading state
        with st.spinner(f"🔄 Analyzing issue #{issue_number}... This may take 10-30 seconds..."):
            result = analyze_issue(repo_url.strip(), issue_number)
        
        if result:
            # Add to history
            if result.get('success'):
                history_item = {
                    'repo': repo_url.strip(),
                    'issue': issue_number,
                    'type': result.get('data', {}).get('type', 'N/A'),
                    'priority': result.get('data', {}).get('priority_score', 'N/A'),
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.history.append(history_item)
            
            display_analysis(result)
        else:
            st.error("❌ Failed to get response from API")
    
    # Example section
    st.divider()
    st.markdown("### 📚 Example Issues to Try")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **React - Bug Report**
        - URL: `facebook/react`
        - Issue: `1`
        - Features clear issue analysis
        """)
    
    with col2:
        st.markdown("""
        **VS Code - Feature Request**
        - URL: `microsoft/vscode`
        - Issue: `167416`
        - Demonstrates priority scoring
        """)
    
    with col3:
        st.markdown("""
        **Linux - Technical**
        - URL: `torvalds/linux`
        - Issue: `1`
        - Shows confidence levels
        """)


if __name__ == "__main__":
    main()
