"""
Synthetic retail data generator for ADK Research Agent.

Generates fct_daily_sales with realistic patterns:
- 5 regions, 5 categories, 50 products
- 5 years of daily data (2020-2024)
- Seasonal patterns (holiday spikes, summer trends)
- Category growth trends
- Regional variation
"""

import pandas as pd
import numpy as np
from google.cloud import bigquery
import sys

PROJECT_ID = "playground-s-11-1e85993b"
DATASET = "retail_gold"
TABLE = "fct_daily_sales"

# --- Configuration ---

REGIONS = ["Northeast", "Southeast", "Midwest", "West", "Southwest"]

# Regional strength multipliers (which regions are strong in which category)
# Each region has a base multiplier that varies by category
REGION_WEIGHTS = {
    "Northeast": {"Electronics": 1.3, "Clothing": 1.2, "Home and Garden": 0.9, "Sports": 0.8, "Grocery": 1.0},
    "Southeast": {"Electronics": 0.9, "Clothing": 1.0, "Home and Garden": 1.3, "Sports": 1.1, "Grocery": 1.2},
    "Midwest":   {"Electronics": 0.8, "Clothing": 0.9, "Home and Garden": 1.1, "Sports": 1.3, "Grocery": 1.1},
    "West":      {"Electronics": 1.4, "Clothing": 1.3, "Home and Garden": 1.0, "Sports": 1.2, "Grocery": 0.9},
    "Southwest": {"Electronics": 1.0, "Clothing": 0.8, "Home and Garden": 1.2, "Sports": 1.0, "Grocery": 1.1},
}

# Category configurations: base_revenue_per_day, annual_growth_rate, seasonality_type
CATEGORIES = {
    "Electronics": {
        "base_revenue": 800,
        "annual_growth": 0.08,        # 8% annual growth
        "seasonality": "holiday",      # Big Q4 spike
        "products": [
            "Wireless Headphones", "Bluetooth Speaker", "USB-C Hub", "Portable Charger",
            "Mechanical Keyboard", "Gaming Mouse", "Webcam HD", "Smart Watch",
            "Tablet Stand", "LED Monitor"
        ],
        "product_price_range": (25, 350),
    },
    "Clothing": {
        "base_revenue": 600,
        "annual_growth": 0.03,         # 3% modest growth
        "seasonality": "bimodal",      # Spring + Fall peaks
        "products": [
            "Cotton T-Shirt", "Denim Jeans", "Running Shoes", "Winter Jacket",
            "Polo Shirt", "Yoga Pants", "Rain Jacket", "Casual Sneakers",
            "Wool Sweater", "Athletic Shorts"
        ],
        "product_price_range": (20, 150),
    },
    "Home and Garden": {
        "base_revenue": 500,
        "annual_growth": 0.12,         # 12% strong growth (post-2020 trend)
        "seasonality": "summer",       # Spring/Summer peak
        "products": [
            "Garden Hose", "LED Bulb Pack", "Throw Pillow Set", "Plant Pot Ceramic",
            "Tool Set Basic", "Outdoor Chair", "Welcome Mat", "Kitchen Organizer",
            "Wall Shelf", "Candle Set"
        ],
        "product_price_range": (15, 200),
    },
    "Sports": {
        "base_revenue": 400,
        "annual_growth": 0.05,         # 5% steady growth
        "seasonality": "summer",       # Summer peak
        "products": [
            "Yoga Mat", "Resistance Bands", "Water Bottle Steel", "Jump Rope",
            "Foam Roller", "Dumbbell Set", "Sports Bag", "Fitness Tracker Band",
            "Tennis Balls Pack", "Running Belt"
        ],
        "product_price_range": (10, 120),
    },
    "Grocery": {
        "base_revenue": 900,
        "annual_growth": 0.02,         # 2% inflation-driven
        "seasonality": "holiday",      # Holiday + steady
        "products": [
            "Organic Coffee Beans", "Protein Bars Box", "Olive Oil Premium",
            "Mixed Nuts Bag", "Green Tea Pack", "Dark Chocolate Bar",
            "Granola Cereal", "Coconut Water Case", "Honey Jar Raw",
            "Trail Mix Variety"
        ],
        "product_price_range": (5, 45),
    },
}


def get_seasonality_factor(date, seasonality_type):
    """Returns a multiplier (0.5 to 2.0) based on date and pattern type."""
    month = date.month
    day_of_year = date.timetuple().tm_yday

    if seasonality_type == "holiday":
        # Big Q4 spike, slight dip in Jan-Feb
        if month == 11:
            return 1.5
        elif month == 12:
            return 1.8
        elif month in [1, 2]:
            return 0.7
        elif month in [6, 7]:
            return 0.9
        else:
            return 1.0

    elif seasonality_type == "summer":
        # Peak in May-Aug, low in Dec-Feb
        if month in [5, 6, 7, 8]:
            return 1.4
        elif month in [12, 1, 2]:
            return 0.6
        elif month in [3, 4, 9]:
            return 1.1
        else:
            return 0.9

    elif seasonality_type == "bimodal":
        # Spring (Mar-Apr) and Fall (Sep-Oct) peaks
        if month in [3, 4]:
            return 1.3
        elif month in [9, 10]:
            return 1.4
        elif month in [1, 2, 7, 8]:
            return 0.8
        else:
            return 1.0

    return 1.0


def generate_data():
    """Generate the full dataset."""
    np.random.seed(42)  # Reproducible results

    dates = pd.date_range("2020-01-01", "2024-12-31", freq="D")
    print(f"Generating data for {len(dates)} days...")

    rows = []
    for date in dates:
        # Calculate years elapsed for growth trend
        years_elapsed = (date - pd.Timestamp("2020-01-01")).days / 365.25

        for cat_name, cat_config in CATEGORIES.items():
            # Category-level factors
            growth_factor = (1 + cat_config["annual_growth"]) ** years_elapsed
            seasonal_factor = get_seasonality_factor(date, cat_config["seasonality"])

            # Day-of-week factor (weekends slightly higher for retail)
            dow = date.dayofweek
            dow_factor = 1.15 if dow >= 5 else 1.0  # 15% weekend bump

            for region in REGIONS:
                region_weight = REGION_WEIGHTS[region][cat_name]

                for product in cat_config["products"]:
                    # Product gets a consistent share of category revenue
                    # Use hash for deterministic but varied product weights
                    product_hash = hash(product) % 100
                    product_weight = 0.5 + (product_hash / 100)  # 0.5 to 1.5

                    # Base daily revenue for this product/region/day
                    base = cat_config["base_revenue"] / len(cat_config["products"])

                    # Apply all factors
                    revenue = (
                        base
                        * growth_factor
                        * seasonal_factor
                        * dow_factor
                        * region_weight
                        * product_weight
                    )

                    # Add noise (±20%)
                    noise = np.random.normal(1.0, 0.2)
                    revenue = max(revenue * noise, 1.0)  # Floor at $1
                    revenue = round(revenue, 2)

                    # Calculate quantity from price range
                    min_price, max_price = cat_config["product_price_range"]
                    avg_price = (min_price + max_price) / 2
                    # Adjust price by product weight (expensive products sell fewer units)
                    effective_price = avg_price * (0.5 + product_weight * 0.5)
                    quantity = max(int(revenue / effective_price), 1)

                    rows.append({
                        "sale_date": date.strftime("%Y-%m-%d"),
                        "region": region,
                        "category": cat_name,
                        "product_name": product,
                        "daily_revenue": revenue,
                        "daily_quantity": quantity,
                    })

    df = pd.DataFrame(rows)
    print(f"Generated {len(df):,} rows")
    print(f"Date range: {df['sale_date'].min()} to {df['sale_date'].max()}")
    print(f"Total revenue: ${df['daily_revenue'].sum():,.0f}")
    print(f"Categories: {df['category'].nunique()}")
    print(f"Regions: {df['region'].nunique()}")
    print(f"Products: {df['product_name'].nunique()}")
    return df


def load_to_bigquery(df):
    """Load dataframe to BigQuery."""
    client = bigquery.Client(project=PROJECT_ID)
    table_id = f"{PROJECT_ID}.{DATASET}.{TABLE}"

    # Define schema explicitly
    schema = [
        bigquery.SchemaField("sale_date", "DATE"),
        bigquery.SchemaField("region", "STRING"),
        bigquery.SchemaField("category", "STRING"),
        bigquery.SchemaField("product_name", "STRING"),
        bigquery.SchemaField("daily_revenue", "FLOAT64"),
        bigquery.SchemaField("daily_quantity", "INT64"),
    ]

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition="WRITE_TRUNCATE",  # Replace table if exists
    )

    print(f"\nLoading to {table_id}...")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # Wait for completion

    table = client.get_table(table_id)
    print(f"Loaded {table.num_rows:,} rows to {table_id}")
    return table.num_rows


if __name__ == "__main__":
    print("=" * 50)
    print("ADK Research Agent — Data Generator")
    print("=" * 50)

    df = generate_data()
    rows_loaded = load_to_bigquery(df)

    print("\n" + "=" * 50)
    print("Data generation complete!")
    print(f"Table: {PROJECT_ID}.{DATASET}.{TABLE}")
    print(f"Rows: {rows_loaded:,}")
    print("=" * 50)
