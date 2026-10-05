
import pandas as pd

from database.google_sheets import open_database
from audit.logger import log_event


# ============================================================
# GET CUSTOMER LOANS
# ============================================================

def get_customer_loans(customer_id, kyc_verified=False):
    """
    Retrieve all loans belonging to a verified customer.

    This function is intended for internal agent/tool use after
    successful KYC verification.

    Security rules:
    - KYC is mandatory.
    - Customer ID is an internal identifier.
    - Customer-facing workflows should never ask the customer
      to provide Customer ID or Loan ID.
    - The internal loan_id may be used by downstream tools.
    """

    customer_id = str(customer_id).strip()

    # --------------------------------------------------------
    # SECURITY CHECK
    # --------------------------------------------------------

    if not kyc_verified:

        log_event(
            customer_id=customer_id,
            event_type="CUSTOMER_LOANS_ACCESS",
            description=(
                "Customer loan lookup was blocked because "
                "KYC verification had not been completed."
            ),
            status="BLOCKED",
            agent="LOAN_TOOL"
        )

        return {
            "success": False,
            "status": "KYC_REQUIRED",
            "message": (
                "KYC verification is required before "
                "loan information can be accessed."
            )
        }

    # --------------------------------------------------------
    # DATABASE LOOKUP
    # --------------------------------------------------------

    try:

        spreadsheet = open_database()

        worksheet = spreadsheet.worksheet("Loans")

        records = worksheet.get_all_records()

        loans = pd.DataFrame(records)

        if loans.empty:

            log_event(
                customer_id=customer_id,
                event_type="CUSTOMER_LOANS_ACCESS",
                description=(
                    "Customer loan lookup failed because "
                    "no loan records were found."
                ),
                status="FAILED",
                agent="LOAN_TOOL"
            )

            return {
                "success": False,
                "status": "NO_LOANS_FOUND",
                "message": "No loan records were found."
            }

        # ----------------------------------------------------
        # FILTER CUSTOMER LOANS
        # ----------------------------------------------------

        customer_loans = loans[
            loans["customer_id"].astype(str).str.strip()
            == customer_id
        ]

        if customer_loans.empty:

            log_event(
                customer_id=customer_id,
                event_type="CUSTOMER_LOANS_ACCESS",
                description=(
                    "No loan records were found for the "
                    "verified customer."
                ),
                status="FAILED",
                agent="LOAN_TOOL"
            )

            return {
                "success": False,
                "status": "NO_LOANS_FOUND",
                "message": (
                    "No loan records were found for this customer."
                )
            }

        # ----------------------------------------------------
        # RETURN LOAN RECORDS
        # ----------------------------------------------------

        loan_list = customer_loans.to_dict(
            orient="records"
        )

        log_event(
            customer_id=customer_id,
            event_type="CUSTOMER_LOANS_ACCESS",
            description=(
                "Customer loan records were successfully "
                "retrieved following successful KYC verification."
            ),
            status="SUCCESS",
            agent="LOAN_TOOL"
        )

        return {
            "success": True,
            "status": "LOANS_FOUND",
            "customer_id": customer_id,
            "loan_count": len(loan_list),
            "loans": loan_list
        }

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="CUSTOMER_LOANS_ACCESS",
            description=(
                f"Customer loan lookup encountered a "
                f"system error: {str(error)}"
            ),
            status="FAILED",
            agent="LOAN_TOOL"
        )

        return {
            "success": False,
            "status": "LOAN_LOOKUP_ERROR",
            "message": (
                "Unable to retrieve loan information at this time."
            )
        }


# ============================================================
# GET LOAN BALANCE
# ============================================================

def get_loan_balance(customer_id, kyc_verified=False):
    """
    Retrieve loan balances only after successful KYC verification.

    Security rule:

    Financial information must not be disclosed unless KYC
    has been successfully completed.
    """

    customer_id = str(customer_id).strip()

    # --------------------------------------------------
    # SECURITY CHECK
    # --------------------------------------------------

    if not kyc_verified:

        log_event(
            customer_id=customer_id,
            event_type="LOAN_BALANCE_ACCESS",
            description=(
                "Loan balance access was blocked because "
                "KYC verification had not been completed."
            ),
            status="BLOCKED",
            agent="LOAN_TOOL"
        )

        return {
            "success": False,
            "status": "KYC_REQUIRED",
            "customer_id": customer_id,
            "message": (
                "KYC verification is required before "
                "loan balance information can be disclosed."
            )
        }

    # --------------------------------------------------
    # DATABASE LOOKUP
    # --------------------------------------------------

    try:

        spreadsheet = open_database()

        worksheet = spreadsheet.worksheet("Loans")

        records = worksheet.get_all_records()

        loans = pd.DataFrame(records)

        if loans.empty:

            log_event(
                customer_id=customer_id,
                event_type="LOAN_BALANCE_ACCESS",
                description=(
                    "Loan balance lookup failed because "
                    "no loan records were found."
                ),
                status="FAILED",
                agent="LOAN_TOOL"
            )

            return {
                "success": False,
                "status": "NO_LOANS_FOUND",
                "customer_id": customer_id,
                "message": "No loan records were found."
            }

        customer_loans = loans[
            loans["customer_id"].astype(str).str.strip()
            == customer_id
        ]

        if customer_loans.empty:

            log_event(
                customer_id=customer_id,
                event_type="LOAN_BALANCE_ACCESS",
                description=(
                    "No loan records were found for the "
                    "verified customer."
                ),
                status="FAILED",
                agent="LOAN_TOOL"
            )

            return {
                "success": False,
                "status": "NO_LOANS_FOUND",
                "customer_id": customer_id,
                "message": (
                    "No loan records were found for this customer."
                )
            }

        loan_list = customer_loans.to_dict(
            orient="records"
        )

        # --------------------------------------------------
        # SUCCESSFUL FINANCIAL DATA ACCESS
        # --------------------------------------------------

        log_event(
            customer_id=customer_id,
            event_type="LOAN_BALANCE_ACCESS",
            description=(
                "Loan balance information was successfully "
                "retrieved following successful KYC verification."
            ),
            status="SUCCESS",
            agent="LOAN_TOOL"
        )

        return {
            "success": True,
            "status": "LOANS_FOUND",
            "customer_id": customer_id,
            "loans": loan_list
        }

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="LOAN_BALANCE_ACCESS",
            description=(
                f"Loan balance lookup encountered a system "
                f"error: {str(error)}"
            ),
            status="FAILED",
            agent="LOAN_TOOL"
        )

        return {
            "success": False,
            "status": "LOAN_LOOKUP_ERROR",
            "message": (
                "Unable to retrieve loan balance information "
                "at this time."
            )
        }


# ============================================================
# TESTS
# ============================================================

if __name__ == "__main__":

    print("==========================================")
    print("LOAN TOOL TEST")
    print("==========================================")

    # --------------------------------------------------------
    # TEST 1
    # --------------------------------------------------------

    print("\nTEST 1: Customer Loan Lookup Without KYC")
    print("------------------------------------------")

    result = get_customer_loans(
        customer_id="CUST001",
        kyc_verified=False
    )

    print(result)

    # --------------------------------------------------------
    # TEST 2
    # --------------------------------------------------------

    print("\nTEST 2: Customer Loan Lookup After KYC")
    print("------------------------------------------")

    result = get_customer_loans(
        customer_id="CUST001",
        kyc_verified=True
    )

    print(result)

    # --------------------------------------------------------
    # TEST 3
    # --------------------------------------------------------

    print("\nTEST 3: Loan Balance Without KYC")
    print("------------------------------------------")

    result = get_loan_balance(
        customer_id="CUST001",
        kyc_verified=False
    )

    print(result)

    # --------------------------------------------------------
    # TEST 4
    # --------------------------------------------------------

    print("\nTEST 4: Loan Balance After KYC")
    print("------------------------------------------")

    result = get_loan_balance(
        customer_id="CUST001",
        kyc_verified=True
    )

    print(result)

    # --------------------------------------------------------
    # TEST 5
    # --------------------------------------------------------

    print("\nTEST 5: Unknown Customer After KYC")
    print("------------------------------------------")

    result = get_customer_loans(
        customer_id="CUST999",
        kyc_verified=True
    )

    print(result)

    print("\n==========================================")
    print("LOAN TOOL TEST COMPLETE")
    print("==========================================")
