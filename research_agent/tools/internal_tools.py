"""Internal data tools - query BigQuery retail_gold for current metrics."""

from google.cloud import bigquery

PROJECT_ID = "playground-s-11-1e85993b"
client = bigquery.Client(project=PROJECT_ID)


def get_category_performance(category: str) -> dict:
    """Get revenue, units sold, and average order value for a product category.

    Args:
        category: Product category name (e.g., 'Electronics', 'Clothing',
                  'Home and Garden', 'Sports', 'Grocery')

    Returns:
        dict with status and performance metrics for the category.
    """
    query = """
        SELECT
            category,
            SUM(daily_revenue) as total_revenue,
            SUM(daily_quantity) as total_units,
            ROUND(AVG(daily_revenue / NULLIF(daily_quantity, 0)), 2) as avg_order_value,
            MIN(sale_date) as earliest_date,
            MAX(sale_date) as latest_date
        FROM `{project}.retail_gold.fct_daily_sales`
        WHERE LOWER(category) = LOWER(@category)
        GROUP BY category
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
            return {"status": "no_data", "message": f"No data found for category: {category}"}
        for row in rows:
            for key, value in row.items():
                if hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return {"status": "success", "data": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_regional_performance(category: str) -> dict:
    """Get performance breakdown by region for a product category.

    Args:
        category: Product category name (e.g., 'Electronics', 'Clothing',
                  'Home and Garden', 'Sports', 'Grocery')

    Returns:
        dict with status and regional performance data.
    """
    query = """
        SELECT
            region,
            SUM(daily_revenue) as total_revenue,
            SUM(daily_quantity) as total_units,
            ROUND(AVG(daily_revenue / NULLIF(daily_quantity, 0)), 2) as avg_order_value
        FROM `{project}.retail_gold.fct_daily_sales`
        WHERE LOWER(category) = LOWER(@category)
        GROUP BY region
        ORDER BY total_revenue DESC
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
            return {"status": "no_data", "message": f"No regional data for category: {category}"}
        return {"status": "success", "data": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_top_products(category: str, limit: int = 10) -> dict:
    """Get the top-selling products in a category by revenue.

    Args:
        category: Product category name (e.g., 'Electronics', 'Clothing',
                  'Home and Garden', 'Sports', 'Grocery')
        limit: Number of products to return (default 10)

    Returns:
        dict with status and top products ranked by revenue.
    """
    query = """
        SELECT
            product_name,
            SUM(daily_revenue) as total_revenue,
            SUM(daily_quantity) as total_units
        FROM `{project}.retail_gold.fct_daily_sales`
        WHERE LOWER(category) = LOWER(@category)
        GROUP BY product_name
        ORDER BY total_revenue DESC
        LIMIT @limit
    """.format(project=PROJECT_ID)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("category", "STRING", category),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )

    try:
        results = client.query(query, job_config=job_config).result()
        rows = [dict(row) for row in results]
        if not rows:
            return {"status": "no_data", "message": f"No products found for category: {category}"}
        return {"status": "success", "data": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}
