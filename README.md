# AI-Powered Excel Mock Interviewer

## Project Overview

This project implements an **AI-powered Excel mock interviewer**, delivering a structured and professional interview experience. Built as a proof-of-concept, it leverages **LangGraph** for orchestration, **Google Gemini** models for LLM capability, and **Streamlit** for an intuitive interface. It is ideal for candidates preparing for Excel-heavy roles, offering **consistent, fair, and intelligent assessments**.

---

## Core Features

- **Secure User & Admin Login**
  - Distinguishes between interview candidates and administrators
  - Ensures data privacy and role-based access

- **User Experience**
  - One-time interview per user (validated via Excel-based status tracking)
  - Dynamic interview driven by an AI persona with strict no-hint policies

- **Admin Capabilities**
  - Admin dashboard to view results of all users
  - Summary verdicts (Correct, Partially Correct, Incorrect) per question
  - Hardcoded demo credentials: `admin/admin`

- **Persistent Excel Storage**
  - Stores usernames, interview status, detailed responses, evaluations, and verdicts
  - Uses `user_credential_and_analysis.xlsx`

- **Agentic Architecture (LangGraph)**
  - Modular tools: `ask_interview_question`, `evaluate_candidate_answer`, etc.
  - LLM agent state is managed via a robust state machine

- **Strict AI Interviewer Persona**
  - Configured through prompt engineering (in `prompts.py`)
  - AI does **not** provide examples, hints, or solutions

- **Conversation Memory**
  - Uses LangGraph checkpointer for stateful interviews
  - Supports context-aware back-referencing

- **Performance Summary**
  - Generated and shown at the end of the interview
  - Saved to Excel for future review

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| LLM | Google Gemini (via `langchain-google-genai`) |
| LLM Framework | LangChain |
| Orchestration | LangGraph |
| Frontend | Streamlit |
| Excel I/O | Pandas, OpenPyXL |
| Env Management | python-dotenv |
| Typing | typing-extensions |
| Utilities | langchain-community |

---

## Project Structure

```bash
.
├── .env                              # API keys & model config (DO NOT COMMIT)
├── app.py                            # Streamlit UI & main logic
├── agent.py                          # LangGraph agent + state logic
├── excel_handler.py                  # Handles reading/writing Excel data
├── prompts.py                        # Interview persona & evaluation prompts
├── questions.json                    # Bank of Excel interview questions
├── requirements.txt                  # All Python dependencies
├── user_credential_and_analysis.xlsx # User data & interview logs
└── README.md                         # Project documentation
```
---

## Getting Started

### Prerequisites

- Python 3.8 or higher
- `pip` (Python package installer)

---

### Installation

#### 1. Clone or Copy Files

Place all project files (`app.py`, `agent.py`, `excel_handler.py`, `prompts.py`, `questions.json`, `requirements.txt`, `.env`) into a single directory.

#### 2. Create a Virtual Environment

```bash
python -m venv venv
```
#### 3. Activate the Environment

```bash
# macOS/Linux
source venv/bin/activate
```
```bash
# Windows
venv\Scripts\activate
```

#### 4. Install Dependencies
```bash
pip install -r requirements.txt
```
#### 5. Configure Environment Variables

Create a `.env` file in the project root and add:

```env
GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY_HERE"
CHAT_MODEL="gemini-2.0-flash"
# CHAT_URL="https://generativelanguage.googleapis.com/v1beta"
```
---
## Preparing User Data

- `user_credential_and_analysis.xlsx` is created automatically on first run.
- To manually add users:
  - Open the file in Excel.
  - Add usernames under the `username` column.
  - Set `test_taken` as `FALSE` or leave blank.

---

## Running the Application

```bash
streamlit run app.py
```
Visit in browser:

```txt
http://localhost:8501
```
## Usage

### User Login (Candidate)

- Select `User` on login.
- Enter your registered username.
- Click `Start Interview`.
- The AI will:
  - Ask for your name
  - Start asking technical Excel questions
  - Evaluate answers using defined prompts
  - Show verdicts:
    - `Correct`
    - `Partially Correct`
    - `Incorrect`
- After all questions, the final performance report will be displayed.
- The chat input is disabled after interview completion.

### Admin Login

- Select `Admin` on login.
- Use credentials:

```txt
Username: admin
Password: admin
```
- Click `Login as Admin`.
- Access the admin dashboard.

---

## Interview Flow

1. AI asks for user's name.  
2. AI starts asking questions from `questions.json`.  
3. User submits answers.  
4. AI evaluates each answer.  
5. Evaluation and verdict are displayed.  
6. Final performance report is generated.  
7. Chat is locked and results are saved.  

---

## Admin Dashboard

- Displays:
  - `username`
  - `test_taken` status
  - `answer_X` fields
  - `evaluation_X` fields
  - Verdict summary

---
a
## License

Licensed under the **MIT License**.  

---

## Contact

- [Open an issue](https://github.com/mohit09082002/ai-excel-interviewer/issues)
- [Start a discussion]([https://github.com/your-repo](https://github.com/mohit09082002/ai-excel-interviewer)/discussions)
- [Submit a Pull Request](https://github.com/mohit09082002/ai-excel-interviewer/pulls)

---



