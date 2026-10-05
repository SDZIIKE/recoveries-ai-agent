
import pandas as pd

from database.google_sheets import open_database
from audit.logger import log_event


# ============================================================
# INTERNAL KYC VERIFICATION
# ============================================================

def verify_customer(customer_id, national_id, date_of_birth):
    """
    Verify customer identity using the internal customer ID,
    national ID and date of birth.

    This function is retained for internal/backend workflows.

    Every KYC attempt is recorded in the Audit Logs.
    """

    customer_id = str(customer_id).strip()

    try:
        spreadsheet = open_database()
        worksheet = spreadsheet.worksheet("Customers")
        records = worksheet.get_all_records()
        customers = pd.DataFrame(records)

        if customers.empty:
            log_event(
                customer_id=customer_id,
                event_type="KYC_VERIFICATION",
                description=(
                    "KYC verification failed because no customer "
                    "records were found."
                ),
                status="FAILED",
                agent="KYC_TOOL"
            )

            return {
                "verified": False,
                "status": "KYC_FAILED",
                "reason": "No customer records were found."
            }

        customer = customers[
            customers["customer_id"].astype(str).str.strip()
            == customer_id
        ]

        if customer.empty:
            log_event(
                customer_id=customer_id,
                event_type="KYC_VERIFICATION",
                description=(
                    "KYC verification failed because the customer "
                    "ID was not found."
                ),
                status="BLOCKED",
                agent="KYC_TOOL"
            )

            return {
                "verified": False,
                "status": "KYC_FAILED",
                "reason": "Customer ID not found."
            }

        customer = customer.iloc[0]

        national_id_match = (
            str(customer["national_id"]).strip()
            == str(national_id).strip()
        )

        dob_match = (
            str(customer["date_of_birth"]).strip()
            == str(date_of_birth).strip()
        )

        if national_id_match and dob_match:

            log_event(
                customer_id=customer_id,
                event_type="KYC_VERIFICATION",
                description="Customer successfully passed KYC verification.",
                status="SUCCESS",
                agent="KYC_TOOL"
            )

            return {
                "verified": True,
                "status": "KYC_VERIFIED",
                "customer_id": customer_id,
                "full_name": str(customer["full_name"])
            }

        log_event(
            customer_id=customer_id,
            event_type="KYC_VERIFICATION",
            description=(
                "KYC verification failed because supplied "
                "identification details did not match customer records."
            ),
            status="BLOCKED",
            agent="KYC_TOOL"
        )

        return {
            "verified": False,
            "status": "KYC_FAILED",
            "reason": (
                "Provided identification details do not match "
                "our records."
            )
        }

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="KYC_VERIFICATION",
            description=(
                f"KYC verification encountered a system error: "
                f"{str(error)}"
            ),
            status="FAILED",
            agent="KYC_TOOL"
        )

        return {
            "verified": False,
            "status": "KYC_ERROR",
            "reason": str(error)
        }


# ============================================================
# CUSTOMER-FACING KYC VERIFICATION
# ============================================================

def verify_customer_by_identity(national_id, date_of_birth):
    """
    Customer-facing KYC verification.

    The customer provides only:
        - National ID
        - Date of Birth

    The internal customer ID is retrieved from the Customers
    database after the identity details successfully match.

    The internal customer ID is never required from the customer.
    """

    national_id = str(national_id).strip()
    date_of_birth = str(date_of_birth).strip()

    # Do not know the internal customer ID yet.
    # Use a neutral audit identifier until the customer is found.
    audit_customer_id = "UNKNOWN"

    try:
        spreadsheet = open_database()
        worksheet = spreadsheet.worksheet("Customers")
        records = worksheet.get_all_records()
        customers = pd.DataFrame(records)

        if customers.empty:

            log_event(
                customer_id=audit_customer_id,
                event_type="KYC_IDENTITY_VERIFICATION",
                description=(
                    "Customer-facing KYC verification failed because "
                    "no customer records were found."
                ),
                status="FAILED",
                agent="KYC_TOOL"
            )

            return {
                "verified": False,
                "status": "KYC_FAILED",
                "reason": "Unable to verify identity."
            }

        # ----------------------------------------------------
        # Match National ID and Date of Birth
        # ----------------------------------------------------

        matching_customers = customers[
            (
                customers["national_id"]
                .astype(str)
                .str.strip()
                == national_id
            )
            &
            (
                customers["date_of_birth"]
                .astype(str)
                .str.strip()
                == date_of_birth
            )
        ]

        # ----------------------------------------------------
        # No Match
        # ----------------------------------------------------

        if matching_customers.empty:

            log_event(
                customer_id=audit_customer_id,
                event_type="KYC_IDENTITY_VERIFICATION",
                description=(
                    "Customer-facing KYC verification failed because "
                    "the supplied National ID and Date of Birth did "
                    "not match customer records."
                ),
                status="BLOCKED",
                agent="KYC_TOOL"
            )

            return {
                "verified": False,
                "status": "KYC_FAILED",
                "reason": (
                    "Provided identification details do not match "
                    "our records."
                )
            }

        # ----------------------------------------------------
        # Multiple Matches
        # ----------------------------------------------------

        if len(matching_customers) > 1:

            log_event(
                customer_id=audit_customer_id,
                event_type="KYC_IDENTITY_VERIFICATION",
                description=(
                    "KYC verification was blocked because multiple "
                    "customer records matched the supplied identity details."
                ),
                status="BLOCKED",
                agent="KYC_TOOL"
            )

            return {
                "verified": False,
                "status": "KYC_ESCALATION_REQUIRED",
                "reason": (
                    "Multiple customer records matched the "
                    "provided identification details."
                )
            }

        # ----------------------------------------------------
        # Successful Match
        # ----------------------------------------------------

        customer = matching_customers.iloc[0]

        internal_customer_id = (
            str(customer["customer_id"]).strip()
        )

        full_name = str(customer["full_name"]).strip()

        log_event(
            customer_id=internal_customer_id,
            event_type="KYC_IDENTITY_VERIFICATION",
            description=(
                "Customer successfully passed customer-facing "
                "KYC verification using National ID and Date of Birth."
            ),
            status="SUCCESS",
            agent="KYC_TOOL"
        )

        return {
            "verified": True,
            "status": "KYC_VERIFIED",

            # Internal field.
            # This is used by downstream tools and should not
            # be displayed directly to the customer.
            "customer_id": internal_customer_id,

            "full_name": full_name
        }

    except Exception as error:

        log_event(
            customer_id=audit_customer_id,
            event_type="KYC_IDENTITY_VERIFICATION",
            description=(
                f"Customer-facing KYC verification encountered "
                f"a system error: {str(error)}"
            ),
            status="FAILED",
            agent="KYC_TOOL"
        )

        return {
            "verified": False,
            "status": "KYC_ERROR",
            "reason": "Unable to complete identity verification."
        }


# ============================================================
# DIRECT KYC TESTS
# ============================================================

if __name__ == "__main__":

    print("==========================================")
    print("KYC + AUDIT LOGGING TEST")
    print("==========================================")

    print("\nTEST 1: Internal Successful KYC")
    print("------------------------------------------")

    result = verify_customer(
        customer_id="CUST001",
        national_id="00-000001A00",
        date_of_birth="1990-01-15"
    )

    print(result)

    print("\nTEST 2: Wrong National ID")
    print("------------------------------------------")

    result = verify_customer(
        customer_id="CUST001",
        national_id="WRONG-ID",
        date_of_birth="1990-01-15"
    )

    print(result)

    print("\nTEST 3: Wrong Date of Birth")
    print("------------------------------------------")

    result = verify_customer(
        customer_id="CUST001",
        national_id="00-000001A00",
        date_of_birth="2000-01-01"
    )

    print(result)

    print("\nTEST 4: Unknown Customer")
    print("------------------------------------------")

    result = verify_customer(
        customer_id="CUST999",
        national_id="00-000999A00",
        date_of_birth="1990-01-15"
    )

    print(result)

    # ========================================================
    # CUSTOMER-FACING KYC TESTS
    # ========================================================

    print("\n==========================================")
    print("CUSTOMER-FACING KYC TESTS")
    print("==========================================")

    print("\nTEST 5: National ID + DOB Successful KYC")
    print("------------------------------------------")

    result = verify_customer_by_identity(
        national_id="00-000001A00",
        date_of_birth="1990-01-15"
    )

    print(result)

    print("\nTEST 6: National ID + DOB Wrong National ID")
    print("------------------------------------------")

    result = verify_customer_by_identity(
        national_id="WRONG-ID",
        date_of_birth="1990-01-15"
    )

    print(result)

    print("\nTEST 7: National ID + DOB Wrong Date of Birth")
    print("------------------------------------------")

    result = verify_customer_by_identity(
        national_id="00-000001A00",
        date_of_birth="2000-01-01"
    )

    print(result)

    print("\n==========================================")
    print("ALL KYC TESTS COMPLETE")
    print("==========================================")
