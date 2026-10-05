
import uuid
from datetime import datetime

from database.google_sheets import open_database


def generate_event_id():
    """
    Generate a unique audit event ID.
    """
    return f"EVT-{uuid.uuid4().hex[:8].upper()}"


def log_event(
    customer_id,
    event_type,
    description,
    status,
    agent="SYSTEM"
):
    """
    Record a system event in the Audit Logs worksheet.

    Parameters:
        customer_id: Customer associated with the event.
        event_type: Type of event being recorded.
        description: Human-readable description.
        status: SUCCESS, FAILED, BLOCKED, etc.
        agent: Component or actor responsible for the event.
    """

    try:
        spreadsheet = open_database()

        audit_sheet = spreadsheet.worksheet("Audit Logs")

        event_id = generate_event_id()

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        audit_record = [
            event_id,
            timestamp,
            str(customer_id),
            str(event_type),
            str(description),
            str(status),
            str(agent)
        ]

        audit_sheet.append_row(
            audit_record,
            value_input_option="USER_ENTERED"
        )

        return {
            "success": True,
            "status": "AUDIT_LOGGED",
            "event_id": event_id,
            "timestamp": timestamp,
            "message": "Audit event recorded successfully."
        }

    except Exception as error:

        return {
            "success": False,
            "status": "AUDIT_LOGGING_ERROR",
            "message": str(error)
        }


if __name__ == "__main__":

    print("==========================================")
    print("AUDIT LOGGER TEST")
    print("==========================================")

    # -----------------------------------------------------
    # TEST 1: Successful event
    # -----------------------------------------------------

    print("\nTEST 1: Successful Event")
    print("------------------------------------------")

    result = log_event(
        customer_id="CUST001",
        event_type="KYC_VERIFICATION",
        description="Customer successfully verified.",
        status="SUCCESS",
        agent="KYC_AGENT"
    )

    print(result)

    # -----------------------------------------------------
    # TEST 2: Blocked event
    # -----------------------------------------------------

    print("\nTEST 2: Blocked Event")
    print("------------------------------------------")

    result = log_event(
        customer_id="CUST001",
        event_type="OFFICER_AUTHORIZATION",
        description="Inactive officer attempted payment plan approval.",
        status="BLOCKED",
        agent="OFFICER_AUTHORIZATION"
    )

    print(result)

    # -----------------------------------------------------
    # TEST 3: Payment plan approval event
    # -----------------------------------------------------

    print("\nTEST 3: Payment Plan Approval")
    print("------------------------------------------")

    result = log_event(
        customer_id="CUST001",
        event_type="PAYMENT_PLAN_APPROVAL",
        description="Payment plan request approved by authorized Recoveries Officer.",
        status="SUCCESS",
        agent="OFF001"
    )

    print(result)

