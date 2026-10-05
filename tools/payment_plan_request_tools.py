
import uuid

from datetime import datetime

from database.google_sheets import open_database
from audit.logger import log_event


# ============================================================
# PAYMENT PLAN REQUEST ID
# ============================================================

def generate_request_id():
    """
    Generate a unique payment-plan request ID.

    Example:
    REQ-A1B2C3D4
    """

    return f"REQ-{uuid.uuid4().hex[:8].upper()}"


# ============================================================
# SUBMIT PAYMENT PLAN REQUEST
# ============================================================

def submit_payment_plan_request(
    customer_id,
    loan_id,
    proposed_amount,
    frequency,
    start_date,
    next_payment_date,
    number_of_payments,
    customer_consent
):
    """
    Submit a customer payment-plan proposal for
    Recoveries Officer approval.

    IMPORTANT:

    This function ONLY creates a PENDING request.

    It does NOT:
    - approve the request
    - reject the request
    - create an active payment plan
    - modify an existing active payment plan

    KYC is expected to be performed by the
    customer-facing wrapper before this function
    is called.
    """

    # ========================================================
    # 1. BASIC INPUT VALIDATION
    # ========================================================

    if not customer_id:
        return {
            "success": False,
            "status": "INVALID_CUSTOMER_ID",
            "message": "Customer ID is required."
        }

    if not loan_id:
        return {
            "success": False,
            "status": "INVALID_LOAN_ID",
            "message": "Loan ID is required."
        }

    # ========================================================
    # 2. CUSTOMER CONSENT
    # ========================================================

    if customer_consent is not True:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_BLOCKED",
            description=(
                f"Payment-plan request for loan {loan_id} "
                "was blocked because explicit customer consent "
                "was not provided."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "CONSENT_REQUIRED",
            "message": (
                "Explicit customer consent is required before "
                "a payment-plan request can be submitted."
            )
        }

    # ========================================================
    # 3. PROPOSED AMOUNT VALIDATION
    # ========================================================

    try:
        proposed_amount = float(proposed_amount)

    except (TypeError, ValueError):

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_BLOCKED",
            description=(
                f"Payment-plan request for loan {loan_id} "
                "was blocked because the proposed amount "
                "was not numeric."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "INVALID_AMOUNT",
            "message": "Proposed payment amount must be numeric."
        }

    if proposed_amount <= 0:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_BLOCKED",
            description=(
                f"Payment-plan request for loan {loan_id} "
                "was blocked because the proposed amount "
                f"was {proposed_amount}."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "INVALID_AMOUNT",
            "message": (
                "Proposed payment amount must be greater "
                "than zero."
            )
        }

    # ========================================================
    # 4. FREQUENCY VALIDATION
    # ========================================================

    if not frequency:

        return {
            "success": False,
            "status": "INVALID_FREQUENCY",
            "message": "Payment frequency is required."
        }

    frequency = str(frequency).strip().upper()

    allowed_frequencies = {
        "WEEKLY",
        "BIWEEKLY",
        "MONTHLY"
    }

    if frequency not in allowed_frequencies:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_BLOCKED",
            description=(
                f"Payment-plan request for loan {loan_id} "
                f"was blocked because frequency '{frequency}' "
                "is not supported."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "INVALID_FREQUENCY",
            "message": (
                "Frequency must be WEEKLY, BIWEEKLY or MONTHLY."
            )
        }

    # ========================================================
    # 5. PAYMENT COUNT VALIDATION
    # ========================================================

    try:
        payment_count = int(number_of_payments)

    except (TypeError, ValueError):

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_BLOCKED",
            description=(
                f"Payment-plan request for loan {loan_id} "
                "was blocked because number_of_payments "
                "was not a valid whole number."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "INVALID_PAYMENT_COUNT",
            "message": (
                "Number of payments must be a whole number "
                "greater than zero."
            )
        }

    if payment_count <= 0:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_BLOCKED",
            description=(
                f"Payment-plan request for loan {loan_id} "
                "was blocked because number_of_payments "
                f"was {payment_count}."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "INVALID_PAYMENT_COUNT",
            "message": (
                "Number of payments must be greater than zero."
            )
        }

    # ========================================================
    # 6. DATE VALIDATION
    # ========================================================

    if not start_date:

        return {
            "success": False,
            "status": "INVALID_START_DATE",
            "message": "Start date is required."
        }

    if not next_payment_date:

        return {
            "success": False,
            "status": "INVALID_NEXT_PAYMENT_DATE",
            "message": "Next payment date is required."
        }

    try:

        parsed_start_date = datetime.strptime(
            str(start_date),
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return {
            "success": False,
            "status": "INVALID_START_DATE",
            "message": (
                "Start date must use YYYY-MM-DD format."
            )
        }

    try:

        parsed_next_payment_date = datetime.strptime(
            str(next_payment_date),
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return {
            "success": False,
            "status": "INVALID_NEXT_PAYMENT_DATE",
            "message": (
                "Next payment date must use YYYY-MM-DD format."
            )
        }

    if parsed_next_payment_date < parsed_start_date:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_BLOCKED",
            description=(
                f"Payment-plan request for loan {loan_id} "
                "was blocked because the next payment date "
                "is earlier than the start date."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "INVALID_DATE_SEQUENCE",
            "message": (
                "Next payment date cannot be earlier "
                "than the start date."
            )
        }

    # ========================================================
    # 7. OPEN DATABASE
    # ========================================================

    try:

        spreadsheet = open_database()

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_ERROR",
            description=(
                f"Unable to connect to the payment-plan database "
                f"for loan {loan_id}: {str(error)}"
            ),
            status="ERROR",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "DATABASE_ERROR",
            "message": (
                "The payment-plan database could not be accessed."
            )
        }

    # ========================================================
    # 8. VERIFY CUSTOMER EXISTS
    # ========================================================

    try:

        customers_sheet = spreadsheet.worksheet("Customers")
        customers_records = customers_sheet.get_all_records()

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_ERROR",
            description=(
                f"Unable to access Customers sheet: {str(error)}"
            ),
            status="ERROR",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "DATABASE_ERROR",
            "message": "Customer information could not be retrieved."
        }

    customer_found = any(
        str(row.get("customer_id", "")).strip()
        == str(customer_id).strip()
        for row in customers_records
    )

    if not customer_found:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_BLOCKED",
            description=(
                f"Payment-plan request was blocked because "
                f"customer {customer_id} was not found."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "CUSTOMER_NOT_FOUND",
            "message": "Customer could not be found."
        }

    # ========================================================
    # 9. VERIFY LOAN EXISTS AND BELONGS TO CUSTOMER
    # ========================================================

    try:

        loans_sheet = spreadsheet.worksheet("Loans")
        loans_records = loans_sheet.get_all_records()

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_ERROR",
            description=(
                f"Unable to access Loans sheet: {str(error)}"
            ),
            status="ERROR",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "DATABASE_ERROR",
            "message": "Loan information could not be retrieved."
        }

    matching_loan = None

    for row in loans_records:

        row_customer_id = str(
            row.get("customer_id", "")
        ).strip()

        row_loan_id = str(
            row.get("loan_id", "")
        ).strip()

        if (
            row_customer_id == str(customer_id).strip()
            and
            row_loan_id == str(loan_id).strip()
        ):

            matching_loan = row
            break

    if matching_loan is None:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_BLOCKED",
            description=(
                f"Payment-plan request was blocked because "
                f"loan {loan_id} does not belong to customer "
                f"{customer_id}."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "LOAN_NOT_FOUND",
            "message": (
                "The specified loan could not be found for "
                "this customer."
            )
        }

    # ========================================================
    # 10. CHECK FOR EXISTING PENDING REQUEST
    # ========================================================

    try:

        requests_sheet = spreadsheet.worksheet(
            "Payment Plan Requests"
        )

        requests_records = requests_sheet.get_all_records()

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_ERROR",
            description=(
                "Unable to access Payment Plan Requests sheet: "
                f"{str(error)}"
            ),
            status="ERROR",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "DATABASE_ERROR",
            "message": (
                "Payment-plan request information could "
                "not be retrieved."
            )
        }

    for row in requests_records:

        row_customer_id = str(
            row.get("customer_id", "")
        ).strip()

        row_loan_id = str(
            row.get("loan_id", "")
        ).strip()

        row_status = str(
            row.get("approval_status", "")
        ).strip().upper()

        if (
            row_customer_id == str(customer_id).strip()
            and
            row_loan_id == str(loan_id).strip()
            and
            row_status == "PENDING"
        ):

            return {
                "success": False,
                "status": "PENDING_REQUEST_EXISTS",
                "message": (
                    "There is already a pending payment-plan "
                    "request for this loan."
                ),
                "request_id": row.get("request_id")
            }

    # ========================================================
    # 11. GENERATE REQUEST ID
    # ========================================================

    request_id = generate_request_id()

    submitted_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # ========================================================
    # 12. CREATE PENDING REQUEST
    # ========================================================

    request_record = [
        request_id,
        str(customer_id),
        str(loan_id),
        proposed_amount,
        frequency,
        str(parsed_start_date),
        str(parsed_next_payment_date),
        payment_count,
        True,
        submitted_at,
        "PENDING",
        "",
        "",
        ""
    ]

    try:

        requests_sheet.append_row(
            request_record,
            value_input_option="USER_ENTERED"
        )

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_ERROR",
            description=(
                f"Failed to create payment-plan request "
                f"{request_id}: {str(error)}"
            ),
            status="ERROR",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "REQUEST_CREATION_ERROR",
            "message": (
                "The payment-plan request could not be created."
            )
        }

    # ========================================================
    # 13. AUDIT SUCCESSFUL SUBMISSION
    # ========================================================

    log_event(
        customer_id=customer_id,
        event_type="PAYMENT_PLAN_REQUEST_SUBMITTED",
        description=(
            f"Payment-plan request {request_id} submitted for "
            f"loan {loan_id}. Proposed amount: "
            f"{proposed_amount}, frequency: {frequency}, "
            f"start date: {parsed_start_date}, next payment date: "
            f"{parsed_next_payment_date}, number of payments: "
            f"{payment_count}. Request is awaiting Recoveries "
            "Officer approval."
        ),
        status="PENDING",
        agent="PAYMENT_PLAN_REQUEST"
    )

    # ========================================================
    # 14. RETURN RESULT
    # ========================================================

    return {
        "success": True,
        "status": "PAYMENT_PLAN_REQUEST_SUBMITTED",
        "request_id": request_id,
        "customer_id": customer_id,
        "loan_id": loan_id,
        "proposed_amount": proposed_amount,
        "frequency": frequency,
        "start_date": str(parsed_start_date),
        "next_payment_date": str(parsed_next_payment_date),
        "number_of_payments": payment_count,
        "customer_consent": True,
        "approval_status": "PENDING",
        "message": (
            "Payment-plan request submitted successfully. "
            "The request is pending Recoveries Officer review "
            "and approval. No active payment plan has been "
            "created or changed."
        )
    }


# ============================================================
# GET PAYMENT PLAN REQUEST STATUS
# ============================================================

def get_payment_plan_request(
    customer_id,
    request_id=None,
    kyc_verified=False
):
    """
    Retrieve payment-plan request information.

    SECURITY:
    This is a read-only function and requires successful KYC.

    It does NOT:
    - approve a request
    - reject a request
    - create a payment plan
    - modify a payment plan
    - modify the request

    If request_id is supplied, the specific request is returned.

    If request_id is omitted, all payment-plan requests
    belonging to the verified customer are returned.
    """

    # ========================================================
    # 1. KYC GUARDRAIL
    # ========================================================

    if not kyc_verified:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_LOOKUP_BLOCKED",
            description=(
                "Payment-plan request lookup was blocked "
                "because KYC verification was not completed."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_REQUEST"
        )

        return {
            "success": False,
            "status": "KYC_REQUIRED",
            "message": (
                "KYC verification is required before "
                "payment-plan request information can "
                "be disclosed."
            )
        }

    # ========================================================
    # 2. CUSTOMER ID VALIDATION
    # ========================================================

    if not customer_id:

        return {
            "success": False,
            "status": "INVALID_CUSTOMER_ID",
            "message": "Customer ID is required."
        }

    # ========================================================
    # 3. OPEN DATABASE
    # ========================================================

    try:

        spreadsheet = open_database()

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_LOOKUP_ERROR",
            description=(
                f"Unable to connect to payment-plan request "
                f"database: {str(error)}"
            ),
            status="ERROR",
            agent="PAYMENT_PLAN_REQUEST_LOOKUP"
        )

        return {
            "success": False,
            "status": "DATABASE_ERROR",
            "message": (
                "Payment-plan request information could "
                "not be retrieved."
            )
        }

    # ========================================================
    # 4. READ REQUESTS
    # ========================================================

    try:

        requests_sheet = spreadsheet.worksheet(
            "Payment Plan Requests"
        )

        requests_records = requests_sheet.get_all_records()

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_LOOKUP_ERROR",
            description=(
                "Unable to access Payment Plan Requests sheet: "
                f"{str(error)}"
            ),
            status="ERROR",
            agent="PAYMENT_PLAN_REQUEST_LOOKUP"
        )

        return {
            "success": False,
            "status": "DATABASE_ERROR",
            "message": (
                "Payment-plan request information could "
                "not be retrieved."
            )
        }

    # ========================================================
    # 5. FILTER CUSTOMER REQUESTS
    # ========================================================

    customer_requests = []

    for row in requests_records:

        row_customer_id = str(
            row.get("customer_id", "")
        ).strip()

        row_request_id = str(
            row.get("request_id", "")
        ).strip()

        if row_customer_id != str(customer_id).strip():
            continue

        if request_id and row_request_id != str(request_id).strip():
            continue

        customer_requests.append({
            "request_id": row.get("request_id"),
            "customer_id": row.get("customer_id"),
            "loan_id": row.get("loan_id"),
            "proposed_amount": row.get("proposed_amount"),
            "frequency": row.get("frequency"),
            "start_date": row.get("start_date"),
            "next_payment_date": row.get("next_payment_date"),
            "number_of_payments": row.get("number_of_payments"),
            "customer_consent": row.get("customer_consent"),
            "submitted_at": row.get("submitted_at"),
            "approval_status": row.get("approval_status"),
            "approved_by": row.get("approved_by"),
            "approved_at": row.get("approved_at"),
            "rejection_reason": row.get("rejection_reason")
        })

    # ========================================================
    # 6. REQUEST NOT FOUND
    # ========================================================

    if not customer_requests:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_LOOKUP",
            description=(
                f"No payment-plan request was found for "
                f"customer {customer_id}"
                + (
                    f" and request {request_id}."
                    if request_id
                    else "."
                )
            ),
            status="NOT_FOUND",
            agent="PAYMENT_PLAN_REQUEST_LOOKUP"
        )

        return {
            "success": False,
            "status": "REQUEST_NOT_FOUND",
            "customer_id": customer_id,
            "request_id": request_id,
            "message": (
                "No matching payment-plan request was found."
            )
        }

    # ========================================================
    # 7. AUDIT SUCCESSFUL LOOKUP
    # ========================================================

    log_event(
        customer_id=customer_id,
        event_type="PAYMENT_PLAN_REQUEST_LOOKUP",
        description=(
            f"Payment-plan request information was retrieved "
            f"for customer {customer_id}"
            + (
                f", request {request_id}."
                if request_id
                else "."
            )
        ),
        status="SUCCESS",
        agent="PAYMENT_PLAN_REQUEST_LOOKUP"
    )

    # ========================================================
    # 8. RETURN RESULT
    # ========================================================

    return {
        "success": True,
        "status": "REQUESTS_FOUND",
        "customer_id": customer_id,
        "request_id": request_id,
        "requests": customer_requests,
        "count": len(customer_requests),
        "message": (
            "Payment-plan request information retrieved "
            "successfully."
        )
    }
