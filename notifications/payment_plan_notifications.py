
from tools.notification_tools import create_notification


def notify_payment_plan_approved(
    request_id,
    customer_id,
    plan_id,
    recipient
):
    """
    Create a notification for an approved payment plan.
    """

    message = (
        f"Your payment plan request {request_id} has been "
        f"approved. Your new payment plan reference is "
        f"{plan_id}. Please ensure payments are made according "
        f"to the agreed repayment schedule."
    )

    return create_notification(
        request_id=request_id,
        customer_id=customer_id,
        notification_type="SMS",
        recipient=recipient,
        message=message
    )


def notify_payment_plan_rejected(
    request_id,
    customer_id,
    rejection_reason,
    recipient
):
    """
    Create a notification for a rejected payment plan.
    """

    message = (
        f"Your payment plan request {request_id} could not "
        f"be approved. Reason: {rejection_reason}. "
        f"Please contact the Recoveries team for assistance."
    )

    return create_notification(
        request_id=request_id,
        customer_id=customer_id,
        notification_type="SMS",
        recipient=recipient,
        message=message
    )

