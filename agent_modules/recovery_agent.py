import os
import re
import calendar
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    ModelSettings,
    function_tool,
    set_tracing_disabled,
)

from tools.kyc_tools import verify_customer_by_identity
from tools.loan_tools import get_customer_loans, get_loan_balance
from tools.payment_tools import (
    get_payment_history,
    verify_payment,
)
from tools.payment_plan_tools import get_payment_plan
from tools.payment_plan_request_tools import (
    submit_payment_plan_request,
    get_payment_plan_request,
)


# ============================================================
# ENVIRONMENT
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

ENV_FILE = os.path.join(
    BASE_DIR,
    ".env"
)

load_dotenv(ENV_FILE)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError(
        "GOOGLE_API_KEY was not found in the project .env file"
    )


# ============================================================
# GEMINI MODEL
# ============================================================

google_client = AsyncOpenAI(
    api_key=GOOGLE_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

google_model = OpenAIChatCompletionsModel(
    model="gemini-3.5-flash-lite",
    openai_client=google_client,
)

set_tracing_disabled(disabled=True)


# ============================================================
# DETERMINISTIC MONEY PARSER
# ============================================================

def extract_monetary_amount(text: str):
    """
    Deterministically extract a monetary amount.

    Supported examples:
        $800              -> 800.0
        $1,000            -> 1000.0
        $10,000           -> 10000.0
        $100,000          -> 100000.0
        800 dollars       -> 800.0
        1,000 dollars     -> 1000.0
        USD 800           -> 800.0
        USD 1,000         -> 1000.0
    """

    if not isinstance(text, str):
        return None

    text = text.strip()

    if not text:
        return None

    # --------------------------------------------------------
    # IMPORTANT:
    # Match the complete monetary number first.
    #
    # This explicitly handles:
    #   1,000
    #   10,000
    #   100,000
    #   1,000.50
    #
    # Commas are thousands separators.
    # --------------------------------------------------------

    amount_pattern = r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?"

    # --------------------------------------------------------
    # 1. Dollar symbol
    #
    # $800
    # $1,000
    # $10,000
    # $100,000
    #
    # The dollar sign is matched literally.
    # --------------------------------------------------------

    match = re.search(
        r"\$\s*(" + amount_pattern + r")",
        text,
        re.IGNORECASE,
    )

    if match:
        raw_amount = match.group(1)

        try:
            amount = float(
                raw_amount.replace(",", "")
            )

            if amount > 0:
                return amount

        except ValueError:
            pass

    # --------------------------------------------------------
    # 2. USD
    #
    # USD 800
    # USD 1,000
    # USD 10,000
    # --------------------------------------------------------

    match = re.search(
        r"\bUSD\s*(" + amount_pattern + r")",
        text,
        re.IGNORECASE,
    )

    if match:
        raw_amount = match.group(1)

        try:
            amount = float(
                raw_amount.replace(",", "")
            )

            if amount > 0:
                return amount

        except ValueError:
            pass

    # --------------------------------------------------------
    # 3. Dollars
    #
    # 800 dollars
    # 1,000 dollars
    # 10,000 dollars
    # --------------------------------------------------------

    match = re.search(
        r"(" + amount_pattern + r")\s*dollars?",
        text,
        re.IGNORECASE,
    )

    if match:
        raw_amount = match.group(1)

        try:
            amount = float(
                raw_amount.replace(",", "")
            )

            if amount > 0:
                return amount

        except ValueError:
            pass

    # --------------------------------------------------------
    # 4. Standalone comma-separated amount
    #
    # 1,000
    # 10,000
    # 100,000
    # --------------------------------------------------------

    match = re.search(
        r"(?<![\d,])"
        r"(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?)"
        r"(?![\d,])",
        text,
    )

    if match:
        raw_amount = match.group(1)

        try:
            amount = float(
                raw_amount.replace(",", "")
            )

            if amount > 0:
                return amount

        except ValueError:
            pass

    # --------------------------------------------------------
    # 5. Plain number
    #
    # Only use this as the final fallback.
    # --------------------------------------------------------

    matches = re.findall(
        r"(?<![\d,])"
        r"(\d+(?:\.\d{1,2})?)"
        r"(?![\d,])",
        text,
    )

    for raw_amount in matches:

        try:
            amount = float(raw_amount)

        except ValueError:
            continue

        if amount <= 0:
            continue

        # Do not interpret obvious years as payment amounts.
        if 1900 <= amount <= 2100:
            continue

        return amount

    return None

# ============================================================
# DETERMINISTIC PAYMENT PLAN AMOUNT TOOL
# ============================================================

@function_tool
def parse_payment_plan_amount_tool(
    customer_message: str,
):
    """
    Deterministically extract the proposed payment amount
    from the customer's original message.

    This tool does NOT submit, approve, reject, or modify
    a payment plan.

    It only interprets the monetary value.
    """

    amount = extract_monetary_amount(
        customer_message
    )

    if amount is None:
        return {
            "success": False,
            "status": "AMOUNT_NOT_FOUND",
            "proposed_amount": None,
            "message": (
                "No valid monetary amount could be safely "
                "identified in the customer's message."
            ),
        }

    return {
        "success": True,
        "status": "AMOUNT_EXTRACTED",
        "proposed_amount": amount,
        "message": (
            "The monetary amount was deterministically "
            "extracted from the customer's message."
        ),
    }


# ============================================================
# CUSTOMER-FACING PAYMENT PLAN SANITISATION
# ============================================================

def _sanitize_payment_plan_request_result(result):
    """
    Convert internal payment-plan request data into a safe
    customer-facing response.

    Internal identifiers such as:

        request_id
        customer_id
        loan_id
        approved_by

    must never be returned to the customer-facing AI.
    """

    if not isinstance(result, dict):
        return result

    sanitized = {
        "success": result.get("success"),
        "status": result.get("status"),
        "message": result.get("message"),
    }

    # --------------------------------------------------------
    # Safe top-level fields
    # --------------------------------------------------------

    safe_fields = [
        "proposed_amount",
        "frequency",
        "start_date",
        "next_payment_date",
        "number_of_payments",
        "customer_consent",
        "approval_status",
        "submitted_at",
        "approved_at",
        "rejection_reason",
        "count",
    ]

    for key in safe_fields:
        if key in result:
            sanitized[key] = result[key]

    # --------------------------------------------------------
    # Customer-facing request list
    # --------------------------------------------------------

    requests = result.get("requests")

    if isinstance(requests, list):

        sanitized_requests = []

        for row in requests:

            if not isinstance(row, dict):
                continue

            safe_row = {
                "proposed_amount": row.get(
                    "proposed_amount"
                ),
                "frequency": row.get(
                    "frequency"
                ),
                "start_date": row.get(
                    "start_date"
                ),
                "next_payment_date": row.get(
                    "next_payment_date"
                ),
                "number_of_payments": row.get(
                    "number_of_payments"
                ),
                "customer_consent": row.get(
                    "customer_consent"
                ),
                "submitted_at": row.get(
                    "submitted_at"
                ),
                "approval_status": row.get(
                    "approval_status"
                ),
            }

            approval_status = str(
                row.get(
                    "approval_status",
                    "",
                )
            ).upper()

            # ------------------------------------------------
            # Approved request
            # ------------------------------------------------

            if approval_status == "APPROVED":

                safe_row["approved_at"] = row.get(
                    "approved_at"
                )

            # ------------------------------------------------
            # Rejected request
            # ------------------------------------------------

            elif approval_status == "REJECTED":

                safe_row["rejection_reason"] = row.get(
                    "rejection_reason"
                )

                safe_row["decision_at"] = row.get(
                    "approved_at"
                )

            sanitized_requests.append(
                safe_row
            )

        # ----------------------------------------------------
        # Prioritise pending requests
        # ----------------------------------------------------

        pending_requests = [
            row
            for row in sanitized_requests
            if str(
                row.get(
                    "approval_status",
                    "",
                )
            ).upper() == "PENDING"
        ]

        if pending_requests:

            sanitized["requests"] = (
                pending_requests
            )

            sanitized["count"] = len(
                pending_requests
            )

            sanitized["status"] = (
                "PENDING_REQUEST_FOUND"
            )

            sanitized["message"] = (
                "There is a pending payment-plan "
                "request awaiting Recoveries Officer "
                "review."
            )

        else:

            # ------------------------------------------------
            # No pending request.
            # Return most recent request.
            # ------------------------------------------------

            if sanitized_requests:

                def sort_key(row):
                    return (
                        row.get(
                            "submitted_at"
                        )
                        or ""
                    )

                sanitized_requests.sort(
                    key=sort_key,
                    reverse=True,
                )

                latest_request = (
                    sanitized_requests[0]
                )

                sanitized["requests"] = [
                    latest_request
                ]

                sanitized["count"] = 1

            else:

                sanitized["requests"] = []
                sanitized["count"] = 0

    return sanitized


# ============================================================
# KYC TOOL
# ============================================================

@function_tool
def kyc_verification_tool(
    national_id: str,
    date_of_birth: str,
):
    """
    Verify a customer using National ID and date of birth.
    """

    return verify_customer_by_identity(
        national_id=national_id,
        date_of_birth=date_of_birth,
    )


# ============================================================
# CUSTOMER LOANS TOOL
# ============================================================

@function_tool
def customer_loans_tool(
    national_id: str,
    date_of_birth: str,
):
    """
    Verify the customer and return safe loan information.

    Internal customer_id and loan_id are removed before
    the result reaches the AI.
    """

    kyc_result = verify_customer_by_identity(
        national_id=national_id,
        date_of_birth=date_of_birth,
    )

    if not kyc_result.get("verified"):
        return kyc_result

    customer_id = kyc_result.get(
        "customer_id"
    )

    result = get_customer_loans(
        customer_id=customer_id,
        kyc_verified=True,
    )

    if not result.get("success"):
        return {
            "success": False,
            "status": result.get("status"),
            "message": result.get("message"),
        }

    safe_loans = []

    for loan in result.get(
        "loans",
        [],
    ):

        safe_loans.append(
            {
                "loan_type": loan.get(
                    "loan_type"
                ),
                "original_amount": loan.get(
                    "original_amount"
                ),
                "outstanding_principal": loan.get(
                    "outstanding_principal"
                ),
                "accrued_interest": loan.get(
                    "accrued_interest"
                ),
                "total_balance": loan.get(
                    "total_balance"
                ),
                "days_in_arrears": loan.get(
                    "days_in_arrears"
                ),
                "loan_status": loan.get(
                    "loan_status"
                ),
            }
        )

    return {
        "success": True,
        "status": "LOANS_FOUND",
        "count": len(safe_loans),
        "loans": safe_loans,
    }


# ============================================================
# LOAN BALANCE TOOL
# ============================================================

@function_tool
def loan_balance_tool(
    national_id: str,
    date_of_birth: str,
):
    """
    Verify customer and retrieve their loan balance.

    KYC is mandatory before any loan information is disclosed.
    """

    kyc_result = verify_customer_by_identity(
        national_id=national_id,
        date_of_birth=date_of_birth,
    )

    if not kyc_result.get("verified"):
        return kyc_result

    customer_id = kyc_result.get(
        "customer_id"
    )

    loans_result = get_customer_loans(
        customer_id=customer_id,
        kyc_verified=True,
    )

    if not loans_result.get("success"):
        return {
            "success": False,
            "status": loans_result.get(
                "status"
            ),
            "message": loans_result.get(
                "message"
            ),
        }

    loans = loans_result.get(
        "loans",
        [],
    )

    if not loans:
        return {
            "success": False,
            "status": "NO_LOANS_FOUND",
            "message": (
                "No loan accounts were found for "
                "the verified customer."
            ),
        }

    if len(loans) > 1:
        return {
            "success": False,
            "status": "MULTIPLE_LOANS_FOUND",
            "message": (
                "Multiple loan accounts were found. "
                "A Recoveries Officer must assist "
                "with identifying the applicable loan."
            ),
        }

    loan_id = loans[0].get(
        "loan_id"
    )

    if not loan_id:
        return {
            "success": False,
            "status": "LOAN_NOT_FOUND",
            "message": (
                "Unable to identify the customer's "
                "loan account."
            ),
        }

    result = get_loan_balance(
        customer_id=customer_id,
        loan_id=loan_id,
        kyc_verified=True,
    )

    if not result.get("success"):
        return {
            "success": False,
            "status": result.get(
                "status"
            ),
            "message": result.get(
                "message"
            ),
        }

    loan = result.get(
        "loan",
        {}
    )

    return {
        "success": True,
        "status": "LOAN_BALANCE_FOUND",
        "loan": {
            "loan_type": loan.get(
                "loan_type"
            ),
            "original_amount": loan.get(
                "original_amount"
            ),
            "outstanding_principal": loan.get(
                "outstanding_principal"
            ),
            "accrued_interest": loan.get(
                "accrued_interest"
            ),
            "total_balance": loan.get(
                "total_balance"
            ),
            "days_in_arrears": loan.get(
                "days_in_arrears"
            ),
            "loan_status": loan.get(
                "loan_status"
            ),
        },
    }


# ============================================================
# PAYMENT HISTORY TOOL
# ============================================================

@function_tool
def payment_history_tool(
    national_id: str,
    date_of_birth: str,
):
    """
    Verify customer and retrieve payment history.

    Internal identifiers are removed before returning
    information to the customer-facing AI.
    """

    kyc_result = verify_customer_by_identity(
        national_id=national_id,
        date_of_birth=date_of_birth,
    )

    if not kyc_result.get("verified"):
        return kyc_result

    customer_id = kyc_result.get(
        "customer_id"
    )

    loans_result = get_customer_loans(
        customer_id=customer_id,
        kyc_verified=True,
    )

    if not loans_result.get("success"):
        return {
            "success": False,
            "status": loans_result.get(
                "status"
            ),
            "message": loans_result.get(
                "message"
            ),
        }

    loans = loans_result.get(
        "loans",
        [],
    )

    if not loans:
        return {
            "success": False,
            "status": "NO_LOANS_FOUND",
            "message": (
                "No loan accounts were found for "
                "the verified customer."
            ),
        }

    if len(loans) > 1:
        return {
            "success": False,
            "status": "MULTIPLE_LOANS_FOUND",
            "message": (
                "Multiple loan accounts were found. "
                "A Recoveries Officer must assist."
            ),
        }

    loan_id = loans[0].get(
        "loan_id"
    )

    result = get_payment_history(
        customer_id=customer_id,
        kyc_verified=True,
    )

    if not result.get("success"):
        return {
            "success": False,
            "status": result.get(
                "status"
            ),
            "message": result.get(
                "message"
            ),
        }

    safe_payments = []

    for payment in result.get(
        "payments",
        [],
    ):

        safe_payments.append(
            {
                "payment_date": payment.get(
                    "payment_date"
                ),
                "amount": payment.get(
                    "amount"
                ),
                "payment_method": payment.get(
                    "payment_method"
                ),
                "reference": payment.get(
                    "reference"
                ),
                "status": payment.get(
                    "status"
                ),
            }
        )

    return {
        "success": True,
        "status": "PAYMENT_HISTORY_FOUND",
        "count": len(safe_payments),
        "payments": safe_payments,
    }


# ============================================================
# PAYMENT VERIFICATION TOOL
# ============================================================

@function_tool
def payment_verification_tool(
    national_id: str,
    date_of_birth: str,
    payment_reference: str,
):
    """
    Verify a customer and verify a payment reference.
    """

    kyc_result = verify_customer_by_identity(
        national_id=national_id,
        date_of_birth=date_of_birth,
    )

    if not kyc_result.get("verified"):
        return kyc_result

    customer_id = kyc_result.get(
        "customer_id"
    )

    loans_result = get_customer_loans(
        customer_id=customer_id,
        kyc_verified=True,
    )

    if not loans_result.get("success"):
        return {
            "success": False,
            "status": loans_result.get(
                "status"
            ),
            "message": loans_result.get(
                "message"
            ),
        }

    loans = loans_result.get(
        "loans",
        [],
    )

    if not loans:
        return {
            "success": False,
            "status": "NO_LOANS_FOUND",
            "message": (
                "No loan accounts were found for "
                "the verified customer."
            ),
        }

    if len(loans) > 1:
        return {
            "success": False,
            "status": "MULTIPLE_LOANS_FOUND",
            "message": (
                "Multiple loan accounts were found. "
                "A Recoveries Officer must assist."
            ),
        }

    loan_id = loans[0].get(
        "loan_id"
    )

    if not loan_id:
        return {
            "success": False,
            "status": "LOAN_NOT_FOUND",
            "message": (
                "Unable to identify the customer's "
                "loan account."
            ),
        }

    result = verify_payment(
        customer_id=customer_id,
        loan_id=loan_id,
        reference=payment_reference,
        kyc_verified=True,
    )

    if not result.get("success"):
        return {
            "success": False,
            "status": result.get(
                "status"
            ),
            "message": result.get(
                "message"
            ),
        }

    payment = result.get(
        "payment",
        {}
    )

    return {
        "success": True,
        "status": result.get(
            "status"
        ),
        "payment": {
            "payment_date": payment.get(
                "payment_date"
            ),
            "amount": payment.get(
                "amount"
            ),
            "payment_method": payment.get(
                "payment_method"
            ),
            "reference": payment.get(
                "reference"
            ),
            "status": payment.get(
                "status"
            ),
        },
        "message": (
            "Payment was successfully verified."
        ),
    }


# ============================================================
# ACTIVE PAYMENT PLAN TOOL
# ============================================================

@function_tool
def payment_plan_tool(
    national_id: str,
    date_of_birth: str,
):
    """
    Verify the customer and retrieve the current active
    payment plan.

    Internal identifiers are removed from the response.
    """

    # --------------------------------------------------------
    # STEP 1: KYC VERIFICATION
    # --------------------------------------------------------
    kyc_result = verify_customer_by_identity(
        national_id=national_id,
        date_of_birth=date_of_birth,
    )

    if not kyc_result.get("verified"):
        return kyc_result

    customer_id = kyc_result.get("customer_id")

    # --------------------------------------------------------
    # STEP 2: RETRIEVE PAYMENT PLANS
    # --------------------------------------------------------
    result = get_payment_plan(
        customer_id=customer_id,
        kyc_verified=True,
    )

    if not result.get("success"):
        return {
            "success": False,
            "status": result.get("status"),
            "message": result.get("message"),
        }

    # --------------------------------------------------------
    # STEP 3: READ PAYMENT PLANS LIST
    # --------------------------------------------------------
    payment_plans = result.get("payment_plans", [])

    if not isinstance(payment_plans, list):
        return {
            "success": False,
            "status": "INVALID_PAYMENT_PLAN_RESPONSE",
            "message": (
                "The payment-plan information returned by "
                "the system could not be safely interpreted."
            ),
        }

    # --------------------------------------------------------
    # STEP 4: FIND ACTIVE PAYMENT PLAN
    # --------------------------------------------------------
    active_plans = [
        plan
        for plan in payment_plans
        if isinstance(plan, dict)
        and str(plan.get("status", "")).strip().upper() == "ACTIVE"
    ]

    # --------------------------------------------------------
    # STEP 5: NO ACTIVE PLAN
    # --------------------------------------------------------
    if not active_plans:
        return {
            "success": True,
            "status": "NO_ACTIVE_PAYMENT_PLAN",
            "message": (
                "No active payment plan is currently "
                "recorded for the verified customer."
            ),
        }

    # --------------------------------------------------------
    # STEP 6: MULTIPLE ACTIVE PLANS
    # --------------------------------------------------------
    if len(active_plans) > 1:
        return {
            "success": False,
            "status": "MULTIPLE_ACTIVE_PAYMENT_PLANS",
            "message": (
                "Multiple active payment plans were found. "
                "A Recoveries Officer must review the account "
                "before payment-plan information can be confirmed."
            ),
        }

    # --------------------------------------------------------
    # STEP 7: RETURN SAFE CUSTOMER-FACING DETAILS
    # --------------------------------------------------------
    plan = active_plans[0]

    safe_plan = {
        "agreed_amount": plan.get("agreed_amount"),
        "frequency": plan.get("frequency"),
        "start_date": plan.get("start_date"),
        "next_payment_date": plan.get("next_payment_date"),
        "number_of_payments": plan.get("number_of_payments"),
        "status": "ACTIVE",
    }

    return {
        "success": True,
        "status": "ACTIVE_PAYMENT_PLAN_FOUND",
        "plan": safe_plan,
    }


# ============================================================
# PAYMENT PLAN REQUEST STATUS TOOL
# ============================================================

@function_tool
def payment_plan_request_status_tool(
    national_id: str,
    date_of_birth: str,
):
    """
    Verify customer and retrieve payment-plan request status.

    Pending requests are prioritised.

    If there is no pending request, the most recent request
    is returned.
    """

    kyc_result = verify_customer_by_identity(
        national_id=national_id,
        date_of_birth=date_of_birth,
    )

    if not kyc_result.get("verified"):
        return kyc_result

    customer_id = kyc_result.get(
        "customer_id"
    )

    result = get_payment_plan_request(
        customer_id=customer_id,
        kyc_verified=True,
    )

    return _sanitize_payment_plan_request_result(
        result
    )


# ============================================================
# PAYMENT PLAN REQUEST TOOL
# ============================================================

@function_tool
def payment_plan_request_tool(
    national_id: str,
    date_of_birth: str,
    proposed_amount: float,
    frequency: str,
    start_date: str,
    number_of_payments: int,
    customer_consent: bool,
):
    """
    Submit a payment-plan request after KYC and explicit
    customer consent.

    This tool does NOT approve or activate the plan.
    """

    # --------------------------------------------------------
    # KYC
    # --------------------------------------------------------

    kyc_result = verify_customer_by_identity(
        national_id=national_id,
        date_of_birth=date_of_birth,
    )

    if not kyc_result.get("verified"):
        return kyc_result

    # --------------------------------------------------------
    # Explicit customer consent
    # --------------------------------------------------------

    if customer_consent is not True:
        return {
            "success": False,
            "status": (
                "CUSTOMER_CONSENT_REQUIRED"
            ),
            "message": (
                "Explicit customer consent is required "
                "before the payment-plan request can "
                "be submitted."
            ),
        }

    # --------------------------------------------------------
    # Amount validation
    # --------------------------------------------------------

    try:
        proposed_amount = float(
            proposed_amount
        )

    except (TypeError, ValueError):

        return {
            "success": False,
            "status": "INVALID_AMOUNT",
            "message": (
                "The proposed payment amount is invalid."
            ),
        }

    if proposed_amount <= 0:

        return {
            "success": False,
            "status": "INVALID_AMOUNT",
            "message": (
                "The proposed payment amount must be "
                "greater than zero."
            ),
        }

    # --------------------------------------------------------
    # Frequency validation
    # --------------------------------------------------------

    frequency = str(
        frequency
    ).upper().strip()

    allowed_frequencies = {
        "WEEKLY",
        "BIWEEKLY",
        "MONTHLY",
    }

    if frequency not in allowed_frequencies:

        return {
            "success": False,
            "status": "INVALID_FREQUENCY",
            "message": (
                "Frequency must be WEEKLY, BIWEEKLY, "
                "or MONTHLY."
            ),
        }

    # --------------------------------------------------------
    # Number of payments validation
    # --------------------------------------------------------

    try:
        number_of_payments = int(
            number_of_payments
        )

    except (TypeError, ValueError):

        return {
            "success": False,
            "status": (
                "INVALID_NUMBER_OF_PAYMENTS"
            ),
            "message": (
                "The number of payments must be a "
                "positive whole number."
            ),
        }

    if number_of_payments <= 0:

        return {
            "success": False,
            "status": (
                "INVALID_NUMBER_OF_PAYMENTS"
            ),
            "message": (
                "The number of payments must be "
                "greater than zero."
            ),
        }

    # --------------------------------------------------------
    # Start date validation
    # --------------------------------------------------------

    try:

        start = datetime.strptime(
            start_date,
            "%Y-%m-%d",
        ).date()

    except (TypeError, ValueError):

        return {
            "success": False,
            "status": "INVALID_START_DATE",
            "message": (
                "Start date must use YYYY-MM-DD format."
            ),
        }

    if start < date.today():

        return {
            "success": False,
            "status": "START_DATE_IN_PAST",
            "message": (
                "The payment-plan start date cannot "
                "be in the past."
            ),
        }

    # --------------------------------------------------------
    # Customer ID
    # --------------------------------------------------------

    customer_id = kyc_result.get(
        "customer_id"
    )

    # --------------------------------------------------------
    # Loan lookup
    # --------------------------------------------------------

    loans_result = get_customer_loans(
        customer_id=customer_id,
        kyc_verified=True,
    )

    if not loans_result.get("success"):

        return {
            "success": False,
            "status": loans_result.get(
                "status"
            ),
            "message": loans_result.get(
                "message"
            ),
        }

    loans = loans_result.get(
        "loans",
        []
    )

    if not loans:

        return {
            "success": False,
            "status": "NO_LOANS_FOUND",
            "message": (
                "No loan accounts were found for "
                "the verified customer."
            ),
        }

    if len(loans) > 1:

        return {
            "success": False,
            "status": (
                "MULTIPLE_LOANS_FOUND"
            ),
            "message": (
                "Multiple loans were found. A Recoveries "
                "Officer must review the applicable loan "
                "before a payment-plan request can be "
                "submitted."
            ),
        }

    loan_id = loans[0].get(
        "loan_id"
    )

    # --------------------------------------------------------
    # Calculate next payment date
    # --------------------------------------------------------

    if frequency == "WEEKLY":

        next_payment_date = (
            start + timedelta(days=7)
        )

    elif frequency == "BIWEEKLY":

        next_payment_date = (
            start + timedelta(days=14)
        )

    else:

        month = start.month
        year = start.year

        if month == 12:

            next_month = 1
            next_year = year + 1

        else:

            next_month = month + 1
            next_year = year

        last_day = calendar.monthrange(
            next_year,
            next_month,
        )[1]

        next_day = min(
            start.day,
            last_day,
        )

        next_payment_date = date(
            next_year,
            next_month,
            next_day,
        )

    # --------------------------------------------------------
    # Submit request to deterministic backend
    # --------------------------------------------------------

    result = submit_payment_plan_request(
        customer_id=customer_id,
        loan_id=loan_id,
        proposed_amount=proposed_amount,
        frequency=frequency,
        start_date=start.strftime(
            "%Y-%m-%d"
        ),
        next_payment_date=next_payment_date.strftime(
            "%Y-%m-%d"
        ),
        number_of_payments=number_of_payments,
        customer_consent=True,
    )

    return _sanitize_payment_plan_request_result(
        result
    )


# ============================================================
# RECOVERIES AI AGENT INSTRUCTIONS
# ============================================================

RECOVERY_AGENT_INSTRUCTIONS = """
You are a Banking Recoveries AI Agent.

You assist customers with:

- Loan balances
- Payment history
- Payment verification
- Payment plans
- Recovery-related queries

You operate under strict banking controls.

============================================================
KYC
============================================================

Customer-specific information MUST NOT be disclosed until
KYC has been successfully completed.

KYC requires:

- National ID
- Date of birth

Never bypass KYC.

If KYC fails, do not disclose:

- Loan balances
- Payment history
- Payment-plan information
- Customer-specific financial information

Ask the customer to provide the required identification
details again or escalate where appropriate.

============================================================
INTERNAL IDENTIFIERS
============================================================

NEVER disclose:

- Customer ID
- Loan ID
- Payment Plan ID
- Payment Plan Request ID
- Officer ID
- Approved-by identifier

Never repeat an internal identifier returned by a tool.

Treat backend identifiers as internal system information.

============================================================
LOAN INFORMATION
============================================================

After successful KYC, you may provide:

- Loan type
- Original loan amount
- Outstanding principal
- Accrued interest
- Total balance
- Days in arrears
- Loan status

Do not disclose internal loan IDs.

============================================================
PAYMENT INFORMATION
============================================================

After successful KYC, you may provide appropriate payment
history and payment verification information.

Do not disclose internal customer or loan identifiers.

============================================================
PAYMENT PLAN INFORMATION
============================================================

You may explain:

- Payment amount
- Frequency
- Start date
- Next payment date
- Number of payments
- Current approval status
- Rejection reason where appropriate
- Approval or decision date where appropriate

Never disclose:

- Request ID
- Customer ID
- Loan ID
- Officer ID
- Approved-by identifier

When a customer asks for their current or active payment
plan:

1. Use the payment-plan tool.

2. Treat the tool result as the authoritative source.

3. Use ONLY the payment-plan fields returned by the tool.

4. Never infer, calculate, remember, or invent payment-plan
   amounts, dates, frequencies, payment counts, or statuses.

5. If the tool reports NO_ACTIVE_PAYMENT_PLAN, explain that
   no active payment plan is currently recorded.

6. If multiple active plans are reported, escalate to a
   Recoveries Officer.

7. Do not use historical payment-plan records to construct
   a current active plan.

============================================================
PAYMENT PLAN REQUEST STATUS
============================================================

When a customer asks about the status of a payment-plan
request:

1. Use the payment-plan request status tool.

2. If there is a PENDING request, report the pending request
   rather than an old historical request.

3. Explain that the request is awaiting Recoveries Officer
   review and approval.

4. If there is no pending request, report the most recent
   relevant request.

5. Never expose internal identifiers.

============================================================
PAYMENT PLAN REQUESTS
============================================================

Customers may request a payment plan.

CRITICAL CONSENT WORKFLOW:

A customer's initial payment-plan request is NOT consent.

Do NOT submit a payment-plan request on the same turn in
which the customer first proposes or asks for a payment plan.

============================================================
STEP 1 — KYC
============================================================

Verify the customer's:

- National ID
- Date of birth

before accessing customer-specific information.

============================================================
STEP 2 — EXTRACT PAYMENT TERMS
============================================================

The required payment-plan terms are:

- Proposed payment amount
- Frequency
- Start date
- Number of payments

The proposed payment amount MUST be extracted using the
deterministic payment-plan amount parser tool.

Do NOT rely on your own interpretation of commas in monetary
amounts.

============================================================
MANDATORY MONEY PARSING RULE
============================================================

When the customer provides a monetary amount, use the
parse_payment_plan_amount_tool.

The tool is the authoritative mechanism for extracting the
monetary value.

Examples:

"$800" -> 800

"$1,000" -> 1000

"$10,000" -> 10000

"$100,000" -> 100000

"800 dollars" -> 800

"1,000 dollars" -> 1000

"10,000 dollars" -> 10000

"USD 800" -> 800

"USD 1,000" -> 1000

"USD 10,000" -> 10000

A comma between groups of digits is a THOUSANDS SEPARATOR.

Therefore:

"$1,000" = 1000

NOT:

1

NOT:

100

NOT:

0

NOT:

an incomplete amount

For the exact customer message:

"I want to change my monthly payment to $1,000."

the correct interpretation is:

proposed_amount = 1000

frequency = MONTHLY

The amount is complete and valid.

Do NOT ask the customer to repeat the amount.

If parse_payment_plan_amount_tool returns:

status = AMOUNT_EXTRACTED

use the returned proposed_amount exactly.

Do not:

- Round it
- Estimate it
- Reduce it
- Increase it
- Replace it
- Ask the customer to repeat it

If parse_payment_plan_amount_tool returns:

status = AMOUNT_NOT_FOUND

then and only then may you ask the customer for
the missing amount.

============================================================
STEP 3 — FREQUENCY
============================================================

Extract the frequency exactly.

Allowed frequencies are:

- WEEKLY
- BIWEEKLY
- MONTHLY

If frequency is missing, ask for it.

Do not invent a frequency.

============================================================
STEP 4 — START DATE
============================================================

Extract the start date from the customer's message.

Convert it to YYYY-MM-DD only when calling the backend
payment-plan request tool.

If the start date is missing, ask for it.

Do not invent a start date.

============================================================
STEP 5 — NUMBER OF PAYMENTS
============================================================

Extract the number of payments exactly.

If the number of payments is missing, ask for it.

Do not invent a number.

============================================================
STEP 6 — PRESENT THE PROPOSAL
============================================================

Once all required terms are available, present the complete
proposal clearly.

Example:

"You are proposing a monthly payment of $1,000 starting
15 October 2026 for 6 payments. Would you like to confirm
these terms?"

Do NOT submit the request yet.

============================================================
STEP 7 — EXPLICIT CONSENT
============================================================

The customer must provide explicit consent in a separate
subsequent message.

These are NOT consent:

- "I would like a payment plan."
- "I want to set up a payment plan."
- "Please arrange $700 monthly for 6 months."
- "Can you set up this payment plan?"
- Any initial payment-plan proposal.

Examples of explicit consent:

- "Yes, I consent to the payment plan."
- "I confirm and agree to the payment plan."
- "Yes, I accept those terms."
- "I confirm."

Only after explicit subsequent confirmation may the
payment-plan request tool be called.

============================================================
CRITICAL TOOL RULE
============================================================

The payment_plan_request_tool MUST NOT be called during
the initial payment-plan proposal turn.

The initial proposal is NOT consent.

After presenting the proposal:

STOP.

Wait for the customer's next message.

Only call payment_plan_request_tool after explicit consent
has been provided in a subsequent message.

============================================================
AFTER EXPLICIT CONSENT
============================================================

After explicit customer consent:

1. Submit the payment-plan request using the backend tool.

2. Inform the customer that the request has been submitted.

3. Explain that it is pending Recoveries Officer review.

4. Never claim the request is approved.

5. Never activate the payment plan yourself.

6. Never reject the request yourself.

A Recoveries Officer must review and approve or reject
the request.

============================================================
MULTIPLE LOANS
============================================================

If multiple loans exist and the applicable loan cannot be
determined safely:

- Do not guess.
- Do not expose loan IDs.
- Ask the customer to identify the loan using safe
  information such as loan type or balance.
- Escalate to a Recoveries Officer where necessary.

============================================================
GUARDRAILS
============================================================

Never bypass KYC.

Never disclose confidential information before KYC.

Never fabricate balances.

Never fabricate payments.

Never fabricate payment-plan requests.

Never fabricate approvals.

Never approve your own payment-plan request.

Never activate or modify an active payment plan without
the authorized workflow.

Never expose internal identifiers.

Never repeat internal identifiers merely because a backend
tool returned them.

When an action requires human authority, clearly explain
that a Recoveries Officer must review or complete it.

============================================================
CUSTOMER COMMUNICATION
============================================================

Be:

- Professional
- Concise
- Respectful
- Clear

Use customer-friendly banking language.

Do not overwhelm customers with technical details.

Do not mention internal system architecture unless necessary.

When appropriate, explain what happens next.

============================================================
SOURCE OF TRUTH
============================================================

Google Sheets is the system of record.

Deterministic Python tools retrieve and modify records.

Your role is to interpret information and communicate with
customers.

Do not invent database information.

============================================================
ESCALATION
============================================================

Escalate when:

- KYC cannot be safely completed.
- Multiple loans cannot be safely distinguished.
- A payment-plan decision requires officer authority.
- An exception falls outside the defined workflow.
- A customer requests an action you are not authorized
  to perform.
"""


# ============================================================
# RECOVERIES AI AGENT
# ============================================================

recovery_agent = Agent(
    name="Recoveries AI Agent",

    model=google_model,

    instructions=RECOVERY_AGENT_INSTRUCTIONS,

    model_settings=ModelSettings(
        temperature=0.0,
    ),

    tools=[
        kyc_verification_tool,
        customer_loans_tool,
        loan_balance_tool,
        payment_history_tool,
        payment_verification_tool,
        payment_plan_tool,
        payment_plan_request_status_tool,

        # Deterministic monetary extraction
        parse_payment_plan_amount_tool,

        # Payment-plan submission
        payment_plan_request_tool,
    ],
)