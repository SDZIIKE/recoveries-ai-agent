
import pandas as pd
from database.google_sheets import open_database


def verify_officer(officer_id):
    """
    Verify whether an officer is authorized to perform
    payment-plan approval actions.

    Authorization requirements:
    1. Officer ID must exist.
    2. Officer status must be ACTIVE.
    3. Officer role must be RECOVERIES OFFICER.
    """

    try:
        # Connect to Google Sheets database
        spreadsheet = open_database()

        # Open Officers worksheet
        worksheet = spreadsheet.worksheet("Officers")

        # Retrieve officer records
        records = worksheet.get_all_records()
        officers = pd.DataFrame(records)

        # Check whether any officers exist
        if officers.empty:
            return {
                "authorized": False,
                "status": "NO_OFFICERS_FOUND",
                "message": "No officer records were found."
            }

        # Find officer by ID
        officer = officers[
            officers["officer_id"].astype(str).str.strip()
            == str(officer_id).strip()
        ]

        # Officer does not exist
        if officer.empty:
            return {
                "authorized": False,
                "status": "OFFICER_NOT_FOUND",
                "message": "Officer ID was not found in the authorized officers database."
            }

        # Get the matching officer record
        officer = officer.iloc[0]

        # Check officer status
        status = str(officer["status"]).strip().upper()

        if status != "ACTIVE":
            return {
                "authorized": False,
                "status": "OFFICER_INACTIVE",
                "officer_id": str(officer["officer_id"]),
                "message": "Officer is not currently authorized to perform approval actions."
            }

        # Check officer role
        role = str(officer["role"]).strip().upper()

        if role != "RECOVERIES OFFICER":
            return {
                "authorized": False,
                "status": "INVALID_OFFICER_ROLE",
                "officer_id": str(officer["officer_id"]),
                "message": "Officer does not have the required Recoveries Officer role."
            }

        # Officer successfully verified
        return {
            "authorized": True,
            "status": "OFFICER_VERIFIED",
            "officer_id": str(officer["officer_id"]),
            "full_name": str(officer["full_name"]),
            "department": str(officer["department"]),
            "role": str(officer["role"]),
            "message": "Officer is authorized to perform approval actions."
        }

    except Exception as error:

        return {
            "authorized": False,
            "status": "OFFICER_VERIFICATION_ERROR",
            "message": str(error)
        }


# ---------------------------------------------------------
# TESTING
# ---------------------------------------------------------

if __name__ == "__main__":

    print("==========================================")
    print("OFFICER AUTHORIZATION TEST")
    print("==========================================")

    # -----------------------------------------------------
    # TEST 1: Active Recoveries Officer
    # -----------------------------------------------------

    print("\nTEST 1: Active Recoveries Officer")
    print("------------------------------------------")

    result = verify_officer("OFF001")

    print(result)

    # -----------------------------------------------------
    # TEST 2: Inactive Officer
    # -----------------------------------------------------

    print("\nTEST 2: Inactive Officer")
    print("------------------------------------------")

    result = verify_officer("OFF002")

    print(result)

    # -----------------------------------------------------
    # TEST 3: Unknown Officer
    # -----------------------------------------------------

    print("\nTEST 3: Unknown Officer")
    print("------------------------------------------")

    result = verify_officer("OFF999")

    print(result)

    # -----------------------------------------------------
    # TEST 4: Empty / Invalid Officer ID
    # -----------------------------------------------------

    print("\nTEST 4: Empty Officer ID")
    print("------------------------------------------")

    result = verify_officer("")

    print(result)

