import os
import json
from typing import List, Optional
from typing_extensions import TypedDict, Annotated
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from prompts import SYSTEM_PROMPT, EVALUATION_PROMPT_TEMPLATE

# --- Agent State Definition ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_name: Optional[str]
    interview_questions: List[dict]
    question_number: int
    feedback_report: Annotated[List[dict], operator.add]
    interview_finished: bool

# --- Tools for the Agent ---
# We define tools and attach them to the agent.
# The agent's state is passed to each tool so it has context.

@tool
def ask_interview_question(state: AgentState) -> str:
    """Use this tool to ask the next technical interview question."""
    q_number = state.get("question_number", 0)
    questions = state.get("interview_questions", [])
    if q_number < len(questions):
        return questions[q_number]["question"]
    else:
        return "NO_MORE_QUESTIONS"

@tool
def evaluate_candidate_answer(user_answer: str, state: AgentState) -> str:
    """Use this tool to evaluate a candidate's answer to a technical question."""
    q_number = state.get("question_number", 0)
    questions = state.get("interview_questions", [])
    
    if q_number >= len(questions):
        return "Evaluation failed: No active question."
        
    question_data = questions[q_number]
    
    # Use a separate LLM call for objective evaluation, configured from .env
    eval_llm = ChatOpenAI(
        model=os.getenv("CHAT_MODEL"),
        api_key=os.getenv("CHAT_KEY"),
        base_url=os.getenv("CHAT_URL"),
        temperature=0.0
    )
    
    prompt = EVALUATION_PROMPT_TEMPLATE.format(
        question=question_data["question"],
        expected_concepts=question_data["expected_concepts"],
        user_answer=user_answer,
    )
    
    evaluation = eval_llm.invoke(prompt).content
    
    # The tool returns the evaluation text. The graph will handle state updates.
    return evaluation

@tool
def conclude_interview(state: AgentState) -> str:
    """Use this tool to end the interview after all questions are asked and evaluated."""
    user_name = state.get("user_name", "Candidate")
    return f"Interview concluded for {user_name}."

# --- Agent Definition ---
def create_agent(llm, tools, checkpointer):
    # This is the primary agent that will drive the conversation.
    agent = llm.bind_tools(tools)

    def agent_node(state: AgentState, agent, name):
        print("\n---AGENT NODE---")
        print(f"Current messages: {[msg.pretty_repr() for msg in state['messages']]}")
        result = agent.invoke(state["messages"])
        print(f"Agent response: {result.pretty_repr()}")
        return {"messages": [result]}

    # Create the graph
    graph = StateGraph(AgentState)
    graph.add_node("interviewer", lambda state: agent_node(state, agent, "interviewer"))
    
    # Define a function to call the tools
    def tool_node(state: AgentState):
        print("\n---TOOL NODE---")
        messages = state["messages"]
        last_message = messages[-1]
        
        tool_invocations = last_message.tool_calls
        print(f"Tool calls: {tool_invocations}")

        q_number = state.get("question_number", 0)
        interview_finished = state.get("interview_finished", False)
        
        # This will hold ONLY the updates for the current step
        new_feedback_reports = []
        tool_outputs = []

        for call in tool_invocations:
            tool_name = call["name"]
            
            # Construct the input for the tool correctly
            tool_input = {**call["args"], "state": state}
            
            if tool_name == "evaluate_candidate_answer":
                result = globals()[tool_name].invoke(tool_input)
                # Create just the NEW report item for this turn
                new_report_item = {
                    "question": state["interview_questions"][q_number]["question"],
                    "evaluation": result
                }
                new_feedback_reports.append(new_report_item)
                q_number += 1
            elif tool_name == "ask_interview_question":
                result = globals()[tool_name].invoke(tool_input)
            elif tool_name == "conclude_interview":
                result = globals()[tool_name].invoke(tool_input)
                interview_finished = True # Set the flag to end the interview
            else:
                result = f"Unknown tool {tool_name} called."

            tool_outputs.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
            
        print(f"Tool outputs: {[msg.pretty_repr() for msg in tool_outputs]}")
        print(f"Interview finished flag: {interview_finished}")
        # Return ONLY the new information. LangGraph will add it to the state.
        return {
            "messages": tool_outputs, 
            "question_number": q_number, 
            "feedback_report": new_feedback_reports,
            "interview_finished": interview_finished
        }

    graph.add_node("tools", tool_node)


    # Define the conditional logic for routing
    def should_continue(state: AgentState):
        print("\n---ROUTING---")
        last_message = state["messages"][-1]
        
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            print("Decision: Call tools.")
            return "tools"
        
        if state.get("interview_finished", False):
            print("Decision: End interview.")
            return END
            
        # After a tool has been called and responded, the agent should respond to the user.
        # If the last message is a tool message, it's the agent's turn.
        if isinstance(last_message, ToolMessage):
             print("Decision: Agent to process tool output.")
             return "interviewer"

        # If the last message is from the human, it's the agent's turn.
        if isinstance(last_message, HumanMessage):
            print("Decision: Agent to process human input.")
            return "interviewer"

        # If the last message is an AI message without tool calls, the turn is over.
        print("Decision: End of turn, wait for user.")
        return END

    graph.add_conditional_edges("interviewer", should_continue, {
        "tools": "tools",
        "interviewer": "interviewer",
        END: END
    })
    graph.add_edge("tools", "interviewer")
    graph.set_entry_point("interviewer")
    
    return graph.compile(checkpointer=checkpointer)