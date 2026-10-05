from datetime import datetime

from database.google_sheets import open_database
from audit.logger import log_event


def deliver_notification(notification_id):
    """
    Simulate delivery of a pending notification.

    In the production version, this function would call
    an SMS, email, or WhatsApp provider.

    For now, it updates the notification status to SENT.
    """

    notification_id = str(notification_id).strip()

    if not notification_id:
        return {
            "success": False,
            "status": "NOTIFICATION_ID_REQUIRED",
            "message": "Notification ID is required."
        }

    try:

        spreadsheet = open_database()

        worksheet = spreadsheet.worksheet("Notifications")

        records = worksheet.get_all_records()

        if not records:
            return {
                "success": False,
                "status": "NO_NOTIFICATIONS_FOUND",
                "message": "No notification records were found."
            }

        notification = None
        target_row = None

        # ---------------------------------------------
        # Locate notification
        # ---------------------------------------------

        for index, record in enumerate(records, start=2):

            current_id = str(
                record.get("notification_id", "")
            ).strip()

            if current_id == notification_id:

                notification = record
                target_row = index
                break

        if notification is None:

            return {
                "success": False,
                "status": "NOTIFICATION_NOT_FOUND",
                "notification_id": notification_id,
                "message": "Notification was not found."
            }

        customer_id = str(
            notification.get("customer_id", "")
        ).strip()

        current_status = str(
            notification.get("status", "")
        ).strip().upper()

        notification_type = str(
            notification.get("notification_type", "")
        ).strip().upper()

        # ---------------------------------------------
        # Only PENDING notifications can be delivered
        # ---------------------------------------------

        if current_status != "PENDING":

            log_event(
                customer_id=customer_id,
                event_type="NOTIFICATION_DELIVERY",
                description=(
                    f"Notification {notification_id} "
                    f"could not be delivered because its "
                    f"current status is {current_status}."
                ),
                status="BLOCKED",
                agent="NOTIFICATION_DELIVERY"
            )

            return {
                "success": False,
                "status": "NOTIFICATION_NOT_PENDING",
                "notification_id": notification_id,
                "current_status": current_status,
                "message": (
                    "Only PENDING notifications can be delivered."
                )
            }

        # ---------------------------------------------
        # Locate status and sent_at columns
        # ---------------------------------------------

        headers = worksheet.row_values(1)

        status_column = headers.index("status") + 1
        sent_at_column = headers.index("sent_at") + 1

        sent_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # ---------------------------------------------
        # Simulated delivery
        # ---------------------------------------------

        worksheet.update_cell(
            target_row,
            status_column,
            "SENT"
        )

        worksheet.update_cell(
            target_row,
            sent_at_column,
            sent_at
        )

        # ---------------------------------------------
        # Audit successful delivery
        # ---------------------------------------------

        log_event(
            customer_id=customer_id,
            event_type="NOTIFICATION_DELIVERY",
            description=(
                f"{notification_type} notification "
                f"{notification_id} was successfully delivered."
            ),
            status="SUCCESS",
            agent="NOTIFICATION_DELIVERY"
        )

        return {
            "success": True,
            "status": "NOTIFICATION_SENT",
            "notification_id": notification_id,
            "customer_id": customer_id,
            "notification_type": notification_type,
            "sent_at": sent_at,
            "message": (
                "Notification was successfully delivered."
            )
        }

    except Exception as error:

        log_event(
            customer_id="UNKNOWN",
            event_type="NOTIFICATION_DELIVERY",
            description=(
                f"Notification delivery failed for "
                f"{notification_id}: {str(error)}"
            ),
            status="FAILED",
            agent="NOTIFICATION_DELIVERY"
        )

        return {
            "success": False,
            "status": "NOTIFICATION_DELIVERY_ERROR",
            "notification_id": notification_id,
            "message": str(error)
        }


if __name__ == "__main__":

    print("==========================================")
    print("NOTIFICATION DELIVERY TEST")
    print("==========================================")

    print("\nTEST 1: Deliver Pending Notification")
    print("------------------------------------------")

    result = deliver_notification(
        "NOT-DF20B0E3"
    )

    print(result)

    print("\nTEST 2: Deliver Already Sent Notification")
    print("------------------------------------------")

    result = deliver_notification(
        "NOT-DF20B0E3"
    )

    print(result)

    print("\nTEST 3: Unknown Notification")
    print("------------------------------------------")

    result = deliver_notification(
        "NOT-UNKNOWN"
    )

    print(result)

    print("\n==========================================")
    print("NOTIFICATION DELIVERY TEST COMPLETE")
    print("==========================================")