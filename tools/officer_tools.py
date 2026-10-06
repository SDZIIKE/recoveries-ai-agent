import pandas as pd

from database.google_sheets import open_database
from audit.logger import log_event


# ============================================================
# OFFICER AUTHORIZATION
# ============================================================

def verify_officer(officer_id):
    """
    Verify whether an officer is authorized to perform
    payment-plan approval actions.

    Authorization requirements:
    1. Officer ID must exist.
    2. Officer status must be ACTIVE.
    3. Officer role must be RECOVERIES OFFICER.
    """

    try:
        # Connect to Google Sheets database
        spreadsheet = open_database()

        # Open Officers worksheet
        worksheet = spreadsheet.worksheet("Officers")

        # Retrieve officer records
        records = worksheet.get_all_records()
        officers = pd.DataFrame(records)

        # Check whether any officers exist
        if officers.empty:
            return {
                "authorized": False,
                "status": "NO_OFFICERS_FOUND",
                "message": "No officer records were found."
            }

        # Find officer by ID
        officer = officers[
            officers["officer_id"].astype(str).str.strip()
            == str(officer_id).strip()
        ]

        # Officer does not exist
        if officer.empty:
            return {
                "authorized": False,
                "status": "OFFICER_NOT_FOUND",
                "message": (
                    "Officer ID was not found in the authorized "
                    "officers database."
                )
            }

        # Get the matching officer record
        officer = officer.iloc[0]

        # Check officer status
        status = str(officer["status"]).strip().upper()

        if status != "ACTIVE":
            return {
                "authorized": False,
                "status": "OFFICER_INACTIVE",
                "officer_id": str(officer["officer_id"]),
                "message": (
                    "Officer is not currently authorized to "
                    "perform approval actions."
                )
            }

        # Check officer role
        role = str(officer["role"]).strip().upper()

        if role != "RECOVERIES OFFICER":
            return {
                "authorized": False,
                "status": "INVALID_OFFICER_ROLE",
                "officer_id": str(officer["officer_id"]),
                "message": (
                    "Officer does not have the required "
                    "Recoveries Officer role."
                )
            }

        # Officer successfully verified
        return {
            "authorized": True,
            "status": "OFFICER_VERIFIED",
            "officer_id": str(officer["officer_id"]),
            "full_name": str(officer["full_name"]),
            "department": str(officer["department"]),
            "role": str(officer["role"]),
            "message": (
                "Officer is authorized to perform approval actions."
            )
        }

    except Exception as error:

        return {
            "authorized": False,
            "status": "OFFICER_VERIFICATION_ERROR",
            "message": str(error)
        }


# ============================================================
# PENDING PAYMENT-PLAN REQUESTS
# ============================================================

def get_pending_payment_plan_requests(officer_id):
    """
    Retrieve all pending payment-plan requests for an authorized
    Recoveries Officer.

    Security controls:
    1. Officer must be ACTIVE.
    2. Officer role must be RECOVERIES OFFICER.
    3. Only requests with approval_status = PENDING are returned.
    4. This function is read-only.
    5. No payment-plan request is modified.
    6. No payment plan is approved or rejected.
    7. Access is recorded in Audit Logs.
    """

    officer_id = str(officer_id or "").strip()

    # --------------------------------------------------------
    # 1. VALIDATE OFFICER ID
    # --------------------------------------------------------

    if not officer_id:
        return {
            "success": False,
            "status": "OFFICER_ID_REQUIRED",
            "message": "Officer ID is required."
        }

    try:

        # ----------------------------------------------------
        # 2. VERIFY OFFICER AUTHORIZATION
        # ----------------------------------------------------

        officer_result = verify_officer(officer_id)

        if not officer_result.get("authorized"):

            try:
                log_event(
                    customer_id="UNKNOWN",
                    event_type="OFFICER_AUTHORIZATION",
                    description=(
                        f"Unauthorized officer {officer_id} attempted "
                        "to retrieve pending payment-plan requests. "
                        f"Reason: {officer_result.get('message')}"
                    ),
                    status="BLOCKED",
                    agent="OFFICER_PORTAL"
                )
            except Exception:
                pass

            return {
                "success": False,
                "status": officer_result.get(
                    "status",
                    "OFFICER_NOT_AUTHORIZED"
                ),
                "message": officer_result.get(
                    "message",
                    "Officer is not authorized."
                )
            }

        # ----------------------------------------------------
        # 3. OPEN DATABASE
        # ----------------------------------------------------

        spreadsheet = open_database()

        # ----------------------------------------------------
        # 4. OPEN PAYMENT PLAN REQUESTS WORKSHEET
        # ----------------------------------------------------

        worksheet = spreadsheet.worksheet(
            "Payment Plan Requests"
        )

        # ----------------------------------------------------
        # 5. RETRIEVE REQUEST RECORDS
        # ----------------------------------------------------

        records = worksheet.get_all_records()
        requests_df = pd.DataFrame(records)

        # ----------------------------------------------------
        # 6. CHECK WHETHER REQUESTS EXIST
        # ----------------------------------------------------

        if requests_df.empty:

            try:
                log_event(
                    customer_id="UNKNOWN",
                    event_type="PENDING_REQUEST_LOOKUP",
                    description=(
                        f"Officer {officer_id} checked for pending "
                        "payment-plan requests. No requests were found."
                    ),
                    status="SUCCESS",
                    agent=officer_id
                )
            except Exception:
                pass

            return {
                "success": True,
                "status": "NO_REQUESTS_FOUND",
                "requests": [],
                "count": 0,
                "message": (
                    "No payment-plan requests were found."
                )
            }

        # ----------------------------------------------------
        # 7. VALIDATE REQUIRED COLUMN
        # ----------------------------------------------------

        required_columns = [
            "approval_status"
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in requests_df.columns
        ]

        if missing_columns:

            try:
                log_event(
                    customer_id="UNKNOWN",
                    event_type="PENDING_REQUEST_LOOKUP",
                    description=(
                        f"Officer {officer_id} attempted to retrieve "
                        "pending payment-plan requests, but the "
                        f"database is missing required columns: "
                        f"{', '.join(missing_columns)}."
                    ),
                    status="FAILED",
                    agent="OFFICER_PORTAL"
                )
            except Exception:
                pass

            return {
                "success": False,
                "status": "INVALID_REQUEST_DATABASE",
                "message": (
                    "The Payment Plan Requests worksheet is missing "
                    "required columns."
                )
            }

        # ----------------------------------------------------
        # 8. FILTER PENDING REQUESTS
        # ----------------------------------------------------

        pending_requests = requests_df[
            requests_df["approval_status"]
            .astype(str)
            .str.strip()
            .str.upper()
            == "PENDING"
        ].copy()

        # ----------------------------------------------------
        # 9. NO PENDING REQUESTS
        # ----------------------------------------------------

        if pending_requests.empty:

            try:
                log_event(
                    customer_id="UNKNOWN",
                    event_type="PENDING_REQUEST_LOOKUP",
                    description=(
                        f"Officer {officer_id} checked for pending "
                        "payment-plan requests. No pending requests "
                        "are currently available."
                    ),
                    status="SUCCESS",
                    agent=officer_id
                )
            except Exception:
                pass

            return {
                "success": True,
                "status": "NO_PENDING_REQUESTS",
                "requests": [],
                "count": 0,
                "message": (
                    "There are currently no pending payment-plan "
                    "requests requiring officer review."
                )
            }

        # ----------------------------------------------------
        # 10. SELECT OFFICER-SAFE FIELDS
        # ----------------------------------------------------

        safe_fields = [
            "request_id",
            "customer_id",
            "loan_id",
            "proposed_amount",
            "frequency",
            "start_date",
            "next_payment_date",
            "number_of_payments",
            "customer_consent",
            "approval_status",
            "submitted_at",
            "reviewed_by",
            "approved_by",
            "approved_at",
            "rejection_reason",
        ]

        available_fields = [
            field
            for field in safe_fields
            if field in pending_requests.columns
        ]

        pending_requests = pending_requests[
            available_fields
        ].copy()

        # ----------------------------------------------------
        # 11. CLEAN NULL VALUES
        # ----------------------------------------------------

        pending_requests = pending_requests.fillna("")

        # ----------------------------------------------------
        # 12. SORT OLDEST REQUESTS FIRST
        # ----------------------------------------------------

        if "submitted_at" in pending_requests.columns:

            pending_requests["_sort_date"] = pd.to_datetime(
                pending_requests["submitted_at"],
                errors="coerce"
            )

            pending_requests = pending_requests.sort_values(
                by="_sort_date",
                ascending=True,
                na_position="last"
            )

            pending_requests = pending_requests.drop(
                columns=["_sort_date"]
            )

        # ----------------------------------------------------
        # 13. CONVERT TO LIST OF DICTIONARIES
        # ----------------------------------------------------

        request_list = pending_requests.to_dict(
            orient="records"
        )

        # ----------------------------------------------------
        # 14. AUDIT SUCCESSFUL LOOKUP
        # ----------------------------------------------------

        try:
            log_event(
                customer_id="UNKNOWN",
                event_type="PENDING_REQUEST_LOOKUP",
                description=(
                    f"Officer {officer_id} retrieved "
                    f"{len(request_list)} pending payment-plan "
                    "request(s) for review."
                ),
                status="SUCCESS",
                agent=officer_id
            )
        except Exception:
            pass

        # ----------------------------------------------------
        # 15. RETURN RESULTS
        # ----------------------------------------------------

        return {
            "success": True,
            "status": "PENDING_REQUESTS_FOUND",
            "requests": request_list,
            "count": len(request_list),
            "message": (
                f"{len(request_list)} pending payment-plan "
                "request(s) require officer review."
            )
        }

    except Exception as error:

        # ----------------------------------------------------
        # 16. SYSTEM ERROR AUDIT
        # ----------------------------------------------------

        try:
            log_event(
                customer_id="UNKNOWN",
                event_type="PENDING_REQUEST_LOOKUP",
                description=(
                    f"System error while officer {officer_id} "
                    "attempted to retrieve pending payment-plan "
                    f"requests: {str(error)}"
                ),
                status="FAILED",
                agent="OFFICER_PORTAL"
            )
        except Exception:
            pass

        return {
            "success": False,
            "status": "PENDING_REQUEST_LOOKUP_ERROR",
            "message": str(error)
        }


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":

    print("==========================================")
    print("OFFICER AUTHORIZATION TESTS")
    print("==========================================")

    # --------------------------------------------------------
    # TEST 1: Active Recoveries Officer
    # --------------------------------------------------------

    print("\nTEST 1: Active Recoveries Officer")
    print("------------------------------------------")

    result = verify_officer("OFF001")

    print(result)

    # --------------------------------------------------------
    # TEST 2: Inactive Officer
    # --------------------------------------------------------

    print("\nTEST 2: Inactive Officer")
    print("------------------------------------------")

    result = verify_officer("OFF002")

    print(result)

    # --------------------------------------------------------
    # TEST 3: Unknown Officer
    # --------------------------------------------------------

    print("\nTEST 3: Unknown Officer")
    print("------------------------------------------")

    result = verify_officer("OFF999")

    print(result)

    # --------------------------------------------------------
    # TEST 4: Empty Officer ID
    # --------------------------------------------------------

    print("\nTEST 4: Empty Officer ID")
    print("------------------------------------------")

    result = verify_officer("")

    print(result)

    print("\n==========================================")
    print("PENDING PAYMENT-PLAN REQUEST TESTS")
    print("==========================================")

    # --------------------------------------------------------
    # TEST 5: Authorized Officer - Pending Requests
    # --------------------------------------------------------

    print("\nTEST 5: Authorized Officer - Pending Requests")
    print("------------------------------------------")

    result = get_pending_payment_plan_requests("OFF001")

    print(result)

    # --------------------------------------------------------
    # TEST 6: Inactive Officer - Pending Requests
    # --------------------------------------------------------

    print("\nTEST 6: Inactive Officer - Pending Requests")
    print("------------------------------------------")

    result = get_pending_payment_plan_requests("OFF002")

    print(result)

    # --------------------------------------------------------
    # TEST 7: Unknown Officer - Pending Requests
    # --------------------------------------------------------

    print("\nTEST 7: Unknown Officer - Pending Requests")
    print("------------------------------------------")

    result = get_pending_payment_plan_requests("OFF999")

    print(result)

    # --------------------------------------------------------
    # TEST 8: Empty Officer ID - Pending Requests
    # --------------------------------------------------------

    print("\nTEST 8: Empty Officer ID - Pending Requests")
    print("------------------------------------------")

    result = get_pending_payment_plan_requests("")

    print(result)

    print("\n==========================================")
    print("OFFICER TOOLS TEST COMPLETE")
    print("==========================================")