import streamlit as st
import os
import json
import time
import pandas as pd
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver

from agent import create_agent_graph, AgentState
from excel_handler import (
    initialize_excel_file,
    validate_user,
    save_interview_results,
    get_all_results,
    EXCEL_FILE
)

# --- Configuration and Initialization ---
load_dotenv()
CHAT_KEY = os.getenv("GOOGLE_API_KEY")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-2.0-flash")

llm = None
if CHAT_KEY:
    llm = ChatGoogleGenerativeAI(model=CHAT_MODEL, google_api_key=CHAT_KEY, temperature=0.7)
else:
    st.error("LLM configuration missing. Please set GOOGLE_API_KEY in your .env file.")

def load_questions():
    try:
        with open("questions.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
interview_questions = load_questions()

# --- App Pages ---
def show_login_page():
    st.header("Login")
    login_type = st.radio("Choose your login type:", ("User", "Admin"))

    if login_type == "User":
        username = st.text_input("Enter your username:")
        if st.button("Start Interview"):
            if username:
                status, interview_type, num_questions = validate_user(username)
                if status == "valid":
                    st.session_state.logged_in = True
                    st.session_state.role = "user"
                    st.session_state.username = username
                    st.session_state.interview_type = interview_type
                    st.session_state.num_questions = num_questions
                    st.rerun()
                elif status == "taken":
                    st.error("This username has already completed the interview.")
                else:
                    st.error("Username not found. Please check the username or contact an administrator.")
            else:
                st.warning("Please enter a username.")

    elif login_type == "Admin":
        admin_user = st.text_input("Admin Username:")
        admin_pass = st.text_input("Admin Password:", type="password")
        if st.button("Login as Admin"):
            if admin_user == "admin" and admin_pass == "admin":
                st.session_state.logged_in = True
                st.session_state.role = "admin"
                st.session_state.username = "admin"
                st.rerun()
            else:
                st.error("Invalid admin credentials.")

def show_admin_dashboard():
    st.header("Admin Dashboard: Interview Results & User Management")
    st.write("View results, manage users, and configure interview settings.")

    results_df = get_all_results()
    if not results_df.empty:
        st.info("You can add/delete users and change settings for anyone who has not taken the test. Usernames for completed interviews cannot be changed.")
        
        edited_df = st.data_editor(
            results_df,
            column_config={
                "username": st.column_config.TextColumn(
                    "Username", help="The candidate's unique username.", required=True,
                ),
                "interview_type": st.column_config.SelectboxColumn(
                    "Interview Type", options=["Static", "Dynamic", "Hybrid"], required=True,
                ),
                "num_questions": st.column_config.NumberColumn(
                    "Number of Questions", help="Set number of questions for Dynamic/Hybrid interviews (e.g., 5). Leave empty for Static.", min_value=1, max_value=10, step=1,
                ),
                "test_taken": st.column_config.CheckboxColumn("Test Taken?", disabled=True),
                "final_rating": st.column_config.TextColumn("Final Rating", disabled=True),
            },
            disabled=[col for col in results_df.columns if "answer_" in col or "evaluation_" in col or col in ["test_taken", "final_rating"]],
            num_rows="dynamic"
        )

        if st.button("Save Changes"):
            try:
                original_df = get_all_results()
                validation_error = False

                for index, edited_row in edited_df.iterrows():
                    if index in original_df.index:
                        original_row = original_df.loc[index]
                        if original_row['test_taken'] == True and original_row['username'] != edited_row['username']:
                            st.error(f"Error: Cannot rename user '{original_row['username']}' because they have already completed the interview.")
                            validation_error = True
                            break
                
                if not validation_error and edited_df['username'].duplicated().any():
                    st.error("Error: Usernames must be unique. Please resolve duplicate entries before saving.")
                    validation_error = True
                
                if not validation_error and edited_df['username'].isnull().any():
                    st.error("Error: Username cannot be empty. Please enter a username for all users.")
                    validation_error = True

                if not validation_error:
                    edited_df['num_questions'] = pd.to_numeric(edited_df['num_questions'], errors='coerce').astype('Int64')
                    edited_df.to_excel(EXCEL_FILE, index=False)
                    st.success("Changes saved successfully!")
                    st.rerun()

            except Exception as e:
                st.error(f"Failed to save changes: {e}")

    else:
        st.info("No interview results found. The file might be empty.")

    if st.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

def show_interview_page():
    interview_type = st.session_state.get("interview_type", "Static")
    st.subheader(f"Mode: {interview_type} Interview")

    if "agent" not in st.session_state:
        thread_id = f"interview-{interview_type}-{st.session_state.username}-{int(time.time())}"
        st.session_state.thread_config = {"configurable": {"thread_id": thread_id}}

        memory = MemorySaver()
        st.session_state.agent = create_agent_graph(llm, checkpointer=memory, interview_type=interview_type)
        
        initial_state: AgentState = {
            "messages": [HumanMessage(content="INITIALIZE_INTERVIEW_AGENT")],
            "interview_questions": interview_questions if interview_type in ["Static", "Hybrid"] else [],
            "question_number": 0, "feedback_report": [], "interview_finished": False,
            "user_name": st.session_state.username, "interview_type": interview_type,
            "current_question": "", "final_rating": None,
            "num_questions_to_ask": st.session_state.get("num_questions")
        }
        with st.spinner(f"Initializing {interview_type} interview..."):
            st.session_state.agent.invoke(initial_state, st.session_state.thread_config)
        st.session_state.processing = False

    if "processing" not in st.session_state:
        st.session_state.processing = False

    history = st.session_state.agent.get_state(st.session_state.thread_config)
    if not history:
        st.rerun()

    # --- NEW: Progress Bar Logic ---
    interview_is_finished = history.values.get("interview_finished", False)
    if not interview_is_finished:
        if interview_type == "Static":
            total_questions = len(interview_questions)
        else:
            total_questions = st.session_state.get("num_questions", 5)

        questions_answered = len(history.values.get("feedback_report", []))
        
        if total_questions > 0:
            current_q_display_num = min(questions_answered + 1, total_questions)
            st.markdown(f"**Question {current_q_display_num} of {total_questions}**")
            progress_value = questions_answered / total_questions
            st.progress(progress_value)
            st.markdown("---")
    # --- End of Progress Bar Logic ---

    for message in history.values['messages']:
        if isinstance(message, (SystemMessage, ToolMessage)) or (isinstance(message, HumanMessage) and message.content == "INITIALIZE_INTERVIEW_AGENT"):
            continue
        if isinstance(message, HumanMessage):
            with st.chat_message("human"): st.markdown(message.content)
        elif isinstance(message, AIMessage) and not message.tool_calls and message.content:
            with st.chat_message("ai"): st.markdown(message.content)

    if not interview_is_finished:
        if prompt := st.chat_input("Your answer...", disabled=st.session_state.processing):
            st.session_state.processing = True
            st.session_state.agent.update_state(st.session_state.thread_config, {"messages": [HumanMessage(content=prompt)]})
            st.rerun()

    if st.session_state.processing:
        with st.spinner("Thinking..."):
            st.session_state.agent.invoke(None, st.session_state.thread_config)
        st.session_state.processing = False
        st.rerun()

    final_state = st.session_state.agent.get_state(st.session_state.thread_config)
    if final_state and final_state.values.get("interview_finished", False):
        st.markdown("---")
        st.header("Final Performance Report")

        final_rating = final_state.values.get("final_rating")
        if final_rating:
            st.metric(label="**Final Interview Score**", value=final_rating)
        
        feedback_data = final_state.values["feedback_report"]
        for item in feedback_data:
            with st.expander(label=f"**{item.get('question', 'Unknown Question')}**"):
                st.markdown(f"**Your Answer:**\n{item.get('user_answer', 'N/A')}")
                st.markdown("---")
                st.markdown(f"**Evaluation:**\n{item.get('evaluation', 'No evaluation found.')}")

        if "results_saved" not in st.session_state:
            save_interview_results(st.session_state.username, feedback_data, final_rating)
            st.session_state.results_saved = True
            st.success("Your interview results have been saved.")

        if st.button("Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

def main():
    st.set_page_config(page_title="AI Excel Interviewer", page_icon="🤖", layout="wide")
    st.title("AI-Powered Excel Interviewer")

    initialize_excel_file()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        show_login_page()
    elif st.session_state.get("role") == "admin":
        show_admin_dashboard()
    elif st.session_state.get("role") == "user":
        if not llm:
            st.warning("The interview system is not configured. Please contact an administrator.")
            st.stop()
        show_interview_page()

if __name__ == "__main__":
    main()
