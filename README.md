# 👻 Study Companion AI

**Development Period:** March 2026

Study Companion AI is an AI-powered learning assistant designed to transform lecture materials into structured study sessions. Instead of manually creating notes and revision resources, the system uses multiple AI agents to analyze lecture content, generate concise summaries, build personalized study plans, create quizzes, and produce flashcards to support active learning.

The project demonstrates the integration of Large Language Models (LLMs), agent orchestration, prompt engineering, and backend services into a single educational workflow.

---

## 🏗️ System Architecture

The following architecture was designed during the initial development of the project and illustrates the interaction between the frontend, backend orchestrator, AI agents, tools, and persistence layer.

<p align="center">
  <img src="assets/architecture.png" width="100%">
</p>

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 📄 Lecture Processing | Extracts and processes lecture content from PDF or text files. |
| 🧠 AI Summarization | Generates structured summaries highlighting key concepts and important information. |
| 📅 Study Planner | Creates personalized study tasks based on the uploaded lecture. |
| ❓ Quiz Generation | Produces multiple-choice and True/False questions for self-assessment. |
| 🃏 Flashcards | Generates memory cards to support active recall and long-term retention. |
| ⏱️ Pomodoro Timer | Encourages focused study sessions using the Pomodoro technique. |
| 💾 Session Persistence | Stores study sessions and progress using SQLite. |
| 🤖 Multi-Agent Workflow | Coordinates specialized AI agents through a Flask-based orchestration layer. |

---

## 📸 Interface Preview

### Dashboard

<p align="center">
  <img src="assets/home.png" width="90%">
</p>

### AI-Generated Quiz

<p align="center">
  <img src="assets/quiz.png" width="90%">
</p>

---

## 🧠 AI Agent Architecture

| Agent | Responsibility |
|--------|----------------|
| **Summary Agent** | Produces structured summaries from lecture content. |
| **Planner Agent** | Generates personalized study tasks and learning objectives. |
| **Quiz Agent** | Creates multiple-choice and True/False assessment questions. |
| **Cards Agent** | Generates flashcards for active recall practice. |
| **Critic Agent** | Reviews and validates generated responses before returning them to the user. |

---

## ⚙️ Tech Stack

| Layer | Technologies |
|------|--------------|
| Programming Language | Python |
| Backend | Flask |
| LLM | Google Gemini |
| AI Framework | LangChain |
| Validation | Pydantic |
| Database | SQLite |
| Frontend | React |
| Environment | python-dotenv |

---

## 🚀 Getting Started

Clone the repository:

```bash
git clone https://github.com/razanalsulaymi/StudyCompanion-Agentic-AI.git

cd StudyCompanion-Agentic-AI
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GOOGLE_API_KEY=YOUR_API_KEY
GEMINI_MODEL=gemini-2.5-flash
FAST_GEMINI_MODEL=gemini-2.5-flash
LLM_TEMPERATURE=0.2
```

Run the application:

```bash
python app.py
```

---

## 📂 Repository

This public repository focuses on the AI architecture, orchestration workflow, and backend implementation.

The original frontend source code has intentionally been excluded to keep the repository centered on the AI components and overall system design while showcasing the application's functionality through screenshots.

---

## 🔮 Future Improvements

- Support multiple LLM providers.
- Improve long-term conversational memory.
- Enhance agent collaboration and planning.
- Add cloud deployment and user authentication.
- Support OCR for scanned lecture documents.
- Expand evaluation and benchmarking for generated educational content.

---

## 👩‍💻 Author

Developed as a personal AI project exploring multi-agent orchestration, LLM-powered educational tools, and intelligent learning workflows.
