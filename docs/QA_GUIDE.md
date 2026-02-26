# QA Guide — ADK Research Agent

## In-Depth Questions and Answers (12 Parts)

---

## Part 1: Architecture Decisions

**Q: Why did you choose a SequentialAgent as the root instead of an LlmAgent?**

A: This was a key discovery during the build. We initially tried an LlmAgent as the root orchestrator with the ParallelAgent as a sub-agent. The problem was that in ADK 1.25.1, when an LlmAgent delegates to a ParallelAgent via `sub_agents`, the parallel results flow through to the user as individual messages but the orchestrator never gets a turn to synthesize them. The user sees 3 separate reports instead of one merged brief.

The fix was a SequentialAgent root that runs two steps in order:
1. `research_team` (ParallelAgent) — gathers all data concurrently
2. `synthesizer` (LlmAgent) — reads the stored results and produces one unified brief

This is a cleaner separation of concerns: the ParallelAgent handles concurrency, the SequentialAgent handles ordering, and the synthesizer handles intelligence.

**Q: Why use a ParallelAgent instead of transfer_to_agent routing like in the Retail Agents project?**

A: Different problems require different patterns. The Retail Agents project uses `transfer_to_agent` because each query needs exactly ONE specialist — a sales question goes to the sales analyst, not the inventory analyst. That's a routing problem.

Research is a breadth problem. When someone asks "How are electronics performing?", you want ALL perspectives simultaneously: internal metrics, external market context, and historical trends. Running them sequentially would triple the latency with no benefit. ParallelAgent runs all 3 concurrently, cutting wall-clock time significantly.

**Q: Why separate the BigQuery tools across two agents (internal_data_analyst and trend_analyst) instead of putting all 6 in one agent?**

A: Three reasons:

1. **Parallel execution**: If all 6 tools were in one agent, that agent would call them sequentially. By splitting them across two agents inside a ParallelAgent, the internal tools and trend tools execute concurrently.

2. **Focused context**: Each agent has a specific instruction about its role. The internal analyst focuses on current snapshot metrics. The trend analyst focuses on patterns over time. This produces better tool selection and more focused outputs.

3. **output_key isolation**: Each agent writes to its own state key (`internal_data` vs `trend_analysis`), making it easy for the synthesizer to reference each perspective separately.

**Q: Why use output_key on the sub-agents?**

A: The `output_key` parameter stores each agent's final output in the session state dictionary under the specified key. When `internal_data_analyst` finishes, its output goes to `state["internal_data"]`. The `synthesizer` agent can then reference these state keys in its instruction to understand what each analyst found.

Without `output_key`, the parallel results would be in the conversation history but not easily addressable by the synthesizer. The state-based approach gives the synthesizer structured access to each analyst's findings.

---

## Part 2: Google Search Grounding

**Q: How does Google Search grounding work in ADK?**

A: Google Search grounding is a built-in Gemini capability where the model automatically searches Google when it needs external information to answer a query. In ADK 1.25.1, you enable it by importing `google_search` from `google.adk.tools` and passing it as a tool to the agent:

```python
from google.adk.tools import google_search

market_research_analyst = LlmAgent(
    name="market_research_analyst",
    model=MODEL,
    tools=[google_search],
)
```

Unlike custom tool functions where you write the logic, `google_search` is an ADK-provided tool. Gemini decides when to search, generates the search queries, retrieves results, and integrates them into its response with source citations. You have no control over the specific search queries — Gemini handles everything.

**Q: Why google_search from google.adk.tools instead of types.Tool(google_search=GoogleSearch())?**

A: This was a compatibility issue we discovered during the build. The initial approach used:

```python
from google.genai import types
SEARCH_GROUNDING = types.Tool(google_search=types.GoogleSearch())
```

This is valid for the google-genai SDK when calling the API directly, but ADK 1.25.1's `LlmAgent.tools` parameter expects items that are either callable functions, `BaseTool` instances, or `BaseToolset` instances. `types.Tool` is none of these, so Pydantic validation rejected it.

The correct ADK approach is `from google.adk.tools import google_search`, which provides a properly wrapped tool object that ADK can handle.

**Q: What happens if the Google Search grounding fails (e.g., DNS resolution error)?**

A: During testing, we encountered `httpx.ConnectError: [Errno -3] Temporary failure in name resolution` when the market research agent's Gemini API call failed due to Cloud Shell DNS issues. Because the ParallelAgent uses `asyncio.TaskGroup`, a failure in any sub-agent crashes the entire parallel group.

In our case, retrying with a new session resolved the transient DNS issue. For a production system, you'd want to add error handling — either a `before_agent_callback` that catches network errors, or a wrapper that provides a fallback response when the market research agent fails.

---

## Part 3: BigQuery Tools

**Q: Why use fixed SQL instead of text-to-SQL for the BigQuery tools?**

A: This is a consistent decision across all portfolio projects (documented as ADR-5 in every project). Fixed SQL provides:

- **Reliability**: The SQL is tested and verified. Text-to-SQL can generate invalid queries.
- **Security**: Parameterized queries prevent SQL injection. Text-to-SQL could potentially be manipulated.
- **Cost control**: Fixed queries have predictable BigQuery costs. Dynamic SQL could scan entire tables.
- **Speed**: No LLM call needed to generate SQL — the tool goes straight to BigQuery.

The NL2SQL Agent (Project 4) already demonstrates dynamic SQL generation, so this project intentionally uses fixed SQL to show the reliable production pattern.

**Q: Why use parameterized queries (@category) instead of f-strings for user input?**

A: SQL injection prevention. If a user asks about a category and the agent passes the input directly into an f-string, a malicious input could alter the query. BigQuery's `@parameter` syntax ensures user input is always treated as a value, never as SQL.

```python
# WRONG — SQL injection risk
query = f"SELECT * FROM table WHERE category = '{category}'"

# CORRECT — parameterized query
query = "SELECT * FROM table WHERE category = @category"
job_config = bigquery.QueryJobConfig(
    query_parameters=[
        bigquery.ScalarQueryParameter("category", "STRING", category)
    ]
)
```

**Q: Why does get_category_performance convert dates with isoformat()?**

A: BigQuery returns `datetime.date` objects for DATE columns. When Gemini receives tool results, it needs JSON-serializable data. `datetime.date` objects aren't JSON-serializable, so the tool converts them to ISO format strings (e.g., "2024-12-31"). We encountered this same issue in the Anomaly Detection project and applied the same fix here.

---

## Part 4: Synthetic Data Design

**Q: Why generate synthetic data instead of using the existing retail_gold dataset from Project 1?**

A: This build was done in a fresh GCP sandbox project with no existing data. The sandbox environments are ephemeral — each new sandbox gets a clean project. Rather than depending on a previous project's data, the data generator creates everything from scratch, making the project fully self-contained and reproducible.

**Q: What patterns are built into the synthetic data and why?**

A: The data has several intentional patterns that make the agent's analysis interesting:

1. **Category growth rates**: Electronics grows at 8% annually, Home and Garden at 12%, Grocery at 2%. This means the YoY comparison tool returns meaningfully different growth rates across categories — not random noise.

2. **Seasonality**: Three patterns — holiday (Q4 spike for Electronics/Grocery), summer (May-Aug for Sports/Home & Garden), bimodal (spring + fall for Clothing). The monthly trend tool captures these patterns clearly.

3. **Regional variation**: The West is strong in Electronics (1.4x multiplier), the Southeast in Home and Garden (1.3x). When the agent asks "which region is best for electronics?", there's a real answer backed by the data.

4. **Product variation**: Each product gets a deterministic weight from its name hash. Portable Charger consistently outsells Bluetooth Speaker. The top products tool returns a realistic product mix, not random ordering.

5. **Random noise (±20%)**: Without noise, every pattern would be perfectly smooth and unrealistic. The noise creates natural variation that makes the data look real.

**Q: Why use np.random.seed(42)?**

A: Reproducibility. With a fixed seed, the data generator produces identical output every time it runs. This matters for verification — the verification script checks for specific row counts and data characteristics that depend on deterministic generation. If the data were random each time, the verification checks would need to be much looser.

---

## Part 5: Agent Configuration

**Q: What model is used and why?**

A: Gemini 2.5 Flash via AI Studio free tier. Flash is chosen for speed (lower latency than Pro) and cost (free tier). Since we're running 3 agents in parallel plus a synthesizer, we make 4+ LLM calls per query. Flash keeps the total response time reasonable.

AI Studio is used instead of Vertex AI because the sandbox blocks `aiplatform.googleapis.com`. Setting `GOOGLE_GENAI_USE_VERTEXAI=FALSE` tells ADK to route through AI Studio instead.

**Q: How does the synthesizer know what the other agents found?**

A: Through the `output_key` mechanism. Each sub-agent in the ParallelAgent has an `output_key` parameter:

- `internal_data_analyst` → `output_key="internal_data"`
- `market_research_analyst` → `output_key="market_research"`
- `trend_analyst` → `output_key="trend_analysis"`

When each agent completes, ADK stores its final text output in the session state under the specified key. The synthesizer's instruction references these keys:

```
- state["internal_data"]: Current performance metrics from BigQuery
- state["market_research"]: External market context from web search
- state["trend_analysis"]: Historical trends and patterns
```

The synthesizer reads these state values and merges them into one cohesive brief.

---

## Part 6: Build Issues and Fixes

**Q: What was the types.Tool validation error and how was it fixed?**

A: When we first created agent.py, the market research agent used:

```python
from google.genai import types
SEARCH_GROUNDING = types.Tool(google_search=types.GoogleSearch())

market_research_analyst = LlmAgent(
    tools=[SEARCH_GROUNDING],
)
```

This produced a Pydantic validation error:
```
tools.0.callable - Input should be callable
tools.0.is-instance[BaseTool] - Input should be an instance of BaseTool
tools.0.is-instance[BaseToolset] - Input should be an instance of BaseToolset
```

The fix was to use ADK's built-in google_search tool:
```python
from google.adk.tools import google_search

market_research_analyst = LlmAgent(
    tools=[google_search],
)
```

**Q: What was the "agents" vs "sub_agents" error?**

A: The initial orchestrator used `agents=[research_team]`:

```python
agent = LlmAgent(
    name="research_orchestrator",
    agents=[research_team],
)
```

This produced:
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for LlmAgent
agents - Extra inputs are not permitted
```

We inspected the LlmAgent signature using `inspect.signature()` and found the correct parameter is `sub_agents`, not `agents`:

```python
agent = LlmAgent(
    name="research_orchestrator",
    sub_agents=[research_team],
)
```

**Q: What was the root_agent discovery issue?**

A: ADK's web UI looks for a variable named `root_agent` in the agent module, not just `agent`. When we only had `agent = research_orchestrator`, the UI showed:

```
No root_agent found for 'research_agent'. Searched in
'research_agent.agent.root_agent', 'research_agent.root_agent' and
'research_agent/root_agent.yaml'.
```

The fix was adding `root_agent = agent` to agent.py.

**Q: What was the synthesis problem and how was it solved?**

A: This was the most significant architectural issue. With an LlmAgent as root and the ParallelAgent as a sub-agent, the parallel results streamed through to the user as separate messages (#8, #9, #10, etc.) but the orchestrator never got control back to merge them. The user saw 3 individual reports instead of one unified brief.

We tried several approaches:
1. Adding `output_key` to sub-agents (helped store results but didn't fix synthesis)
2. Updating the orchestrator instruction to be more explicit about synthesis (didn't work — the orchestrator never got a turn)
3. **Final solution**: Restructured the root from an LlmAgent to a SequentialAgent with two steps:
   - Step 1: ParallelAgent (gathers data from all 3 analysts)
   - Step 2: Synthesizer LlmAgent (reads state, produces unified brief)

This guaranteed the synthesizer runs AFTER all parallel results are stored in state.

**Q: What was the BigQuery metadata server error?**

A: During testing, all BigQuery tools returned: `Unexpected response from metadata server: service account info is missing 'email' field.`

This happened because Cloud Shell's default service account credentials didn't have the proper email field. The fix was running `gcloud auth application-default login --no-launch-browser` to create user-level application default credentials with proper authentication.

**Q: What was the DNS resolution error in ParallelAgent?**

A: When 3 agents made simultaneous Gemini API calls, Cloud Shell's DNS occasionally failed with: `httpx.ConnectError: [Errno -3] Temporary failure in name resolution`

This is a transient Cloud Shell networking issue — the DNS resolver gets overwhelmed by concurrent outbound connections. The error crashes the entire ParallelAgent because `asyncio.TaskGroup` propagates any sub-task exception. Retrying with a new session typically resolves it. In production, you'd add retry logic or error boundaries.

---

## Part 7: Testing and Verification

**Q: How do you verify that the ParallelAgent is actually running concurrently?**

A: In the ADK web UI's Trace view, you can see the timing of each agent's execution. With parallel execution, all 3 sub-agents start within milliseconds of each other — you see `transfer_to_agent` calls for all 3 at roughly the same timestamp. With sequential execution, each would start only after the previous one completes.

The trace also shows the tool calls for each agent happening concurrently: `get_category_performance`, `get_regional_performance`, `get_top_products` from the internal analyst overlap in time with `get_monthly_trend`, `get_yoy_comparison`, `get_category_share` from the trend analyst and the Google Search call from the market research analyst.

**Q: What does the verification script check?**

A: The verification script (scripts/verify.sh) runs 35+ checks across 6 categories:

1. **Environment**: Python, pip packages, environment variables
2. **Project structure**: All required files exist
3. **Imports**: All 6 tools and the root agent import correctly
4. **Agent structure**: research_team is a ParallelAgent, all 3 sub-agents present, correct tool counts
5. **BigQuery data validation**: Row count (456K+), 5 categories, 5 regions, 50 products, date range
6. **Tool tests**: All 6 tools return success from BigQuery
7. **Data quality**: Category shares sum to 100%, revenue is positive, all regions returned, YoY growth calculations work

**Q: What does the eval set test?**

A: The 10-case eval set covers:

- Single category queries (electronics performance)
- Cross-category comparison (grocery vs clothing)
- Market-only queries (retail outlook — tests Google Search path)
- Regional analysis (strongest region)
- Monthly trends, YoY growth, category share
- Top products
- Strategic recommendations (multi-tool)
- External factors (Home and Garden market — tests Google Search)

---

## Part 8: Data Flow

**Q: Walk through the complete data flow for "How are electronics performing?"**

A: Here's the step-by-step flow:

1. **User** sends "How are electronics performing?" to the ADK web UI
2. **research_pipeline** (SequentialAgent) receives the query
3. **Step 1**: SequentialAgent delegates to **research_team** (ParallelAgent)
4. ParallelAgent sends the query to all 3 sub-agents simultaneously:

   **internal_data_analyst** (concurrent):
   - Gemini decides to call `get_category_performance("Electronics")`
   - Tool queries BigQuery: SELECT SUM(daily_revenue)... WHERE category = 'Electronics'
   - Returns: $10.25M revenue, 91K units, $111.85 AOV
   - Gemini decides to call `get_regional_performance("Electronics")`
   - Returns: 5 regions with revenue breakdown
   - Gemini decides to call `get_top_products("Electronics", 10)`
   - Returns: 10 products ranked by revenue
   - Agent produces summary, stored in state["internal_data"]

   **market_research_analyst** (concurrent):
   - Gemini decides it needs web search for external context
   - Google Search grounding automatically searches for electronics market data
   - Gemini synthesizes search results with citations
   - Agent produces market overview, stored in state["market_research"]

   **trend_analyst** (concurrent):
   - Gemini calls `get_monthly_trend("Electronics", 12)`
   - Gemini calls `get_yoy_comparison("Electronics")`
   - Gemini calls `get_category_share()`
   - Agent produces trend analysis, stored in state["trend_analysis"]

5. All 3 agents complete. ParallelAgent finishes.
6. **Step 2**: SequentialAgent delegates to **synthesizer**
7. Synthesizer reads state["internal_data"], state["market_research"], state["trend_analysis"]
8. Synthesizer produces unified research brief:
   - Headline: "Electronics Category Leads Growth"
   - Internal data: $10.25M revenue, 27.49% market share
   - External context: $1.46T global market, 7.8% CAGR
   - Alignment: "Our 8.32% YoY outpaces global CAGR"
   - Recommendations: Expand into AI products, optimize e-commerce, manage supply chain
9. **User** sees the synthesized brief

---

## Part 9: Comparison with Other Portfolio Projects

**Q: How does this project compare architecturally to the other ADK builds?**

A: Each project demonstrates a distinct agent pattern:

| Project | Root Agent | Sub-Agents | Tools | Key Pattern |
|---------|-----------|------------|-------|-------------|
| ADK Retail Agents | LlmAgent (orchestrator) | 3 specialists via transfer_to_agent | 11 fixed SQL | Sequential routing |
| ADK NL2SQL Agent | LlmAgent | Single agent | Dynamic SQL generation | Text-to-SQL |
| ADK Anomaly Detection | LlmAgent | Single specialist | 6 fixed SQL + ARIMA_PLUS | BigQuery ML integration |
| **ADK Research Agent** | **SequentialAgent** | **ParallelAgent + synthesizer** | **6 fixed SQL + Google Search** | **Concurrent execution + external retrieval + synthesis** |

The Research Agent is the most architecturally complex, using 3 ADK agent types (SequentialAgent, ParallelAgent, LlmAgent) in a single system.

---

## Part 10: ADK-Specific Technical Details

**Q: What ADK version was used and what API differences matter?**

A: ADK 1.25.1. Key version-specific details:

- `LlmAgent` uses `sub_agents` parameter (not `agents`)
- `tools` parameter accepts callables, `BaseTool`, or `BaseToolset` instances (not `types.Tool`)
- Google Search grounding uses `from google.adk.tools import google_search`
- ADK web UI looks for `root_agent` variable name
- `adk web .` must be run from the parent directory (not inside the agent package)
- `ParallelAgent` uses `sub_agents` parameter for its child agents
- `SequentialAgent` uses `sub_agents` parameter and runs them in list order
- `output_key` stores agent output in session state

**Q: How does SequentialAgent pass data between steps?**

A: Through session state. The SequentialAgent doesn't explicitly pass data — it runs sub-agents in order, and they all share the same session. When Step 1's parallel agents write to state via `output_key`, Step 2's synthesizer can read those state values. The shared session is the communication channel.

---

## Part 11: Sandbox Constraints

**Q: What sandbox restrictions apply to this project?**

A: The GCP sandbox has several restrictions. Here's what we navigated:

| Constraint | Impact | Solution |
|-----------|--------|----------|
| Vertex AI not supported | Can't use aiplatform.googleapis.com | Use AI Studio free tier (GOOGLE_GENAI_USE_VERTEXAI=FALSE) |
| Cloud Run conditionally supported | Gen2 Cloud Functions create Cloud Run services | Not used in this project |
| No IAM changes | Can't assign custom roles | Use default credentials |
| Region restrictions | US-East-1, US-West-1, US-Central-1, etc. | BigQuery dataset in US location |
| Metadata server issues | Service account missing email field | Use gcloud auth application-default login |

**Q: Could this project run outside the sandbox without changes?**

A: Yes, with minor adjustments:
- Remove `GOOGLE_GENAI_USE_VERTEXAI=FALSE` to use Vertex AI instead of AI Studio
- Update `PROJECT_ID` in tools to match the target project
- The architecture, agents, and tools are all portable

---

## Part 12: Production Considerations

**Q: What would need to change for production deployment?**

A: Several areas:

1. **Error handling**: Add retry logic for transient API failures, especially for the Google Search agent. The DNS resolution errors we encountered would need to be handled gracefully.

2. **Authentication**: Move from application-default credentials to a service account with minimal permissions (BigQuery Data Viewer, BigQuery Job User).

3. **Deployment**: Deploy to Cloud Run or GKE instead of Cloud Shell. Use environment variables or Secret Manager for the API key.

4. **Monitoring**: Add Cloud Logging and Cloud Monitoring for agent performance, tool latency, and error rates.

5. **Caching**: Cache BigQuery results for repeated queries. The underlying data changes infrequently, so a 1-hour cache would reduce costs and latency.

6. **Rate limiting**: AI Studio free tier has rate limits. Production would need a paid Gemini API plan or Vertex AI.

7. **Input validation**: Add guardrails to reject off-topic queries and validate category/region inputs before querying BigQuery.
