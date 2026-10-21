from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import mysql.connector
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from app.database import get_db_connection
from app.permissions import roles_required

case_entry_bp = Blueprint(
    "case_entry",
    __name__,
    url_prefix="/cases"
)

# Review 2 only: authentication is deferred.
# Replace this with the logged-in user's ID in the next review.


def optional_decimal(value, field_name):
    """Convert an optional form value to Decimal and validate its range."""
    value = (value or "").strip()

    if not value:
        return None

    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{field_name} must be a valid number.")

    if not result.is_finite():
        raise ValueError(f"{field_name} must be a finite number.")

    if field_name == "Latitude" and not Decimal("-90") <= result <= Decimal("90"):
        raise ValueError("Latitude must be between -90 and 90.")

    if field_name == "Longitude" and not Decimal("-180") <= result <= Decimal("180"):
        raise ValueError("Longitude must be between -180 and 180.")

    return result


def optional_datetime(value):
    """Convert a datetime-local form value into a Python datetime."""
    value = (value or "").strip()

    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Evidence collection date and time is invalid.")


@case_entry_bp.route("/new", methods=["GET", "POST"])
@roles_required("ADMIN", "INVESTIGATOR")
def new_case():
    if request.method == "GET":
        return render_template(
            "new_case.html",
            error=None,
            form_data={},
            created_case_id=request.args.get("created")
        )

    form_data = request.form

    def text_value(name):
        return (form_data.get(name) or "").strip() or None

    connection = None
    cursor = None

    try:
        # Case fields
        case_number = text_value("case_number")
        case_title = text_value("case_title")
        description = text_value("description")
        crime_type = text_value("crime_type")
        priority = text_value("priority") or "MEDIUM"
        status = text_value("status") or "OPEN"

        incident_date_text = text_value("incident_date")
        if incident_date_text:
            try:
                incident_date = date.fromisoformat(incident_date_text)
            except ValueError:
                raise ValueError("Please enter a valid incident date.")
        else:
            raise ValueError("Incident date is required.")

        # Location fields
        address = text_value("address")
        city = text_value("city")
        state = text_value("state")
        postal_code = text_value("postal_code")
        latitude = optional_decimal(form_data.get("latitude"), "Latitude")
        longitude = optional_decimal(form_data.get("longitude"), "Longitude")

        # Optional person fields
        person_name = text_value("person_name")
        person_role = text_value("person_role")
        person_notes = text_value("person_notes")

        if not person_name and (person_role or person_notes):
            raise ValueError("Enter a person's name or leave all person fields blank.")

        if person_name and not person_role:
            raise ValueError("Select a role for the person.")

        # Optional evidence fields
        evidence_code = text_value("evidence_code")
        evidence_description = text_value("evidence_description")
        evidence_category = text_value("evidence_category")
        evidence_collection_datetime = optional_datetime(
            form_data.get("evidence_collection_datetime")
        )
        evidence_storage_location = text_value("evidence_storage_location")

        evidence_details = (
            evidence_description,
            evidence_category,
            evidence_collection_datetime,
            evidence_storage_location
        )

        if not evidence_code and any(value is not None for value in evidence_details):
            raise ValueError("Enter an evidence code or leave all evidence fields blank.")

        if evidence_code and (not evidence_description or not evidence_category):
            raise ValueError(
                "Evidence description and category are required when an evidence code is provided."
            )

        # Basic required-field validation
        if not all((case_number, case_title, crime_type, address, city)):
            raise ValueError(
                "Case number, case title, crime type, address, and city are required."
            )

        # Call the stored procedure.
        connection = get_db_connection()
        cursor = connection.cursor()

        procedure_args = (
            case_number,
            case_title,
            description,
            crime_type,
            priority,
            status,
            incident_date,
            session["user_id"],
            address,
            city,
            state,
            postal_code,
            latitude,
            longitude,
            person_name,
            person_role,
            person_notes,
            evidence_code,
            evidence_description,
            evidence_category,
            evidence_collection_datetime,
            evidence_storage_location,
            0  # OUT parameter: new case ID
        )

        result = cursor.callproc(
            "sp_create_case_transactional",
            procedure_args
        )

        new_case_id = result[-1]

        if not new_case_id:
            raise RuntimeError(
                "The database procedure completed without returning a case ID."
            )

        # The stored procedure commits the transaction itself.
        return redirect(
            url_for("case_entry.new_case", created=new_case_id)
        )

    except ValueError as error:
        return render_template(
            "new_case.html",
            error=str(error),
            form_data=form_data,
            created_case_id=None
        ), 400

    except mysql.connector.Error as error:
        return render_template(
            "new_case.html",
            error=f"Database operation failed: {error.msg}",
            form_data=form_data,
            created_case_id=None
        ), 400

    except RuntimeError as error:
        return render_template(
            "new_case.html",
            error=str(error),
            form_data=form_data,
            created_case_id=None
        ), 500

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()