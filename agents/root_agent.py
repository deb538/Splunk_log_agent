from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai.types import Content, Part
from typing import AsyncGenerator
import logging

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
        logging.info("Orchestrator: Starting workflow...")

        try:
            logging.info("Orchestrator: Calling Planner Agent...")
            async for event in planner_agent.run_async(ctx):
                yield event
        except Exception as e:
            logging.error(f"Orchestrator: Planner Agent failed: {e}")
            yield Event(author=self.name, content=Content(parts=[Part(text="I'm having trouble planning my next steps. Please try rephrasing your request.")]), is_final_response=True)
            return

        plan: PlanOutput | None = ctx.session.state.get('plan')

        if not plan or not isinstance(plan, PlanOutput):
            logging.error("Orchestrator: Plan is missing or not a valid PlanOutput object.")
            yield Event(author=self.name, content=Content(parts=[Part(text="I had trouble creating a plan for your request. Could you please rephrase?")]), is_final_response=True)
            return

        logging.info(f"Orchestrator: Planner Thought: {plan.thought}")

        if plan.status == "CLARIFICATION_NEEDED":
            logging.info("Orchestrator: Pausing workflow for user clarification.")
            yield Event(author=self.name, content=Content(parts=[Part(text=plan.clarification_question)]), is_final_response=True)
            return

        logging.info(f"Orchestrator: Planner identified intents: {plan.user_intents}")
        
        try:
            logging.info("Orchestrator: Calling Splunk Analyzer Agent...")
            async for event in splunk_analyzer_agent.run_async(ctx):
                yield event
        except Exception as e:
            logging.error(f"Orchestrator: Splunk Analyzer Agent failed: {e}")
            yield Event(author=self.name, content=Content(parts=[Part(text="I was unable to retrieve data from Splunk. Please check the connection or your query.")]), is_final_response=True)
            return
        
        for intent in plan.user_intents:
            try:
                if intent == 'code_analysis':
                    logging.info("Orchestrator: Calling Code Agent...")
                    async for event in code_agent.run_async(ctx):
                        yield event
                
                elif intent == 'visualization':
                    logging.info("Orchestrator: Calling Visualization Agent...")
                    async for event in visualization_agent.run_async(ctx):
                        yield event
            except Exception as e:
                logging.error(f"Orchestrator: Agent for intent '{intent}' failed: {e}")
                yield Event(author=self.name, content=Content(parts=[Part(text=f"I encountered an error during the {intent} step.")]), is_final_response=True)
                return
        
        logging.info("Orchestrator: Calling Summarizer Agent...")
        async for event in summarizer_agent.run_async(ctx):
            yield event
        
        logging.info("Orchestrator: Workflow complete.")

root_orchestrator_agent = RootOrchestrator(
    name="RootOrchestrator",
    description="The main orchestrator that runs dynamic workflows with HITL."
)