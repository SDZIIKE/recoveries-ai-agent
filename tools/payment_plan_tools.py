import pandas as pd

from datetime import datetime

from database.google_sheets import open_database
from audit.logger import log_event
from tools.officer_tools import verify_officer


def get_payment_plan(customer_id, kyc_verified=False):
    """
    Retrieve existing payment plans.

    KYC is required before payment-plan information
    can be disclosed.
    """

    customer_id = str(customer_id).strip()

    # ---------------------------------------------
    # KYC SECURITY CHECK
    # ---------------------------------------------
    if not kyc_verified:
        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_ACCESS",
            description=(
                "Payment plan access was blocked because "
                "KYC verification had not been completed."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_TOOL"
        )

        return {
            "success": False,
            "status": "KYC_REQUIRED",
            "customer_id": customer_id,
            "message": (
                "KYC verification is required before "
                "payment plan information can be disclosed."
            )
        }

    try:
        spreadsheet = open_database()
        worksheet = spreadsheet.worksheet("Payment Plans")
        records = worksheet.get_all_records()
        plans = pd.DataFrame(records)

        if plans.empty:
            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_ACCESS",
                description=(
                    "Payment plan lookup failed because "
                    "no payment plan records were found."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_TOOL"
            )

            return {
                "success": False,
                "status": "NO_PAYMENT_PLANS_FOUND",
                "customer_id": customer_id,
                "message": "No payment plan records were found."
            }

        customer_plans = plans[
            plans["customer_id"].astype(str).str.strip()
            == customer_id
        ]

        if customer_plans.empty:
            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_ACCESS",
                description=(
                    "No payment plans were found for "
                    "the verified customer."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_TOOL"
            )

            return {
                "success": False,
                "status": "NO_PAYMENT_PLANS_FOUND",
                "customer_id": customer_id,
                "message": (
                    "No payment plans were found "
                    "for this customer."
                )
            }

        plan_list = customer_plans.to_dict(orient="records")

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_ACCESS",
            description=(
                "Payment plan information was successfully "
                "retrieved following successful KYC verification."
            ),
            status="SUCCESS",
            agent="PAYMENT_PLAN_TOOL"
        )

        return {
            "success": True,
            "status": "PAYMENT_PLANS_FOUND",
            "customer_id": customer_id,
            "payment_plans": plan_list
        }

    except Exception as error:
        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_ACCESS",
            description=(
                f"Payment plan lookup encountered a "
                f"system error: {str(error)}"
            ),
            status="FAILED",
            agent="PAYMENT_PLAN_TOOL"
        )

        return {
            "success": False,
            "status": "PAYMENT_PLAN_LOOKUP_ERROR",
            "message": str(error)
        }


def get_active_payment_plans_by_national_id(national_id, officer_id):
    """
    Retrieve ACTIVE payment plans using the customer's National ID.

    This function is intended for the authorized Recoveries Officer
    portal and is not exposed to the customer-facing AI.

    Workflow:
    National ID -> Customer record -> internal Customer ID
    -> ACTIVE payment plans.

    Security controls:
    - Officer must exist.
    - Officer must be ACTIVE.
    - Officer must have RECOVERIES OFFICER role.
    - National ID must match exactly after trimming.
    - Only ACTIVE payment plans are returned.
    - Internal Customer ID is not returned in the customer-facing
      payment-plan result.
    """

    national_id = str(national_id).strip()
    officer_id = str(officer_id).strip()

    # ---------------------------------------------
    # INPUT VALIDATION
    # ---------------------------------------------
    if not national_id:
        return {
            "success": False,
            "status": "NATIONAL_ID_REQUIRED",
            "message": "National ID is required."
        }

    if not officer_id:
        return {
            "success": False,
            "status": "OFFICER_ID_REQUIRED",
            "message": "Officer ID is required."
        }

    # ---------------------------------------------
    # OFFICER AUTHORIZATION
    # ---------------------------------------------
    officer_result = verify_officer(officer_id)

    if not officer_result.get("authorized"):
        log_event(
            customer_id="UNKNOWN",
            event_type="ACTIVE_PAYMENT_PLAN_LOOKUP",
            description=(
                f"Unauthorized active payment-plan lookup attempt "
                f"using National ID by officer {officer_id}. "
                f"Reason: {officer_result.get('message', '')}"
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_LOOKUP"
        )

        return {
            "success": False,
            "status": officer_result.get(
                "status",
                "OFFICER_NOT_AUTHORIZED"
            ),
            "message": officer_result.get(
                "message",
                "Officer is not authorized to retrieve payment plans."
            )
        }

    try:
        spreadsheet = open_database()

        # ---------------------------------------------
        # FIND CUSTOMER BY NATIONAL ID
        # ---------------------------------------------
        customers_worksheet = spreadsheet.worksheet("Customers")
        customer_records = customers_worksheet.get_all_records()
        customers = pd.DataFrame(customer_records)

        if customers.empty:
            log_event(
                customer_id="UNKNOWN",
                event_type="ACTIVE_PAYMENT_PLAN_LOOKUP",
                description=(
                    "Active payment-plan lookup failed because "
                    "no customer records were found."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LOOKUP"
            )

            return {
                "success": False,
                "status": "CUSTOMER_NOT_FOUND",
                "message": "No customer was found for the provided National ID."
            }

        if "national_id" not in customers.columns:
            return {
                "success": False,
                "status": "INVALID_CUSTOMER_DATABASE",
                "message": (
                    "The Customers database does not contain "
                    "the required national_id column."
                )
            }

        matching_customers = customers[
            customers["national_id"].astype(str).str.strip()
            == national_id
        ]

        if matching_customers.empty:
            log_event(
                customer_id="UNKNOWN",
                event_type="ACTIVE_PAYMENT_PLAN_LOOKUP",
                description=(
                    "No customer was found for the supplied National ID "
                    f"during lookup by officer {officer_id}."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LOOKUP"
            )

            return {
                "success": False,
                "status": "CUSTOMER_NOT_FOUND",
                "message": (
                    "No customer was found for the provided National ID."
                )
            }

        # National ID should uniquely identify one customer.
        if len(matching_customers) > 1:
            log_event(
                customer_id="UNKNOWN",
                event_type="ACTIVE_PAYMENT_PLAN_LOOKUP",
                description=(
                    "Multiple customer records matched the supplied "
                    f"National ID during lookup by officer {officer_id}."
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_LOOKUP"
            )

            return {
                "success": False,
                "status": "MULTIPLE_CUSTOMER_MATCHES",
                "message": (
                    "Multiple customer records matched the provided "
                    "National ID. The lookup has been blocked."
                )
            }

        customer = matching_customers.iloc[0]

        customer_id = str(
            customer.get("customer_id", "")
        ).strip()

        if not customer_id:
            return {
                "success": False,
                "status": "INVALID_CUSTOMER_RECORD",
                "message": (
                    "The matched customer record does not contain "
                    "a valid customer ID."
                )
            }

        # ---------------------------------------------
        # FIND ACTIVE PAYMENT PLANS
        # ---------------------------------------------
        plans_worksheet = spreadsheet.worksheet("Payment Plans")
        plan_records = plans_worksheet.get_all_records()
        plans = pd.DataFrame(plan_records)

        if plans.empty:
            log_event(
                customer_id=customer_id,
                event_type="ACTIVE_PAYMENT_PLAN_LOOKUP",
                description=(
                    "No payment plan records were found during "
                    "National ID lookup."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LOOKUP"
            )

            return {
                "success": False,
                "status": "NO_ACTIVE_PAYMENT_PLANS",
                "message": (
                    "No active payment plans were found for this customer."
                )
            }

        required_plan_columns = {
            "customer_id",
            "status",
            "plan_id"
        }

        missing_columns = required_plan_columns.difference(
            set(plans.columns)
        )

        if missing_columns:
            return {
                "success": False,
                "status": "INVALID_PAYMENT_PLAN_DATABASE",
                "message": (
                    "The Payment Plans database is missing required "
                    f"columns: {', '.join(sorted(missing_columns))}."
                )
            }

        customer_plans = plans[
            plans["customer_id"].astype(str).str.strip()
            == customer_id
        ]

        active_plans = customer_plans[
            customer_plans["status"].astype(str).str.strip().str.upper()
            == "ACTIVE"
        ]

        if active_plans.empty:
            log_event(
                customer_id=customer_id,
                event_type="ACTIVE_PAYMENT_PLAN_LOOKUP",
                description=(
                    "No active payment plans were found for the customer "
                    f"identified by National ID. Lookup performed by "
                    f"officer {officer_id}."
                ),
                status="SUCCESS",
                agent="PAYMENT_PLAN_LOOKUP"
            )

            return {
                "success": True,
                "status": "NO_ACTIVE_PAYMENT_PLANS",
                "national_id": national_id,
                "payment_plans": [],
                "message": (
                    "No active payment plans were found for this customer."
                )
            }

        # ---------------------------------------------
        # CUSTOMER-FACING / PORTAL-SAFE OUTPUT
        # ---------------------------------------------
        plan_list = active_plans.to_dict(orient="records")

        # Do not expose the internal customer_id through this lookup.
        for plan in plan_list:
            plan.pop("customer_id", None)

        log_event(
            customer_id=customer_id,
            event_type="ACTIVE_PAYMENT_PLAN_LOOKUP",
            description=(
                "Active payment plans were successfully retrieved "
                f"using National ID by authorized officer {officer_id}."
            ),
            status="SUCCESS",
            agent="PAYMENT_PLAN_LOOKUP"
        )

        return {
            "success": True,
            "status": "ACTIVE_PAYMENT_PLANS_FOUND",
            "national_id": national_id,
            "payment_plans": plan_list,
            "message": (
                f"{len(plan_list)} active payment plan(s) were found."
            )
        }

    except Exception as error:
        log_event(
            customer_id="UNKNOWN",
            event_type="ACTIVE_PAYMENT_PLAN_LOOKUP",
            description=(
                "Active payment-plan lookup encountered a system error: "
                f"{str(error)}"
            ),
            status="FAILED",
            agent="PAYMENT_PLAN_LOOKUP"
        )

        return {
            "success": False,
            "status": "ACTIVE_PAYMENT_PLAN_LOOKUP_ERROR",
            "message": str(error)
        }


def _ensure_payment_plan_columns(worksheet, required_columns):
    """
    Ensure closure-related columns exist in the Payment Plans sheet.

    Existing columns are preserved. Missing columns are appended
    to the header row.
    """

    headers = worksheet.row_values(1)

    changed = False

    for column in required_columns:
        if column not in headers:
            headers.append(column)
            changed = True

    if changed:
        worksheet.update("1:1", [headers])


def close_payment_plan(plan_id, officer_id, closure_reason):
    """
    Close an ACTIVE payment plan through an authorized
    Recoveries Officer workflow.

    This function is intentionally NOT exposed to the customer-facing AI.

    Security controls:
    - Officer must exist.
    - Officer must be ACTIVE.
    - Officer must have RECOVERIES OFFICER role.
    - Plan must exist.
    - Plan must currently be ACTIVE.
    - A closure reason is mandatory.
    """

    plan_id = str(plan_id).strip()
    officer_id = str(officer_id).strip()
    closure_reason = str(closure_reason).strip()

    # ---------------------------------------------
    # VALIDATE CLOSURE REASON
    # ---------------------------------------------
    if not closure_reason:
        return {
            "success": False,
            "status": "CLOSURE_REASON_REQUIRED",
            "message": (
                "A closure reason is required before "
                "an active payment plan can be closed."
            )
        }

    # ---------------------------------------------
    # OFFICER AUTHORIZATION
    # ---------------------------------------------
    officer_result = verify_officer(officer_id)

    if not officer_result.get("authorized"):
        log_event(
            customer_id="UNKNOWN",
            event_type="PAYMENT_PLAN_CLOSURE",
            description=(
                f"Unauthorized payment-plan closure attempt "
                f"for plan {plan_id} by officer {officer_id}. "
                f"Reason: {officer_result.get('message', '')}"
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_CLOSURE"
        )

        return {
            "success": False,
            "status": officer_result.get(
                "status",
                "OFFICER_NOT_AUTHORIZED"
            ),
            "message": officer_result.get(
                "message",
                "Officer is not authorized to close payment plans."
            )
        }

    try:
        spreadsheet = open_database()
        worksheet = spreadsheet.worksheet("Payment Plans")

        records = worksheet.get_all_records()
        plans = pd.DataFrame(records)

        if plans.empty:
            return {
                "success": False,
                "status": "NO_PAYMENT_PLANS_FOUND",
                "message": "No payment plan records were found."
            }

        required_columns = [
            "closure_reason",
            "closed_by",
            "closed_at"
        ]

        _ensure_payment_plan_columns(
            worksheet,
            required_columns
        )

        # Re-read records after ensuring the headers exist.
        headers = worksheet.row_values(1)
        records = worksheet.get_all_records()
        plans = pd.DataFrame(records)

        if "plan_id" not in plans.columns:
            return {
                "success": False,
                "status": "INVALID_PAYMENT_PLAN_DATABASE",
                "message": (
                    "The Payment Plans database does not contain "
                    "the required plan_id column."
                )
            }

        matching = plans[
            plans["plan_id"].astype(str).str.strip()
            == plan_id
        ]

        if matching.empty:
            log_event(
                customer_id="UNKNOWN",
                event_type="PAYMENT_PLAN_CLOSURE",
                description=(
                    f"Payment plan {plan_id} was not found "
                    f"during an authorized closure attempt."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_CLOSURE"
            )

            return {
                "success": False,
                "status": "PAYMENT_PLAN_NOT_FOUND",
                "message": (
                    f"Payment plan {plan_id} was not found."
                )
            }

        row = matching.iloc[0]

        customer_id = str(
            row.get("customer_id", "")
        ).strip()

        loan_id = str(
            row.get("loan_id", "")
        ).strip()

        current_status = str(
            row.get("status", "")
        ).strip().upper()

        # ---------------------------------------------
        # ACTIVE-PLAN GUARDRAIL
        # ---------------------------------------------
        if current_status != "ACTIVE":
            log_event(
                customer_id=customer_id or "UNKNOWN",
                event_type="PAYMENT_PLAN_CLOSURE",
                description=(
                    f"Closure of payment plan {plan_id} was blocked "
                    f"because its current status is {current_status}."
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_CLOSURE"
            )

            return {
                "success": False,
                "status": "PAYMENT_PLAN_NOT_ACTIVE",
                "plan_id": plan_id,
                "current_status": current_status,
                "message": (
                    f"Payment plan {plan_id} is not active and "
                    f"cannot be closed through this workflow."
                )
            }

        # ---------------------------------------------
        # CLOSE THE PLAN
        # ---------------------------------------------
        plan_row_number = matching.index[0] + 2

        status_column = headers.index("status") + 1
        reason_column = headers.index("closure_reason") + 1
        closed_by_column = headers.index("closed_by") + 1
        closed_at_column = headers.index("closed_at") + 1

        closed_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        worksheet.update_cell(
            plan_row_number,
            status_column,
            "CLOSED"
        )

        worksheet.update_cell(
            plan_row_number,
            reason_column,
            closure_reason
        )

        worksheet.update_cell(
            plan_row_number,
            closed_by_column,
            officer_id
        )

        worksheet.update_cell(
            plan_row_number,
            closed_at_column,
            closed_at
        )

        # ---------------------------------------------
        # AUDIT LOG
        # ---------------------------------------------
        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_PLAN_CLOSURE",
            description=(
                f"Payment plan {plan_id} for loan {loan_id} "
                f"was closed by authorized Recoveries Officer "
                f"{officer_id}. Closure reason: {closure_reason}"
            ),
            status="SUCCESS",
            agent="PAYMENT_PLAN_CLOSURE"
        )

        return {
            "success": True,
            "status": "PAYMENT_PLAN_CLOSED",
            "plan_id": plan_id,
            "customer_id": customer_id,
            "loan_id": loan_id,
            "closed_by": officer_id,
            "closed_at": closed_at,
            "closure_reason": closure_reason,
            "message": (
                f"Payment plan {plan_id} was successfully closed "
                f"through the authorized Recoveries Officer workflow."
            )
        }


    except Exception as error:
        log_event(
            customer_id="UNKNOWN",
            event_type="PAYMENT_PLAN_CLOSURE",
            description=(
                f"Payment plan closure encountered a "
                f"system error for plan {plan_id}: {str(error)}"
            ),
            status="FAILED",
            agent="PAYMENT_PLAN_CLOSURE"
        )

        return {
            "success": False,
            "status": "PAYMENT_PLAN_CLOSURE_ERROR",
            "message": str(error)
        }


if __name__ == "__main__":

    print("==========================================")
    print("PAYMENT PLAN + KYC GUARDRAIL TEST")
    print("==========================================")

    # ---------------------------------------------
    # TEST 1
    # ---------------------------------------------
    print("\nTEST 1: Payment Plan Access Without KYC")
    print("------------------------------------------")

    result = get_payment_plan(
        customer_id="CUST001",
        kyc_verified=False
    )

    print(result)

    # ---------------------------------------------
    # TEST 2
    # ---------------------------------------------
    print("\nTEST 2: Payment Plan Access After KYC")
    print("------------------------------------------")

    result = get_payment_plan(
        customer_id="CUST001",
        kyc_verified=True
    )

    print(result)

    # ---------------------------------------------
    # TEST 3
    # ---------------------------------------------
    print("\nTEST 3: Unknown Customer After KYC")
    print("------------------------------------------")

    result = get_payment_plan(
        customer_id="CUST999",
        kyc_verified=True
    )

    print(result)

    # ---------------------------------------------
    # TEST 4
    # ---------------------------------------------
    print("\nTEST 4: Unauthorized Payment Plan Closure")
    print("------------------------------------------")

    result = close_payment_plan(
        plan_id="PLAN007",
        officer_id="OFF999",
        closure_reason="Replacement requested by customer."
    )

    print(result)

    # ---------------------------------------------
    # TEST 5
    # ---------------------------------------------
    print("\nTEST 5: Missing Closure Reason")
    print("------------------------------------------")

    result = close_payment_plan(
        plan_id="PLAN007",
        officer_id="OFF001",
        closure_reason=""
    )

    print(result)

    # ---------------------------------------------
    # TEST 6
    # ---------------------------------------------
    print("\nTEST 6: Active Payment Plans By National ID")
    print("------------------------------------------")

    result = get_active_payment_plans_by_national_id(
        national_id="00-000001A00",
        officer_id="OFF001"
    )

    print(result)

    print("\n==========================================")
    print("PAYMENT PLAN TEST COMPLETE")
    print("==========================================")
