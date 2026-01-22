# 🐞 GitHub Issue Assistant

> **AI-Powered GitHub Issue Analysis Tool**  
> *Seedling Labs Engineering Assignment - 2026*

A professional streamit application that automatically fetches and analyzes GitHub issues using OpenAI's GPT models. It provides structured JSON outputs strictly adhering to Seedling Labs' engineering standards.

## 🔑 Key Features

| Feature | Description |
| :--- | :--- |
| **🤖 AI Analysis** | Automates issue classification using GPT-3.5 Turbo with strict JSON schema enforcement. |
| **🛡️ Hybrid Secrets** | Intelligent secret loading that works seamlessly on both Local (`.env`) and Cloud (`st.secrets`) environments. |
| **📦 Unified Architecture** | Single-file architecture (`streamlit_app.py`) for zero-latency deployment on Streamlit Cloud. |
| **📊 Structured Output** | Delivers precise JSON with `summary`, `type`, `priority_score`, and `potential_impact`. |
| **⚡ Real-time Fetching** | Integrates directly with GitHub REST API to pull live issue data. |

## 📂 Project Structure

```bash
github-issue-assistant/
├── streamlit_app.py       # 🚀 Main Application (Frontend + Backend)
├── requirements.txt       # 📦 Dependencies
├── .env.example          # 🔐 Environment Variables Template
├── .gitignore            # 🙈 Git Ignore Rules
├── README.md             # 📄 Documentation
├── frontend/             # 🎨 Archived React Frontend (Reference)
└── backend/              # 🐍 Archived FastAPI Backend (Reference)
```

## ⚙️ Environment Variables

To run the application, you need the following keys.  
**Auto-Detection:** The app automatically scans `.env` locally or `Secrets` in the cloud.

```ini
# Required
OPENAI_API_KEY=sk-...    # OpenAI API Key for GPT Analysis

# Optional (Recommended for higher limits)
GITHUB_TOKEN=ghp_...     # GitHub Personal Access Token
```

## 🛠️ Local Installation

Follow these steps to run the app on your machine.

### 1. Clone the Repository
```bash
git clone https://github.com/Yaseenmahek/github-issue-assistant.git
cd github-issue-assistant
```

### 2. Setup Virtual Environment

**🪟 Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

**🐧 Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the App
```bash
streamlit run streamlit_app.py
```
Open **http://localhost:8501** in your browser.

## 🌐 Deployment

**Streamlit Community Cloud (Production)**

*   **Live URL:** [https://github-issue-assistant-YOUR-APP.streamlit.app](https://share.streamlit.io)
*   **Runtime:** Python 3.10+
*   **Secrets:** Managed via Streamlit Cloud Dashboard

### 🚀 Quick Deploy
1.  Push code to GitHub.
2.  Go to **[share.streamlit.io](https://share.streamlit.io)**.
3.  Deploy from existing repo.
4.  Add secrets in **Settings > Secrets**.

## 🔗 Links

*   **GitHub Repository:** [Yaseenmahek/github-issue-assistant](https://github.com/Yaseenmahek/github-issue-assistant)
*   **Live Demo:** [Live URL](https://yaseenmahek-github-issue-assistant-streamlit-app-jw47xx.streamlit.app/)

---
*Developed by **Yaseen Mahek***
