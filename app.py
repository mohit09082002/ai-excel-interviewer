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
    update_user_interview_type
)

# --- Configuration and Initialization ---
load_dotenv()
CHAT_KEY = os.getenv("GOOGLE_API_KEY") # Updated to use the standard env var name
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-1.5-flash")

# Initialize the LLM once
llm = None
if CHAT_KEY:
    llm = ChatGoogleGenerativeAI(model=CHAT_MODEL, google_api_key=CHAT_KEY, temperature=0.7)
else:
    st.error("LLM configuration missing. Please set GOOGLE_API_KEY in your .env file.")

# Load questions for static and hybrid interviews
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
                status, interview_type = validate_user(username)
                if status == "valid":
                    st.session_state.logged_in = True
                    st.session_state.role = "user"
                    st.session_state.username = username
                    st.session_state.interview_type = interview_type
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
    st.header("Admin Dashboard: Interview Results & Configuration")
    st.write("View results and configure the interview type for each user.")

    results_df = get_all_results()
    if not results_df.empty:
        st.info("You can change the 'interview_type' for any user who has not taken the test.")
        
        edited_df = st.data_editor(
            results_df,
            column_config={
                "interview_type": st.column_config.SelectboxColumn(
                    "Interview Type",
                    help="Set the type of interview for the user.",
                    options=["Static", "Dynamic", "Hybrid"],
                    required=True,
                ),
                "test_taken": st.column_config.CheckboxColumn(
                    "Test Taken?",
                    disabled=True,
                ),
                "final_rating": st.column_config.TextColumn(
                    "Final Rating",
                    disabled=True,
                )
            },
            disabled=["username", "test_taken", "final_rating"] + [col for col in results_df.columns if "answer_" in col or "evaluation_" in col],
            num_rows="dynamic" # Allows adding new users
        )

        if st.button("Save Changes"):
            # Compare the dataframes to find changes
            for index, row in edited_df.iterrows():
                original_row = results_df.loc[results_df['username'] == row['username']]
                if not original_row.empty:
                    if original_row.iloc[0]['interview_type'] != row['interview_type']:
                        update_user_interview_type(row['username'], row['interview_type'])
            st.success("Changes saved successfully!")
            st.rerun()

    else:
        st.info("No interview results found. The file might be empty.")

    if st.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

def show_interview_page():
    # --- Session State and Agent Initialization ---
    if "agent" not in st.session_state:
        interview_type = st.session_state.get("interview_type", "Static")
        st.subheader(f"Mode: {interview_type} Interview")

        thread_id = f"interview-{interview_type}-{st.session_state.username}-{int(time.time())}"
        st.session_state.thread_config = {"configurable": {"thread_id": thread_id}}

        memory = MemorySaver()
        st.session_state.agent = create_agent_graph(llm, checkpointer=memory, interview_type=interview_type)

        initial_state: AgentState = {
            "messages": [HumanMessage(content="INITIALIZE_INTERVIEW_AGENT")],
            "interview_questions": interview_questions if interview_type in ["Static", "Hybrid"] else [],
            "question_number": 0,
            "feedback_report": [],
            "interview_finished": False,
            "user_name": st.session_state.username,
            "interview_type": interview_type,
            "current_question": "",
            "final_rating": None,
        }
        with st.spinner(f"Initializing {interview_type} interview..."):
            st.session_state.agent.invoke(initial_state, st.session_state.thread_config)
        st.session_state.processing = False

    if "processing" not in st.session_state:
        st.session_state.processing = False

    # Display chat history
    history = st.session_state.agent.get_state(st.session_state.thread_config)
    if history:
        for message in history.values['messages']:
            if isinstance(message, SystemMessage) or \
               (isinstance(message, HumanMessage) and message.content == "INITIALIZE_INTERVIEW_AGENT"):
                continue
            if isinstance(message, HumanMessage):
                with st.chat_message("human"):
                    st.markdown(message.content)
            elif isinstance(message, AIMessage) and not message.tool_calls and message.content:
                with st.chat_message("ai"):
                    st.markdown(message.content)

    current_state = st.session_state.agent.get_state(st.session_state.thread_config)
    interview_is_finished = current_state and current_state.values.get("interview_finished", False)

    if not interview_is_finished:
        if prompt := st.chat_input("Your answer...", disabled=st.session_state.processing):
            st.session_state.processing = True
            st.session_state.agent.update_state(
                st.session_state.thread_config,
                {"messages": [HumanMessage(content=prompt)]},
            )
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

# --- Main App ---
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