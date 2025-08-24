from pydantic import BaseModel, Field
from typing import List, Literal

class PlanOutput(BaseModel):
    """The structured output from the PlannerAgent."""
    thought: str = Field(description="The reasoning process for determining the status, intents, and queries.")
    status: Literal["SUCCESS", "CLARIFICATION_NEEDED"] = Field(description="The status of the planning phase.")
    user_intents: List[Literal["summary", "visualization", "code_analysis"]] = Field(description="A list of all identified user intents.")
    splunk_queries: List[str] = Field(description="A list of all necessary SPL queries.")
    clarification_question: str = Field(description="A question to ask the user if the intent is unclear.", default="")