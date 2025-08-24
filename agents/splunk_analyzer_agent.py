from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from tools.splunk_tool import splunk_search

CLAUDE_SONNET_BEDROCK = "bedrock/anthropic.claude-3-sonnet-20240229-v1:0"

splunk_analyzer_agent = LlmAgent(
    name="SplunkAnalyzer",
    model=LiteLlm(model=CLAUDE_SONNET_BEDROCK),
    instruction="""
    You are an automated Splunk search executor. Your job is to run all the queries provided by the planner.
    1. Read the plan object from the session state: {plan}
    2. Extract the list of queries from the `splunk_queries` key. For example, the plan might look like: {{"thought": "...", "status":"SUCCESS", "user_intents":["summary"], "splunk_queries":["index=web status=404"], "clarification_question":""}}
    3. Iterate through each query in the list.
    4. For each query, execute it using the `splunk_search` tool.
    5. Aggregate the results from all searches into a single, final JSON array.
    6. Output ONLY this combined JSON array.
    """,
    description="Executes one or more Splunk queries from the planner's output and returns the raw log data.",
    tools=[splunk_search],
    output_key="splunk_results"
)