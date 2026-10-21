from datetime import date, datetime

import mysql.connector
from flask import Blueprint, render_template, request, redirect, url_for
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.database import get_db_connection
from app.permissions import roles_required

investigation_bp = Blueprint(
    "investigation",
    __name__,
    url_prefix="/investigation"
)
PAGE_SIZE = 25


@investigation_bp.route("/", methods=["GET"])
def index():
    case_number = (request.args.get("case_number") or "").strip()
    crime_type = (request.args.get("crime_type") or "").strip()
    priority = (request.args.get("priority") or "").strip().upper()
    status = (request.args.get("status") or "").strip().upper()

    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1

    # Validate filter values before querying MySQL.
    if priority not in ("", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
        priority = ""

    if status not in ("", "OPEN", "UNDER_INVESTIGATION", "SOLVED", "CLOSED"):
        status = ""

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        conditions = []
        parameters = []

        # Prefix search can use the indexed case_number column.
        if case_number:
            conditions.append("c.case_number LIKE %s")
            parameters.append(case_number + "%")

        if crime_type:
            conditions.append("c.crime_type = %s")
            parameters.append(crime_type)

        if priority:
            conditions.append("c.priority = %s")
            parameters.append(priority)

        if status:
            conditions.append("c.status = %s")
            parameters.append(status)

        where_sql = ""
        if conditions:
            where_sql = "WHERE " + " AND ".join(conditions)

        offset = (page - 1) * PAGE_SIZE

        # Fetch only one page. The indexed case_id orders newest
        # inserted cases first. Related counts use indexed foreign keys.
        query = f"""
            SELECT
                c.case_id,
                c.case_number,
                c.case_title,
                c.crime_type,
                c.priority,
                c.status,
                c.incident_date,

                (
                    SELECT l.address
                    FROM case_locations cl
                    JOIN locations l
                        ON l.location_id = cl.location_id
                    WHERE cl.case_id = c.case_id
                    ORDER BY cl.location_id
                    LIMIT 1
                ) AS incident_address,

                (
                    SELECT COUNT(*)
                    FROM evidence e
                    WHERE e.case_id = c.case_id
                ) AS evidence_count,

                (
                    SELECT COUNT(*)
                    FROM case_person cp
                    WHERE cp.case_id = c.case_id
                ) AS person_count

            FROM cases c
            {where_sql}
            ORDER BY c.case_id DESC
            LIMIT %s OFFSET %s
        """

        parameters.extend([PAGE_SIZE + 1, offset])
        cursor.execute(query, tuple(parameters))

        rows = cursor.fetchall()
        has_next = len(rows) > PAGE_SIZE
        case_rows = rows[:PAGE_SIZE]

        return render_template(
            "investigation.html",
            cases=case_rows,
            case_number=case_number,
            crime_type=crime_type,
            priority=priority,
            status=status,
            page=page,
            has_next=has_next,
            error=None
        )

    except mysql.connector.Error:
        # Avoid displaying database credentials or internal details.
        return render_template(
            "investigation.html",
            cases=[],
            case_number=case_number,
            crime_type=crime_type,
            priority=priority,
            status=status,
            page=page,
            has_next=False,
            error="The case list could not be loaded. Check the database connection and try again."
        ), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

@investigation_bp.route("/case/<int:case_id>", methods=["GET"])
def case_detail(case_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                c.case_id,
                c.case_number,
                c.case_title,
                c.description,
                c.crime_type,
                c.priority,
                c.status,
                c.incident_date,
                c.report_date,
                creator.username AS created_by_username,
                investigator.full_name AS lead_investigator
            FROM cases c
            LEFT JOIN users creator
                ON creator.user_id = c.created_by
            LEFT JOIN users investigator
                ON investigator.user_id = c.lead_investigator_id
            WHERE c.case_id = %s
        """, (case_id,))

        case_record = cursor.fetchone()

        if not case_record:
            return render_template(
                "case_detail.html",
                case_record=None,
                error="Case not found."
            ), 404

        # Locations linked to the case
        cursor.execute("""
            SELECT
                l.location_id,
                l.address,
                l.city,
                l.state,
                l.postal_code,
                l.latitude,
                l.longitude,
                cl.location_type
            FROM case_locations cl
            JOIN locations l ON l.location_id = cl.location_id
            WHERE cl.case_id = %s
            ORDER BY l.location_id
        """, (case_id,))
        locations = cursor.fetchall()

        # People and their roles in this case
        cursor.execute("""
            SELECT
                p.person_id,
                p.full_name,
                p.date_of_birth,
                p.gender,
                cp.person_role,
                cp.notes
            FROM case_person cp
            JOIN persons p ON p.person_id = cp.person_id
            WHERE cp.case_id = %s
            ORDER BY cp.person_role, p.full_name
        """, (case_id,))
        people = cursor.fetchall()

        # Evidence records
        cursor.execute("""
            SELECT
                e.evidence_id,
                e.evidence_code,
                e.description,
                e.category,
                e.collection_datetime,
                e.status,
                e.storage_location,
                e.serial_number,
                e.notes
            FROM evidence e
            WHERE e.case_id = %s
            ORDER BY e.evidence_id DESC
        """, (case_id,))
        evidence = cursor.fetchall()

        # Forensic examination records
        cursor.execute("""
            SELECT
                ft.test_id,
                e.evidence_code,
                ft.test_type,
                ft.status,
                ft.request_date,
                ft.completed_date,
                ft.result,
                ft.conclusion,
                requester.username AS requested_by,
                analyst.full_name AS analyst
            FROM forensic_tests ft
            JOIN evidence e ON e.evidence_id = ft.evidence_id
            LEFT JOIN users requester
                ON requester.user_id = ft.requested_by
            LEFT JOIN users analyst
                ON analyst.user_id = ft.analyst_id
            WHERE e.case_id = %s
            ORDER BY ft.request_date DESC, ft.test_id DESC
        """, (case_id,))
        forensic_tests = cursor.fetchall()

        # Evidence custody history
        cursor.execute("""
            SELECT
                ec.custody_id,
                e.evidence_code,
                source_user.username AS from_user,
                target_user.username AS to_user,
                ec.transfer_datetime,
                ec.notes
            FROM evidence_custody ec
            JOIN evidence e ON e.evidence_id = ec.evidence_id
            LEFT JOIN users source_user
                ON source_user.user_id = ec.from_user_id
            JOIN users target_user
                ON target_user.user_id = ec.to_user_id
            WHERE e.case_id = %s
            ORDER BY ec.transfer_datetime DESC, ec.custody_id DESC
        """, (case_id,))
        custody_records = cursor.fetchall()

        # Digital file metadata, not the actual file contents
        cursor.execute("""
            SELECT
                df.file_id,
                e.evidence_code,
                df.file_name,
                df.file_type,
                df.file_size,
                df.file_path,
                df.checksum,
                uploader.username AS uploaded_by,
                df.uploaded_at
            FROM digital_files df
            JOIN evidence e ON e.evidence_id = df.evidence_id
            LEFT JOIN users uploader
                ON uploader.user_id = df.uploaded_by
            WHERE e.case_id = %s
            ORDER BY df.uploaded_at DESC, df.file_id DESC
        """, (case_id,))
        digital_files = cursor.fetchall()

        # Investigation timeline
        cursor.execute("""
            SELECT
                ct.timeline_id,
                ct.event_time,
                ct.event_type,
                ct.description,
                u.username AS created_by
            FROM case_timeline ct
            LEFT JOIN users u ON u.user_id = ct.created_by
            WHERE ct.case_id = %s
            ORDER BY ct.event_time DESC, ct.timeline_id DESC
            LIMIT 100
        """, (case_id,))
        timeline = cursor.fetchall()

        # Assigned investigation tasks
        cursor.execute("""
            SELECT
                t.task_id,
                t.title,
                t.description,
                t.priority,
                t.status,
                t.due_date,
                t.completed_at,
                u.username AS assigned_to
            FROM investigation_tasks t
            LEFT JOIN users u ON u.user_id = t.assigned_to
            WHERE t.case_id = %s
            ORDER BY
                CASE t.status
                    WHEN 'IN_PROGRESS' THEN 1
                    WHEN 'PENDING' THEN 2
                    WHEN 'COMPLETED' THEN 3
                    WHEN 'CANCELLED' THEN 4
                END,
                t.due_date,
                t.task_id
        """, (case_id,))
        tasks = cursor.fetchall()

        # Previously saved relationships with other cases
        cursor.execute("""
            SELECT
                cr.relationship_id,
                cr.relationship_type,
                cr.notes,
                other.case_id AS related_case_id,
                other.case_number AS related_case_number,
                other.case_title AS related_case_title
            FROM case_relationships cr
            JOIN cases other
                ON other.case_id = CASE
                    WHEN cr.case_id_1 = %s THEN cr.case_id_2
                    ELSE cr.case_id_1
                END
            WHERE cr.case_id_1 = %s
               OR cr.case_id_2 = %s
            ORDER BY cr.created_at DESC
        """, (case_id, case_id, case_id))
        relationships = cursor.fetchall()

        return render_template(
            "case_detail.html",
            case_record=case_record,
            locations=locations,
            people=people,
            evidence=evidence,
            forensic_tests=forensic_tests,
            custody_records=custody_records,
            digital_files=digital_files,
            timeline=timeline,
            tasks=tasks,
            relationships=relationships,
            error=None,
            notice=request.args.get("notice")
        )

    except mysql.connector.Error:
        return render_template(
            "case_detail.html",
            case_record=None,
            error="The case details could not be loaded. Check the database connection and try again."
        ), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

@investigation_bp.route("/case/<int:case_id>/connections", methods=["GET"])
def case_connections(case_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT case_id, case_number, case_title, crime_type, incident_date
            FROM cases
            WHERE case_id = %s
        """, (case_id,))

        case_record = cursor.fetchone()

        if not case_record:
            return "Case not found.", 404

        # Run Connection Finder only when the user requests it.
        cursor.callproc(
            "sp_find_case_connections",
            (case_id, 7)
        )

        connections = []

        for result in cursor.stored_results():
            try:
                connections = result.fetchall()
            finally:
                result.close()

        return render_template(
            "case_connections.html",
            case_record=case_record,
            connections=connections,
            error=None
        )

    except mysql.connector.Error:
        return render_template(
            "case_connections.html",
            case_record=None,
            connections=[],
            error="Connection Finder could not complete. Check the database connection and try again."
        ), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

@investigation_bp.route("/case/<int:case_id>/timeline/add", methods=["POST"])
@roles_required("ADMIN", "INVESTIGATOR")
def add_timeline_event(case_id):
    event_type = (request.form.get("event_type") or "").strip()
    description = (request.form.get("description") or "").strip()
    event_time_text = (request.form.get("event_time") or "").strip()

    if not event_type or not description:
        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="timeline_required"
        ))

    try:
        event_time = (
            datetime.fromisoformat(event_time_text)
            if event_time_text
            else None
        )
    except ValueError:
        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="timeline_invalid_date"
        ))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT 1 FROM cases WHERE case_id = %s",
            (case_id,)
        )
        if cursor.fetchone() is None:
            connection.rollback()
            return "Case not found.", 404

        if event_time is None:
            cursor.execute("""
                INSERT INTO case_timeline
                    (case_id, event_type, description, created_by)
                VALUES (%s, %s, %s, %s)
            """, (case_id, event_type, description, 1))
        else:
            cursor.execute("""
                INSERT INTO case_timeline
                    (case_id, event_time, event_type, description, created_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (case_id, event_time, event_type, description, 1))

        connection.commit()

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="timeline_added"
        ))

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="timeline_failed"
        ))

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


@investigation_bp.route("/case/<int:case_id>/tasks/add", methods=["POST"])
@roles_required("ADMIN", "INVESTIGATOR")
def add_investigation_task(case_id):
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    priority = (request.form.get("priority") or "MEDIUM").strip().upper()
    assigned_to_text = (request.form.get("assigned_to") or "").strip()
    due_date_text = (request.form.get("due_date") or "").strip()

    if not title:
        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="task_title_required"
        ))

    if priority not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="task_invalid_priority"
        ))

    try:
        assigned_to = int(assigned_to_text) if assigned_to_text else None
        due_date = date.fromisoformat(due_date_text) if due_date_text else None
    except ValueError:
        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="task_invalid_value"
        ))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT 1 FROM cases WHERE case_id = %s",
            (case_id,)
        )
        if cursor.fetchone() is None:
            connection.rollback()
            return "Case not found.", 404

        if assigned_to is not None:
            cursor.execute(
                "SELECT 1 FROM users WHERE user_id = %s",
                (assigned_to,)
            )
            if cursor.fetchone() is None:
                connection.rollback()
                return redirect(url_for(
                    "investigation.case_detail",
                    case_id=case_id,
                    notice="task_invalid_assignee"
                ))

        cursor.execute("""
            INSERT INTO investigation_tasks
                (case_id, assigned_to, title, description,
                 priority, status, due_date)
            VALUES (%s, %s, %s, %s, %s, 'PENDING', %s)
        """, (
            case_id,
            assigned_to,
            title,
            description,
            priority,
            due_date
        ))

        connection.commit()

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="task_added"
        ))

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="task_failed"
        ))

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
@investigation_bp.route(
    "/case/<int:case_id>/tasks/<int:task_id>/status",
    methods=["POST"]
)
@roles_required("ADMIN", "INVESTIGATOR")
def update_task_status(case_id, task_id):
    new_status = (request.form.get("status") or "").strip().upper()

    allowed_statuses = {
        "PENDING",
        "IN_PROGRESS",
        "COMPLETED",
        "CANCELLED"
    }

    if new_status not in allowed_statuses:
        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="task_invalid_status"
        ))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor()

        # Make sure this task belongs to the selected case.
        cursor.execute("""
            SELECT task_id
            FROM investigation_tasks
            WHERE task_id = %s
              AND case_id = %s
            FOR UPDATE
        """, (task_id, case_id))

        if cursor.fetchone() is None:
            connection.rollback()
            return "Task not found for this case.", 404

        cursor.execute("""
            UPDATE investigation_tasks
            SET
                status = %s,
                completed_at = CASE
                    WHEN %s = 'COMPLETED'
                        THEN COALESCE(completed_at, CURRENT_TIMESTAMP)
                    ELSE NULL
                END
            WHERE task_id = %s
              AND case_id = %s
        """, (new_status, new_status, task_id, case_id))

        connection.commit()

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="task_status_updated"
        ))

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="task_status_failed"
        ))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

@investigation_bp.route(
    "/case/<int:case_id>/connections/save",
    methods=["POST"]
)
@roles_required("ADMIN", "INVESTIGATOR")
def save_case_connection(case_id):
    try:
        related_case_id = int(
            request.form.get("related_case_id", "")
        )
    except (ValueError, TypeError):
        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="connection_invalid"
        ))

    if related_case_id == case_id:
        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="connection_invalid"
        ))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        # Confirm that both cases exist.
        cursor.execute("""
            SELECT case_id, case_number, crime_type, incident_date
            FROM cases
            WHERE case_id = %s
        """, (case_id,))
        base_case = cursor.fetchone()

        cursor.execute("""
            SELECT case_id, case_number, crime_type, incident_date
            FROM cases
            WHERE case_id = %s
        """, (related_case_id,))
        candidate = cursor.fetchone()

        if not base_case or not candidate:
            connection.rollback()
            return redirect(url_for(
                "investigation.case_detail",
                case_id=case_id,
                notice="connection_invalid"
            ))

        # Never mix clearly labelled synthetic demo cases
        # with source-derived cases.
        base_is_demo = base_case["case_number"].startswith("DEMO-CASE-")
        candidate_is_demo = candidate["case_number"].startswith("DEMO-CASE-")

        if base_is_demo != candidate_is_demo:
            connection.rollback()
            return redirect(url_for(
                "investigation.case_detail",
                case_id=case_id,
                notice="connection_provenance_mismatch"
            ))

        # Count exact shared location IDs.
        cursor.execute("""
            SELECT COUNT(DISTINCT a.location_id) AS shared_count
            FROM case_locations a
            JOIN case_locations b
                ON b.location_id = a.location_id
            WHERE a.case_id = %s
              AND b.case_id = %s
        """, (case_id, related_case_id))

        shared_count = cursor.fetchone()["shared_count"]

        # Calculate the available matching criteria on the server.
        same_crime_type = (
            base_case["crime_type"] == candidate["crime_type"]
        )

        date_difference = abs(
            (base_case["incident_date"] - candidate["incident_date"]).days
        )

        within_seven_days = date_difference <= 7

        if not shared_count and not same_crime_type and not within_seven_days:
            connection.rollback()
            return redirect(url_for(
                "investigation.case_detail",
                case_id=case_id,
                notice="connection_invalid"
            ))

        location_points = 25 if shared_count else 0
        crime_type_points = 15 if same_crime_type else 0
        date_points = 10 if within_seven_days else 0

        score = location_points + crime_type_points + date_points

        reasons = [
            f"Shared locations: {shared_count} "
            f"({location_points} points)",
            f"Same crime type: {'yes' if same_crime_type else 'no'} "
            f"({crime_type_points} points)",
            f"Incident dates within seven days: "
            f"{'yes' if within_seven_days else 'no'} "
            f"({date_points} points)"
        ]

        notes = (
            f"POTENTIAL CONNECTION - similarity score {score}/50. "
            + "; ".join(reasons)
            + ". Requires investigator review; not proof of a connection."
        )

        # Store the pair in a consistent order.
        case_id_1 = min(case_id, related_case_id)
        case_id_2 = max(case_id, related_case_id)

        cursor.execute("""
            INSERT INTO case_relationships
                (case_id_1, case_id_2, relationship_type, notes)
            VALUES (%s, %s, %s, %s)
        """, (
            case_id_1,
            case_id_2,
            "POTENTIAL_CONNECTION",
            notes
        ))

        connection.commit()

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="connection_saved"
        ))

    except mysql.connector.IntegrityError as error:
        if connection is not None:
            connection.rollback()

        notice = (
            "connection_exists"
            if error.errno == 1062
            else "connection_failed"
        )

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice=notice
        ))

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="connection_failed"
        ))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

@investigation_bp.route(
    "/case/<int:case_id>/edit",
    methods=["GET", "POST"]
)
@roles_required("ADMIN", "INVESTIGATOR")
def edit_case(case_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                case_id,
                case_number,
                case_title,
                description,
                crime_type,
                priority,
                status,
                incident_date
            FROM cases
            WHERE case_id = %s
        """, (case_id,))

        case_record = cursor.fetchone()

        if not case_record:
            return "Case not found.", 404

        if request.method == "GET":
            return render_template(
                "edit_case.html",
                case_record=case_record,
                error=None
            )

        # Read form data.
        case_number = (request.form.get("case_number") or "").strip()
        case_title = (request.form.get("case_title") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        crime_type = (request.form.get("crime_type") or "").strip()
        priority = (request.form.get("priority") or "").strip().upper()
        status = (request.form.get("status") or "").strip().upper()
        incident_date_text = (request.form.get("incident_date") or "").strip()

        # Preserve submitted values when displaying validation errors.
        form_record = dict(case_record)
        form_record.update({
            "case_number": case_number,
            "case_title": case_title,
            "description": description or "",
            "crime_type": crime_type,
            "priority": priority,
            "status": status,
            "incident_date": incident_date_text
        })

        if not case_number or not case_title or not crime_type:
            return render_template(
                "edit_case.html",
                case_record=form_record,
                error="Case number, title, and crime type are required."
            ), 400

        if priority not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            return render_template(
                "edit_case.html",
                case_record=form_record,
                error="Select a valid priority."
            ), 400

        if status not in ("OPEN", "UNDER_INVESTIGATION", "SOLVED", "CLOSED"):
            return render_template(
                "edit_case.html",
                case_record=form_record,
                error="Select a valid case status."
            ), 400

        try:
            incident_date = date.fromisoformat(incident_date_text)
        except ValueError:
            return render_template(
                "edit_case.html",
                case_record=form_record,
                error="Enter a valid incident date."
            ), 400

        # Use the prototype's system account for audit attribution.
        # Authentication will replace this fixed ID in the next review.
        # Finish the earlier read transaction before starting the write transaction.
        connection.commit()
        connection.start_transaction()

        cursor.execute("SET @app_user_id = %s", (session["user_id"],))

        cursor.execute("""
            UPDATE cases
            SET
                case_number = %s,
                case_title = %s,
                description = %s,
                crime_type = %s,
                priority = %s,
                status = %s,
                incident_date = %s
            WHERE case_id = %s
        """, (
            case_number,
            case_title,
            description,
            crime_type,
            priority,
            status,
            incident_date,
            case_id
        ))

        # The existing AFTER UPDATE trigger writes the audit record.
        connection.commit()

        cursor.execute("SET @app_user_id = NULL")

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="case_updated"
        ))

    except mysql.connector.IntegrityError as error:
        if connection is not None:
            connection.rollback()

        if cursor is not None:
            cursor.execute("SET @app_user_id = NULL")

        error_message = (
            "That case number is already in use."
            if error.errno == 1062
            else "The case could not be updated because of a database constraint."
        )

        return render_template(
            "edit_case.html",
            case_record=form_record if "form_record" in locals() else case_record,
            error=error_message
        ), 400

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        if cursor is not None:
            cursor.execute("SET @app_user_id = NULL")

        return render_template(
            "edit_case.html",
            case_record=form_record if "form_record" in locals() else case_record,
            error="A database error prevented the case from being updated."
        ), 500

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

@investigation_bp.route(
    "/case/<int:case_id>/person/<int:person_id>/edit",
    methods=["GET", "POST"]
)
@roles_required("ADMIN", "INVESTIGATOR")
def edit_person(case_id, person_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Only allow editing a person linked to this case.
        cursor.execute("""
            SELECT
                p.person_id,
                p.full_name,
                p.date_of_birth,
                p.gender,
                p.phone,
                p.email,
                p.address
            FROM persons p
            JOIN case_person cp
                ON cp.person_id = p.person_id
            WHERE cp.case_id = %s
              AND p.person_id = %s
            LIMIT 1
        """, (case_id, person_id))

        person = cursor.fetchone()

        if not person:
            return "Person not found for this case.", 404

        if request.method == "GET":
            return render_template(
                "edit_person.html",
                case_id=case_id,
                person=person,
                error=None
            )

        # Read the submitted form.
        full_name = (request.form.get("full_name") or "").strip()
        dob_text = (request.form.get("date_of_birth") or "").strip()
        gender = (request.form.get("gender") or "").strip() or None
        phone = (request.form.get("phone") or "").strip() or None
        email = (request.form.get("email") or "").strip() or None
        address = (request.form.get("address") or "").strip() or None

        form_person = dict(person)
        form_person.update({
            "full_name": full_name,
            "date_of_birth": dob_text or None,
            "gender": gender,
            "phone": phone,
            "email": email,
            "address": address
        })

        if not full_name:
            return render_template(
                "edit_person.html",
                case_id=case_id,
                person=form_person,
                error="Full name is required."
            ), 400

        if len(full_name) > 100:
            return render_template(
                "edit_person.html",
                case_id=case_id,
                person=form_person,
                error="Full name cannot exceed 100 characters."
            ), 400

        if gender and len(gender) > 20:
            return render_template(
                "edit_person.html",
                case_id=case_id,
                person=form_person,
                error="Gender cannot exceed 20 characters."
            ), 400

        if phone and len(phone) > 20:
            return render_template(
                "edit_person.html",
                case_id=case_id,
                person=form_person,
                error="Phone cannot exceed 20 characters."
            ), 400

        if email and len(email) > 100:
            return render_template(
                "edit_person.html",
                case_id=case_id,
                person=form_person,
                error="Email cannot exceed 100 characters."
            ), 400

        if address and len(address) > 255:
            return render_template(
                "edit_person.html",
                case_id=case_id,
                person=form_person,
                error="Address cannot exceed 255 characters."
            ), 400

        try:
            date_of_birth = (
                date.fromisoformat(dob_text)
                if dob_text else None
            )
        except ValueError:
            return render_template(
                "edit_person.html",
                case_id=case_id,
                person=form_person,
                error="Enter a valid date of birth."
            ), 400

        # Start a fresh write transaction after the earlier SELECT.
        connection.commit()
        connection.start_transaction()

        # Review 2 prototype account; authentication is deferred.
        cursor.execute("SET @app_user_id = %s", (session["user_id"],))

        cursor.execute("""
            UPDATE persons
            SET
                full_name = %s,
                date_of_birth = %s,
                gender = %s,
                phone = %s,
                email = %s,
                address = %s
            WHERE person_id = %s
        """, (
            full_name,
            date_of_birth,
            gender,
            phone,
            email,
            address,
            person_id
        ))

        # The PERSONS AFTER UPDATE trigger records old/new values.
        connection.commit()

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="person_updated"
        ))

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        return render_template(
            "edit_person.html",
            case_id=case_id,
            person=form_person if "form_person" in locals() else person,
            error="A database error prevented the person from being updated."
        ), 500

    finally:
        if cursor is not None:
            try:
                cursor.execute("SET @app_user_id = NULL")
            except mysql.connector.Error:
                pass
            cursor.close()

        if connection is not None:
            connection.close()

@investigation_bp.route(
    "/case/<int:case_id>/evidence/<int:evidence_id>/edit",
    methods=["GET", "POST"]
)
@roles_required("ADMIN", "INVESTIGATOR", "FORENSIC_ANALYST")
def edit_evidence(case_id, evidence_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Only edit evidence belonging to the selected case.
        cursor.execute("""
            SELECT
                evidence_id,
                case_id,
                evidence_code,
                description,
                category,
                collection_datetime,
                status,
                storage_location,
                serial_number,
                notes
            FROM evidence
            WHERE case_id = %s
              AND evidence_id = %s
        """, (case_id, evidence_id))

        evidence = cursor.fetchone()

        if not evidence:
            return "Evidence not found for this case.", 404

        if request.method == "GET":
            form_evidence = dict(evidence)

            if form_evidence["collection_datetime"] is not None:
                form_evidence["collection_datetime"] = (
                    form_evidence["collection_datetime"].strftime(
                        "%Y-%m-%dT%H:%M"
                    )
                )

            return render_template(
                "edit_evidence.html",
                case_id=case_id,
                evidence=form_evidence,
                error=None
            )

        # Read submitted form values.
        evidence_code = (
            request.form.get("evidence_code") or ""
        ).strip()

        description = (
            request.form.get("description") or ""
        ).strip()

        category = (
            request.form.get("category") or ""
        ).strip()

        status = (
            request.form.get("status") or ""
        ).strip().upper()

        collection_text = (
            request.form.get("collection_datetime") or ""
        ).strip()

        storage_location = (
            request.form.get("storage_location") or ""
        ).strip() or None

        serial_number = (
            request.form.get("serial_number") or ""
        ).strip() or None

        notes = (
            request.form.get("notes") or ""
        ).strip() or None

        form_evidence = {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "evidence_code": evidence_code,
            "description": description,
            "category": category,
            "collection_datetime": collection_text,
            "status": status,
            "storage_location": storage_location or "",
            "serial_number": serial_number or "",
            "notes": notes or ""
        }

        # Validate required fields and database limits.
        if not evidence_code or not description or not category:
            return render_template(
                "edit_evidence.html",
                case_id=case_id,
                evidence=form_evidence,
                error="Evidence code, description, and category are required."
            ), 400

        if len(evidence_code) > 30:
            raise ValueError("Evidence code cannot exceed 30 characters.")

        if len(category) > 100:
            raise ValueError("Category cannot exceed 100 characters.")

        if storage_location and len(storage_location) > 255:
            raise ValueError("Storage location cannot exceed 255 characters.")

        if serial_number and len(serial_number) > 100:
            raise ValueError("Serial number cannot exceed 100 characters.")

        if status not in (
            "COLLECTED", "IN_LAB", "STORED", "RELEASED", "DESTROYED"
        ):
            return render_template(
                "edit_evidence.html",
                case_id=case_id,
                evidence=form_evidence,
                error="Select a valid evidence status."
            ), 400

        try:
            collection_datetime = (
                datetime.fromisoformat(collection_text)
                if collection_text else None
            )
        except ValueError:
            return render_template(
                "edit_evidence.html",
                case_id=case_id,
                evidence=form_evidence,
                error="Enter a valid collection date and time."
            ), 400

        # Start a fresh write transaction.
        connection.commit()
        connection.start_transaction()

        # Review 2 prototype account; authentication is deferred.
        cursor.execute("SET @app_user_id = %s", (session["user_id"],))
        cursor.execute("""
            UPDATE evidence
            SET
                evidence_code = %s,
                description = %s,
                category = %s,
                collection_datetime = %s,
                status = %s,
                storage_location = %s,
                serial_number = %s,
                notes = %s
            WHERE case_id = %s
              AND evidence_id = %s
        """, (
            evidence_code,
            description,
            category,
            collection_datetime,
            status,
            storage_location,
            serial_number,
            notes,
            case_id,
            evidence_id
        ))

        # The EVIDENCE AFTER UPDATE trigger records the update.
        connection.commit()

        return redirect(url_for(
            "investigation.case_detail",
            case_id=case_id,
            notice="evidence_updated"
        ))

    except ValueError as error:
        return render_template(
            "edit_evidence.html",
            case_id=case_id,
            evidence=form_evidence if "form_evidence" in locals() else evidence,
            error=str(error)
        ), 400

    except mysql.connector.IntegrityError as error:
        if connection is not None:
            connection.rollback()

        message = (
            "That evidence code is already in use."
            if error.errno == 1062
            else "A database constraint prevented the evidence update."
        )

        return render_template(
            "edit_evidence.html",
            case_id=case_id,
            evidence=form_evidence if "form_evidence" in locals() else evidence,
            error=message
        ), 400

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        return render_template(
            "edit_evidence.html",
            case_id=case_id,
            evidence=form_evidence if "form_evidence" in locals() else evidence,
            error="A database error prevented the evidence from being updated."
        ), 500

    finally:
        if cursor is not None:
            try:
                cursor.execute("SET @app_user_id = NULL")
            except mysql.connector.Error:
                pass
            cursor.close()

        if connection is not None:
            connection.close()

