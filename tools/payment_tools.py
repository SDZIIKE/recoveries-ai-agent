import pandas as pd

from database.google_sheets import open_database
from audit.logger import log_event


def get_payment_history(customer_id, kyc_verified=False):
    """
    Retrieve payment history only after successful KYC.
    """

    customer_id = str(customer_id).strip()

    # ---------------------------------------------
    # KYC SECURITY CHECK
    # ---------------------------------------------

    if not kyc_verified:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_HISTORY_ACCESS",
            description=(
                "Payment history access was blocked because "
                "KYC verification had not been completed."
            ),
            status="BLOCKED",
            agent="PAYMENT_TOOL"
        )

        return {
            "success": False,
            "status": "KYC_REQUIRED",
            "customer_id": customer_id,
            "message": (
                "KYC verification is required before "
                "payment information can be disclosed."
            )
        }

    try:

        spreadsheet = open_database()

        worksheet = spreadsheet.worksheet("Payments")

        records = worksheet.get_all_records()

        payments = pd.DataFrame(records)

        if payments.empty:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_HISTORY_ACCESS",
                description="No payment records were found.",
                status="FAILED",
                agent="PAYMENT_TOOL"
            )

            return {
                "success": False,
                "status": "NO_PAYMENTS_FOUND",
                "customer_id": customer_id,
                "message": "No payment records were found."
            }

        customer_payments = payments[
            payments["customer_id"].astype(str).str.strip()
            == customer_id
        ]

        if customer_payments.empty:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_HISTORY_ACCESS",
                description=(
                    "No payment records were found for "
                    "the verified customer."
                ),
                status="FAILED",
                agent="PAYMENT_TOOL"
            )

            return {
                "success": False,
                "status": "NO_PAYMENTS_FOUND",
                "customer_id": customer_id,
                "message": (
                    "No payment records were found "
                    "for this customer."
                )
            }

        payment_list = customer_payments.to_dict(
            orient="records"
        )

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_HISTORY_ACCESS",
            description=(
                "Payment history was successfully retrieved "
                "following successful KYC verification."
            ),
            status="SUCCESS",
            agent="PAYMENT_TOOL"
        )

        return {
            "success": True,
            "status": "PAYMENTS_FOUND",
            "customer_id": customer_id,
            "payments": payment_list
        }

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_HISTORY_ACCESS",
            description=(
                f"Payment history lookup encountered a "
                f"system error: {str(error)}"
            ),
            status="FAILED",
            agent="PAYMENT_TOOL"
        )

        return {
            "success": False,
            "status": "PAYMENT_HISTORY_ERROR",
            "message": str(error)
        }


def verify_payment(
    customer_id,
    loan_id,
    reference,
    kyc_verified=False
):
    """
    Verify a payment only after successful KYC.

    The payment must also match:
    - customer ID
    - loan ID
    - payment reference
    - VERIFIED payment status
    """

    customer_id = str(customer_id).strip()
    loan_id = str(loan_id).strip()
    reference = str(reference).strip()

    # ---------------------------------------------
    # KYC SECURITY CHECK
    # ---------------------------------------------

    if not kyc_verified:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_VERIFICATION",
            description=(
                "Payment verification was blocked because "
                "KYC verification had not been completed."
            ),
            status="BLOCKED",
            agent="PAYMENT_TOOL"
        )

        return {
            "success": False,
            "status": "KYC_REQUIRED",
            "customer_id": customer_id,
            "message": (
                "KYC verification is required before "
                "payment verification can be performed."
            )
        }

    try:

        spreadsheet = open_database()

        worksheet = spreadsheet.worksheet("Payments")

        records = worksheet.get_all_records()

        payments = pd.DataFrame(records)

        if payments.empty:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_VERIFICATION",
                description=(
                    "Payment verification failed because "
                    "no payment records were found."
                ),
                status="FAILED",
                agent="PAYMENT_TOOL"
            )

            return {
                "success": False,
                "status": "NO_PAYMENTS_FOUND",
                "message": "No payment records were found."
            }

        payment_match = payments[
            (payments["customer_id"].astype(str).str.strip() == customer_id)
            &
            (payments["loan_id"].astype(str).str.strip() == loan_id)
            &
            (payments["reference"].astype(str).str.strip() == reference)
        ]

        if payment_match.empty:

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_VERIFICATION",
                description=(
                    f"Payment verification failed for loan "
                    f"{loan_id}. No matching payment reference "
                    f"was found."
                ),
                status="FAILED",
                agent="PAYMENT_TOOL"
            )

            return {
                "success": False,
                "status": "PAYMENT_NOT_FOUND",
                "customer_id": customer_id,
                "loan_id": loan_id,
                "message": (
                    "No matching payment was found."
                )
            }

        payment = payment_match.iloc[0]

        payment_status = str(
            payment["status"]
        ).strip().upper()

        if payment_status != "VERIFIED":

            log_event(
                customer_id=customer_id,
                event_type="PAYMENT_VERIFICATION",
                description=(
                    f"Payment reference {reference} was found "
                    f"but has status {payment_status}."
                ),
                status="BLOCKED",
                agent="PAYMENT_TOOL"
            )

            return {
                "success": False,
                "status": "PAYMENT_NOT_VERIFIED",
                "customer_id": customer_id,
                "loan_id": loan_id,
                "reference": reference,
                "message": (
                    "Payment exists but has not been verified."
                )
            }

        payment_data = payment.to_dict()

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_VERIFICATION",
            description=(
                f"Payment reference {reference} for loan "
                f"{loan_id} was successfully verified."
            ),
            status="SUCCESS",
            agent="PAYMENT_TOOL"
        )

        return {
            "success": True,
            "status": "PAYMENT_VERIFIED",
            "customer_id": customer_id,
            "loan_id": loan_id,
            "reference": reference,
            "payment": payment_data
        }

    except Exception as error:

        log_event(
            customer_id=customer_id,
            event_type="PAYMENT_VERIFICATION",
            description=(
                f"Payment verification encountered a "
                f"system error: {str(error)}"
            ),
            status="FAILED",
            agent="PAYMENT_TOOL"
        )

        return {
            "success": False,
            "status": "PAYMENT_VERIFICATION_ERROR",
            "message": str(error)
        }


if __name__ == "__main__":

    print("==========================================")
    print("PAYMENT TOOL + KYC GUARDRAIL TEST")
    print("==========================================")

    # ---------------------------------------------
    # TEST 1
    # ---------------------------------------------

    print("\nTEST 1: Payment History Without KYC")
    print("------------------------------------------")

    result = get_payment_history(
        customer_id="CUST001",
        kyc_verified=False
    )

    print(result)

    # ---------------------------------------------
    # TEST 2
    # ---------------------------------------------

    print("\nTEST 2: Payment History After KYC")
    print("------------------------------------------")

    result = get_payment_history(
        customer_id="CUST001",
        kyc_verified=True
    )

    print(result)

    # ---------------------------------------------
    # TEST 3
    # ---------------------------------------------

    print("\nTEST 3: Payment Verification Without KYC")
    print("------------------------------------------")

    result = verify_payment(
        customer_id="CUST001",
        loan_id="LN001",
        reference="TXN001",
        kyc_verified=False
    )

    print(result)

    # ---------------------------------------------
    # TEST 4
    # ---------------------------------------------

    print("\nTEST 4: Successful Payment Verification")
    print("------------------------------------------")

    result = verify_payment(
        customer_id="CUST001",
        loan_id="LN001",
        reference="TXN001",
        kyc_verified=True
    )

    print(result)

    # ---------------------------------------------
    # TEST 5
    # ---------------------------------------------

    print("\nTEST 5: Wrong Payment Reference")
    print("------------------------------------------")

    result = verify_payment(
        customer_id="CUST001",
        loan_id="LN001",
        reference="WRONG001",
        kyc_verified=True
    )

    print(result)

    print("\n==========================================")
    print("PAYMENT TOOL TEST COMPLETE")
    print("==========================================")