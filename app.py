import os
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

from tools.officer_tools import (
    verify_officer,
    get_pending_payment_plan_requests,
)


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
# PENDING PAYMENT PLAN REQUESTS
# ============================================================

def load_pending_requests(officer_id):
    """
    Load pending payment-plan requests for an authorized
    Recoveries Officer.

    The backend remains authoritative for authorization and
    request status. This function only prepares the data for
    the Gradio Officer Portal.
    """

    officer_id = (officer_id or "").strip()

    if not officer_id:
        return (
            gr.update(choices=[], value=None),
            "Please enter your Officer ID.",
        )

    try:
        officer_result = verify_officer(officer_id)

        if not officer_result.get("authorized"):
            return (
                gr.update(choices=[], value=None),
                officer_result.get(
                    "message",
                    "Officer verification failed.",
                ),
            )

        result = get_pending_payment_plan_requests(
            officer_id
        )

        if not result.get("success"):
            return (
                gr.update(choices=[], value=None),
                result.get(
                    "message",
                    "Unable to retrieve pending payment-plan requests.",
                ),
            )

        requests = result.get("requests", []) or []

        if not requests:
            return (
                gr.update(
                    choices=[],
                    value=None,
                ),
                "There are currently no pending payment-plan requests requiring officer review.",
            )

        choices = []

        lines = [
            f"Pending Payment-Plan Requests: {len(requests)}",
            "",
        ]

        for request in requests:

            request_id = str(
                request.get(
                    "request_id",
                    "",
                )
            ).strip()

            if not request_id:
                continue

            proposed_amount = request.get(
                "proposed_amount",
                0,
            )

            try:
                amount_text = (
                    f"${float(proposed_amount or 0):,.2f}"
                )
            except (TypeError, ValueError):
                amount_text = str(proposed_amount)

            label = (
                f"{request_id} | "
                f"{amount_text} | "
                f"{request.get('frequency', 'N/A')} | "
                f"{request.get('submitted_at', 'N/A')}"
            )

            choices.append(
                (
                    label,
                    request_id,
                )
            )

            lines.extend(
                [
                    f"--- {request_id} ---",
                    f"Customer ID: {request.get('customer_id', 'N/A')}",
                    f"Loan ID: {request.get('loan_id', 'N/A')}",
                    f"Proposed Amount: {amount_text}",
                    f"Frequency: {request.get('frequency', 'N/A')}",
                    f"Start Date: {request.get('start_date', 'N/A')}",
                    f"Next Payment Date: {request.get('next_payment_date', 'N/A')}",
                    f"Number of Payments: {request.get('number_of_payments', 'N/A')}",
                    f"Customer Consent: {request.get('customer_consent', 'N/A')}",
                    f"Approval Status: {request.get('approval_status', 'N/A')}",
                    f"Submitted At: {request.get('submitted_at', 'N/A')}",
                    "",
                ]
            )

        if not choices:
            return (
                gr.update(
                    choices=[],
                    value=None,
                ),
                "No valid pending payment-plan requests were returned by the system.",
            )

        return (
            gr.update(
                choices=choices,
                value=choices[0][1],
            ),
            "\n".join(lines),
        )

    except Exception as error:
        print("PENDING REQUEST LOAD ERROR:")
        print(error)

        return (
            gr.update(
                choices=[],
                value=None,
            ),
            "Unable to retrieve pending payment-plan requests at this time. "
            "Please try again later.",
        )


# ============================================================
# ACTIVE PAYMENT PLAN LOOKUP
# ============================================================

def lookup_active_payment_plans(
    officer_id,
    national_id,
):
    """
    Retrieve ACTIVE payment plans using the customer's
    National ID.

    This is an officer-only workflow. The deterministic backend
    validates officer authorization, resolves the National ID
    to the internal customer record, and returns ACTIVE plans only.
    """

    officer_id = (officer_id or "").strip()
    national_id = (national_id or "").strip()

    if not officer_id:
        return "Please enter your Officer ID."

    if not national_id:
        return "Please enter the customer's National ID."

    try:

        officer_result = verify_officer(
            officer_id
        )

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

        plans = result.get(
            "payment_plans",
            [],
        )

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

        for index, plan in enumerate(
            plans,
            start=1,
        ):

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

def close_plan(
    officer_id,
    plan_id,
    closure_reason,
):
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

        officer_result = verify_officer(
            officer_id
        )

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
            f"Payment plan "
            f"{result.get('plan_id', plan_id)} "
            "was successfully closed.\n\n"
            f"Customer ID: "
            f"{result.get('customer_id', 'N/A')}\n"
            f"Loan ID: "
            f"{result.get('loan_id', 'N/A')}\n"
            f"Closed By: "
            f"{result.get('closed_by', officer_id)}\n"
            f"Closed At: "
            f"{result.get('closed_at', 'N/A')}\n"
            f"Closure Reason: "
            f"{result.get('closure_reason', closure_reason)}"
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

        ask_button = gr.Button(
            "Send"
        )

        clear_button = gr.Button(
            "Clear"
        )

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
        fn=lambda: (
            "",
            "",
            [],
        ),
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

        This section is restricted to authorized
        Recoveries Officers.

        Officers can:

        - Search active payment plans using National ID
        - Load pending payment-plan requests
        - Review pending payment-plan requests
        - Approve payment-plan requests
        - Reject payment-plan requests
        - Close active payment plans
        - Provide rejection and closure reasons

        The AI assistant does not approve, reject,
        or close payment plans.
        """
    )

    # ========================================================
    # OFFICER ID
    # ========================================================

    officer_id = gr.Textbox(
        label="Officer ID",
        placeholder="Example: OFF001",
    )

    # ========================================================
    # ACTIVE PAYMENT PLAN LOOKUP
    # ========================================================

    gr.Markdown(
        "### Active Payment Plan Lookup"
    )

    gr.Markdown(
        """
        Enter the customer's **National ID** to retrieve
        active payment plans.

        The system resolves the customer internally and
        displays active plans only.
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

    lookup_button = gr.Button(
        "Search Active Payment Plans"
    )

    lookup_button.click(
        fn=lookup_active_payment_plans,
        inputs=[
            officer_id,
            national_id,
        ],
        outputs=lookup_output,
    )

    # ========================================================
    # PENDING PAYMENT PLAN REQUESTS
    # ========================================================

    gr.Markdown(
        "### Pending Payment-Plan Requests"
    )

    gr.Markdown(
        """
        Load the requests that are currently **PENDING**
        and awaiting Recoveries Officer review.

        The list is retrieved directly from the
        deterministic backend.
        """
    )

    load_requests_button = gr.Button(
        "Load Pending Requests"
    )

    pending_request_id = gr.Dropdown(
        choices=[],
        label="Pending Payment-Plan Request",
        value=None,
        interactive=True,
    )

    pending_request_summary = gr.Textbox(
        label="Pending Request Summary",
        lines=14,
    )

    load_requests_button.click(
        fn=load_pending_requests,
        inputs=[
            officer_id,
        ],
        outputs=[
            pending_request_id,
            pending_request_summary,
        ],
    )

    # ========================================================
    # PAYMENT PLAN REQUEST REVIEW
    # ========================================================

    gr.Markdown(
        "### Payment Plan Request Review"
    )

    request_id = pending_request_id

    review_output = gr.Textbox(
        label="Request Details",
        lines=12,
    )

    review_button = gr.Button(
        "Review Selected Request"
    )

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

    gr.Markdown(
        "### Payment Plan Decision"
    )

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

    decision_button = gr.Button(
        "Submit Decision"
    )

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

    gr.Markdown(
        "---"
    )

    gr.Markdown(
        "### Active Payment Plan Closure"
    )

    gr.Markdown(
        """
        Use this section when an **ACTIVE payment plan**
        must be formally closed.

        A closure reason is mandatory.

        The closure is processed by the deterministic
        payment-plan backend and is restricted to an
        authorized Recoveries Officer.
        """
    )

    plan_id = gr.Textbox(
        label="Active Payment Plan ID",
        placeholder="Example: PLAN009",
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
        lines=8,
    )

    close_button = gr.Button(
        "Close Active Payment Plan"
    )

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

    with gr.Tab(
        "Customer Assistant"
    ):
        build_customer_interface()

    with gr.Tab(
        "Recoveries Officer"
    ):
        build_officer_interface()


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":

    app.launch(
        server_name="0.0.0.0",
        server_port=int(
            os.environ.get(
                "PORT",
                7860,
            )
        ),
    )