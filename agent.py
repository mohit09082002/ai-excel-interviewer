import os
import json
from typing import List, Optional, Dict
from typing_extensions import TypedDict, Annotated
import operator
import re
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from prompts import (
    STATIC_SYSTEM_PROMPT,
    STATIC_EVALUATION_PROMPT_TEMPLATE,
    DYNAMIC_SYSTEM_PROMPT,
    DYNAMIC_EVALUATION_PROMPT_TEMPLATE,
    QUESTION_GENERATION_PROMPT_TEMPLATE,
    HYBRID_SYSTEM_PROMPT,
    HYBRID_QUESTION_GENERATION_PROMPT_TEMPLATE,
    FINAL_JUDGING_PROMPT_TEMPLATE,
)

# --- Agent State Definition ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_name: Optional[str]
    # For static and hybrid agents
    interview_questions: List[dict]
    # For all agents
    question_number: int
    feedback_report: Annotated[List[dict], operator.add]
    interview_finished: bool
    # For dynamic and hybrid agents
    interview_type: str
    current_question: str
    # For final rating
    final_rating: Optional[str]


# --- Tools for the Agents ---

# --- Tool for STATIC agent ---
@tool
def ask_static_question(state: AgentState) -> str:
    """Use this tool to ask the next predefined technical interview question from a list."""
    q_number = state.get("question_number", 0)
    questions = state.get("interview_questions", [])
    if q_number < len(questions):
        question_text = questions[q_number]["question"]
        return question_text
    else:
        return "NO_MORE_QUESTIONS"

# --- Tool for DYNAMIC agent ---
@tool
def generate_dynamic_question(state: AgentState, request: str) -> str:
    """Use this tool to generate a new, adaptive interview question based on the conversation history."""
    print("\n---GENERATING DYNAMIC QUESTION---")
    
    history_summary = []
    if state.get("feedback_report"):
        for report in state["feedback_report"]:
            history_summary.append(f"- Asked: '{report['question']}' -> Verdict: {report.get('verdict', 'N/A')}")
    history_str = "\n".join(history_summary) if history_summary else "No questions have been asked yet."

    gen_llm = ChatGoogleGenerativeAI(
        model=os.getenv("CHAT_MODEL", "gemini-1.5-flash"),
        temperature=0.8
    )
    
    prompt = QUESTION_GENERATION_PROMPT_TEMPLATE.format(
        history=history_str,
        request=request,
    )
    
    new_question = gen_llm.invoke(prompt).content
    print(f"Generated new question: {new_question}")
    return new_question

# --- Tool for HYBRID agent ---
@tool
def generate_hybrid_question(state: AgentState, request: str) -> str:
    """Use this tool to generate a new, curriculum-based interview question."""
    print("\n---GENERATING HYBRID QUESTION---")
    
    # Create a concise history for the tool prompt
    history_summary = []
    if state.get("feedback_report"):
        for report in state["feedback_report"]:
            history_summary.append(f"- Asked: '{report['question']}' -> Verdict: {report.get('verdict', 'N/A')}")
    history_str = "\n".join(history_summary) if history_summary else "No questions have been asked yet."
    
    # Format the static questions as the curriculum
    static_questions = state.get("interview_questions", [])
    curriculum = "\n".join([f"- {q['question']} (Covers: {q['expected_concepts']})" for q in static_questions])

    gen_llm = ChatGoogleGenerativeAI(
        model=os.getenv("CHAT_MODEL", "gemini-1.5-flash"),
        temperature=0.85 # Slightly higher temp for more creative, scenario-based questions
    )
    
    prompt = HYBRID_QUESTION_GENERATION_PROMPT_TEMPLATE.format(
        static_questions=curriculum,
        history=history_str,
        request=request,
    )
    
    new_question = gen_llm.invoke(prompt).content
    print(f"Generated new question: {new_question}")
    return new_question


# --- Tools for ALL agents ---
@tool
def evaluate_candidate_answer(user_answer: str, state: AgentState) -> str:
    """Use this tool to evaluate a candidate's answer to the most recent technical question."""
    print("\n---EVALUATING ANSWER---")
    interview_type = state.get("interview_type", "Static")
    
    eval_llm = ChatGoogleGenerativeAI(
        model=os.getenv("CHAT_MODEL", "gemini-1.5-flash"),
        temperature=0.0
    )
    
    if interview_type == "Static":
        q_number = state.get("question_number", 0)
        questions = state.get("interview_questions", [])
        if q_number >= len(questions):
            return "Evaluation failed: No active question."
        question_data = questions[q_number]
        prompt = STATIC_EVALUATION_PROMPT_TEMPLATE.format(
            question=question_data["question"],
            expected_concepts=question_data["expected_concepts"],
            user_answer=user_answer,
        )
    else: # Dynamic and Hybrid use the same evaluation logic
        current_question = state.get("current_question", "No question found.")
        prompt = DYNAMIC_EVALUATION_PROMPT_TEMPLATE.format(
            question=current_question,
            user_answer=user_answer,
        )

    evaluation = eval_llm.invoke(prompt).content
    print(f"Evaluation result: {evaluation}")
    return evaluation

@tool
def judge_interview_performance(state: AgentState) -> str:
    """Use this tool only at the very end of the interview to provide a final, holistic rating."""
    print("\n---JUDGING FINAL PERFORMANCE---")
    feedback_report = state.get("feedback_report", [])
    
    # Format the entire interview into a single transcript string
    transcript_parts = []
    for report_item in feedback_report:
        transcript_parts.append(f"Question: {report_item['question']}")
        transcript_parts.append(f"Candidate's Answer: {report_item['user_answer']}")
        transcript_parts.append(f"Evaluation: {report_item['evaluation']}\n")
    
    interview_transcript = "\n".join(transcript_parts)
    
    judging_llm = ChatGoogleGenerativeAI(
        model=os.getenv("CHAT_MODEL", "gemini-1.5-flash"),
        temperature=0.2
    )
    
    prompt = FINAL_JUDGING_PROMPT_TEMPLATE.format(interview_transcript=interview_transcript)
    
    final_judgment = judging_llm.invoke(prompt).content
    print(f"Final Judgment: {final_judgment}")
    return final_judgment

@tool
def conclude_interview(state: AgentState) -> str:
    """Use this tool to end the interview after all questions are asked and evaluated."""
    user_name = state.get("user_name", "Candidate")
    return f"Interview concluded for {user_name}."


# --- Agent Definition ---
def create_agent_graph(llm, checkpointer, interview_type: str):
    """Factory function to create the appropriate agent graph based on interview type."""
    
    if interview_type == "Static":
        tools = [ask_static_question, evaluate_candidate_answer, judge_interview_performance, conclude_interview]
        system_prompt = STATIC_SYSTEM_PROMPT
    elif interview_type == "Dynamic":
        tools = [generate_dynamic_question, evaluate_candidate_answer, judge_interview_performance, conclude_interview]
        system_prompt = DYNAMIC_SYSTEM_PROMPT
    elif interview_type == "Hybrid":
        tools = [generate_hybrid_question, evaluate_candidate_answer, judge_interview_performance, conclude_interview]
        system_prompt = HYBRID_SYSTEM_PROMPT
    else:
        raise ValueError(f"Unknown interview type: {interview_type}")

    agent = llm.bind_tools(tools)

    # --- Graph Nodes ---
    def agent_node(state: AgentState):
        print(f"\n---AGENT NODE ({interview_type})---")
        # Add the system prompt to the start of the message list for the LLM call
        messages_with_system_prompt = [SystemMessage(content=system_prompt)] + state["messages"]
        result = agent.invoke(messages_with_system_prompt)
        return {"messages": [result]}

    def tool_node(state: AgentState):
        print(f"\n---TOOL NODE ({interview_type})---")
        messages = state["messages"]
        last_message = messages[-1]
        
        tool_invocations = last_message.tool_calls
        tool_outputs = []
        new_feedback_reports = []
        q_number = state.get("question_number", 0)
        current_question = state.get("current_question", "")
        interview_finished = state.get("interview_finished", False)
        final_rating = state.get("final_rating")

        for call in tool_invocations:
            tool_name = call["name"]
            tool_input = {**call["args"], "state": state}
            
            # Route to the correct tool implementation
            if tool_name == "evaluate_candidate_answer":
                # Get the user's answer directly from the tool call arguments
                user_answer = call["args"].get("user_answer", "")
                result = evaluate_candidate_answer.invoke(tool_input)
                
                # Extract verdict for dynamic agent's context
                verdict = "N/A"
                if "Verdict: " in result:
                    verdict = result.split("Verdict: ")[-1].strip()
                
                question_to_log = current_question
                if interview_type == "Static":
                    question_to_log = state["interview_questions"][q_number]["question"]

                new_report_item = {"question": question_to_log, "user_answer": user_answer, "evaluation": result, "verdict": verdict}
                new_feedback_reports.append(new_report_item)
                q_number += 1
            elif tool_name in ["ask_static_question", "generate_dynamic_question", "generate_hybrid_question"]:
                if tool_name == "ask_static_question":
                    result = ask_static_question.invoke(tool_input)
                elif tool_name == "generate_dynamic_question":
                    result = generate_dynamic_question.invoke(tool_input)
                else: # generate_hybrid_question
                    result = generate_hybrid_question.invoke(tool_input)
                current_question = result # Store the new question
            elif tool_name == "judge_interview_performance":
                result = judge_interview_performance.invoke(tool_input)
                # Parse rating from the result
                match = re.search(r"Final Rating: (\d{1,2}/10)", result)
                if match:
                    final_rating = match.group(1)
            elif tool_name == "conclude_interview":
                result = conclude_interview.invoke(tool_input)
                interview_finished = True
            else:
                result = f"Unknown tool {tool_name} called."

            tool_outputs.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
            
        return {
            "messages": tool_outputs, 
            "question_number": q_number, 
            "feedback_report": new_feedback_reports,
            "interview_finished": interview_finished,
            "current_question": current_question,
            "final_rating": final_rating,
        }

    # --- Graph Routing ---
    def should_continue(state: AgentState):
        print("\n---ROUTING---")
        last_message = state["messages"][-1]
        
        # If the AI has just called a tool, the next step is to run the tool.
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            print("Decision: Call tools.")
            return "tools"
        
        # If the interview is finished, stop.
        if state.get("interview_finished", False):
            print("Decision: End interview now.")
            return END
            
        # If the last message was from a human, the agent should respond.
        if isinstance(last_message, HumanMessage):
            print("Decision: Agent to process human input.")
            return "interviewer"

        # If the last message was a tool output, the agent should process it.
        if isinstance(last_message, ToolMessage):
            print("Decision: Agent to process tool output.")
            return "interviewer"

        # Otherwise, the turn is over. Wait for the user's next input.
        print("Decision: End of current turn, waiting for user input.")
        return END

    # --- Assemble Graph ---
    graph = StateGraph(AgentState)
    graph.add_node("interviewer", agent_node)
    graph.add_node("tools", tool_node)
    
    graph.set_entry_point("interviewer")
    
    # The conditional edge now correctly handles all paths from the interviewer node
    graph.add_conditional_edges(
        "interviewer",
        should_continue,
        {
            "tools": "tools",
            "interviewer": "interviewer", # Added this path for HumanMessage/ToolMessage routing
            END: END
        }
    )
    # After tools are called, the flow always returns to the interviewer to process the tool output
    graph.add_edge("tools", "interviewer")
    
    return graph.compile(checkpointer=checkpointer)