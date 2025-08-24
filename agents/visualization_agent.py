from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .schemas import VisualizationOutput
import config

visualization_agent = LlmAgent(
    name="VisualizationAgent",
    model=LiteLlm(model=config.MODEL_NAME),
    instruction="""
    You are a data visualization expert for a web application that uses Chart.js.

    **Your Task:**
    1.  **Thought Process:** Reason about the best way to visualize the data based on the user's query and the data's structure. Record this in the `thought` field.
    2.  **Analyze Data:** Review the user's query and the Splunk data: `{splunk_results}`.
    3.  **Determine Chart Type:** Choose the most effective chart type (`line`, `bar`, `pie`, `doughnut`).
    4.  **Format Data:** Transform the raw Splunk data into the specific JSON format required by Chart.js.

    **Output Format:**
    You MUST output ONLY the final JSON object conforming to the `VisualizationOutput` schema.
    """,
    description="Generates Chart.js JSON configuration from Splunk data to create visualizations.",
    output_schema=VisualizationOutput,
    output_key="visualization_output"
)