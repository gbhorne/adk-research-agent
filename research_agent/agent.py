"""
ADK Research Agent — ParallelAgent with Google Search Grounding

Architecture:
  research_pipeline (SequentialAgent - root)
    ├── Step 1: research_team (ParallelAgent)
    │     ├── internal_data_analyst (LlmAgent + BigQuery tools)
    │     ├── market_research_analyst (LlmAgent + Google Search)
    │     └── trend_analyst (LlmAgent + BigQuery tools)
    └── Step 2: synthesizer (LlmAgent - merges all results)
"""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import google_search

from research_agent.tools.internal_tools import (
    get_category_performance,
    get_regional_performance,
    get_top_products,
)
from research_agent.tools.trend_tools import (
    get_monthly_trend,
    get_yoy_comparison,
    get_category_share,
)

MODEL = "gemini-2.5-flash"

internal_data_analyst = LlmAgent(
    name="internal_data_analyst",
    model=MODEL,
    instruction="""You are an internal data analyst. Retrieve and summarize
current performance data from BigQuery.

When given a research question:
1. Identify relevant product categories
2. Use your tools to pull metrics, regional breakdowns, and top products
3. Present data clearly with specific numbers

Available categories: Electronics, Clothing, Home and Garden, Sports, Grocery

Always call at least one tool. Report exact figures.""",
    tools=[get_category_performance, get_regional_performance, get_top_products],
    output_key="internal_data",
)

market_research_analyst = LlmAgent(
    name="market_research_analyst",
    model=MODEL,
    instruction="""You are a market research analyst. Find external context
about retail industry trends, competitive landscape, and market outlook.

When given a research question:
1. Search for recent market data, industry reports, and news
2. Focus on the last 6-12 months
3. Look for forecasts, market size data, and competitive moves
4. Note macroeconomic factors

Provide specific data points. Focus on actionable insights.""",
    tools=[google_search],
    output_key="market_research",
)

trend_analyst = LlmAgent(
    name="trend_analyst",
    model=MODEL,
    instruction="""You are a trend analyst. Examine historical sales patterns
and identify significant trends in company data.

When given a research question:
1. Pull monthly trends and year-over-year comparisons
2. Identify acceleration, deceleration, or seasonal patterns
3. Compare category market share shifts
4. Highlight notable changes or inflection points

Available categories: Electronics, Clothing, Home and Garden, Sports, Grocery

Always call at least one tool. Use specific numbers and percentages.""",
    tools=[get_monthly_trend, get_yoy_comparison, get_category_share],
    output_key="trend_analysis",
)

research_team = ParallelAgent(
    name="research_team",
    sub_agents=[
        internal_data_analyst,
        market_research_analyst,
        trend_analyst,
    ],
)

synthesizer = LlmAgent(
    name="synthesizer",
    model=MODEL,
    instruction="""You are a senior research director. Your three analysts
have just completed their research in parallel. Their findings are in the
session state:

- state["internal_data"]: Current performance metrics from BigQuery
- state["market_research"]: External market context from web search
- state["trend_analysis"]: Historical trends and patterns

Synthesize ALL THREE into ONE unified research brief.

Your brief MUST:
- Lead with the key finding or headline insight
- Combine internal data with external context
- Highlight where internal performance aligns or diverges from market trends
- Call out risks and opportunities
- Use specific numbers from both internal and external sources
- End with 2-3 actionable recommendations

Do NOT repeat each analyst's report separately.
MERGE their findings into a cohesive narrative.
Keep it concise but data-rich. Executives will read this.""",
)

root_agent = agent = SequentialAgent(
    name="research_pipeline",
    sub_agents=[research_team, synthesizer],
)
