# Recoveries AI Agent

A governed AI-powered banking recoveries assistant designed to support customer servicing, payment-plan workflows, payment processing, notifications, and officer oversight.

The project combines **LLM-based conversational interaction** with **deterministic banking tools and human approval controls**. The AI does not directly make financial decisions or modify critical records without the appropriate backend validation and authorization.

---

## 1. Project Overview

The Recoveries AI Agent was developed to demonstrate how an AI agent can support banking recoveries operations while maintaining appropriate controls around:

* Customer identity verification
* Loan information disclosure
* Payment-plan requests
* Officer approval
* Payment processing
* Payment-plan schedule management
* Customer notifications
* Audit logging
* Idempotency and duplicate-payment prevention
* Human-in-the-loop decision making

The project uses an AI agent for conversational reasoning and tool selection, while critical financial operations are handled by deterministic Python functions connected to a structured Google Sheets data store.

---

## 2. Business Problem

Traditional recoveries processes can involve repetitive activities such as:

* Verifying customer identity
* Retrieving loan information
* Checking payment-plan status
* Capturing payment-plan requests
* Communicating payment information
* Updating payment-plan schedules
* Recording recovery actions
* Notifying customers

Automating these activities can improve consistency and reduce manual workload, but financial services require strong controls.

An AI system should therefore not be allowed to independently make or execute sensitive financial decisions simply because a customer asks it to do so.

This project addresses that problem by separating:

**Conversational AI**

from

**Deterministic financial operations and authorization controls.**

---

## 3. Solution Architecture

```text
                    Customer
                       │
                       ▼
              ┌─────────────────┐
              │   Gradio App    │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Recovery AI    │
              │     Agent       │
              └────────┬────────┘
                       │
              Tool selection / reasoning
                       │
        ┌──────────────┼───────────────┐
        │              │               │
        ▼              ▼               ▼
      KYC           Loans          Payments
        │              │               │
        └──────────────┼───────────────┘
                       │
                       ▼
              Payment Plan Tools
                       │
                       ▼
             Officer Approval Flow
                       │
                       ▼
              Payment Plan Lifecycle
                       │
                       ▼
                Notifications
                       │
                       ▼
                 Audit Logs
                       │
                       ▼
              Google Sheets Database
```

---

## 4. AI and Deterministic Responsibilities

A key design principle of the project is that the LLM is not treated as the system of record.

### AI responsibilities

The AI agent is responsible for:

* Understanding customer requests
* Maintaining conversational context
* Determining which approved tool is relevant
* Communicating tool results in customer-friendly language
* Asking for information when required
* Respecting workflow instructions
* Escalating situations that require human intervention

### Deterministic responsibilities

Python tools are responsible for:

* KYC verification
* Loan retrieval
* Payment validation
* Payment-plan validation
* Officer authorization
* Payment-plan approval/rejection
* Payment processing
* Schedule calculations
* Idempotency checks
* Notification creation
* Notification delivery
* Audit logging

This separation reduces the risk of the LLM independently inventing or executing financial actions.

---

## 5. KYC and Customer Privacy

Customer-facing loan information requires successful KYC verification.

The customer-facing KYC workflow uses:

* National ID
* Date of birth

A successful match results in:

```text
KYC_VERIFIED
```

Invalid identity information results in:

```text
KYC_FAILED
```

The agent is instructed to verify KYC before disclosing protected customer or loan information.

Internal identifiers such as customer IDs and request IDs are not intended to be exposed to customers.

---

## 6. Loan Information

After successful KYC, the agent can retrieve customer loan information through deterministic tools.

The loan workflow includes controls preventing access before KYC.

Example:

```text
Customer request
       │
       ▼
KYC verification
       │
       ├── Failed ──► No loan disclosure
       │
       ▼
Loan lookup
       │
       ▼
Customer loan information
```

The system was tested to confirm that loan information cannot be retrieved through the customer-facing workflow without KYC.

---

## 7. Payment-Plan Workflow

The payment-plan workflow separates customer request submission from officer authorization.

```text
Customer
   │
   ▼
Payment-plan request
   │
   ▼
Validation
   │
   ▼
Pending request
   │
   ▼
Officer review
   │
   ├── Reject ──► Request rejected
   │
   ▼
Approve
   │
   ▼
Active payment plan
```

The AI agent does not independently approve or reject payment-plan requests.

Officer authorization is handled by deterministic backend logic.

---

## 8. Human-in-the-Loop Approval

Payment-plan approval requires an authorized officer.

The system validates:

* Officer existence
* Officer status
* Officer role
* Request status
* Existing active payment plans
* Rejection reason where applicable

Tested scenarios included:

```text
Active authorized officer
        → Review permitted

Inactive officer
        → Action blocked

Unknown officer
        → Action blocked
```

This creates a human-in-the-loop control for sensitive financial decisions.

---

## 9. Payment Processing

Verified payments are processed through the payment-plan lifecycle.

The workflow validates:

1. Payment existence
2. Payment status
3. Customer ownership
4. Loan ownership
5. Active payment plan
6. Duplicate processing
7. Payment amount
8. Agreed payment amount
9. Payment-plan schedule

After successful processing, the payment-plan schedule is advanced and the payment ID is recorded against the plan.

---

## 10. Payment Idempotency

Financial transactions must not be processed repeatedly because of retries, duplicate requests, or system failures.

The system therefore maintains payment idempotency.

For example, attempting to process `PAY007` a second time returns:

```text
PAYMENT_ALREADY_PROCESSED
```

rather than applying the payment again.

This is an important control for preventing duplicate financial processing.

---

## 11. Partial Payments

The payment lifecycle contains a control for payments that do not match the agreed payment-plan amount.

For example:

```text
Agreed amount: $600
Payment:       $300
```

Such payments can be escalated for review rather than silently advancing the payment plan as though the full instalment had been received.

---

## 12. Payment-Plan Schedule Management

When a valid payment is successfully applied, the payment-plan schedule is advanced according to the plan frequency.

The tested example demonstrated:

```text
Previous next payment:
2027-01-20

Payment processed:
PAY007 / $600

New next payment:
2027-02-20
```

The payment plan also records the most recently processed payment ID.

---

## 13. Notifications

Successful payment-plan payments generate customer notifications.

The notification lifecycle is separated from payment processing:

```text
Payment processed
       │
       ▼
Notification created
       │
       ▼
PENDING
       │
       ▼
Notification delivery
       │
       ▼
SENT
```

This separation means notification delivery can fail or be retried without incorrectly reversing the financial transaction.

The tested workflow successfully created an SMS notification and subsequently delivered it.

---

## 14. Notification Idempotency

Notifications cannot simply be sent repeatedly.

The delivery tool checks the current notification status.

A notification that has already reached:

```text
SENT
```

cannot be delivered again through the normal pending-notification workflow.

A second delivery attempt returns:

```text
NOTIFICATION_NOT_PENDING
```

This prevents duplicate delivery.

---

## 15. Audit Logging

Important actions are recorded through the audit logging component.

Audit events support traceability of activities such as:

* KYC events
* Payment-plan actions
* Notification creation
* Financial workflow actions

The audit layer provides an additional record of important system activity beyond the conversational interface.

---

## 16. Technology Stack

### Programming

* Python
* Pandas
* Pydantic
* Python-dotenv

### AI

* OpenAI Agents SDK
* OpenRouter
* OpenAI-compatible chat-completions interface

### Interface

* Gradio

### Database / Storage

* Google Sheets
* gspread
* Google authentication

### Development

* Python virtual environment
* PowerShell
* Git / GitHub

---

## 17. Project Structure

```text
agents/
│
├── agent_modules/
│   ├── __init__.py
│   └── recovery_agent.py
│
├── audit/
│   ├── __init__.py
│   └── logger.py
│
├── database/
│   ├── google_sheets.py
│   └── schemas.py
│
├── notifications/
│   ├── email.py
│   ├── sms.py
│   ├── whatsapp.py
│   └── payment_plan_notifications.py
│
├── scheduler/
│   └── reminders.py
│
├── tools/
│   ├── kyc_tools.py
│   ├── account_tools.py
│   ├── loan_tools.py
│   ├── payment_tools.py
│   ├── payment_plan_tools.py
│   ├── payment_plan_request_tools.py
│   ├── payment_plan_approval_tools.py
│   ├── payment_plan_lifecycle_tools.py
│   ├── officer_tools.py
│   ├── notification_tools.py
│   └── notification_delivery_tools.py
│
├── app.py
├── test_ai_agent.py
├── pyproject.toml
├── uv.lock
└── .gitignore
```

---

## 18. Testing

The project has been tested at both component and workflow levels.

### KYC

Tested:

* Successful internal KYC
* Incorrect National ID
* Incorrect date of birth
* Unknown customer
* Customer-facing KYC

### Loans

Tested:

* Loan lookup without KYC
* Loan lookup after KYC
* Balance lookup without KYC
* Balance lookup after KYC
* Unknown customer

### Payment Plans

Tested:

* Officer review
* Authorized officer
* Inactive officer
* Unknown officer
* Approval workflow
* Rejection workflow
* Active payment-plan creation

### Payments

Tested:

* Verified payment processing
* Payment-plan schedule advancement
* Payment amount validation
* Partial payment handling
* Duplicate payment prevention
* Payment-plan `last_payment_id` update

### Notifications

Tested:

* Notification creation
* SMS notification creation
* Pending notification state
* Notification delivery
* Already-sent notification protection

### AI Agent

The multi-turn agent test verifies:

* KYC-driven customer interaction
* Payment-plan status retrieval
* Customer-safe responses
* Internal ID protection
* Conversation continuity
* Avoidance of duplicate payment-plan actions

The automated AI test completed successfully with:

```text
ALL AI AGENT TESTS PASSED
```

---

## 19. Security Considerations

Credentials and secrets should not be committed to source control.

The project uses environment variables for sensitive configuration.

Credential files are excluded from Git through `.gitignore`.

The Google service-account credentials should remain outside the public repository.

The production deployment should additionally use a secure secret-management mechanism rather than storing secrets directly in source code.

---

## 20. Important Design Principle

The project intentionally does not treat an LLM response as authorization to execute a financial action.

For example:

```text
Customer:
"Approve my payment plan."

        ↓

AI Agent

        ↓

Payment-plan request tool

        ↓

Pending request

        ↓

Authorized Recovery Officer

        ↓

Approve / Reject

        ↓

Deterministic backend action
```

The AI therefore acts as an intelligent interface and orchestration layer rather than an autonomous financial decision-maker.

---

## 21. Limitations

This project is a portfolio and development implementation rather than a production banking system.

The current implementation uses Google Sheets as the database layer for demonstration purposes.

A production implementation would require additional infrastructure and controls, including:

* Enterprise relational database
* Secure secrets management
* Production-grade authentication
* Role-based access control
* API security
* Transaction management
* Comprehensive automated test coverage
* Monitoring and alerting
* Production notification providers
* Disaster recovery
* High-availability infrastructure
* Formal model and AI governance
* Data protection and regulatory controls

---

## 22. Future Enhancements

Potential extensions include:

* Integration with a production core-banking system
* Real SMS provider integration
* WhatsApp integration
* Email integration
* Automated recovery reminders
* Recovery officer dashboards
* Portfolio-level recovery analytics
* Delinquency segmentation
* Promise-to-pay monitoring
* Payment-plan performance monitoring
* Model-based recovery prioritization
* Retrieval-augmented recovery policy assistance
* More comprehensive automated tests
* Containerized deployment
* CI/CD pipeline
* Production observability

---

## 23. Key Portfolio Skills Demonstrated

This project demonstrates practical experience across several areas:

### Banking and Credit

* Loan recoveries
* Credit risk
* Payment-plan management
* Customer servicing
* Officer authorization
* Financial transaction controls

### AI Engineering

* AI agents
* Tool calling
* Multi-turn conversations
* Agent orchestration
* Guardrails
* Human-in-the-loop workflows

### Data and Software Engineering

* Python
* Pandas
* Google Sheets integration
* API-style tool design
* Validation
* Idempotency
* Audit logging
* Automated testing

### Governance

* KYC controls
* Access control
* Internal identifier protection
* Deterministic financial operations
* Human approval
* Transaction safeguards
* Notification controls

---

## 24. Project Objective

The primary objective of the project was not simply to build a chatbot.

The objective was to demonstrate how **AI can be integrated into a banking recoveries workflow while retaining deterministic controls, human oversight, auditability, and protection against unsafe financial actions.**

This distinction is central to the architecture of the system.
