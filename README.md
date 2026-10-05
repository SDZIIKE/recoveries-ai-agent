# Banking Recoveries AI Agent

An AI-powered banking recoveries assistant designed to support customers with loan-recovery enquiries and payment-plan requests while enforcing KYC, deterministic business rules, human approval, auditability, notifications, and payment reminders.

> **Built with Python, Google Gemini, OpenAI Agents SDK, Google Sheets, and Gradio**

---

## Overview

The Banking Recoveries AI Agent addresses a practical banking operations problem: customers often need assistance with loan balances, payment history, payment verification, and repayment arrangements outside normal Recoveries Officer working hours.

The system provides an AI conversational interface for routine customer assistance while keeping sensitive financial decisions under deterministic backend controls and human authority.

The design deliberately separates:

**AI conversation and explanation**

from

**financial rules, authorization, database updates, and audit controls.**

Google Sheets is used as the system of record for this prototype.

---

## Business Problem

Traditional recoveries workflows can require customers to wait for a Recoveries Officer before receiving basic information or requesting repayment arrangements.

This can create:

- Delays in customer support
- Increased recoveries workload
- Manual handling of repetitive enquiries
- Risk of inconsistent responses
- Limited support outside working hours
- Weak traceability when actions are not systematically logged

The goal of this project is to provide an AI-assisted recovery workflow that improves responsiveness without allowing the AI to make uncontrolled financial decisions.

---

## Solution

The agent provides a controlled workflow:

```text
Customer
   │
   ▼
Gradio Customer Interface
   │
   ▼
Recoveries AI Agent
   │
   ├── KYC Verification
   │
   ├── Loan Information
   │
   ├── Payment History
   │
   ├── Payment Verification
   │
   ├── Active Payment Plan
   │
   └── Payment Plan Request
              │
              ▼
      Deterministic Backend
              │
              ├── Business Rules
              ├── Validation
              ├── Authorization
              ├── Audit Logging
              └── Notifications
                       │
                       ▼
                Google Sheets
                       │
              ┌────────┴────────┐
              ▼                 ▼
      Customer Notification   Officer Review
                                    │
                                    ▼
                         Approve / Reject / Escalate
```

---

## Core Capabilities

### Customer Assistance

The customer-facing agent can assist with:

- KYC verification
- Loan information
- Loan balances
- Payment history
- Payment verification
- Active payment-plan information
- Payment-plan request submission
- Payment-plan request status

### Recoveries Officer Workflow

The officer interface supports:

- Officer authorization
- Payment-plan request review
- Payment-plan approval
- Payment-plan rejection
- Mandatory rejection reasons
- Active payment-plan lookup
- Payment-plan closure

### Notifications and Automation

The system also provides:

- Customer notification creation
- Notification delivery workflow
- Duplicate notification protection
- Payment-plan reminders
- Duplicate reminder protection
- Audit logging of important actions

---

## Safety and Guardrails

This project is intentionally designed as a **bounded AI agent**, not an unrestricted chatbot.

### 1. KYC Before Confidential Information

Customer-specific financial information requires successful verification using:

- National ID
- Date of birth

If KYC fails, confidential customer information is not disclosed.

### 2. Internal Identifier Protection

The customer-facing AI must never expose internal identifiers such as:

- Customer ID
- Loan ID
- Payment Plan ID
- Payment Plan Request ID
- Officer ID

Sensitive backend responses are sanitized before being returned to the customer-facing agent.

### 3. Human-in-the-Loop Approval

The AI cannot approve or reject its own payment-plan requests.

A payment-plan request follows:

```text
Customer Proposal
      ↓
Explicit Customer Consent
      ↓
Request Submitted
      ↓
Recoveries Officer Review
      ↓
Approved / Rejected
```

### 4. Deterministic Financial Logic

Financial and workflow decisions are implemented in Python rather than delegated to the language model.

Examples include:

- Payment validation
- Full vs partial payment determination
- Payment-plan eligibility controls
- Duplicate-payment protection
- Active-plan checks
- Officer authorization
- Schedule advancement
- Duplicate reminder protection

### 5. Escalation

The system escalates situations that require human intervention, including:

- Failed KYC
- Multiple loans where the applicable loan cannot be safely determined
- Multiple active payment plans
- Payment-plan approval decisions
- Unsupported or exceptional workflows

---

## Payment Lifecycle

Verified payments are processed using deterministic backend rules.

### Full Payment

A full instalment:

1. Is validated
2. Is applied to the payment plan
3. Advances the next payment date
4. Updates the latest payment reference
5. Creates a customer notification
6. Creates an audit event

### Partial Payment

A partial instalment:

1. Is validated
2. Is applied to the payment plan
3. Records the outstanding shortfall
4. Does not advance the scheduled instalment date
5. Creates a customer notification
6. Creates an audit event

### Duplicate Payment Protection

A payment that has already been processed cannot be processed again.

This prevents duplicate financial application.

---

## Payment-Plan Workflow

A customer can propose a repayment arrangement using natural language.

Example:

```text
I want to pay $1,000 monthly starting on October 15, 2026
for 6 payments.
```

The system extracts and validates the proposed terms.

The AI must then obtain explicit customer consent in a subsequent interaction before submitting the request.

The request remains pending until a Recoveries Officer makes the decision.

The AI does not claim approval unless an authorized backend workflow has actually approved the request.

---

## Notifications

Notifications are stored in the `Notifications` Google Sheets tab.

The prototype separates:

### Notification Creation

Creates a pending notification record after a qualifying business event.

### Notification Delivery

The current development implementation simulates provider delivery by changing the notification status from:

```text
PENDING
```

to:

```text
SENT
```

and recording the send timestamp.

A production implementation could replace this simulated delivery layer with an approved SMS, email, or WhatsApp provider.

---

## Payment Reminders

The reminder scheduler checks active payment plans and identifies plans whose next payment date is:

```text
today or earlier
```

For qualifying plans it creates a customer reminder notification.

The scheduler also includes duplicate protection so the same plan/payment date does not continuously generate duplicate reminders.

---

## Auditability

Important actions are recorded in the `Audit Logs` sheet.

Examples include:

- KYC events
- Payment-plan access
- Payment processing
- Payment-plan approval
- Payment-plan rejection
- Officer authorization failures
- Notification delivery
- Reminder creation
- System errors

This provides an operational trail for reviewing what happened and when.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Programming Language | Python |
| LLM | Google Gemini |
| Agent Framework | OpenAI Agents SDK |
| Customer Interface | Gradio |
| Data Store | Google Sheets |
| Data Access | `gspread` / Google authentication |
| Data Processing | Pandas |
| Configuration | `python-dotenv` |
| Validation | Python / Pydantic |
| Testing | Python test scripts |
| Version Control | Git / GitHub |

---

## Project Structure

```text
recoveries-ai-agent/
│
├── agent_modules/
│   ├── __init__.py
│   └── recovery_agent.py
│
├── audit/
│   └── logger.py
│
├── database/
│   └── google_sheets.py
│
├── notifications/
│   ├── __init__.py
│   ├── email.py
│   ├── payment_plan_notifications.py
│   ├── sms.py
│   └── whatsapp.py
│
├── scheduler/
│   ├── __init__.py
│   └── reminders.py
│
├── tools/
│   ├── kyc_tools.py
│   ├── loan_tools.py
│   ├── notification_delivery_tools.py
│   ├── notification_tools.py
│   ├── officer_tools.py
│   ├── payment_plan_approval_tools.py
│   ├── payment_plan_lifecycle_tools.py
│   ├── payment_plan_request_tools.py
│   ├── payment_plan_tools.py
│   └── payment_tools.py
│
├── app.py
├── README.md
├── requirements.txt
├── test_ai_agent.py
├── test_extractor.py
├── test_money_parser.py
└── .gitignore
```

---

## Google Sheets Data Model

The prototype uses the following worksheets:

```text
Customers
Loans
Payments
Payment Plans
Payment Plan Requests
Officers
Notifications
Audit Logs
```

Google Sheets functions as the system of record while Python modules provide controlled access to the data.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/SDZIIKE/recoveries-ai-agent.git
cd recoveries-ai-agent
```

### 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file containing the required configuration values used by the application.

Example:

```env
GOOGLE_API_KEY=your_gemini_api_key
SPREADSHEET_ID=your_google_sheet_id
```

The Google service-account credentials should be kept outside source control.

**Never commit:**

```text
.env
service-account JSON credentials
API keys
private keys
secrets
```

The repository `.gitignore` is intended to prevent sensitive files from being committed.

---

## Running the Application

Start the Gradio application:

```powershell
python app.py
```

The application provides two main areas:

```text
Customer Assistant
Recoveries Officer
```

---

## Testing

The project includes focused tests for the major workflow components.

### AI Agent Tests

```powershell
python test_ai_agent.py
```

### Payment-Plan Extraction Tests

```powershell
python test_extractor.py
```

### Money Parsing Tests

```powershell
python test_money_parser.py
```

The implementation has been tested across:

- KYC verification
- KYC failure handling
- Loan information retrieval
- Payment history retrieval
- Payment verification
- Payment-plan lookup
- Payment-plan requests
- Payment-plan request status
- Officer authorization
- Officer review
- Officer decision controls
- Payment lifecycle processing
- Full payments
- Partial payments
- Duplicate payments
- Notifications
- Notification delivery
- Duplicate notification delivery
- Payment reminders
- Duplicate reminder protection
- Audit logging
- Live Gradio customer workflow
- Live Gradio officer workflow

---

## Example Customer Interaction

```text
Customer:
My National ID is 00-000001A00 and my date of birth is
1990-01-15. What is my current payment plan?

AI:
Your active payment plan is $700 per month.
Your next scheduled payment is due on 15 December 2026.
```

The customer-facing response is generated from the controlled backend result rather than from an assumed or remembered value.

---

## Example Payment-Plan Request Flow

```text
Customer:
I want to change my payment to $1,000 per month.

AI:
Confirms the proposed terms and asks for the remaining
required information.

Customer:
Start date is 15 October 2026 and I want 6 payments.

AI:
Summarizes the complete proposal and requests explicit consent.

Customer:
Yes, I confirm and give my consent.

System:
Submits the request for Recoveries Officer review.

AI:
Explains that the request is pending officer review.
```

The AI does not independently approve or activate the arrangement.

---

## Design Principles

The project follows several principles:

### AI for Conversation

The LLM interprets natural-language requests and explains validated results.

### Python for Control

Sensitive business rules remain deterministic.

### Human Authority for Decisions

Actions requiring institutional authority remain with authorized Recoveries Officers.

### Data Minimization

Only customer-appropriate fields are returned to the customer-facing AI.

### Auditability

Important operations are logged for traceability.

### Fail Closed

When the system cannot safely determine the correct action, it blocks or escalates rather than guessing.

---

## Current Prototype Limitations

This is a portfolio and development prototype rather than a production banking deployment.

Current limitations include:

- Google Sheets is used instead of a production core-banking database.
- Notification delivery is simulated in the development environment.
- Authentication and authorization would require integration with enterprise identity infrastructure for production.
- Production deployment would require enterprise security, monitoring, secrets management, rate limiting, and additional compliance controls.
- The current dataset is a controlled demonstration environment rather than live banking data.

---

## Future Enhancements

Potential production-oriented extensions include:

- Core banking integration
- Enterprise identity and access management
- Production SMS/WhatsApp/email gateways
- PostgreSQL or enterprise database integration
- Role-based officer permissions
- Advanced observability and monitoring
- Retrieval and conversation analytics
- Recoveries prioritization models
- Probability-of-default and collections-risk integration
- Collections strategy optimization
- Production API layer
- Containerized deployment
- Automated CI/CD testing

---

## Why This Project Matters

This project demonstrates the application of AI to a real banking operations problem while addressing one of the biggest challenges with financial AI systems:

> **How do you make an AI assistant useful without allowing it to make unsafe financial decisions?**

The solution is a hybrid architecture in which:

```text
LLM
 ↓
Conversation + Interpretation
 ↓
Deterministic Tools
 ↓
Business Rules + Validation + Authorization
 ↓
Database / Workflow
 ↓
Audit + Notification
```

This approach makes the system more controllable, testable, and suitable for regulated financial workflows than a general-purpose chatbot.

---

## Author

**Simbarashe Dziike**

Banking | Credit Risk | Recoveries | Data Analytics | AI

GitHub:
https://github.com/SDZIIKE

---

## Disclaimer

This repository is a portfolio and development prototype.

It is not intended for direct deployment into a production banking environment without appropriate security, compliance, authorization, infrastructure, data-protection, monitoring, and operational controls.