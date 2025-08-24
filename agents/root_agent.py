from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai.types import Content, Part
from typing import AsyncGenerator

from .schemas import PlanOutput
from .planner_agent import planner_agent
from .splunk_analyzer_agent import splunk_analyzer_agent
from .code_agent import code_agent
from .visualization_agent import visualization_agent
from .summarizer_agent import summarizer_agent

class RootOrchestrator(BaseAgent):
    """A custom agent that orchestrates workflows based on user intent."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        print("--- Orchestrator: Starting workflow ---")

        print("--- Orchestrator: Calling Planner Agent ---")
        async for event in planner_agent.run_async(ctx):
            yield event

        # The ADK automatically parses the LLM's JSON into the Pydantic object
        plan: PlanOutput | None = ctx.session.state.get('plan')

        if not plan or not isinstance(plan, PlanOutput):
            print("--- Orchestrator: ERROR - Plan is missing or not a valid PlanOutput object. ---")
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text="I had trouble creating a plan for your request. Could you please rephrase?")]),
                is_final_response=True
            )
            return

        print(f"--- Orchestrator: Planner Thought: {plan.thought} ---")

        if plan.status == "CLARIFICATION_NEEDED":
            print(f"--- Orchestrator: Pausing workflow for user clarification. ---")
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=plan.clarification_question)]),
                is_final_response=True
            )
            return

        print(f"--- Orchestrator: Planner identified intents: {plan.user_intents} ---")
        
        print("--- Orchestrator: Calling Splunk Analyzer Agent ---")
        async for event in splunk_analyzer_agent.run_async(ctx):
            yield event
        
        for intent in plan.user_intents:
            if intent == 'code_analysis':
                print("--- Orchestrator: Calling Code Agent ---")
                async for event in code_agent.run_async(ctx):
                    yield event
            
            elif intent == 'visualization':
                print("--- Orchestrator: Calling Visualization Agent ---")
                async for event in visualization_agent.run_async(ctx):
                    yield event
        
        print("--- Orchestrator: Calling Summarizer Agent ---")
        async for event in summarizer_agent.run_async(ctx):
            yield event
        
        print("--- Orchestrator: Workflow complete ---")

root_orchestrator_agent = RootOrchestrator(
    name="RootOrchestrator",
    description="The main orchestrator that runs dynamic workflows with HITL."
)
