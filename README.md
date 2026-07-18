# Study Companion AI 👻 

An AI-powered study assistant that transforms lecture materials into structured learning sessions. The system automatically analyzes lecture content, generates study tasks, creates concise summaries, builds quizzes, and produces flashcards to support active learning.

> This project focuses on AI orchestration and learning automation rather than frontend development.

---

## Features

- 📄 Lecture text/PDF processing
- 🧠 AI-generated structured summaries
- ✅ Personalized study task planning
- ❓ Automatic quiz generation (MCQ / True-False)
- 🃏 Flashcard generation
- ⏱️ Pomodoro study recommendations
- 💾 Session persistence using SQLite
- 🤖 Multi-agent orchestration pipeline

---

## AI Workflow

```text
Lecture PDF/Text
        │
        ▼
Content Extraction
        │
        ▼
Summary Agent
        │
        ├──────────────┐
        ▼              ▼
Planner Agent     Quiz Agent
        │              │
        ▼              ▼
 Study Tasks     Practice Questions
        │
        ▼
 Flashcard Agent
        │
        ▼
     Student
```

---

## Screenshots

### Home

![Home](assets/home.png)

### Quiz Generation

![Quiz](assets/quiz.png)

---

## Tech Stack

| Category | Technologies |
|----------|--------------|
| Backend | Flask, Python |
| LLM | Google Gemini API |
| AI Framework | LangChain |
| Database | SQLite |
| Validation | Pydantic |
| Frontend | React |
| Styling | CSS |
| Environment | dotenv |

---

## Project Structure

```text
Study_Companion/
│
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## AI Components

| Component | Responsibility |
|------------|----------------|
| Planner Agent | Generates personalized study tasks |
| Summary Agent | Produces structured lecture summaries |
| Quiz Agent | Creates MCQ and True/False assessments |
| Cards Agent | Generates memory flashcards |
| Critic Agent | Validates AI outputs before returning results |

---

## Learning Pipeline

1. Upload lecture material.
2. Extract lecture text.
3. Generate a structured summary.
4. Build a personalized study plan.
5. Generate quizzes.
6. Create flashcards.
7. Continue studying using the Pomodoro timer.

---

## Installation

```bash
git clone https://github.com/USERNAME/Study-Companion-AI.git

cd Study-Companion-AI

pip install -r requirements.txt
```

Create a `.env`

```env
GOOGLE_API_KEY=YOUR_API_KEY
GEMINI_MODEL=gemini-2.5-flash
FAST_GEMINI_MODEL=gemini-2.5-flash
```

Run

```bash
python app.py
```

---

## Notes

This repository focuses on the AI backend and orchestration logic. The frontend has intentionally been omitted from the public repository to keep the project centered on the AI architecture and learning pipeline.
