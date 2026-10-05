
import pandas as pd

from datetime import datetime

from database.google_sheets import open_database

from tools.officer_tools import verify_officer

from audit.logger import log_event

from notifications.payment_plan_notifications import (
    notify_payment_plan_approved,
    notify_payment_plan_rejected
)


# ============================================================
# OFFICER PAYMENT-PLAN REQUEST REVIEW
# ============================================================

def review_payment_plan_request(
    request_id,
    officer_id
):
    """
    Review a payment-plan request before making a decision.

    SECURITY CONTROLS:

    1. Officer must exist.
    2. Officer must be ACTIVE.
    3. Officer must be a RECOVERIES OFFICER.
    4. Request must exist.
    5. Review is READ-ONLY.
    6. No request status is changed.
    7. No payment plan is created.
    8. No approval or rejection is performed.
    9. Review activity is recorded in Audit Logs.

    This function is intended for the HUMAN approval workflow.
    """

    request_id = str(request_id).strip()
    officer_id = str(officer_id).strip()

    try:

        # ========================================================
        # 1. VERIFY OFFICER AUTHORIZATION
        # ========================================================

        officer_result = verify_officer(officer_id)

        if not officer_result["authorized"]:

            log_event(
                customer_id="UNKNOWN",
                event_type="OFFICER_AUTHORIZATION",
                description=(
                    f"Unauthorized officer {officer_id} attempted "
                    f"to review payment plan request {request_id}. "
                    f"Reason: {officer_result['message']}"
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_APPROVAL"
            )

            return {
                "success": False,
                "status": officer_result["status"],
                "officer_id": officer_id,
                "message": officer_result["message"]
            }

        # ========================================================
        # 2. VALIDATE REQUEST ID
        # ========================================================

        if not request_id:

            log_event(
                customer_id="UNKNOWN",
                event_type="PAYMENT_PLAN_REQUEST_REVIEW",
                description=(
                    f"Officer {officer_id} attempted to review "
                    f"a payment plan request without a request ID."
                ),
                status="BLOCKED",
                agent=officer_id
            )

            return {
                "success": False,
                "status": "REQUEST_ID_REQUIRED",
                "message": "Payment plan request ID is required."
            }

        # ========================================================
        # 3. OPEN DATABASE
        # ========================================================

        spreadsheet = open_database()

        requests_sheet = spreadsheet.worksheet(
            "Payment Plan Requests"
        )

        requests = requests_sheet.get_all_records()

        requests_df = pd.DataFrame(requests)

        # ========================================================
        # 4. CHECK WHETHER REQUESTS EXIST
        # ========================================================

        if requests_df.empty:

            log_event(
                customer_id="UNKNOWN",
                event_type="PAYMENT_PLAN_REQUEST_REVIEW",
                description=(
                    f"Officer {officer_id} attempted to review "
                    f"request {request_id}, but no payment plan "
                    f"requests exist."
                ),
                status="FAILED",
                agent=officer_id
            )

            return {
                "success": False,
                "status": "NO_REQUESTS_FOUND",
                "request_id": request_id,
                "message": (
                    "No payment plan requests were found."
                )
            }

        # ========================================================
        # 5. FIND REQUEST
        # ========================================================

        request_match = requests_df[
            requests_df["request_id"].astype(str).str.strip()
            == request_id
        ]

        if request_match.empty:

            log_event(
                customer_id="UNKNOWN",
                event_type="PAYMENT_PLAN_REQUEST_REVIEW",
                description=(
                    f"Officer {officer_id} attempted to review "
                    f"request {request_id}, but the request "
                    f"was not found."
                ),
                status="FAILED",
                agent=officer_id
            )

            return {
                "success": False,
                "status": "REQUEST_NOT_FOUND",
                "request_id": request_id,
                "message": (
                    "Payment plan request was not found."
                )
            }

        # ========================================================
        # 6. CONVERT REQUEST TO SAFE PYTHON TYPES
        # ========================================================

        request = request_match.iloc[0]

        customer_id = str(
            request["customer_id"]
        ).strip()

        loan_id = str(
            request["loan_id"]
        ).strip()

        proposed_amount = float(
            request["proposed_amount"]
        )

        frequency = str(
            request["frequency"]
        ).strip()

        start_date = str(
            request["start_date"]
        ).strip()

        next_payment_date = str(
            request["next_payment_date"]
        ).strip()

        number_of_payments = int(
            request["number_of_payments"]
        )

        customer_consent = str(
            request["customer_consent"]
        ).strip()

        submitted_at = str(
            request["submitted_at"]
        ).strip()

        approval_status = str(
            request["approval_status"]
        ).strip().upper()

        approved_by = str(
            request.get("approved_by", "")
        ).strip()

        approved_at = str(
            request.get("approved_at", "")
        ).strip()

        rejection_reason = str(
            request.get("rejection_reason", "")
        ).strip()

        # ========================================================
        # 7. AUDIT REVIEW
        # ========================================================

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_REQUEST_REVIEW",
            description=(
                f"Officer {officer_id} reviewed payment plan "
                f"request {request_id} for loan {loan_id}. "
                f"Current status: {approval_status}."
            ),
            status="SUCCESS",
            agent=officer_id
        )

        # ========================================================
        # 8. RETURN READ-ONLY REQUEST INFORMATION
        # ========================================================

        return {
            "success": True,
            "status": "REQUEST_REVIEWED",
            "request_id": request_id,
            "customer_id": customer_id,
            "loan_id": loan_id,
            "proposed_amount": proposed_amount,
            "frequency": frequency,
            "start_date": start_date,
            "next_payment_date": next_payment_date,
            "number_of_payments": number_of_payments,
            "customer_consent": customer_consent,
            "submitted_at": submitted_at,
            "approval_status": approval_status,
            "approved_by": approved_by,
            "approved_at": approved_at,
            "rejection_reason": rejection_reason,
            "reviewed_by": officer_id,
            "message": (
                "Payment plan request reviewed successfully. "
                "No changes were made to the request or "
                "Payment Plans database."
            )
        }

    except Exception as error:

        # ========================================================
        # 9. SYSTEM ERROR AUDIT
        # ========================================================

        try:

            log_event(
                customer_id="UNKNOWN",
                event_type="PAYMENT_PLAN_REQUEST_REVIEW",
                description=(
                    f"System error while officer {officer_id} "
                    f"reviewed payment plan request {request_id}: "
                    f"{str(error)}"
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_APPROVAL"
            )

        except Exception:
            pass

        return {
            "success": False,
            "status": "PAYMENT_PLAN_REVIEW_ERROR",
            "request_id": request_id,
            "message": str(error)
        }


# ============================================================
# PROCESS PAYMENT-PLAN DECISION
# ============================================================

def process_payment_plan_decision(
    request_id,
    officer_id,
    decision,
    rejection_reason=""
):
    """
    Process a payment plan request decision.

    Security and business controls:

    1. Officer must exist.
    2. Officer must be ACTIVE.
    3. Officer must be a RECOVERIES OFFICER.
    4. Decision must be APPROVED or REJECTED.
    5. Rejection requires a reason.
    6. Request must exist.
    7. Request must still be PENDING.
    8. Approved requests must not create a duplicate ACTIVE plan.
    9. Approved plans are written to Payment Plans.
    10. Customer notification is created after approval/rejection.
    11. Notification failure does not reverse a successful business decision.
    12. Important actions are recorded in Audit Logs.

    IMPORTANT:

    This function is intended for the HUMAN approval workflow.

    The AI agent must not approve its own payment-plan requests.
    """

    request_id = str(request_id).strip()
    officer_id = str(officer_id).strip()

    try:

        # ==================================================
        # 1. VERIFY OFFICER AUTHORIZATION
        # ==================================================

        officer_result = verify_officer(officer_id)

        if not officer_result["authorized"]:

            log_event(
                customer_id="UNKNOWN",
                event_type="OFFICER_AUTHORIZATION",
                description=(
                    f"Unauthorized officer {officer_id} attempted "
                    f"to process payment plan request {request_id}. "
                    f"Reason: {officer_result['message']}"
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_APPROVAL"
            )

            return {
                "success": False,
                "status": officer_result["status"],
                "officer_id": officer_id,
                "message": officer_result["message"]
            }

        # ==================================================
        # 2. VALIDATE DECISION
        # ==================================================

        decision = str(decision).strip().upper()

        if decision not in ["APPROVED", "REJECTED"]:

            log_event(
                customer_id="UNKNOWN",
                event_type="PAYMENT_PLAN_DECISION",
                description=(
                    f"Invalid decision '{decision}' submitted "
                    f"for request {request_id} by officer "
                    f"{officer_id}."
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_APPROVAL"
            )

            return {
                "success": False,
                "status": "INVALID_DECISION",
                "message": (
                    "Decision must be APPROVED or REJECTED."
                )
            }

        # ==================================================
        # 3. VALIDATE REJECTION REASON
        # ==================================================

        if decision == "REJECTED":

            if (
                not rejection_reason
                or not str(rejection_reason).strip()
            ):

                log_event(
                    customer_id="UNKNOWN",
                    event_type="PAYMENT_PLAN_REJECTION",
                    description=(
                        f"Payment plan request {request_id} "
                        f"was submitted for rejection without "
                        f"a reason."
                    ),
                    status="BLOCKED",
                    agent=officer_id
                )

                return {
                    "success": False,
                    "status": "REJECTION_REASON_REQUIRED",
                    "message": (
                        "A rejection reason is required."
                    )
                }

        # ==================================================
        # 4. OPEN DATABASE
        # ==================================================

        spreadsheet = open_database()

        requests_sheet = spreadsheet.worksheet(
            "Payment Plan Requests"
        )

        requests = requests_sheet.get_all_records()

        requests_df = pd.DataFrame(requests)

        # ==================================================
        # 5. CHECK WHETHER REQUESTS EXIST
        # ==================================================

        if requests_df.empty:

            log_event(
                customer_id="UNKNOWN",
                event_type="PAYMENT_PLAN_REQUEST_LOOKUP",
                description=(
                    f"No payment plan requests were found "
                    f"while processing request {request_id}."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_APPROVAL"
            )

            return {
                "success": False,
                "status": "NO_REQUESTS_FOUND",
                "message": (
                    "No payment plan requests were found."
                )
            }

        # ==================================================
        # 6. FIND REQUEST
        # ==================================================

        request_match = requests_df[
            requests_df["request_id"].astype(str).str.strip()
            == request_id
        ]

        if request_match.empty:

            log_event(
                customer_id="UNKNOWN",
                event_type="PAYMENT_PLAN_REQUEST_LOOKUP",
                description=(
                    f"Payment plan request {request_id} "
                    f"was not found."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_APPROVAL"
            )

            return {
                "success": False,
                "status": "REQUEST_NOT_FOUND",
                "request_id": request_id,
                "message": (
                    "Payment plan request was not found."
                )
            }

        request = request_match.iloc[0]

        customer_id = str(
            request["customer_id"]
        ).strip()

        loan_id = str(
            request["loan_id"]
        ).strip()

        # ==================================================
        # 7. CHECK REQUEST STATUS
        # ==================================================

        current_status = str(
            request["approval_status"]
        ).strip().upper()

        if current_status != "PENDING":

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_DECISION",
                description=(
                    f"Officer {officer_id} attempted to "
                    f"process request {request_id}, but "
                    f"the request was already processed. "
                    f"Current status: {current_status}."
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_APPROVAL"
            )

            return {
                "success": False,
                "status": "REQUEST_ALREADY_PROCESSED",
                "request_id": request_id,
                "message": (
                    "Request has already been processed. "
                    f"Current status: {current_status}"
                )
            }

        # ==================================================
        # 8. LOCATE REQUEST ROW
        # ==================================================

        request_row = None

        for index, row in enumerate(requests, start=2):

            if (
                str(row["request_id"]).strip()
                == request_id
            ):

                request_row = index
                break

        if request_row is None:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_REQUEST_LOOKUP",
                description=(
                    f"Request {request_id} was found in "
                    f"the database but its worksheet row "
                    f"could not be located."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_APPROVAL"
            )

            return {
                "success": False,
                "status": "REQUEST_ROW_NOT_FOUND",
                "message": (
                    "Unable to locate request row."
                )
            }

        # ==================================================
        # 9. GET CUSTOMER CONTACT INFORMATION
        # ==================================================

        customers_sheet = spreadsheet.worksheet(
            "Customers"
        )

        customers = customers_sheet.get_all_records()

        customer_match = None

        for customer in customers:

            current_customer_id = str(
                customer.get("customer_id", "")
            ).strip()

            if current_customer_id == customer_id:

                customer_match = customer
                break

        if customer_match is None:

            log_event(
                customer_id=customer_id,
                event_type="CUSTOMER_LOOKUP",
                description=(
                    f"Customer {customer_id} associated with "
                    f"request {request_id} could not be found."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_APPROVAL"
            )

            return {
                "success": False,
                "status": "CUSTOMER_NOT_FOUND",
                "customer_id": customer_id,
                "request_id": request_id,
                "message": (
                    "Customer record could not be found."
                )
            }

        phone_number = str(
            customer_match.get("phone_number", "")
        ).strip()

        # ==================================================
        # 10. LOAD EXISTING PAYMENT PLANS
        # ==================================================

        plans_sheet = spreadsheet.worksheet(
            "Payment Plans"
        )

        existing_plans = plans_sheet.get_all_records()

        # ==================================================
        # 11. ACTIVE PAYMENT PLAN GUARDRAIL
        # ==================================================

        if decision == "APPROVED":

            active_plan_exists = False
            existing_plan_id = None

            for plan in existing_plans:

                existing_customer_id = str(
                    plan["customer_id"]
                ).strip()

                existing_loan_id = str(
                    plan["loan_id"]
                ).strip()

                existing_status = str(
                    plan["status"]
                ).strip().upper()

                if (
                    existing_customer_id == customer_id
                    and existing_loan_id == loan_id
                    and existing_status == "ACTIVE"
                ):

                    active_plan_exists = True

                    existing_plan_id = str(
                        plan["plan_id"]
                    ).strip()

                    break

            if active_plan_exists:

                log_event(
                    customer_id=customer_id,
                    event_type="PAYMENT_PLAN_APPROVAL",
                    description=(
                        f"Payment plan request {request_id} "
                        f"was blocked because active payment "
                        f"plan {existing_plan_id} already exists "
                        f"for loan {loan_id}."
                    ),
                    status="BLOCKED",
                    agent="PAYMENT_PLAN_APPROVAL"
                )

                return {
                    "success": False,
                    "status": "ACTIVE_PLAN_EXISTS",
                    "request_id": request_id,
                    "customer_id": customer_id,
                    "loan_id": loan_id,
                    "existing_plan_id": existing_plan_id,
                    "message": (
                        "An active payment plan already exists "
                        "for this loan. A new plan cannot be "
                        "approved until the existing plan is "
                        "properly closed or replaced through "
                        "an authorized workflow."
                    )
                }

        # ==================================================
        # 12. GENERATE PROCESSING TIMESTAMP
        # ==================================================

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # ==================================================
        # 13. PROCESS REJECTION
        # ==================================================

        if decision == "REJECTED":

            requests_sheet.update_cell(
                request_row,
                11,
                "REJECTED"
            )

            requests_sheet.update_cell(
                request_row,
                12,
                officer_id
            )

            requests_sheet.update_cell(
                request_row,
                13,
                timestamp
            )

            requests_sheet.update_cell(
                request_row,
                14,
                str(rejection_reason)
            )

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_REJECTION",
                description=(
                    f"Payment plan request {request_id} "
                    f"for loan {loan_id} was rejected by "
                    f"officer {officer_id}. Reason: "
                    f"{rejection_reason}"
                ),
                status="SUCCESS",
                agent=officer_id
            )

            # ---------------------------------------------
            # Create rejection notification
            # ---------------------------------------------

            notification_result = None

            if phone_number:

                try:

                    notification_result = (
                        notify_payment_plan_rejected(
                            request_id=request_id,
                            customer_id=customer_id,
                            rejection_reason=str(
                                rejection_reason
                            ),
                            recipient=phone_number
                        )
                    )

                except Exception as notification_error:

                    log_event(
                        customer_id=customer_id,
                        event_type="NOTIFICATION_ERROR",
                        description=(
                            f"Rejection notification for "
                            f"request {request_id} failed: "
                            f"{str(notification_error)}"
                        ),
                        status="FAILED",
                        agent="PAYMENT_PLAN_APPROVAL"
                    )

                    notification_result = {
                        "success": False,
                        "status": "NOTIFICATION_ERROR",
                        "message": str(notification_error)
                    }

            else:

                notification_result = {
                    "success": False,
                    "status": "NO_PHONE_NUMBER",
                    "message": (
                        "Payment plan was rejected, but no "
                        "customer phone number was available."
                    )
                }

            return {
                "success": True,
                "status": "PAYMENT_PLAN_REJECTED",
                "request_id": request_id,
                "officer_id": officer_id,
                "rejected_at": timestamp,
                "rejection_reason": str(
                    rejection_reason
                ),
                "notification": notification_result,
                "message": (
                    "Payment plan request was rejected."
                )
            }

        # ==================================================
        # 14. CONVERT REQUEST DATA TO SAFE PYTHON TYPES
        # ==================================================

        proposed_amount = float(
            request["proposed_amount"]
        )

        frequency = str(
            request["frequency"]
        ).strip()

        start_date = str(
            request["start_date"]
        ).strip()

        next_payment_date = str(
            request["next_payment_date"]
        ).strip()

        number_of_payments = int(
            request["number_of_payments"]
        )

        # ==================================================
        # 15. UPDATE REQUEST TO APPROVED
        # ==================================================

        requests_sheet.update_cell(
            request_row,
            11,
            "APPROVED"
        )

        requests_sheet.update_cell(
            request_row,
            12,
            officer_id
        )

        requests_sheet.update_cell(
            request_row,
            13,
            timestamp
        )

        # ==================================================
        # 16. GENERATE NEW PAYMENT PLAN ID
        # ==================================================

        plan_number = len(existing_plans) + 1

        plan_id = f"PLAN{plan_number:03d}"

        # ==================================================
        # 17. CREATE APPROVED PAYMENT PLAN
        # ==================================================

        new_plan = [
            plan_id,
            customer_id,
            loan_id,
            proposed_amount,
            frequency,
            start_date,
            next_payment_date,
            number_of_payments,
            "ACTIVE"
        ]

        plans_sheet.append_row(
            new_plan,
            value_input_option="USER_ENTERED"
        )

        # ==================================================
        # 18. AUDIT SUCCESSFUL APPROVAL
        # ==================================================

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_APPROVAL",
            description=(
                f"Payment plan request {request_id} "
                f"for loan {loan_id} was approved by "
                f"officer {officer_id}. Payment plan "
                f"{plan_id} was created successfully."
            ),
            status="SUCCESS",
            agent=officer_id
        )

        # ==================================================
        # 19. CREATE APPROVAL NOTIFICATION
        # ==================================================

        notification_result = None

        if phone_number:

            try:

                notification_result = (
                    notify_payment_plan_approved(
                        request_id=request_id,
                        customer_id=customer_id,
                        plan_id=plan_id,
                        recipient=phone_number
                    )
                )

            except Exception as notification_error:

                log_event(
                    customer_id=customer_id,
                    event_type="NOTIFICATION_ERROR",
                    description=(
                        f"Approval notification for "
                        f"request {request_id} failed: "
                        f"{str(notification_error)}"
                    ),
                    status="FAILED",
                    agent="PAYMENT_PLAN_APPROVAL"
                )

                notification_result = {
                    "success": False,
                    "status": "NOTIFICATION_ERROR",
                    "message": str(notification_error)
                }

        else:

            notification_result = {
                "success": False,
                "status": "NO_PHONE_NUMBER",
                "message": (
                    "Payment plan was approved, but no "
                    "customer phone number was available."
                )
            }

        # ==================================================
        # 20. RETURN SUCCESS
        # ==================================================

        return {
            "success": True,
            "status": "PAYMENT_PLAN_APPROVED",
            "request_id": request_id,
            "plan_id": plan_id,
            "officer_id": officer_id,
            "approved_at": timestamp,
            "notification": notification_result,
            "message": (
                "Payment plan request approved and "
                "added to the Payment Plans database."
            )
        }

    except Exception as error:

        # ==================================================
        # 21. SYSTEM ERROR AUDIT
        # ==================================================

        try:

            log_event(
                customer_id="UNKNOWN",
                event_type="PAYMENT_PLAN_DECISION",
                description=(
                    f"System error while processing "
                    f"payment plan request {request_id}: "
                    f"{str(error)}"
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_APPROVAL"
            )

        except Exception:
            pass

        return {
            "success": False,
            "status": "PAYMENT_PLAN_DECISION_ERROR",
            "message": str(error)
        }


# ============================================================
# DIRECT TESTS
# ============================================================

if __name__ == "__main__":

    print("==========================================")
    print("PAYMENT PLAN APPROVAL + REVIEW TEST")
    print("==========================================")

    print("\nTEST 1: Officer Review")
    print("------------------------------------------")

    result = review_payment_plan_request(
        request_id="REQ-3B65F2E7",
        officer_id="OFF001"
    )

    print(result)

    print("\nTEST 2: Inactive Officer")
    print("------------------------------------------")

    result = review_payment_plan_request(
        request_id="REQ-3B65F2E7",
        officer_id="OFF002"
    )

    print(result)

    print("\nTEST 3: Unknown Officer")
    print("------------------------------------------")

    result = review_payment_plan_request(
        request_id="REQ-3B65F2E7",
        officer_id="OFF999"
    )

    print(result)

    print("\n==========================================")
    print("PAYMENT PLAN REVIEW TEST COMPLETE")
    print("==========================================")
