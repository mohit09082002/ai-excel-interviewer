import streamlit as st
import os
import json
import time
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver

from agent import create_agent, AgentState, ask_interview_question, evaluate_candidate_answer, conclude_interview
from prompts import SYSTEM_PROMPT
from excel_handler import initialize_excel_file, validate_user, save_interview_results, get_all_results

# # --- Configuration and Initialization ---
# load_dotenv()
# CHAT_KEY = os.getenv("CHAT_KEY")
# CHAT_URL = os.getenv("CHAT_URL")
# CHAT_MODEL = os.getenv("CHAT_MODEL")

# # Initialize the LLM once
# llm = None
# if CHAT_KEY and CHAT_URL and CHAT_MODEL:
#     llm = ChatOpenAI(
#         model=CHAT_MODEL,
#         api_key=CHAT_KEY,
#         base_url=CHAT_URL,
#         temperature=0.7
#     )

# --- Configuration and Initialization ---
load_dotenv()
# Changed to GOOGLE_API_KEY
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# Using a generic URL for Gemini API, if needed. For most cases, you don't need to specify base_url for Google models.
# If you are using a custom endpoint, specify it here.
CHAT_URL = os.getenv("CHAT_URL", "https://generativelanguage.googleapis.com/v1beta") # Default for Gemini API
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-2.0-flash") # Default to gemini-2.0-flash

# Initialize the LLM once
llm = None
# Check for GOOGLE_API_KEY
if GOOGLE_API_KEY and CHAT_MODEL:
    llm = ChatGoogleGenerativeAI(
        model=CHAT_MODEL,
        google_api_key=GOOGLE_API_KEY, # Use google_api_key parameter
        # base_url=CHAT_URL, # base_url is usually not needed for standard Gemini API access
        temperature=0.7
    )
else:
    st.error("LLM configuration missing. Please ensure GOOGLE_API_KEY and CHAT_MODEL are set in your .env file.")


# Load questions once
def load_questions():
    with open("questions.json", "r") as f:
        return json.load(f)
interview_questions = load_questions()

# --- App Pages ---

def show_login_page():
    st.header("Login")
    login_type = st.radio("Choose your login type:", ("User", "Admin"))

    if login_type == "User":
        username = st.text_input("Enter your username:")
        if st.button("Start Interview"):
            if username:
                status = validate_user(username)
                if status == "valid":
                    st.session_state.logged_in = True
                    st.session_state.role = "user"
                    st.session_state.username = username
                    st.rerun()
                elif status == "taken":
                    st.error("This username has already completed the interview.")
                else:
                    st.error("Username not found. Please contact an administrator.")
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
    st.header("Admin Dashboard: Interview Results")
    st.write("Here you can see the results of all user interviews.")

    results_df = get_all_results()
    if not results_df.empty:
        st.dataframe(results_df)
    else:
        st.info("No interview results found.")

    if st.button("Logout"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()


def show_interview_page():
    # --- Session State and Agent Initialization ---
    if "agent" not in st.session_state:
        # Each user gets their own thread
        thread_id = f"interview-session-{st.session_state.username}-{int(time.time())}"
        st.session_state.thread_config = {"configurable": {"thread_id": thread_id}}

        memory = MemorySaver()
        tools = [ask_interview_question, evaluate_candidate_answer, conclude_interview]
        st.session_state.agent = create_agent(llm, tools, checkpointer=memory)

        # Initial state for a new interview
        initial_state: AgentState = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                # Changed the initial HumanMessage to a generic internal signal
                HumanMessage(content="INITIALIZE_INTERVIEW_AGENT")
            ],
            "interview_questions": interview_questions,
            "question_number": 0,
            "feedback_report": [],
            "interview_finished": False,
            "user_name": st.session_state.username # user_name is still passed here
        }
        with st.spinner("Initializing interview..."):
            st.session_state.agent.invoke(initial_state, st.session_state.thread_config)
        st.session_state.processing = False

    if "processing" not in st.session_state:
        st.session_state.processing = False

    # Display chat history
    history = st.session_state.agent.get_state(st.session_state.thread_config)
    if history:
        # Filter out the initial system message and the internal trigger message from display
        for message in history.values['messages']:
            if isinstance(message, SystemMessage) or \
               (isinstance(message, HumanMessage) and message.content == "INITIALIZE_INTERVIEW_AGENT"):
                continue

            if isinstance(message, HumanMessage):
                with st.chat_message("human"):
                    st.markdown(message.content)
            elif isinstance(message, AIMessage) and not message.tool_calls:
                with st.chat_message("ai"):
                    st.markdown(message.content)

    # Get the current state to check if the interview is finished
    current_state = st.session_state.agent.get_state(st.session_state.thread_config)
    interview_is_finished = current_state and current_state.values.get("interview_finished", False)

    # This block captures new user input and triggers the processing stage
    # The chat input is disabled if processing or if the interview is finished
    # Only display the chat input if the interview is NOT finished
    if not interview_is_finished:
        if prompt := st.chat_input("Your answer...", disabled=st.session_state.processing):
            st.session_state.processing = True
            st.session_state.agent.update_state(
                st.session_state.thread_config,
                {"messages": [HumanMessage(content=prompt)]},
            )
            st.rerun()

    # This block runs the agent when the app is in a processing state
    if st.session_state.processing:
        with st.spinner("Thinking..."):
            st.session_state.agent.invoke(None, st.session_state.thread_config)
        st.session_state.processing = False
        st.rerun()


    # Display the final report and save results
    final_state = st.session_state.agent.get_state(st.session_state.thread_config)
    if final_state and final_state.values.get("interview_finished", False):
        st.markdown("---")
        st.header("Final Performance Report")

        feedback_data = final_state.values["feedback_report"]
        for item in feedback_data:
            try:
                question = item.get("question", "Unknown Question")
                evaluation = item.get("evaluation", "No evaluation found.")
                with st.expander(label=f"**{question}**"):
                    st.markdown(evaluation)
            except Exception:
                st.markdown("Could not display one of the feedback items.")

        # Save results to Excel file
        if "results_saved" not in st.session_state:
            save_interview_results(st.session_state.username, feedback_data)
            st.session_state.results_saved = True
            st.success("Your interview results have been saved.")

        if st.button("Logout"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()


# --- Main App ---
def main():
    st.set_page_config(page_title="AI Excel Interviewer", page_icon="🤖", layout="wide")
    st.title("AI-Powered Excel Interviewer")

    # Ensure Excel file exists before any logic
    initialize_excel_file()

    # Initialize session state for login
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.username = None

    # Page routing
    if not st.session_state.logged_in:
        show_login_page()
    elif st.session_state.role == "admin":
        show_admin_dashboard()
    elif st.session_state.role == "user":
        # Check for LLM configuration only if a user is trying to take the interview
        if not llm:
            st.warning("The interview system is not configured. Please contact an administrator.")
            st.stop()
        show_interview_page()

if __name__ == "__main__":
    main()
