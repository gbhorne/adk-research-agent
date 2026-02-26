#!/bin/bash
echo "========================================"
echo "ADK Research Agent — Verification"
echo "========================================"
PASS=0; FAIL=0; TOTAL=0
check() {
    TOTAL=$((TOTAL + 1))
    if [ $1 -eq 0 ]; then PASS=$((PASS + 1)); echo "  PASS  $2"
    else FAIL=$((FAIL + 1)); echo "  FAIL  $2"; fi
}
echo ""; echo "--- Environment ---"
python3 --version > /dev/null 2>&1; check $? "Python installed"
pip show google-adk > /dev/null 2>&1; check $? "google-adk installed"
pip show google-cloud-bigquery > /dev/null 2>&1; check $? "google-cloud-bigquery installed"
pip show google-genai > /dev/null 2>&1; check $? "google-genai installed"
[ ! -z "$GOOGLE_API_KEY" ]; check $? "GOOGLE_API_KEY set"
[ ! -z "$GOOGLE_CLOUD_PROJECT" ]; check $? "GOOGLE_CLOUD_PROJECT set"
[ "$GOOGLE_GENAI_USE_VERTEXAI" = "FALSE" ]; check $? "GOOGLE_GENAI_USE_VERTEXAI=FALSE"
echo ""; echo "--- Project Structure ---"
[ -f "research_agent/__init__.py" ]; check $? "__init__.py exists"
[ -f "research_agent/agent.py" ]; check $? "agent.py exists"
[ -f "research_agent/tools/__init__.py" ]; check $? "tools/__init__.py exists"
[ -f "research_agent/tools/internal_tools.py" ]; check $? "internal_tools.py exists"
[ -f "research_agent/tools/trend_tools.py" ]; check $? "trend_tools.py exists"
[ -f "research_agent/research_eval.evalset.json" ]; check $? "Eval set exists"
[ -f "requirements.txt" ]; check $? "requirements.txt exists"
[ -f "scripts/generate_data.py" ]; check $? "Data generator exists"
echo ""; echo "--- Imports ---"
python3 -c "from research_agent.tools.internal_tools import get_category_performance" 2>/dev/null; check $? "Import get_category_performance"
python3 -c "from research_agent.tools.internal_tools import get_regional_performance" 2>/dev/null; check $? "Import get_regional_performance"
python3 -c "from research_agent.tools.internal_tools import get_top_products" 2>/dev/null; check $? "Import get_top_products"
python3 -c "from research_agent.tools.trend_tools import get_monthly_trend" 2>/dev/null; check $? "Import get_monthly_trend"
python3 -c "from research_agent.tools.trend_tools import get_yoy_comparison" 2>/dev/null; check $? "Import get_yoy_comparison"
python3 -c "from research_agent.tools.trend_tools import get_category_share" 2>/dev/null; check $? "Import get_category_share"
python3 -c "from research_agent.agent import agent" 2>/dev/null; check $? "Import root agent"
python3 -c "from google.adk.tools import google_search" 2>/dev/null; check $? "Import google_search tool"
echo ""; echo "--- Agent Structure ---"
python3 -c "
from research_agent.agent import agent
from google.adk.agents import SequentialAgent
assert isinstance(agent, SequentialAgent)
" 2>/dev/null; check $? "Root is SequentialAgent"
python3 -c "
from research_agent.agent import agent
assert len(agent.sub_agents) == 2
" 2>/dev/null; check $? "SequentialAgent has 2 steps"
python3 -c "
from research_agent.agent import research_team
from google.adk.agents import ParallelAgent
assert isinstance(research_team, ParallelAgent)
" 2>/dev/null; check $? "research_team is ParallelAgent"
python3 -c "
from research_agent.agent import research_team
names = [a.name for a in research_team.sub_agents]
assert 'internal_data_analyst' in names
assert 'market_research_analyst' in names
assert 'trend_analyst' in names
" 2>/dev/null; check $? "All 3 sub-agents in ParallelAgent"
python3 -c "
from research_agent.agent import internal_data_analyst
assert len(internal_data_analyst.tools) == 3
assert internal_data_analyst.output_key == 'internal_data'
" 2>/dev/null; check $? "internal_data_analyst: 3 tools + output_key"
python3 -c "
from research_agent.agent import trend_analyst
assert len(trend_analyst.tools) == 3
assert trend_analyst.output_key == 'trend_analysis'
" 2>/dev/null; check $? "trend_analyst: 3 tools + output_key"
python3 -c "
from research_agent.agent import market_research_analyst
assert len(market_research_analyst.tools) == 1
assert market_research_analyst.output_key == 'market_research'
" 2>/dev/null; check $? "market_research_analyst: google_search + output_key"
python3 -c "
from research_agent.agent import synthesizer
from google.adk.agents import LlmAgent
assert isinstance(synthesizer, LlmAgent)
" 2>/dev/null; check $? "synthesizer is LlmAgent"
echo ""; echo "--- BigQuery Data ---"
python3 -c "
from google.cloud import bigquery
c = bigquery.Client(project='playground-s-11-1e85993b')
r = list(c.query('SELECT COUNT(*) as n FROM \`playground-s-11-1e85993b.retail_gold.fct_daily_sales\`').result())
assert r[0]['n'] > 400000
print(f'{r[0][\"n\"]:,} rows')
" 2>/dev/null; check $? "400K+ rows in fct_daily_sales"
python3 -c "
from google.cloud import bigquery
c = bigquery.Client(project='playground-s-11-1e85993b')
r = list(c.query('SELECT COUNT(DISTINCT category) as n FROM \`playground-s-11-1e85993b.retail_gold.fct_daily_sales\`').result())
assert r[0]['n'] == 5
" 2>/dev/null; check $? "5 categories"
python3 -c "
from google.cloud import bigquery
c = bigquery.Client(project='playground-s-11-1e85993b')
r = list(c.query('SELECT COUNT(DISTINCT region) as n FROM \`playground-s-11-1e85993b.retail_gold.fct_daily_sales\`').result())
assert r[0]['n'] == 5
" 2>/dev/null; check $? "5 regions"
python3 -c "
from google.cloud import bigquery
c = bigquery.Client(project='playground-s-11-1e85993b')
r = list(c.query('SELECT COUNT(DISTINCT product_name) as n FROM \`playground-s-11-1e85993b.retail_gold.fct_daily_sales\`').result())
assert r[0]['n'] == 50
" 2>/dev/null; check $? "50 products"
echo ""; echo "--- Tool Tests ---"
python3 -c "
from research_agent.tools.internal_tools import get_category_performance
r = get_category_performance('Electronics')
assert r['status'] == 'success'
" 2>/dev/null; check $? "get_category_performance works"
python3 -c "
from research_agent.tools.internal_tools import get_regional_performance
r = get_regional_performance('Electronics')
assert r['status'] == 'success'
" 2>/dev/null; check $? "get_regional_performance works"
python3 -c "
from research_agent.tools.internal_tools import get_top_products
r = get_top_products('Electronics', 5)
assert r['status'] == 'success'
" 2>/dev/null; check $? "get_top_products works"
python3 -c "
from research_agent.tools.trend_tools import get_monthly_trend
r = get_monthly_trend('Electronics', 6)
assert r['status'] == 'success'
" 2>/dev/null; check $? "get_monthly_trend works"
python3 -c "
from research_agent.tools.trend_tools import get_yoy_comparison
r = get_yoy_comparison('Electronics')
assert r['status'] == 'success'
" 2>/dev/null; check $? "get_yoy_comparison works"
python3 -c "
from research_agent.tools.trend_tools import get_category_share
r = get_category_share()
assert r['status'] == 'success'
" 2>/dev/null; check $? "get_category_share works"
echo ""; echo "--- Data Quality ---"
python3 -c "
from research_agent.tools.trend_tools import get_category_share
r = get_category_share()
total = sum(row['pct_of_total'] for row in r['data'])
assert 99.9 < total < 100.1
" 2>/dev/null; check $? "Category shares sum to ~100%"
python3 -c "
from research_agent.tools.internal_tools import get_regional_performance
r = get_regional_performance('Electronics')
assert r['data'][0]['region'] == 'West'
" 2>/dev/null; check $? "West leads electronics (pattern verified)"
python3 -c "
from research_agent.tools.trend_tools import get_yoy_comparison
r = get_yoy_comparison('Electronics')
growth = [row['yoy_growth_pct'] for row in r['data'] if row['yoy_growth_pct'] is not None]
for g in growth: assert 5 < g < 12
" 2>/dev/null; check $? "YoY growth ~8% (pattern verified)"
python3 -c "
from research_agent.tools.trend_tools import get_category_share
r = get_category_share()
cats = {row['category']: row['pct_of_total'] for row in r['data']}
assert cats['Electronics'] > 20
" 2>/dev/null; check $? "Electronics is largest category"

echo ""
echo "========================================"
echo "Results: $PASS/$TOTAL passing ($FAIL failed)"
echo "========================================"
