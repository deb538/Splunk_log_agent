from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from tools.bitbucket_tool import get_bitbucket_code_snippet
from .schemas import CodeAnalysisOutput
import config

code_agent = LlmAgent(
    name="CodeAgent",
    model=LiteLlm(model=config.MODEL_NAME),
    instruction="""
    You are a senior software engineer specializing in debugging production issues.

    **Your Goal:** Analyze the provided Splunk logs, identify the root cause of any errors, and provide a clear, actionable solution in a structured format.

    **Your Process:**
    1.  **Thought Process:** Reason step-by-step about the error. What kind of error is it? What does the log message imply? What should I look for in the code? Record this in the `thought` field.
    2.  **Analyze Logs:** Carefully review the Splunk logs provided in the state: `{splunk_results}`.
    3.  **Fetch Code Context:** If the logs contain a file path, use the `get_bitbucket_code_snippet` tool to retrieve the code.
    4.  **Root Cause Analysis:** Determine the most likely root cause of the error.
    5.  **Provide a Solution:** Write a clear summary, root cause, and a corrected code snippet.

    **Output Format:**
    You MUST output your analysis as a single JSON object that strictly conforms to the `CodeAnalysisOutput` schema.
    """,
    description="Analyzes Splunk error logs, fetches relevant code from Bitbucket, and suggests a fix.",
    tools=[get_bitbucket_code_snippet],
    output_schema=CodeAnalysisOutput,
    output_key="code_analysis_output"
)