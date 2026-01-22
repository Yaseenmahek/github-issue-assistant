# GitHub Issue Assistant

A web app that analyzes GitHub issues using AI. Built as part of my Seedling Labs Engineering Internship project.

## What it does

Enter a GitHub repository URL and issue number, and the app will:
- Fetch the issue details from GitHub
- Analyze it using OpenAI's GPT model
- Return a structured JSON response with summary, type, priority, labels, and impact

## Output Format

```json
{
  "summary": "Brief description of the issue",
  "type": "bug | feature_request | documentation | question | other",
  "priority_score": "1-5 with justification",
  "suggested_labels": ["label1", "label2"],
  "potential_impact": "Impact if not addressed"
}
```

## Tech Stack

- Python 3.10+
- Streamlit (frontend)
- OpenAI API (GPT-3.5)
- GitHub REST API

## Setup

1. Clone the repo
```bash
git clone https://github.com/yourusername/github-issue-assistant.git
cd github-issue-assistant
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Create `.env` file with your API keys
```
OPENAI_API_KEY=your_openai_key
GITHUB_TOKEN=your_github_token
```

4. Run the app
```bash
streamlit run streamlit_app.py
```

5. Open http://localhost:8501 in your browser

## Deployment

The app can be deployed on Streamlit Cloud:
1. Push code to GitHub (make sure `.env` is in `.gitignore`)
2. Go to share.streamlit.io
3. Connect your repo and set `streamlit_app.py` as the main file
4. Add your API keys in the Secrets section

## Project Structure

```
├── streamlit_app.py    # Main application
├── requirements.txt    # Dependencies
├── .env.example        # Environment variables template
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Author

Yaseen Mahek  
Seedling Labs Engineering assignment - 2026
