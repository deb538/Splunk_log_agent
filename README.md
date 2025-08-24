Architecture Deep Dive: The Agent Workflow
This project uses a dynamic, multi-agent architecture orchestrated by a custom RootOrchestrator. This design is more efficient than a static pipeline as it only runs the necessary agents for a given task.

The flow of information is as follows:

User Query (app.py): The FastAPI server receives the user's request.

RootOrchestrator: This is the central "brain." It receives the query and begins the workflow. Its first and most important step is to call the PlannerAgent.

PlannerAgent: This agent analyzes the user's natural language to determine their intent and constructs the necessary Splunk (SPL) queries. It outputs a structured Pydantic object (defined in agents/schemas.py) which is saved to the session state.

If the query is ambiguous, the planner's status will be CLARIFICATION_NEEDED, and the orchestrator will pause and ask the user for more information (Human-in-the-Loop).

Specialist Agents: The RootOrchestrator reads the user_intents from the plan in the session state and calls the required specialist agents in a logical sequence:

SplunkAnalyzer (Always runs first): Executes the SPL queries from the plan and saves the raw log data to the session state.

CodeAgent / VisualizationAgent (Run conditionally): If the intent was code_analysis or visualization, the corresponding agent runs, reads the Splunk data from the session state, performs its task, and writes its output back to the session state.

SummarizerAgent: This is the final agent in the workflow. It reads all the results from the session state (the plan, the Splunk data, and any analysis reports) and synthesizes a single, comprehensive response for the user.

Streaming Response (app.py): Throughout this entire process, events from each agent are streamed back to the user, providing a real-time view of the agent's progress.

Data Communication: Agents do not talk to each other directly. They communicate asynchronously by reading from and writing to a shared session.state dictionary, which acts as a central scratchpad for the duration of the user's request.