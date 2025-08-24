This project uses a dynamic, multi-agent architecture orchestrated by a custom RootOrchestrator. This design is more efficient than a static pipeline as it only runs the necessary agents for a given task.

The flow of information is as follows:

User Query (app.py): The FastAPI server receives the user's request.

RootOrchestrator: This is the central "brain." It receives the query and begins the workflow. Its first and most important step is to call the PlannerAgent.

PlannerAgent: This agent analyzes the user's natural language to determine their intent and constructs the necessary Splunk (SPL) queries. It outputs a structured Pydantic object (defined in agents/schemas.py) which is saved to the session state.

If the query is ambiguous, the planner's status will be CLARIFICATION_NEEDED, and the orchestrator will pause and ask the user for more information (Human-in-the-Loop).

Specialist Agents: The RootOrchestrator reads the user_intents from the plan in the session state and calls the required specialist agents in a logical sequence:

SplunkAnalyzer (Always runs first): Executes the SPL queries from the plan and saves the raw log data to the session state.

CodeAgent / VisualizationAgent (Run conditionally): If the intent was code_analysis or visualization, the corresponding agent runs, reads the Splunk data from the session state, performs its task, and writes its structured Pydantic output back to the session state.

SummarizerAgent: This is the final agent in the workflow. It reads all the results from the session state and synthesizes a single, comprehensive response for the user.

Streaming Response (app.py): Throughout this entire process, events from each agent are streamed back to the user, providing a real-time view of the agent's progress.

Data Communication: Agents do not talk to each other directly. They communicate asynchronously by reading from and writing to a shared session.state dictionary, which acts as a central scratchpad for the duration of the user's request.

Example User Scenarios
To make the data flow clear, here are a few examples of how the system handles different requests.

Scenario 1: Simple Summary Query

User Query: "How many 404 errors did we have yesterday?"

PlannerAgent runs: Writes plan to session.state with user_intents: ["summary"] and the correct SPL query.

SplunkAnalyzer runs: Executes the query and writes the results (e.g., [{"count": 78}]) to session.state['splunk_results'].

SummarizerAgent runs: Reads plan and splunk_results from state and generates the final answer: "There were 78 404 errors yesterday."

Scenario 2: Multi-Intent Query

User Query: "Find the root cause of the NullPointerExceptions and show me a chart of them by host."

PlannerAgent runs: Writes plan to session.state with user_intents: ["code_analysis", "visualization"] and two SPL queries.

SplunkAnalyzer runs: Executes both queries and writes the combined results to session.state['splunk_results'].

CodeAgent runs: Reads splunk_results, calls the Bitbucket tool, and writes its findings to session.state['code_analysis_output'].

VisualizationAgent runs: Reads splunk_results and writes Chart.js JSON to session.state['visualization_output'].

SummarizerAgent runs: Reads all the data from the state and combines the code analysis report with a message that a chart has been generated.

Scenario 3: Ambiguous Query (Human-in-the-Loop)

User Query: "Check the logs."

PlannerAgent runs: Cannot determine a clear intent. It writes a plan to session.state with status: "CLARIFICATION_NEEDED" and a clarification_question.

RootOrchestrator detects the status, stops the workflow, and sends the clarification_question back to the user. The agent now waits.

User Responds: "Show me a summary of errors."

Workflow Restarts: The new query is sent. The PlannerAgent now has enough context to create a successful plan, and the flow continues like Scenario 1.