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
    interview_questions: List[dict]
    question_number: int
    feedback_report: Annotated[List[dict], operator.add]
    interview_finished: bool
    interview_type: str
    current_question: str
    final_rating: Optional[str]
    # --- ADDED: Field for number of questions ---
    num_questions_to_ask: Optional[int]


# --- Tools (No changes needed to tools themselves) ---
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

@tool
def generate_dynamic_question(state: AgentState, request: str) -> str:
    """Use this tool to generate a new, adaptive interview question based on the conversation history."""
    print("\n---GENERATING DYNAMIC QUESTION---")
    history_summary = [f"- Asked: '{r['question']}' -> Verdict: {r.get('verdict', 'N/A')}" for r in state.get("feedback_report", [])]
    history_str = "\n".join(history_summary) if history_summary else "No questions have been asked yet."
    gen_llm = ChatGoogleGenerativeAI(model=os.getenv("CHAT_MODEL", "gemini-2.0-flash"), temperature=0.8)
    prompt = QUESTION_GENERATION_PROMPT_TEMPLATE.format(history=history_str, request=request)
    new_question = gen_llm.invoke(prompt).content
    print(f"Generated new question: {new_question}")
    return new_question

@tool
def generate_hybrid_question(state: AgentState, request: str) -> str:
    """Use this tool to generate a new, curriculum-based interview question."""
    print("\n---GENERATING HYBRID QUESTION---")
    history_summary = [f"- Asked: '{r['question']}' -> Verdict: {r.get('verdict', 'N/A')}" for r in state.get("feedback_report", [])]
    history_str = "\n".join(history_summary) if history_summary else "No questions have been asked yet."
    static_questions = state.get("interview_questions", [])
    curriculum = "\n".join([f"- {q['question']} (Covers: {q['expected_concepts']})" for q in static_questions])
    gen_llm = ChatGoogleGenerativeAI(model=os.getenv("CHAT_MODEL", "gemini-2.0-flash"), temperature=0.85)
    prompt = HYBRID_QUESTION_GENERATION_PROMPT_TEMPLATE.format(static_questions=curriculum, history=history_str, request=request)
    new_question = gen_llm.invoke(prompt).content
    print(f"Generated new question: {new_question}")
    return new_question

@tool
def evaluate_candidate_answer(user_answer: str, state: AgentState) -> str:
    """Use this tool to evaluate a candidate's answer to the most recent technical question."""
    print("\n---EVALUATING ANSWER---")
    interview_type = state.get("interview_type", "Static")
    eval_llm = ChatGoogleGenerativeAI(model=os.getenv("CHAT_MODEL", "gemini-2.0-flash"), temperature=0.0)
    if interview_type == "Static":
        q_number = state.get("question_number", 0)
        questions = state.get("interview_questions", [])
        if q_number >= len(questions): return "Evaluation failed: No active question."
        question_data = questions[q_number]
        prompt = STATIC_EVALUATION_PROMPT_TEMPLATE.format(question=question_data["question"], expected_concepts=question_data["expected_concepts"], user_answer=user_answer)
    else:
        current_question = state.get("current_question", "No question found.")
        prompt = DYNAMIC_EVALUATION_PROMPT_TEMPLATE.format(question=current_question, user_answer=user_answer)
    evaluation = eval_llm.invoke(prompt).content
    print(f"Evaluation result: {evaluation}")
    return evaluation

@tool
def judge_interview_performance(state: AgentState) -> str:
    """Use this tool only at the very end of the interview to provide a final, holistic rating."""
    print("\n---JUDGING FINAL PERFORMANCE---")
    feedback_report = state.get("feedback_report", [])
    transcript_parts = [f"Question: {r['question']}\nCandidate's Answer: {r['user_answer']}\nEvaluation: {r['evaluation']}\n" for r in feedback_report]
    interview_transcript = "\n".join(transcript_parts)
    judging_llm = ChatGoogleGenerativeAI(model=os.getenv("CHAT_MODEL", "gemini-2.0-flash"), temperature=0.2)
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
        system_prompt_template = STATIC_SYSTEM_PROMPT
    elif interview_type == "Dynamic":
        tools = [generate_dynamic_question, evaluate_candidate_answer, judge_interview_performance, conclude_interview]
        system_prompt_template = DYNAMIC_SYSTEM_PROMPT
    elif interview_type == "Hybrid":
        tools = [generate_hybrid_question, evaluate_candidate_answer, judge_interview_performance, conclude_interview]
        system_prompt_template = HYBRID_SYSTEM_PROMPT
    else:
        raise ValueError(f"Unknown interview type: {interview_type}")

    agent = llm.bind_tools(tools)

    def agent_node(state: AgentState):
        print(f"\n---AGENT NODE ({interview_type})---")
        # --- MODIFIED: Format the system prompt with the number of questions ---
        num_questions = state.get("num_questions_to_ask", 5) # Default to 5 if not set
        system_prompt = system_prompt_template.format(num_questions=num_questions)
        
        messages_with_system_prompt = [SystemMessage(content=system_prompt)] + state["messages"]
        result = agent.invoke(messages_with_system_prompt)
        return {"messages": [result]}

    def tool_node(state: AgentState):
        print(f"\n---TOOL NODE ({interview_type})---")
        # (No changes to the logic inside tool_node, it remains the same)
        messages = state["messages"]
        last_message = messages[-1]
        tool_invocations = last_message.tool_calls
        tool_outputs, new_feedback_reports = [], []
        q_number = state.get("question_number", 0)
        current_question = state.get("current_question", "")
        interview_finished = state.get("interview_finished", False)
        final_rating = state.get("final_rating")

        for call in tool_invocations:
            tool_name, tool_input = call["name"], {**call["args"], "state": state}
            if tool_name == "evaluate_candidate_answer":
                user_answer = call["args"].get("user_answer", "")
                result = evaluate_candidate_answer.invoke(tool_input)
                verdict = result.split("Verdict: ")[-1].strip() if "Verdict: " in result else "N/A"
                question_to_log = current_question if interview_type != "Static" else state["interview_questions"][q_number]["question"]
                new_feedback_reports.append({"question": question_to_log, "user_answer": user_answer, "evaluation": result, "verdict": verdict})
                q_number += 1
            elif tool_name in ["ask_static_question", "generate_dynamic_question", "generate_hybrid_question"]:
                result = globals()[tool_name].invoke(tool_input)
                current_question = result
            elif tool_name == "judge_interview_performance":
                result = judge_interview_performance.invoke(tool_input)
                match = re.search(r"Final Rating: (\d{1,2}/10)", result)
                if match: final_rating = match.group(1)
            elif tool_name == "conclude_interview":
                result = conclude_interview.invoke(tool_input)
                interview_finished = True
            else: result = f"Unknown tool {tool_name} called."
            tool_outputs.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
            
        return {"messages": tool_outputs, "question_number": q_number, "feedback_report": new_feedback_reports, "interview_finished": interview_finished, "current_question": current_question, "final_rating": final_rating}

    def should_continue(state: AgentState):
        # (No changes to routing logic)
        print("\n---ROUTING---")
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls: return "tools"
        if state.get("interview_finished", False): return END
        if isinstance(last_message, (HumanMessage, ToolMessage)): return "interviewer"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("interviewer", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("interviewer")
    graph.add_conditional_edges("interviewer", should_continue, {"tools": "tools", "interviewer": "interviewer", END: END})
    graph.add_edge("tools", "interviewer")
    return graph.compile(checkpointer=checkpointer)
