
import mysql.connector
from flask import Blueprint, render_template

from app.database import get_db_connection

analytics_bp = Blueprint(
    "analytics",
    __name__,
    url_prefix="/analytics"
)


@analytics_bp.route("/", methods=["GET"])
def index():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                COUNT(*) AS total_records,
                COUNT(DISTINCT primary_type) AS crime_type_count,
                MIN(year) AS first_year,
                MAX(year) AS last_year,
                COALESCE(SUM(arrest = 1), 0) AS arrest_records,
                COALESCE(SUM(domestic = 1), 0) AS domestic_records,
                COALESCE(
                    SUM(latitude IS NOT NULL AND longitude IS NOT NULL),
                    0
                ) AS records_with_coordinates
            FROM chicago_crime_data
        """)
        summary = cursor.fetchone()

        cursor.execute("""
            SELECT
                primary_type,
                COUNT(*) AS total
            FROM chicago_crime_data
            GROUP BY primary_type
            ORDER BY total DESC, primary_type
            LIMIT 10
        """)
        crime_types = cursor.fetchall()

        cursor.execute("""
            SELECT
                year,
                COUNT(*) AS total,
                COALESCE(SUM(arrest = 1), 0) AS arrests
            FROM chicago_crime_data
            GROUP BY year
            ORDER BY year
        """)
        yearly_counts = cursor.fetchall()

        # Prepare bar lengths for CSS visualization.
        max_crime_count = max(
            (row["total"] for row in crime_types),
            default=1
        )

        for row in crime_types:
            row["bar_width"] = round(
                row["total"] * 100 / max_crime_count
            )

        return render_template(
            "analytics.html",
            summary=summary,
            crime_types=crime_types,
            yearly_counts=yearly_counts,
            error=None
        )

    except mysql.connector.Error:
        return render_template(
            "analytics.html",
            summary=None,
            crime_types=[],
            yearly_counts=[],
            error=(
                "Analytics could not be loaded. "
                "Check the database connection and try again."
            )
        ), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
