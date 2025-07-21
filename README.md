AI-Powered Excel Mock Interviewer
Project Overview
This project implements an AI-powered Excel mock interviewer designed to provide a structured and professional technical interview experience. Built as a proof-of-concept, it leverages a large language model (LLM) orchestrated by LangGraph to conduct conversational interviews, with a user-friendly interface powered by Streamlit. This system is ideal for candidates preparing for Excel-focused roles, offering a consistent and unbiased assessment.

The core of the application features a sophisticated agent-with-tools architecture, where a primary conversational agent intelligently manages the interview flow, utilizing specialized tools to dynamically ask questions and objectively evaluate candidate responses.

Core Features
Secure User & Admin Login: The application incorporates a robust login system, distinguishing between interview candidates (users) and administrators, ensuring data segregation and controlled access.

User Privileges: Regular users can log in with a pre-registered username to take the mock interview. Each user's interview progress and results are tracked and saved. A user can only take the interview once, ensuring fair assessment and preventing repeated attempts from the same account.

Admin Privileges: The administrator has elevated access, allowing them to view a comprehensive dashboard of all user interview results. This provides an overview of candidate performance, interview history, and allows for data oversight. The admin login uses a simple, hardcoded credential for demonstration purposes (admin/admin).

Persistent Data Storage: All user credentials, their interview status (whether they have taken the test), and comprehensive interview results (including detailed evaluations and verdicts for each question) are securely stored and managed within an Excel file (user_credential_and_analysis.xlsx). This allows for easy review, analysis, and record-keeping, even after the application is closed and restarted.

Intuitive Admin Dashboard: Administrators can access a dedicated dashboard to view and analyze the complete interview results for all users directly within the application, facilitating oversight and performance tracking. The dashboard displays a table with usernames, test status, and detailed evaluations for each question, including the extracted verdict (Correct, Partially Correct, or Incorrect) in a separate column.

Advanced Agentic Architecture: A sophisticated conversational agent, powered by LangGraph, drives the interview process. It intelligently selects and executes specialized tools for tasks such as asking questions, evaluating answers, and concluding the interview, ensuring a dynamic and adaptive interview experience. The agent's behavior is defined by its state machine, ensuring a consistent and controlled interview flow.

Strict Interviewer Persona: The AI interviewer adheres to a strict persona, explicitly programmed via prompts.py to avoid providing hints, examples, or direct answers to technical questions. This ensures a realistic, fair, and challenging interview environment, focusing solely on assessing the candidate's knowledge and problem-solving abilities.

Stateful Conversation Memory: The agent maintains a complete memory of the entire conversation history using LangGraph's checkpointer. This enables context-aware interactions, allowing the AI to refer back to previous parts of the conversation and ensuring a seamless interview flow, even across multiple turns.

Comprehensive Performance Report: Upon interview completion, a detailed and expandable performance summary is generated and displayed directly to the user. This report includes the original question, the AI's detailed evaluation, and a clear verdict (Correct, Partially Correct, or Incorrect) for each question. This report is also saved to the Excel file for administrative review. The user input box is automatically hidden once the report is displayed, indicating the end of the interactive session.

Tech Stack
LLM Integration: Configurable via environment variables (.env), supporting Google's Gemini models through langchain-google-genai. This allows for flexible deployment with different LLM providers and models.

LLM Framework: LangChain for building applications with language models, and langchain-google-genai for seamless integration with Google's generative AI models.

Agentic Logic & State Management: LangGraph for creating robust, stateful, and multi-actor applications with LLMs, managing the complex interview flow and tool orchestration.

Frontend Framework: Streamlit for rapidly building interactive web applications with Python, providing a clean, responsive, and easy-to-use user interface.

Data Management: Pandas for efficient data manipulation and analysis of the Excel file, and OpenPyXL for robust reading and writing of .xlsx files.

Environment Variables: python-dotenv for securely loading environment variables from a .env file, keeping sensitive information (like API keys) out of the codebase.

Type Hinting: typing-extensions for advanced type hints, improving code readability, maintainability, and enabling static analysis.

Core Utilities: langchain-community for common LangChain utilities and integrations.

Project Structure
This project is organized into several Python files, each serving a distinct purpose:

.
├── .env                              # Environment variables for API keys and model configuration (Crucial for security, DO NOT COMMIT!)
├── app.py                            # The main Streamlit application. Handles the web UI, user/admin login, and manages the interaction with the LangGraph agent. This is the file you run to start the application.
├── agent.py                          # Defines the core LangGraph agent. This includes the agent's state, the custom tools (e.g., `ask_interview_question`, `evaluate_candidate_answer`, `conclude_interview`) that the agent can use, and the state machine logic (nodes and edges) that dictates the interview flow.
├── excel_handler.py                  # A utility module responsible for all interactions with the `user_credential_and_analysis.xlsx` file. It handles initialization of the Excel file, user validation, saving interview results, and retrieving all user data for the admin dashboard.
├── prompts.py                        # Contains the large language model's system prompts and templates. This includes the `SYSTEM_PROMPT` that defines the AI interviewer's persona and interview flow rules, and `EVALUATION_PROMPT_TEMPLATE` used for assessing candidate answers.
├── questions.json                    # A JSON file containing the bank of predefined Excel interview questions. Each question includes its category, difficulty, the question text, and expected concepts for evaluation.
├── requirements.txt                  # Lists all Python package dependencies required to run the project. You use this file with `pip install -r requirements.txt` to set up your environment.
├── user_credential_and_analysis.xlsx # The Excel file that stores user accounts (usernames, test taken status) and the detailed results of completed interviews. This file is created automatically on first run if it doesn't exist.
└── README.md                         # This comprehensive documentation file, providing an overview, setup instructions, usage guide, and project details.

Getting Started
Follow these steps to set up and run the AI-Powered Excel Mock Interviewer locally.

Prerequisites
Python 3.8 or higher (It's recommended to use the latest stable version of Python 3.)

pip (Python package installer, usually comes with Python installation)

Installation
Clone the repository (or create project files):
If you have the project files locally, create a new, empty directory. Then, copy all the project files (app.py, agent.py, excel_handler.py, prompts.py, questions.json, requirements.txt, and the empty .env file you intend to use) into this new directory.

Create a virtual environment (highly recommended):
Using a virtual environment isolates your project's dependencies from your system's Python packages, preventing conflicts.

python -m venv venv

Activate the virtual environment:

On macOS/Linux:

source venv/bin/activate

On Windows:

venv\Scripts\activate

Install dependencies:
With your virtual environment activated, install all required Python packages listed in requirements.txt:

pip install -r requirements.txt

Configure Environment Variables (The .env file):
The .env file is crucial for securely storing your API key and LLM configuration without hardcoding them into your application code.

Location: Ensure your .env file is in the root directory of your project (the same directory as app.py).

Content: Open the .env file with a text editor and add the following lines. Replace YOUR_GOOGLE_API_KEY_HERE with your actual Google API Key. You can also specify the CHAT_MODEL if you want to use a different Gemini model (e.g., gemini-1.5-flash, gemini-1.5-pro).

GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY_HERE"
CHAT_MODEL="gemini-2.0-flash" # Or another Gemini model like gemini-1.5-pro
# CHAT_URL="https://generativelanguage.googleapis.com/v1beta" # Uncomment and modify if you need a custom endpoint

How to get an API Key: You can obtain a Google API Key from the Google AI Studio or Google Cloud Console. Make sure it has access to the Gemini API.

Security Note: The .env file is intentionally excluded from version control (.gitignore) because it contains sensitive information. Never commit your .env file to a public repository.

Prepare User Data (user_credential_and_analysis.xlsx):
This Excel file manages user accounts and stores interview results.

Automatic Creation: The first time you run app.py, this Excel file will be automatically created with the necessary columns (username, test_taken, answer_1, evaluation_1, etc.) if it doesn't already exist.

Adding Users: To add new users who can take mock interviews, open user_credential_and_analysis.xlsx (e.g., using Microsoft Excel, Google Sheets, or LibreOffice Calc). Add unique usernames in the username column. Ensure the test_taken column is set to FALSE (or left blank, as the application treats empty cells as FALSE) for new users who haven't completed the interview yet. Save the file after making changes.

Running the Application
Start the Streamlit application:
From your project's root directory (where app.py is located), ensure your virtual environment is activated, and then run the command:

streamlit run app.py

Access the Interviewer:
The application will automatically open in your default web browser (usually at http://localhost:8501). If it doesn't, copy and paste the URL provided in your terminal into your browser.

Usage
User Login (Candidate)
On the initial login page, select "User" as your login type.

Enter your username. This username must already exist in the user_credential_and_analysis.xlsx file, and the test_taken status for this user must be FALSE (or empty).

Click the "Start Interview" button.

If the username is valid and the test has not been taken previously, you will be redirected to the interview chat page.

Admin Login
On the initial login page, select "Admin" as your login type.

Enter the default administrative credentials:

Admin Username: admin

Admin Password: admin

Click the "Login as Admin" button.

Upon successful login, you will be directed to the Admin Dashboard.

Taking the Interview (as a User)
Once on the interview page, the AI interviewer, "Excel Ninja," will introduce itself and prompt you to provide your name.

Type your name in the chat input box and press Enter. The AI will then greet you personally.

Immediately after the personal greeting, the AI will ask the first technical Excel question.

Type your answer to the question in the input box and press Enter.

The AI will process your response, evaluate your answer based on the expected_concepts defined in questions.json, and provide a brief evaluation along with a clear verdict (e.g., "Verdict: Correct", "Verdict: Partially Correct", or "Verdict: Incorrect").

This process of asking a question, receiving your answer, and providing evaluation continues for all questions defined in questions.json.

Once all questions have been asked and evaluated, the interview will formally conclude. A "Final Performance Report" will be displayed on the screen, summarizing your performance for each question. At this point, the chat input box will automatically disappear, signifying the end of the interactive interview session. Your comprehensive results will be saved to the Excel file.

Viewing Results (as an Admin)
Log in to the application as an Admin using the default credentials.

The Admin Dashboard will be displayed, presenting a Streamlit dataframe (st.dataframe) that shows all registered users and their interview results.

You can review the test_taken column to see which users have completed the interview.

The evaluation_X columns contain the detailed evaluation text provided by the AI for each question.

The answer_X columns (e.g., answer_1, answer_2) will contain the extracted "Verdict" (Correct, Partially Correct, or Incorrect) for each corresponding question, providing a quick summary of performance.

Contributing
Contributions are welcome! If you have suggestions for improvements, bug fixes, or new features, please feel free to:

Fork the repository.

Create a new branch (git checkout -b feature/your-feature-name).

Make your changes and ensure they align with the project's coding style and principles.

Commit your changes with a clear and concise message (git commit -m 'Add new feature: [Brief description]').

Push your changes to your new branch (git push origin feature/your-feature-name).

Open a Pull Request to the main repository, providing a detailed description of your changes and their purpose.

License
This project is open-sourced under the MIT License. A LICENSE file should be included in the repository for full details.