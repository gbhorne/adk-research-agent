"""Trend analysis tools - query BigQuery retail_gold for historical patterns."""

from google.cloud import bigquery

PROJECT_ID = "playground-s-11-1e85993b"
client = bigquery.Client(project=PROJECT_ID)


def get_monthly_trend(category: str, months: int = 12) -> dict:
    """Get month-over-month revenue trend for a category.

    Args:
        category: Product category name (e.g., 'Electronics', 'Clothing',
                  'Home and Garden', 'Sports', 'Grocery')
        months: Number of recent months to include (default 12)

    Returns:
        dict with status and monthly revenue data.
    """
    query = """
        SELECT
            FORMAT_DATE('%Y-%m', sale_date) as month,
            SUM(daily_revenue) as monthly_revenue,
            SUM(daily_quantity) as monthly_units
        FROM `{project}.retail_gold.fct_daily_sales`
        WHERE LOWER(category) = LOWER(@category)
        GROUP BY month
        ORDER BY month DESC
        LIMIT @months
    """.format(project=PROJECT_ID)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("category", "STRING", category),
            bigquery.ScalarQueryParameter("months", "INT64", months),
        ]
    )

    try:
        results = client.query(query, job_config=job_config).result()
        rows = [dict(row) for row in results]
        if not rows:
            return {"status": "no_data", "message": f"No trend data for category: {category}"}
        return {"status": "success", "data": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_yoy_comparison(category: str) -> dict:
    """Get year-over-year revenue comparison for a category.

    Args:
        category: Product category name (e.g., 'Electronics', 'Clothing',
                  'Home and Garden', 'Sports', 'Grocery')

    Returns:
        dict with status and yearly revenue with growth rates.
    """
    query = """
        WITH yearly AS (
            SELECT
                EXTRACT(YEAR FROM sale_date) as year,
                SUM(daily_revenue) as annual_revenue,
                SUM(daily_quantity) as annual_units
            FROM `{project}.retail_gold.fct_daily_sales`
            WHERE LOWER(category) = LOWER(@category)
            GROUP BY year
        )
        SELECT
            year,
            annual_revenue,
            annual_units,
            ROUND(
                (annual_revenue - LAG(annual_revenue) OVER (ORDER BY year))
                / NULLIF(LAG(annual_revenue) OVER (ORDER BY year), 0) * 100,
                2
            ) as yoy_growth_pct
        FROM yearly
        ORDER BY year
    """.format(project=PROJECT_ID)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("category", "STRING", category)
        ]
    )

    try:
        results = client.query(query, job_config=job_config).result()
        rows = [dict(row) for row in results]
        if not rows:
            return {"status": "no_data", "message": f"No YoY data for category: {category}"}
        return {"status": "success", "data": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_category_share() -> dict:
    """Get revenue share across all product categories.

    Returns:
        dict with status and each category's revenue and percentage of total.
    """
    query = """
        WITH totals AS (
            SELECT
                category,
                SUM(daily_revenue) as category_revenue
            FROM `{project}.retail_gold.fct_daily_sales`
            GROUP BY category
        )
        SELECT
            category,
            category_revenue,
            ROUND(category_revenue / SUM(category_revenue) OVER () * 100, 2) as pct_of_total
        FROM totals
        ORDER BY category_revenue DESC
    """.format(project=PROJECT_ID)

    try:
        results = client.query(query).result()
        rows = [dict(row) for row in results]
        if not rows:
            return {"status": "no_data", "message": "No category data found"}
        return {"status": "success", "data": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}
