import gradio as gr

from agents import Runner

from agent_modules.recovery_agent import recovery_agent

from tools.payment_plan_approval_tools import (
    review_payment_plan_request,
    process_payment_plan_decision,
)

from tools.payment_plan_tools import (
    close_payment_plan,
    get_active_payment_plans_by_national_id,
)

from tools.officer_tools import verify_officer


# ============================================================
# CUSTOMER AI ASSISTANT
# ============================================================

async def ask_recovery_agent(customer_message, conversation_history):
    """
    Send a customer message to the Recoveries AI Agent while
    maintaining conversation state within the current session.
    """

    customer_message = (customer_message or "").strip()

    if not customer_message:
        return "", conversation_history

    try:
        if not conversation_history:
            agent_input = customer_message
        else:
            agent_input = conversation_history + [
                {
                    "role": "user",
                    "content": customer_message,
                }
            ]

        result = await Runner.run(
            recovery_agent,
            agent_input,
        )

        updated_history = result.to_input_list()

        return result.final_output, updated_history

    except Exception as error:
        print("AI AGENT ERROR:")
        print(error)

        return (
            "I am currently unable to process your request. "
            "Please try again later or contact a Recoveries Officer "
            "for assistance.",
            conversation_history,
        )


# ============================================================
# OFFICER REQUEST REVIEW
# ============================================================

def review_request(officer_id, request_id):
    """
    Allow an authorized Recoveries Officer to review a
    payment-plan request before making a decision.
    """

    officer_id = (officer_id or "").strip()
    request_id = (request_id or "").strip()

    if not officer_id:
        return "Please enter your Officer ID."

    if not request_id:
        return "Please enter the Payment Plan Request ID."

    try:
        officer_result = verify_officer(officer_id)

        if not officer_result.get("authorized"):
            return officer_result.get(
                "message",
                "Officer verification failed.",
            )

        result = review_payment_plan_request(
            officer_id=officer_id,
            request_id=request_id,
        )

        if not result.get("success"):
            return result.get(
                "message",
                "Unable to review the payment-plan request.",
            )

        return (
            f"Request ID: {result.get('request_id', 'N/A')}\n"
            f"Customer ID: {result.get('customer_id', 'N/A')}\n"
            f"Loan ID: {result.get('loan_id', 'N/A')}\n"
            f"Proposed Amount: ${float(result.get('proposed_amount', 0) or 0):,.2f}\n"
            f"Frequency: {result.get('frequency', 'N/A')}\n"
            f"Start Date: {result.get('start_date', 'N/A')}\n"
            f"Next Payment Date: {result.get('next_payment_date', 'N/A')}\n"
            f"Number of Payments: {result.get('number_of_payments', 'N/A')}\n"
            f"Customer Consent: {result.get('customer_consent', 'N/A')}\n"
            f"Approval Status: {result.get('approval_status', 'N/A')}\n"
            f"Submitted At: {result.get('submitted_at', 'N/A')}\n"
            f"Reviewed By: {result.get('reviewed_by', officer_id)}"
        )

    except Exception as error:
        print("OFFICER REVIEW ERROR:")
        print(error)

        return (
            "Unable to review the request at this time. "
            "Please try again later."
        )


# ============================================================
# OFFICER DECISION
# ============================================================

def submit_decision(
    officer_id,
    request_id,
    decision,
    rejection_reason,
):
    """
    Submit an approval or rejection decision for a
    payment-plan request.
    """

    officer_id = (officer_id or "").strip()
    request_id = (request_id or "").strip()
    decision = (decision or "").strip().upper()
    rejection_reason = (rejection_reason or "").strip()

    if not officer_id:
        return "Please enter your Officer ID."

    if not request_id:
        return "Please enter the Payment Plan Request ID."

    if decision not in ["APPROVED", "REJECTED"]:
        return "Decision must be APPROVED or REJECTED."

    if decision == "REJECTED" and not rejection_reason:
        return "A rejection reason is required."

    try:
        officer_result = verify_officer(officer_id)

        if not officer_result.get("authorized"):
            return officer_result.get(
                "message",
                "Officer verification failed.",
            )

        result = process_payment_plan_decision(
            officer_id=officer_id,
            request_id=request_id,
            decision=decision,
            rejection_reason=rejection_reason,
        )

        if not result.get("success"):
            return result.get(
                "message",
                "Unable to process the decision.",
            )

        return result.get(
            "message",
            f"Request {request_id} processed successfully.",
        )

    except Exception as error:
        print("OFFICER DECISION ERROR:")
        print(error)

        return (
            "Unable to process the officer decision at this time. "
            "Please try again later."
        )


# ============================================================
# ACTIVE PAYMENT PLAN LOOKUP
# ============================================================

def lookup_active_payment_plans(officer_id, national_id):
    """
    Retrieve ACTIVE payment plans using the customer's National ID.

    This is an officer-only workflow. The deterministic backend
    validates officer authorization, resolves the National ID to
    the internal customer record, and returns ACTIVE plans only.
    """

    officer_id = (officer_id or "").strip()
    national_id = (national_id or "").strip()

    if not officer_id:
        return "Please enter your Officer ID."

    if not national_id:
        return "Please enter the customer's National ID."

    try:
        officer_result = verify_officer(officer_id)

        if not officer_result.get("authorized"):
            return officer_result.get(
                "message",
                "Officer verification failed.",
            )

        result = get_active_payment_plans_by_national_id(
            national_id=national_id,
            officer_id=officer_id,
        )

        if not result.get("success"):
            return result.get(
                "message",
                "Unable to retrieve active payment plans.",
            )

        if result.get("status") == "NO_ACTIVE_PAYMENT_PLANS":
            return (
                f"National ID: {national_id}\n\n"
                "No active payment plans were found for this customer."
            )

        plans = result.get("payment_plans", [])

        if not plans:
            return (
                f"National ID: {national_id}\n\n"
                "No active payment plans were found for this customer."
            )

        lines = [
            f"National ID: {national_id}",
            "",
            f"Active Payment Plans Found: {len(plans)}",
            "",
        ]

        for index, plan in enumerate(plans, start=1):
            lines.extend(
                [
                    f"--- Active Payment Plan {index} ---",
                    f"Plan ID: {plan.get('plan_id', 'N/A')}",
                    f"Loan ID: {plan.get('loan_id', 'N/A')}",
                    f"Agreed Amount: ${float(plan.get('agreed_amount', 0) or 0):,.2f}",
                    f"Frequency: {plan.get('frequency', 'N/A')}",
                    f"Start Date: {plan.get('start_date', 'N/A')}",
                    f"Next Payment Date: {plan.get('next_payment_date', 'N/A')}",
                    f"Number of Payments: {plan.get('number_of_payments', 'N/A')}",
                    f"Status: {plan.get('status', 'N/A')}",
                    "",
                ]
            )

        return "\n".join(lines)

    except Exception as error:
        print("ACTIVE PAYMENT PLAN LOOKUP ERROR:")
        print(error)

        return (
            "Unable to retrieve active payment plans at this time. "
            "Please try again later."
        )


# ============================================================
# ACTIVE PAYMENT PLAN CLOSURE
# ============================================================

def close_plan(officer_id, plan_id, closure_reason):
    """
    Close an ACTIVE payment plan through the authorized
    Recoveries Officer workflow.
    """

    officer_id = (officer_id or "").strip()
    plan_id = (plan_id or "").strip()
    closure_reason = (closure_reason or "").strip()

    if not officer_id:
        return "Please enter your Officer ID."

    if not plan_id:
        return "Please enter the Payment Plan ID."

    if not closure_reason:
        return "A closure reason is required."

    try:
        officer_result = verify_officer(officer_id)

        if not officer_result.get("authorized"):
            return officer_result.get(
                "message",
                "Officer verification failed.",
            )

        result = close_payment_plan(
            plan_id=plan_id,
            officer_id=officer_id,
            closure_reason=closure_reason,
        )

        if not result.get("success"):
            return result.get(
                "message",
                "Unable to close the payment plan.",
            )

        return (
            f"Payment plan {result.get('plan_id', plan_id)} was successfully closed.\n\n"
            f"Customer ID: {result.get('customer_id', 'N/A')}\n"
            f"Loan ID: {result.get('loan_id', 'N/A')}\n"
            f"Closed By: {result.get('closed_by', officer_id)}\n"
            f"Closed At: {result.get('closed_at', 'N/A')}\n"
            f"Closure Reason: {result.get('closure_reason', closure_reason)}"
        )

    except Exception as error:
        print("PAYMENT PLAN CLOSURE ERROR:")
        print(error)

        return (
            "Unable to close the payment plan at this time. "
            "Please try again later."
        )


# ============================================================
# CUSTOMER INTERFACE
# ============================================================

def build_customer_interface():
    conversation_state = gr.State([])

    gr.Markdown(
        """
        # Recoveries AI Assistant

        Welcome to the Recoveries AI Assistant.

        The assistant can help with:
        - Loan balance enquiries
        - Loan information
        - Payment history
        - Payment verification
        - Payment-plan requests

        **Identity verification is required before confidential
        customer information is disclosed.**

        Payment-plan requests require Recoveries Officer approval.
        """
    )

    customer_message = gr.Textbox(
        label="Customer Message",
        placeholder=(
            "Example: My National ID is 00-000001A00 "
            "and my date of birth is 1990-01-15."
        ),
        lines=5,
    )

    ai_response = gr.Textbox(
        label="AI Response",
        lines=10,
    )

    with gr.Row():
        ask_button = gr.Button("Send")
        clear_button = gr.Button("Clear")

    ask_button.click(
        fn=ask_recovery_agent,
        inputs=[
            customer_message,
            conversation_state,
        ],
        outputs=[
            ai_response,
            conversation_state,
        ],
    )

    clear_button.click(
        fn=lambda: ("", "", []),
        inputs=None,
        outputs=[
            customer_message,
            ai_response,
            conversation_state,
        ],
    )


# ============================================================
# OFFICER INTERFACE
# ============================================================

def build_officer_interface():
    gr.Markdown(
        """
        # Recoveries Officer Portal

        This section is restricted to authorized Recoveries Officers.

        Officers can:
        - Search active payment plans using National ID
        - Review pending payment-plan requests
        - Approve payment-plan requests
        - Reject payment-plan requests
        - Close active payment plans
        - Provide rejection and closure reasons

        The AI assistant does not approve, reject, or close
        payment plans.
        """
    )

    officer_id = gr.Textbox(
        label="Officer ID",
        placeholder="Example: OFF001",
    )

    # ========================================================
    # ACTIVE PAYMENT PLAN LOOKUP
    # ========================================================

    gr.Markdown("### Active Payment Plan Lookup")

    gr.Markdown(
        """
        Enter the customer's **National ID** to retrieve
        active payment plans. The system resolves the customer
        internally and displays active plans only.
        """
    )

    national_id = gr.Textbox(
        label="Customer National ID",
        placeholder="Example: 00-000001A00",
    )

    lookup_output = gr.Textbox(
        label="Active Payment Plan Results",
        lines=12,
    )

    lookup_button = gr.Button("Search Active Payment Plans")

    lookup_button.click(
        fn=lookup_active_payment_plans,
        inputs=[
            officer_id,
            national_id,
        ],
        outputs=lookup_output,
    )

    # ========================================================
    # PAYMENT PLAN REQUEST REVIEW
    # ========================================================

    gr.Markdown("### Payment Plan Request Review")

    request_id = gr.Textbox(
        label="Payment Plan Request ID",
        placeholder="Example: REQ-XXXXXXXX",
    )

    review_output = gr.Textbox(
        label="Request Details",
        lines=12,
    )

    review_button = gr.Button("Review Request")

    review_button.click(
        fn=review_request,
        inputs=[
            officer_id,
            request_id,
        ],
        outputs=review_output,
    )

    # ========================================================
    # PAYMENT PLAN DECISION
    # ========================================================

    gr.Markdown("### Decision")

    decision = gr.Dropdown(
        choices=[
            "APPROVED",
            "REJECTED",
        ],
        label="Decision",
    )

    rejection_reason = gr.Textbox(
        label="Rejection Reason",
        placeholder=(
            "Required when rejecting a payment-plan request."
        ),
        lines=3,
    )

    decision_output = gr.Textbox(
        label="Decision Result",
        lines=5,
    )

    decision_button = gr.Button("Submit Decision")

    decision_button.click(
        fn=submit_decision,
        inputs=[
            officer_id,
            request_id,
            decision,
            rejection_reason,
        ],
        outputs=decision_output,
    )

    # ========================================================
    # ACTIVE PAYMENT PLAN CLOSURE
    # ========================================================

    gr.Markdown("### Active Payment Plan Closure")

    gr.Markdown(
        """
        Use this section only when an active payment arrangement
        must be formally closed. A closure reason is mandatory.
        """
    )

    plan_id = gr.Textbox(
        label="Active Payment Plan ID",
        placeholder="Example: PLAN008",
    )

    closure_reason = gr.Textbox(
        label="Closure Reason",
        placeholder=(
            "Explain why the active payment plan is being closed."
        ),
        lines=4,
    )

    closure_output = gr.Textbox(
        label="Closure Result",
        lines=7,
    )

    close_button = gr.Button("Close Active Payment Plan")

    close_button.click(
        fn=close_plan,
        inputs=[
            officer_id,
            plan_id,
            closure_reason,
        ],
        outputs=closure_output,
    )


# ============================================================
# MAIN APPLICATION
# ============================================================

with gr.Blocks(
    title="Recoveries AI Agent",
) as app:

    gr.Markdown(
        """
        # Banking Recoveries AI Agent

        AI-assisted customer recovery support with:

        **KYC → Information Retrieval → Customer Assistance
        → Human Approval → Payment Plan → Notifications
        → Audit Logging**

        Google Sheets remains the system of record.

        Deterministic backend tools enforce sensitive operations,
        while the AI is responsible for conversation and explanation.
        """
    )

    with gr.Tab("Customer Assistant"):
        build_customer_interface()

    with gr.Tab("Recoveries Officer"):
        build_officer_interface()


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":
    app.launch()
