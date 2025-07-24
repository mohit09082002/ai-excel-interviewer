import pandas as pd
import os
import json
from typing import Tuple, Optional

EXCEL_FILE = "user_credential_and_analysis.xlsx"

def initialize_excel_file():
    """Creates the Excel file with the required columns and default users if it doesn't exist."""
    if not os.path.exists(EXCEL_FILE):
        try:
            with open("questions.json", "r") as f:
                num_static_questions = len(json.load(f))
        except FileNotFoundError:
            num_static_questions = 5

        # Defines the new column order as requested
        columns = ["username", "interview_type", "num_questions", "test_taken", "final_rating"]
        for i in range(1, num_static_questions + 1):
            columns.append(f"answer_{i}")
            columns.append(f"evaluation_{i}")

        df = pd.DataFrame(columns=columns)
        
        # Populates with the new default users and num_questions as requested
        default_users = [
            {"username": "user1", "interview_type": "Static", "num_questions": None},
            {"username": "user2", "interview_type": "Dynamic", "num_questions": 4},
            {"username": "user3", "interview_type": "Hybrid", "num_questions": 5},
        ]
        
        df = pd.concat([df, pd.DataFrame(default_users)], ignore_index=True)
        # Ensure correct column order and handle NaNs for empty cells
        df = df.reindex(columns=columns)
        df.to_excel(EXCEL_FILE, index=False)
        print(f"'{EXCEL_FILE}' created with default users.")

def validate_user(username: str) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Validates the user and returns their status, interview type, and number of questions.
    Returns: A tuple of (status, interview_type, num_questions).
    """
    try:
        df = pd.read_excel(EXCEL_FILE)
        # Add num_questions column with a default if it doesn't exist
        if "num_questions" not in df.columns:
            df.insert(2, "num_questions", 5) # Default to 5 questions
            df.to_excel(EXCEL_FILE, index=False)

        user_row = df[df["username"] == username]
        if not user_row.empty:
            if user_row.iloc[0]["test_taken"] == True:
                return "taken", None, None
            else:
                interview_type = user_row.iloc[0]["interview_type"]
                
                num_questions_val = user_row.iloc[0]["num_questions"]
                # Handle empty/NaN values for num_questions (e.g., for Static type)
                if pd.isna(num_questions_val):
                    num_questions = None
                else:
                    num_questions = int(num_questions_val)
                    
                return "valid", interview_type, num_questions
        else:
            return "not_found", None, None
    except FileNotFoundError:
        initialize_excel_file()
        return validate_user(username)

def save_interview_results(username: str, feedback_report: list, final_rating: Optional[str]):
    """Saves the interview results to the Excel file."""
    try:
        df = pd.read_excel(EXCEL_FILE)
        user_index = df[df["username"] == username].index

        if not user_index.empty:
            df.loc[user_index, "test_taken"] = True
            df.loc[user_index, "final_rating"] = final_rating

            for i, report in enumerate(feedback_report, 1):
                eval_col = f"evaluation_{i}"
                ans_col = f"answer_{i}"

                if eval_col not in df.columns:
                    df[eval_col] = pd.NA
                if ans_col not in df.columns:
                    df[ans_col] = pd.NA

                full_text = f"Question: {report['question']}\n\nEvaluation: {report['evaluation']}"
                df.loc[user_index, eval_col] = full_text

                evaluation_text = report['evaluation']
                verdict_prefix = "Verdict: "
                verdict = "N/A"
                if verdict_prefix in evaluation_text:
                    verdict = evaluation_text.split(verdict_prefix)[-1].strip()

                df.loc[user_index, ans_col] = verdict

            df.to_excel(EXCEL_FILE, index=False)
            print(f"Results saved for user '{username}'.")
    except Exception as e:
        print(f"Error saving results for {username}: {e}")

def get_all_results() -> pd.DataFrame:
    """Loads and returns all user data and results from the Excel file."""
    try:
        df = pd.read_excel(EXCEL_FILE)
        return df
    except FileNotFoundError:
        initialize_excel_file()
        return pd.read_excel(EXCEL_FILE)
