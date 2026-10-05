
from datetime import datetime, date, timedelta
import calendar
import pandas as pd

from database.google_sheets import open_database
from audit.logger import log_event
from tools.notification_tools import create_notification


def process_verified_payment_for_plan(
    payment_id,
    customer_id,
    loan_id
):
    """
    Process a VERIFIED payment against an ACTIVE payment plan.

    Business rules:
    1. Payment must exist.
    2. Payment must have VERIFIED status.
    3. Payment customer must match customer_id.
    4. Payment loan must match loan_id.
    5. An ACTIVE payment plan must exist.
    6. The same payment cannot be processed twice.
    7. Payment amount must be greater than zero.
    8. A full payment advances the payment schedule.
    9. A partial payment is accepted but does not satisfy the full instalment.
    10. A partial payment does not advance the payment-plan schedule.
    11. The remaining instalment shortfall remains outstanding.
    12. Payment-plan dates are advanced according to frequency.
    11. Every important action is audited.
    12. Customer notification is created after successful processing.

    IMPORTANT:
    The financial decision is deterministic.
    The LLM does not decide whether a payment is full or partial.
    """

    payment_id = str(payment_id).strip()
    customer_id = str(customer_id).strip()
    loan_id = str(loan_id).strip()

    # -------------------------------------------------
    # 1. Validate required identifiers
    # -------------------------------------------------

    if not payment_id or not customer_id or not loan_id:

        log_event(
            customer_id=customer_id or "UNKNOWN",
            event_type="PAYMENT_PLAN_PAYMENT",
            description=(
                "Payment-plan payment processing was blocked "
                "because a required identifier was missing."
            ),
            status="BLOCKED",
            agent="PAYMENT_PLAN_LIFECYCLE"
        )

        return {
            "success": False,
            "status": "REQUIRED_IDENTIFIER_MISSING",
            "message": (
                "payment_id, customer_id and loan_id are required."
            )
        }

    try:

        spreadsheet = open_database()

        # =================================================
        # 2. Retrieve payment
        # =================================================

        payments_sheet = spreadsheet.worksheet("Payments")

        payment_records = payments_sheet.get_all_records()

        payments = pd.DataFrame(payment_records)

        if payments.empty:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment {payment_id} could not be processed "
                    f"because no payment records were found."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "PAYMENT_NOT_FOUND",
                "payment_id": payment_id,
                "message": "Payment was not found."
            }

        payment_match = payments[
            payments["payment_id"].astype(str).str.strip()
            == payment_id
        ]

        if payment_match.empty:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment {payment_id} was not found."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "PAYMENT_NOT_FOUND",
                "payment_id": payment_id,
                "message": "Payment was not found."
            }

        payment = payment_match.iloc[0]

        payment_customer_id = str(
            payment["customer_id"]
        ).strip()

        payment_loan_id = str(
            payment["loan_id"]
        ).strip()

        payment_status = str(
            payment["status"]
        ).strip().upper()

        # =================================================
        # 3. Payment must be VERIFIED
        # =================================================

        if payment_status != "VERIFIED":

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment {payment_id} was rejected for "
                    f"payment-plan processing because its status "
                    f"is {payment_status}, not VERIFIED."
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "PAYMENT_NOT_VERIFIED",
                "payment_id": payment_id,
                "payment_status": payment_status,
                "message": (
                    "Only VERIFIED payments can be processed "
                    "against a payment plan."
                )
            }

        # =================================================
        # 4. Validate customer ownership
        # =================================================

        if payment_customer_id != customer_id:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment {payment_id} was blocked because "
                    f"the payment customer {payment_customer_id} "
                    f"does not match the supplied customer "
                    f"{customer_id}."
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "PAYMENT_CUSTOMER_MISMATCH",
                "payment_id": payment_id,
                "message": (
                    "Payment does not belong to the supplied customer."
                )
            }

        # =================================================
        # 5. Validate loan ownership
        # =================================================

        if payment_loan_id != loan_id:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment {payment_id} was blocked because "
                    f"the payment loan {payment_loan_id} does not "
                    f"match the supplied loan {loan_id}."
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "PAYMENT_LOAN_MISMATCH",
                "payment_id": payment_id,
                "message": (
                    "Payment does not belong to the supplied loan."
                )
            }

        # =================================================
        # 6. GLOBAL IDEMPOTENCY CHECK
        # =================================================

        # Check ALL payment plans, including CLOSED plans.
        #
        # This prevents a payment that was already processed
        # against a previous payment plan from being processed
        # again against a new ACTIVE plan.

        plans_sheet = spreadsheet.worksheet("Payment Plans")

        plan_records = plans_sheet.get_all_records()

        plans = pd.DataFrame(plan_records)

        if not plans.empty and "last_payment_id" in plans.columns:

            processed_payment_matches = plans[
                plans["last_payment_id"]
                .astype(str)
                .str.strip()
                == payment_id
            ]

            if not processed_payment_matches.empty:

                processed_plan = processed_payment_matches.iloc[0]

                processed_plan_id = str(
                    processed_plan["plan_id"]
                ).strip()

                processed_plan_customer_id = str(
                    processed_plan["customer_id"]
                ).strip()

                processed_plan_loan_id = str(
                    processed_plan["loan_id"]
                ).strip()

                log_event(
                    customer_id=customer_id,
                    event_type="PAYMENT_PLAN_PAYMENT",
                    description=(
                        f"Payment {payment_id} was already processed "
                        f"against payment plan {processed_plan_id}. "
                        f"Duplicate processing was blocked."
                    ),
                    status="BLOCKED",
                    agent="PAYMENT_PLAN_LIFECYCLE"
                )

                return {
                    "success": False,
                    "status": "PAYMENT_ALREADY_PROCESSED",
                    "payment_id": payment_id,
                    "plan_id": processed_plan_id,
                    "customer_id": processed_plan_customer_id,
                    "loan_id": processed_plan_loan_id,
                    "message": (
                        "This payment has already been processed "
                        "against a payment plan."
                    )
                }

        # =================================================
        # 7. Retrieve ACTIVE payment plan
        # =================================================

        if plans.empty:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"No payment plans were found for customer "
                    f"{customer_id} and loan {loan_id}."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "NO_PAYMENT_PLAN_FOUND",
                "customer_id": customer_id,
                "loan_id": loan_id,
                "message": "No payment plan was found."
            }

        active_plans = plans[
            (plans["customer_id"].astype(str).str.strip() == customer_id)
            & (plans["loan_id"].astype(str).str.strip() == loan_id)
            & (
                plans["status"]
                .astype(str)
                .str.strip()
                .str.upper()
                == "ACTIVE"
            )
        ]

        if active_plans.empty:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"No ACTIVE payment plan exists for customer "
                    f"{customer_id} and loan {loan_id}."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "ACTIVE_PAYMENT_PLAN_NOT_FOUND",
                "customer_id": customer_id,
                "loan_id": loan_id,
                "message": (
                    "No ACTIVE payment plan exists for this loan."
                )
            }

        # =================================================
        # 8. Multiple active plans are not permitted
        # =================================================

        if len(active_plans) > 1:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Multiple ACTIVE payment plans were found "
                    f"for customer {customer_id} and loan {loan_id}. "
                    f"Payment processing was escalated for review."
                ),
                status="ESCALATED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "MULTIPLE_ACTIVE_PLANS",
                "customer_id": customer_id,
                "loan_id": loan_id,
                "message": (
                    "Multiple active payment plans were found. "
                    "Human review is required."
                )
            }

        plan = active_plans.iloc[0]

        plan_id = str(
            plan["plan_id"]
        ).strip()

        # =================================================
        # 9. Secondary idempotency check
        # =================================================

        # Keep this check as a defensive safeguard.

        last_payment_id = str(
            plan.get("last_payment_id", "")
        ).strip()

        if last_payment_id == payment_id:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment {payment_id} was already recorded "
                    f"as the last processed payment for "
                    f"payment plan {plan_id}."
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "PAYMENT_ALREADY_PROCESSED",
                "payment_id": payment_id,
                "plan_id": plan_id,
                "customer_id": customer_id,
                "loan_id": loan_id,
                "message": (
                    "This payment has already been processed "
                    "against the payment plan."
                )
            }

        # =================================================
        # 10. Validate payment amount
        # =================================================

        try:

            payment_amount = float(
                payment["amount"]
            )

        except (TypeError, ValueError):

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment {payment_id} contains an invalid "
                    f"payment amount."
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "INVALID_PAYMENT_AMOUNT",
                "payment_id": payment_id,
                "message": "Payment amount is invalid."
            }

        if payment_amount <= 0:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment {payment_id} has a non-positive "
                    f"amount of {payment_amount}."
                ),
                status="BLOCKED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "INVALID_PAYMENT_AMOUNT",
                "payment_id": payment_id,
                "payment_amount": payment_amount,
                "message": (
                    "Payment amount must be greater than zero."
                )
            }

        # =================================================
        # 11. Validate agreed payment amount
        # =================================================

        try:

            agreed_amount = float(
                plan["agreed_amount"]
            )

        except (TypeError, ValueError):

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment plan {plan_id} contains an invalid "
                    f"agreed payment amount."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "INVALID_AGREED_AMOUNT",
                "plan_id": plan_id,
                "message": (
                    "The payment plan agreed amount is invalid."
                )
            }

        if agreed_amount <= 0:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment plan {plan_id} has a non-positive "
                    f"agreed amount of {agreed_amount}."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "INVALID_AGREED_AMOUNT",
                "plan_id": plan_id,
                "agreed_amount": agreed_amount,
                "message": (
                    "The agreed payment amount must be greater than zero."
                )
            }

        # =================================================
        # 12. Identify partial payment
        # =================================================

        is_partial_payment = payment_amount < agreed_amount
        partial_shortfall = round(
            max(agreed_amount - payment_amount, 0),
            2
        )

        # =================================================
        # 13. Validate next payment date
        # =================================================

        next_payment_date = str(
            plan["next_payment_date"]
        ).strip()

        try:

            current_next_payment_date = datetime.strptime(
                next_payment_date,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment plan {plan_id} contains an invalid "
                    f"next payment date: {next_payment_date}."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "INVALID_NEXT_PAYMENT_DATE",
                "plan_id": plan_id,
                "next_payment_date": next_payment_date,
                "message": (
                    "The payment plan next payment date is invalid."
                )
            }

        # =================================================
        # 14. Calculate next payment date
        # =================================================

        frequency = str(
            plan["frequency"]
        ).strip().upper()

        if frequency == "WEEKLY":

            new_next_payment_date = (
                current_next_payment_date
                + timedelta(days=7)
            )

        elif frequency == "BIWEEKLY":

            new_next_payment_date = (
                current_next_payment_date
                + timedelta(days=14)
            )

        elif frequency == "MONTHLY":

            year = current_next_payment_date.year
            month = current_next_payment_date.month

            if month == 12:
                next_year = year + 1
                next_month = 1
            else:
                next_year = year
                next_month = month + 1

            last_day = calendar.monthrange(
                next_year,
                next_month
            )[1]

            new_day = min(
                current_next_payment_date.day,
                last_day
            )

            new_next_payment_date = date(
                next_year,
                next_month,
                new_day
            )

        else:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment plan {plan_id} has unsupported "
                    f"frequency {frequency}."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "UNSUPPORTED_FREQUENCY",
                "plan_id": plan_id,
                "frequency": frequency,
                "message": (
                    "The payment plan frequency is not supported."
                )
            }

        # =================================================
        # 15. Locate payment-plan worksheet row
        # =================================================

        plan_rows = plans_sheet.get_all_values()

        header = plan_rows[0]

        plan_id_column = header.index("plan_id") + 1

        next_payment_date_column = (
            header.index("next_payment_date") + 1
        )

        last_payment_id_column = (
            header.index("last_payment_id") + 1
        )

        target_row = None

        for row_number, row in enumerate(
            plan_rows[1:],
            start=2
        ):

            if len(row) > plan_id_column - 1:

                sheet_plan_id = str(
                    row[plan_id_column - 1]
                ).strip()

                if sheet_plan_id == plan_id:

                    target_row = row_number
                    break

        if target_row is None:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_PLAN_PAYMENT",
                description=(
                    f"Payment plan {plan_id} could not be located "
                    f"in the worksheet for payment update."
                ),
                status="FAILED",
                agent="PAYMENT_PLAN_LIFECYCLE"
            )

            return {
                "success": False,
                "status": "PLAN_ROW_NOT_FOUND",
                "plan_id": plan_id,
                "message": (
                    "Payment plan record could not be located."
                )
            }

        # =================================================
        # 16. Update payment-plan record
        # =================================================

        # Every verified payment is recorded as the latest payment.
        # A partial payment, however, must NOT advance the next
        # scheduled instalment date because the full instalment was
        # not satisfied.

        if not is_partial_payment:

            plans_sheet.update_cell(
                target_row,
                next_payment_date_column,
                new_next_payment_date.isoformat()
            )

        plans_sheet.update_cell(
            target_row,
            last_payment_id_column,
            payment_id
        )

        effective_next_payment_date = (
            current_next_payment_date
            if is_partial_payment
            else new_next_payment_date
        )

        # =================================================
        # 17. Create customer notification
        # =================================================

        notification_result = None

        try:

            customers_sheet = spreadsheet.worksheet("Customers")

            customer_records = (
                customers_sheet.get_all_records()
            )

            customer_match = next(
                (
                    row
                    for row in customer_records
                    if str(
                        row.get("customer_id", "")
                    ).strip() == customer_id
                ),
                None
            )

            if customer_match:

                phone_number = str(
                    customer_match.get(
                        "phone_number",
                        ""
                    )
                ).strip()

                if phone_number:

                    notification_result = create_notification(
                        request_id=f"PAYMENT-{payment_id}",
                        customer_id=customer_id,
                        notification_type="SMS",
                        recipient=phone_number,
                        message=(
                            (
                                f"Your partial payment of "
                                f"{payment_amount:.2f} has been applied "
                                f"to your payment plan. The agreed "
                                f"instalment is {agreed_amount:.2f}; "
                                f"the outstanding instalment shortfall is "
                                f"{partial_shortfall:.2f}. Your next "
                                f"scheduled payment remains due on "
                                f"{effective_next_payment_date.isoformat()}."
                            )
                            if is_partial_payment
                            else (
                                f"Your payment of "
                                f"{payment_amount:.2f} "
                                f"has been successfully applied to "
                                f"your payment plan. Your next "
                                f"scheduled payment is due on "
                                f"{effective_next_payment_date.isoformat()}."
                            )
                        )
                    )

                else:

                    notification_result = {
                        "success": False,
                        "status": "NO_PHONE_NUMBER",
                        "message": (
                            "Payment was successfully processed, "
                            "but no customer phone number was "
                            "available for notification."
                        )
                    }

            else:

                notification_result = {
                    "success": False,
                    "status": "CUSTOMER_NOT_FOUND",
                    "message": (
                        "Payment was successfully processed, "
                        "but the customer record could not be "
                        "located for notification."
                    )
                }

        except Exception as notification_error:

            notification_result = {
                "success": False,
                "status": "NOTIFICATION_CREATION_ERROR",
                "message": str(notification_error)
            }

        # =================================================
        # 18. Audit successful processing
        # =================================================

        log_event(
            customer_id=customer_id,
            event_type=(
                "PARTIAL_PAYMENT_APPLIED"
                if is_partial_payment
                else "PAYMENT_PLAN_PAYMENT"
            ),
            description=(
                (
                    f"Verified partial payment {payment_id} of "
                    f"{payment_amount} was successfully applied "
                    f"against payment plan {plan_id}. The agreed "
                    f"instalment was {agreed_amount}; the outstanding "
                    f"instalment shortfall is {partial_shortfall}. "
                    f"The next payment date was not advanced and "
                    f"remains {current_next_payment_date.isoformat()}."
                )
                if is_partial_payment
                else (
                    f"Verified payment {payment_id} of "
                    f"{payment_amount} was successfully processed "
                    f"against payment plan {plan_id}. "
                    f"Next payment date advanced from "
                    f"{current_next_payment_date.isoformat()} "
                    f"to {new_next_payment_date.isoformat()}."
                )
            ),
            status="SUCCESS",
            agent="PAYMENT_PLAN_LIFECYCLE"
        )

        # =================================================
        # 19. Return successful result
        # =================================================

        return {
            "success": True,
            "status": (
                "PAYMENT_PARTIALLY_APPLIED"
                if is_partial_payment
                else "PAYMENT_PROCESSED"
            ),
            "payment_id": payment_id,
            "plan_id": plan_id,
            "customer_id": customer_id,
            "loan_id": loan_id,
            "payment_amount": payment_amount,
            "agreed_amount": agreed_amount,
            "is_partial_payment": is_partial_payment,
            "instalment_shortfall": (
                partial_shortfall if is_partial_payment else 0.0
            ),
            "previous_next_payment_date": (
                current_next_payment_date.isoformat()
            ),
            "new_next_payment_date": (
                effective_next_payment_date.isoformat()
            ),
            "schedule_advanced": not is_partial_payment,
            "notification_created": (
                notification_result.get("success", False)
                if isinstance(notification_result, dict)
                else False
            ),
            "notification_status": (
                notification_result.get("status")
                if isinstance(notification_result, dict)
                else "NOTIFICATION_NOT_ATTEMPTED"
            ),
            "message": (
                (
                    "Partial payment was successfully applied. "
                    "The payment does not satisfy the full instalment, "
                    "the shortfall remains outstanding, and the "
                    "payment-plan schedule was not advanced."
                )
                if is_partial_payment
                else (
                    "Payment was successfully processed and "
                    "the payment-plan schedule was advanced."
                )
            )
        }

    except Exception as error:

        log_event(
            customer_id=customer_id or "UNKNOWN",
            event_type="PAYMENT_PLAN_PAYMENT",
            description=(
                f"System error occurred while processing "
                f"payment {payment_id}: {str(error)}"
            ),
            status="FAILED",
            agent="PAYMENT_PLAN_LIFECYCLE"
        )

        return {
            "success": False,
            "status": "PAYMENT_PLAN_PAYMENT_ERROR",
            "payment_id": payment_id,
            "customer_id": customer_id,
            "loan_id": loan_id,
            "message": str(error)
        }
