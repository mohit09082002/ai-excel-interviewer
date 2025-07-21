import pandas as pd
import os

EXCEL_FILE = "user_credential_and_analysis.xlsx"

def initialize_excel_file():
    """Creates the Excel file with the required columns if it doesn't exist."""
    if not os.path.exists(EXCEL_FILE):
        df = pd.DataFrame(columns=["username", "test_taken"])
        # Add columns for each question's answer and evaluation
        # This part can be made more dynamic if questions change often
        for i in range(1, 5): # Assuming 4 questions for now
            df[f"answer_{i}"] = None
            df[f"evaluation_{i}"] = None
        df.to_excel(EXCEL_FILE, index=False)
        print(f"'{EXCEL_FILE}' created successfully.")

def validate_user(username: str) -> str:
    """
    Validates the user.
    Returns "valid" if the user exists and has not taken the test.
    Returns "taken" if the user exists but has already taken the test.
    Returns "not_found" if the user does not exist.
    """
    try:
        df = pd.read_excel(EXCEL_FILE)
        user_row = df[df["username"] == username]
        if not user_row.empty:
            if user_row.iloc[0]["test_taken"] == True:
                return "taken"
            else:
                return "valid"
        else:
            return "not_found"
    except FileNotFoundError:
        initialize_excel_file()
        return "not_found"

def save_interview_results(username: str, feedback_report: list):
    """Saves the interview results to the Excel file."""
    try:
        df = pd.read_excel(EXCEL_FILE)
        user_index = df[df["username"] == username].index
        
        if not user_index.empty:
            # Mark the test as taken
            df.loc[user_index, "test_taken"] = True
            
            # Save each question and its evaluation
            for i, report in enumerate(feedback_report, 1):
                if f"evaluation_{i}" in df.columns:
                    full_text = f"Question: {report['question']}\n\nEvaluation: {report['evaluation']}"
                    df.loc[user_index, f"evaluation_{i}"] = full_text

                    # Extract the verdict from the evaluation text
                    evaluation_text = report['evaluation']
                    verdict_prefix = "Verdict: "
                    verdict = "N/A" # Default if verdict not found
                    if verdict_prefix in evaluation_text:
                        # Split by the prefix and take the last part, then strip whitespace
                        verdict = evaluation_text.split(verdict_prefix)[-1].strip()
                    
                    # Populate the answer_X column with the extracted verdict
                    if f"answer_{i}" in df.columns:
                        df.loc[user_index, f"answer_{i}"] = verdict
            
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
