import pandas as pd
import os
import json
from typing import Tuple, Optional

EXCEL_FILE = "user_credential_and_analysis.xlsx"

def initialize_excel_file():
    """Creates the Excel file with the required columns if it doesn't exist."""
    if not os.path.exists(EXCEL_FILE):
        # Load questions to determine how many answer/evaluation columns are needed for static interviews
        try:
            with open("questions.json", "r") as f:
                num_questions = len(json.load(f))
        except FileNotFoundError:
            num_questions = 5 # Default to 5 if questions.json is missing

        # Defines the column order, with "final_rating" in position 4
        columns = ["username", "interview_type", "test_taken", "final_rating"]
        for i in range(1, num_questions + 1):
            columns.append(f"answer_{i}")
            columns.append(f"evaluation_{i}")

        df = pd.DataFrame(columns=columns)
        # Add some default users
        default_users = [
            {"username": "mohit_static", "test_taken": False, "interview_type": "Static"},
            {"username": "rohan_dynamic", "test_taken": False, "interview_type": "Dynamic"},
            {"username": "sara_hybrid", "test_taken": False, "interview_type": "Hybrid"},
            {"username": "jane_doe", "test_taken": False, "interview_type": "Static"},
        ]
        df = pd.concat([df, pd.DataFrame(default_users)], ignore_index=True)
        # Ensure the columns are written in the specified order and new columns have NaNs
        df = df.reindex(columns=columns)
        df.to_excel(EXCEL_FILE, index=False)
        print(f"'{EXCEL_FILE}' created with default users.")

def validate_user(username: str) -> Tuple[str, Optional[str]]:
    """
    Validates the user and returns their status and interview type.
    Returns:
    - ("valid", interview_type) if the user exists and has not taken the test.
    - ("taken", None) if the user exists but has already taken the test.
    - ("not_found", None) if the user does not exist.
    """
    try:
        df = pd.read_excel(EXCEL_FILE)
        # Ensure 'interview_type' column exists, add it if not
        if "interview_type" not in df.columns:
            # If it's missing, add it in the desired position
            df.insert(1, "interview_type", "Static") # Default to static
            df.to_excel(EXCEL_FILE, index=False)

        user_row = df[df["username"] == username]
        if not user_row.empty:
            if user_row.iloc[0]["test_taken"] == True:
                return "taken", None
            else:
                interview_type = user_row.iloc[0]["interview_type"]
                return "valid", interview_type
        else:
            return "not_found", None
    except FileNotFoundError:
        initialize_excel_file()
        # After initializing, try to find the user again.
        df = pd.read_excel(EXCEL_FILE)
        user_row = df[df["username"] == username]
        if not user_row.empty:
            interview_type = user_row.iloc[0]["interview_type"]
            return "valid", interview_type
        else:
            return "not_found", None


def update_user_interview_type(username: str, interview_type: str):
    """Updates the interview type for a specific user."""
    try:
        df = pd.read_excel(EXCEL_FILE)
        user_index = df[df["username"] == username].index
        if not user_index.empty:
            df.loc[user_index, "interview_type"] = interview_type
            df.to_excel(EXCEL_FILE, index=False)
            print(f"Updated interview type for {username} to {interview_type}")
            return True
        return False
    except Exception as e:
        print(f"Error updating interview type for {username}: {e}")
        return False


def save_interview_results(username: str, feedback_report: list, final_rating: Optional[str]):
    """Saves the interview results to the Excel file."""
    try:
        df = pd.read_excel(EXCEL_FILE)
        user_index = df[df["username"] == username].index

        if not user_index.empty:
            df.loc[user_index, "test_taken"] = True
            # Save the final rating
            df.loc[user_index, "final_rating"] = final_rating

            for i, report in enumerate(feedback_report, 1):
                eval_col = f"evaluation_{i}"
                ans_col = f"answer_{i}"

                # Dynamically add columns if they don't exist (for dynamic interviews > static count)
                if eval_col not in df.columns:
                    df[eval_col] = None
                if ans_col not in df.columns:
                    df[ans_col] = None

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
    """Loads and returns all user data and results."""
    try:
        df = pd.read_excel(EXCEL_FILE)
        return df
    except FileNotFoundError:
        initialize_excel_file()
        return pd.DataFrame()