
import pandas as pd
from datetime import datetime

from database.google_sheets import open_database
from tools.notification_tools import create_notification
from audit.logger import log_event


def send_due_payment_plan_reminders():
    """
    Identify active payment plans that are due for payment
    and create customer reminder notifications.

    Important:
    - This function creates notifications only.
    - It does not directly deliver SMS/WhatsApp/email.
    - Actual delivery is handled by the notification delivery layer.
    - Duplicate reminders for the same plan and payment date
      are prevented.
    """

    today = datetime.now().date()

    try:
        spreadsheet = open_database()

        # --------------------------------------------------
        # 1. LOAD PAYMENT PLANS
        # --------------------------------------------------
        plans_sheet = spreadsheet.worksheet("Payment Plans")
        plans = plans_sheet.get_all_records()
        plans_df = pd.DataFrame(plans)

        if plans_df.empty:
            return {
                "success": True,
                "status": "NO_PAYMENT_PLANS",
                "reminders_created": 0,
                "message": "No payment plans were found."
            }

        # --------------------------------------------------
        # 2. LOAD CUSTOMERS
        # --------------------------------------------------
        customers_sheet = spreadsheet.worksheet("Customers")
        customers = customers_sheet.get_all_records()

        if not customers:
            return {
                "success": False,
                "status": "NO_CUSTOMERS_FOUND",
                "reminders_created": 0,
                "message": "No customer records were found."
            }

        # --------------------------------------------------
        # 3. LOAD EXISTING NOTIFICATIONS
        # --------------------------------------------------
        notifications_sheet = spreadsheet.worksheet("Notifications")
        notifications = notifications_sheet.get_all_records()

        # --------------------------------------------------
        # 4. FIND DUE ACTIVE PLANS
        # --------------------------------------------------
        due_plans = []

        for _, plan in plans_df.iterrows():

            status = str(plan["status"]).strip().upper()

            if status != "ACTIVE":
                continue

            next_payment_date_raw = str(
                plan["next_payment_date"]
            ).strip()

            try:
                next_payment_date = datetime.strptime(
                    next_payment_date_raw,
                    "%Y-%m-%d"
                ).date()
            except ValueError:

                log_event(
                    customer_id=str(plan["customer_id"]).strip(),
                    event_type="PAYMENT_PLAN_REMINDER",
                    description=(
                        f"Payment plan {plan['plan_id']} has "
                        f"an invalid next payment date: "
                        f"{next_payment_date_raw}."
                    ),
                    status="FAILED",
                    agent="REMINDER_SCHEDULER"
                )

                continue

            # Only process plans that are due today or overdue.
            if next_payment_date <= today:
                due_plans.append(
                    {
                        "plan_id": str(
                            plan["plan_id"]
                        ).strip(),
                        "customer_id": str(
                            plan["customer_id"]
                        ).strip(),
                        "loan_id": str(
                            plan["loan_id"]
                        ).strip(),
                        "next_payment_date": (
                            next_payment_date_raw
                        ),
                        "frequency": str(
                            plan["frequency"]
                        ).strip(),
                        "agreed_amount": str(
                            plan["agreed_amount"]
                        ).strip()
                    }
                )

        if not due_plans:
            return {
                "success": True,
                "status": "NO_DUE_PAYMENT_PLANS",
                "reminders_created": 0,
                "message": (
                    "No active payment plans are currently "
                    "due for payment."
                )
            }

        # --------------------------------------------------
        # 5. PROCESS DUE PLANS
        # --------------------------------------------------
        reminders_created = []
        reminders_skipped = []

        for plan in due_plans:

            plan_id = plan["plan_id"]
            customer_id = plan["customer_id"]
            payment_date = plan["next_payment_date"]

            # --------------------------------------------------
            # 6. FIND CUSTOMER
            # --------------------------------------------------
            customer = None

            for customer_record in customers:

                current_customer_id = str(
                    customer_record.get(
                        "customer_id",
                        ""
                    )
                ).strip()

                if current_customer_id == customer_id:
                    customer = customer_record
                    break

            if customer is None:

                log_event(
                    customer_id=customer_id,
                    event_type="PAYMENT_PLAN_REMINDER",
                    description=(
                        f"Customer {customer_id} could not be "
                        f"found for payment plan {plan_id}."
                    ),
                    status="FAILED",
                    agent="REMINDER_SCHEDULER"
                )

                reminders_skipped.append(
                    {
                        "plan_id": plan_id,
                        "reason": "CUSTOMER_NOT_FOUND"
                    }
                )

                continue

            # --------------------------------------------------
            # 7. GET CUSTOMER PHONE NUMBER
            # --------------------------------------------------
            phone_number = str(
                customer.get(
                    "phone_number",
                    ""
                )
            ).strip()

            if not phone_number:

                log_event(
                    customer_id=customer_id,
                    event_type="PAYMENT_PLAN_REMINDER",
                    description=(
                        f"No phone number was available for "
                        f"customer {customer_id}. Reminder "
                        f"for payment plan {plan_id} was "
                        f"not created."
                    ),
                    status="FAILED",
                    agent="REMINDER_SCHEDULER"
                )

                reminders_skipped.append(
                    {
                        "plan_id": plan_id,
                        "reason": "NO_PHONE_NUMBER"
                    }
                )

                continue

            # --------------------------------------------------
            # 8. DUPLICATE REMINDER GUARDRAIL
            # --------------------------------------------------
            duplicate_found = False

            for notification in notifications:

                notification_type = str(
                    notification.get(
                        "notification_type",
                        ""
                    )
                ).strip().upper()

                notification_customer = str(
                    notification.get(
                        "customer_id",
                        ""
                    )
                ).strip()

                notification_message = str(
                    notification.get(
                        "message",
                        ""
                    )
                ).strip()

                notification_status = str(
                    notification.get(
                        "status",
                        ""
                    )
                ).strip().upper()

                if (
                    notification_type == "SMS"
                    and notification_customer == customer_id
                    and plan_id in notification_message
                    and payment_date in notification_message
                    and notification_status in {
                        "PENDING",
                        "SENT"
                    }
                ):
                    duplicate_found = True
                    break

            if duplicate_found:

                reminders_skipped.append(
                    {
                        "plan_id": plan_id,
                        "reason": "REMINDER_ALREADY_EXISTS"
                    }
                )

                continue

            # --------------------------------------------------
            # 9. CREATE REMINDER MESSAGE
            # --------------------------------------------------
            message = (
                f"Reminder: Your payment of "
                f"{plan['agreed_amount']} for payment plan "
                f"{plan_id} is due on {payment_date}. "
                f"Please make your payment according to "
                f"your agreed repayment arrangement."
            )

            # --------------------------------------------------
            # 10. CREATE NOTIFICATION
            # --------------------------------------------------
            notification_result = create_notification(
                request_id=plan_id,
                customer_id=customer_id,
                notification_type="SMS",
                recipient=phone_number,
                message=message
            )

            if notification_result.get("success"):

                reminders_created.append(
                    {
                        "plan_id": plan_id,
                        "customer_id": customer_id,
                        "notification_id": (
                            notification_result[
                                "notification_id"
                            ]
                        ),
                        "status": "PENDING"
                    }
                )

                # Add to local notification list so that
                # duplicate protection also works within
                # the same scheduler execution.
                notifications.append(
                    {
                        "notification_type": "SMS",
                        "customer_id": customer_id,
                        "message": message,
                        "status": "PENDING"
                    }
                )

                log_event(
                    customer_id=customer_id,
                    event_type="PAYMENT_PLAN_REMINDER",
                    description=(
                        f"Payment reminder created for "
                        f"payment plan {plan_id}. "
                        f"Payment date: {payment_date}."
                    ),
                    status="SUCCESS",
                    agent="REMINDER_SCHEDULER"
                )

            else:

                reminders_skipped.append(
                    {
                        "plan_id": plan_id,
                        "reason": (
                            notification_result.get(
                                "status",
                                "NOTIFICATION_CREATION_FAILED"
                            )
                        )
                    }
                )

        # --------------------------------------------------
        # 11. RETURN SUMMARY
        # --------------------------------------------------
        return {
            "success": True,
            "status": "REMINDER_PROCESSING_COMPLETED",
            "reminders_created": len(
                reminders_created
            ),
            "reminders_skipped": len(
                reminders_skipped
            ),
            "created": reminders_created,
            "skipped": reminders_skipped,
            "processed_date": str(today),
            "message": (
                "Payment plan reminder processing "
                "completed successfully."
            )
        }

    except Exception as error:

        try:
            log_event(
                customer_id="SYSTEM",
                event_type="PAYMENT_PLAN_REMINDER",
                description=(
                    f"Reminder scheduler encountered "
                    f"a system error: {str(error)}"
                ),
                status="FAILED",
                agent="REMINDER_SCHEDULER"
            )
        except Exception:
            pass

        return {
            "success": False,
            "status": "REMINDER_PROCESSING_ERROR",
            "reminders_created": 0,
            "message": str(error)
        }


if __name__ == "__main__":

    print("==========================================")
    print("PAYMENT PLAN REMINDER SCHEDULER TEST")
    print("==========================================")

    result = send_due_payment_plan_reminders()

    print("\nRESULT")
    print("------------------------------------------")
    print(result)

    print("\n==========================================")
    print("REMINDER SCHEDULER TEST COMPLETE")
    print("==========================================")
