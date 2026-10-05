import os
import gspread
from google.oauth2.service_account import Credentials


# ============================================================
# GOOGLE SHEETS CONFIGURATION
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

CREDENTIALS_FILE = os.path.join(
    BASE_DIR,
    "credentials",
    "recoveries-ai-agent.json"
)

SPREADSHEET_ID = "1GQ_fbsSaWSZJpwgv0FDu6r2IjnzVV22lgMMkyKX1afs"


# ============================================================
# CONNECT TO GOOGLE SHEETS
# ============================================================

def connect_to_google_sheets():

    credentials = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=SCOPES
    )

    client = gspread.authorize(credentials)

    return client


# ============================================================
# OPEN DATABASE
# ============================================================

def open_database():

    client = connect_to_google_sheets()

    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    return spreadsheet


# ============================================================
# TEST CONNECTION
# ============================================================

if __name__ == "__main__":

    print("==========================================")
    print("GOOGLE SHEETS DIAGNOSTIC TEST")
    print("==========================================")

    try:

        print("1. Loading credentials...")

        credentials = Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=SCOPES
        )

        print("✓ Credentials loaded")
        print(
            f"Service account: {credentials.service_account_email}"
        )

        print()
        print("2. Authenticating with Google Sheets...")

        client = gspread.authorize(credentials)

        print("✓ Authentication successful")

        print()
        print("3. Opening spreadsheet by ID...")

        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        print("✓ Spreadsheet opened successfully")

        print()
        print("==========================================")
        print("SUCCESS")
        print("==========================================")

        print(f"Database: {spreadsheet.title}")

        print()
        print("Worksheets:")

        for worksheet in spreadsheet.worksheets():
            print(f" - {worksheet.title}")

    except Exception as error:

        print()
        print("==========================================")
        print("FAILED")
        print("==========================================")

        print(f"Error type: {type(error).__name__}")
        print(f"Error: {repr(error)}")

        print()
        print("FULL TRACEBACK:")

        import traceback
        traceback.print_exc()