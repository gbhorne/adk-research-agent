# Architecture Decision Records

## ADR-1: ADK for Agent Framework
**Decision:** Google ADK over LangGraph or CrewAI
**Reason:** Native GCP integration, Gemini-optimized, consistent with portfolio projects 3-5. ADK provides ParallelAgent and SequentialAgent primitives out of the box.

## ADR-2: AI Studio over Vertex AI
**Decision:** Use Gemini via AI Studio free tier
**Reason:** Sandbox blocks aiplatform.googleapis.com. AI Studio provides identical model access at zero cost.

## ADR-3: SequentialAgent Root with ParallelAgent + Synthesizer
**Decision:** Use SequentialAgent as root, containing a ParallelAgent (Step 1) and a synthesizer LlmAgent (Step 2)
**Reason:** Initial attempt used an LlmAgent as root with the ParallelAgent as a sub-agent. The parallel results streamed through to the user as individual messages, but the orchestrator never regained control to synthesize them. SequentialAgent guarantees ordering: all parallel data is gathered first, then the synthesizer runs to produce one unified brief. This separates concurrency (ParallelAgent), ordering (SequentialAgent), and intelligence (LlmAgent).

## ADR-4: ParallelAgent for Concurrent Research
**Decision:** Use ParallelAgent to run 3 analyst agents simultaneously
**Reason:** Research benefits from breadth — multiple perspectives on one question, not routing to one specialist. ParallelAgent runs all sub-agents concurrently, reducing wall-clock time. This is a distinct pattern from the transfer_to_agent routing used in the Retail Agents project.

## ADR-5: Google Search Grounding for External Data
**Decision:** Use Gemini's built-in Google Search grounding via `google.adk.tools.google_search`
**Reason:** Sandbox-safe, zero configuration. Gemini handles search query generation, retrieval, and citation automatically. Initial attempt using `types.Tool(google_search=GoogleSearch())` failed Pydantic validation in ADK 1.25.1 — the ADK-native `google_search` tool is the correct approach.

## ADR-6: Fixed SQL over Text-to-SQL
**Decision:** Parameterized fixed SQL queries in tool functions
**Reason:** Consistent with portfolio convention. Reliability, security, and cost control. The NL2SQL project (Project 4) already demonstrates dynamic SQL generation.

## ADR-7: Separated Internal vs. Trend Analysts
**Decision:** Split BigQuery tools across two agents instead of one
**Reason:** Enables true parallel execution — internal analyst pulls current snapshot while trend analyst pulls historical patterns simultaneously. Provides cleaner instructions and focused context. Each agent writes to its own output_key for clean state separation.

## ADR-8: output_key for State-Based Data Passing
**Decision:** Use output_key on each sub-agent to store results in session state
**Reason:** The synthesizer needs structured access to each analyst's findings. output_key stores each agent's output in state (e.g., state["internal_data"]), which the synthesizer references by key. Without this, parallel results would only be in conversation history, making synthesis unreliable.

## ADR-9: Synthetic Data with Realistic Patterns
**Decision:** Generate synthetic data with built-in seasonality, growth trends, and regional variation
**Reason:** Fresh sandbox project with no existing data. Synthetic data provides ground truth for validation — known patterns (8% electronics growth, 12% home/garden growth, West leads electronics) can be verified in agent outputs. Deterministic seed (42) ensures reproducibility across runs.
