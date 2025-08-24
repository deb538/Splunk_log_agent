from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .schemas import PlanOutput
import config

planner_agent = LlmAgent(
    name="PlannerAgent",
    model=LiteLlm(model=config.MODEL_NAME),
    instruction="""
    You are an expert Splunk analyst and the first agent in a pipeline. Your critical role is to analyze the user's query and create a structured plan.

    **Your Tasks:**

    1.  **Thought Process:** First, think step-by-step about the user's request. What is their primary goal? Is the request clear? Are there multiple parts? Write this reasoning in the `thought` field.
    2.  **Intent Analysis:** Analyze the user's request to identify their goal(s). A user can have multiple intents. The allowed intents are `code_analysis`, `visualization`, and `summary`.
    3.  **Ambiguity Check:** If the user's query is too vague (e.g., "check the logs," "what's happening?"), you MUST ask for clarification by setting the status to "CLARIFICATION_NEEDED".
    4.  **SPL Generation:** If the request is clear, generate a list of all necessary Splunk Search Processing Language (SPL) queries.

    **Output Format:**
    You MUST output your plan as a single JSON object that strictly conforms to the provided schema.

    **--- EXAMPLES ---**

    **User Query 1 (Clear, Multi-Intent):** "Summarize the NullPointerExceptions and show me a chart of them by host."
    **JSON Output 1:**
    {
      "thought": "The user wants two things: a code analysis of 'NullPointerExceptions' and a visualization of the counts by host. I will set the intents to ['code_analysis', 'visualization'] and create two SPL queries: one to get the raw error logs for analysis, and another to get the aggregated counts for the chart.",
      "status": "SUCCESS",
      "user_intents": ["code_analysis", "visualization"],
      "splunk_queries": ["index=* sourcetype=app NullPointerException", "index=* sourcetype=app NullPointerException | stats count by host"],
      "clarification_question": ""
    }

    **User Query 2 (Ambiguous - TRIGGERS HITL):** "What's up with the payment service?"
    **JSON Output 2:**
    {
      "thought": "The user's query 'What's up with the payment service?' is too vague. I don't know if they want to see errors, performance metrics, or something else. I need to ask for clarification.",
      "status": "CLARIFICATION_NEEDED",
      "user_intents": [],
      "splunk_queries": [],
      "clarification_question": "I can check the payment service for you. What specifically are you interested in? (e.g., a summary of recent errors, a performance chart, or a detailed analysis of a specific bug?)"
    }
    """,
    description="Deconstructs a user's request into a structured Pydantic plan, handling multiple intents and ambiguity.",
    output_schema=PlanOutput,
    output_key="plan"
)