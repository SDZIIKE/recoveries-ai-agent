import uuid
from datetime import datetime

from database.google_sheets import open_database
from audit.logger import log_event


def generate_notification_id():
    """
    Generate a unique notification ID.
    """
    return f"NOT-{uuid.uuid4().hex[:8].upper()}"


def create_notification(
    request_id,
    customer_id,
    notification_type,
    recipient,
    message
):
    """
    Create a notification record.

    This function records the notification that needs to be sent.
    It does not yet connect to SMS, WhatsApp, or email providers.
    """

    request_id = str(request_id).strip()
    customer_id = str(customer_id).strip()
    notification_type = str(notification_type).strip().upper()
    recipient = str(recipient).strip()
    message = str(message).strip()

    # ---------------------------------------------
    # 1. Validate required fields
    # ---------------------------------------------

    if not request_id:
        return {
            "success": False,
            "status": "REQUEST_ID_REQUIRED",
            "message": "Request ID is required."
        }

    if not customer_id:
        return {
            "success": False,
            "status": "CUSTOMER_ID_REQUIRED",
            "message": "Customer ID is required."
        }

    if not notification_type:
        return {
            "success": False,
            "status": "NOTIFICATION_TYPE_REQUIRED",
            "message": "Notification type is required."
        }

    if not recipient:
        return {
            "success": False,
            "status": "RECIPIENT_REQUIRED",
            "message": "Notification recipient is required."
        }

    if not message:
        return {
            "success": False,
            "status": "MESSAGE_REQUIRED",
            "message": "Notification message is required."
        }

    # ---------------------------------------------
    # 2. Validate notification type
    # ---------------------------------------------

    allowed_types = {
        "EMAIL",
        "SMS",
        "WHATSAPP"
    }

    if notification_type not in allowed_types:

        return {
            "success": False,
            "status": "INVALID_NOTIFICATION_TYPE",
            "notification_type": notification_type,
            "message": (
                "Notification type must be EMAIL, SMS, or WHATSAPP."
            )
        }

    # ---------------------------------------------
    # 3. Open database
    # ---------------------------------------------

    try:

        spreadsheet = open_database()

        worksheet = spreadsheet.worksheet("Notifications")

        # -----------------------------------------
        # 4. Generate notification ID
        # -----------------------------------------

        notification_id = generate_notification_id()

        created_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # -----------------------------------------
        # 5. Initial notification status
        # -----------------------------------------

        status = "PENDING"

        # -----------------------------------------
        # 6. Create notification record
        # -----------------------------------------

        notification_record = [
            notification_id,
            request_id,
            customer_id,
            notification_type,
            recipient,
            message,
            status,
            created_at,
            ""
        ]

        worksheet.append_row(
            notification_record,
            value_input_option="USER_ENTERED"
        )

        # -----------------------------------------
        # 7. Audit event
        # -----------------------------------------

        log_event(
            customer_id=customer_id,
            event_type="NOTIFICATION_CREATED",
            description=(
                f"{notification_type} notification "
                f"{notification_id} was created for request "
                f"{request_id}."
            ),
            status="SUCCESS",
            agent="NOTIFICATION_TOOL"
        )

        return {
            "success": True,
            "status": "NOTIFICATION_CREATED",
            "notification_id": notification_id,
            "request_id": request_id,
            "customer_id": customer_id,
            "notification_type": notification_type,
            "recipient": recipient,
            "notification_status": status,
            "created_at": created_at,
            "message": (
                "Notification was created successfully "
                "and is pending delivery."
            )
        }

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="NOTIFICATION_CREATED",
            description=(
                f"Notification creation failed: {str(error)}"
            ),
            status="FAILED",
            agent="NOTIFICATION_TOOL"
        )

        return {
            "success": False,
            "status": "NOTIFICATION_CREATION_ERROR",
            "message": str(error)
        }


if __name__ == "__main__":

    print("==========================================")
    print("NOTIFICATION TOOL TEST")
    print("==========================================")

    print("\nTEST 1: Create SMS Notification")
    print("------------------------------------------")

    result = create_notification(
        request_id="REQ005",
        customer_id="CUST001",
        notification_type="SMS",
        recipient="0770000000",
        message=(
            "Your payment plan request REQ005 "
            "has been approved. Your new payment "
            "plan reference is PLAN003."
        )
    )

    print(result)

    print("\nTEST 2: Invalid Notification Type")
    print("------------------------------------------")

    result = create_notification(
        request_id="REQ005",
        customer_id="CUST001",
        notification_type="TELEGRAM",
        recipient="0770000000",
        message="Test notification"
    )

    print(result)

    print("\nTEST 3: Missing Recipient")
    print("------------------------------------------")

    result = create_notification(
        request_id="REQ005",
        customer_id="CUST001",
        notification_type="SMS",
        recipient="",
        message="Test notification"
    )

    print(result)

    print("\n==========================================")
    print("NOTIFICATION TEST COMPLETE")
    print("==========================================")