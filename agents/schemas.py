from pydantic import BaseModel, Field
from typing import List, Literal, Dict, Any

class PlanOutput(BaseModel):
    """The structured output from the PlannerAgent."""
    thought: str = Field(description="The reasoning process for determining the status, intents, and queries.")
    status: Literal["SUCCESS", "CLARIFICATION_NEEDED"] = Field(description="The status of the planning phase.")
    user_intents: List[Literal["summary", "visualization", "code_analysis"]] = Field(description="A list of all identified user intents.")
    splunk_queries: List[str] = Field(description="A list of all necessary SPL queries.")
    clarification_question: str = Field(description="A question to ask the user if the intent is unclear.", default="")

class CodeAnalysisOutput(BaseModel):
    """The structured output from the CodeAgent."""
    thought: str = Field(description="The reasoning process for analyzing the code and logs.")
    summary: str = Field(description="A brief summary of the error.")
    root_cause: str = Field(description="A detailed explanation of the root cause.")
    suggested_fix: str = Field(description="A corrected code snippet and an explanation of the fix.")

class VisualizationOutput(BaseModel):
    """The structured output from the VisualizationAgent, conforming to Chart.js format."""
    thought: str = Field(description="The reasoning process for choosing the chart type and structuring the data.")
    chart_type: Literal["line", "bar", "pie", "doughnut"] = Field(description="The type of chart to be rendered.")
    data: Dict[str, Any] = Field(description="The data object for Chart.js, including labels and datasets.")
