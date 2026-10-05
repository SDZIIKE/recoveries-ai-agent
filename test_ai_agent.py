import asyncio

from agents import Runner
from agent_modules.recovery_agent import recovery_agent


async def main():
    print("==========================================")
    print("RECOVERIES AI AGENT MULTI-TURN TEST")
    print("==========================================")

    # ---------------------------------------------------------
    # TURN 1: Customer provides identity and asks for
    # payment-plan request status
    # ---------------------------------------------------------
    message_1 = (
        "My National ID is 00-000001A00 and my date of birth is "
        "1990-01-15. What is the status of my payment plan request?"
    )

    print("\nCUSTOMER - TURN 1:")
    print(message_1)

    result_1 = await Runner.run(
        recovery_agent,
        message_1
    )

    response_1 = result_1.final_output

    print("\nAI RESPONSE - TURN 1:")
    print("------------------------------------------")
    print(response_1)

    # ---------------------------------------------------------
    # TURN 1 ASSERTIONS
    # ---------------------------------------------------------
    response_1_lower = response_1.lower()

    assert "approved" in response_1_lower, (
        "FAIL: Agent did not identify the payment-plan request "
        "as approved."
    )

    assert "600" in response_1, (
        "FAIL: Expected approved payment amount was not returned."
    )

    assert "monthly" in response_1_lower, (
        "FAIL: Expected payment frequency was not returned."
    )

    # Internal identifiers must not be exposed to the customer.
    assert "cust001" not in response_1_lower, (
        "FAIL: Internal customer ID was exposed."
    )

    assert "req-" not in response_1_lower, (
        "FAIL: Internal request ID was exposed."
    )

    # ---------------------------------------------------------
    # TURN 2: Customer gives consent
    # ---------------------------------------------------------
    message_2 = "Yes, I consent to the payment plan."

    print("\nCUSTOMER - TURN 2:")
    print(message_2)

    conversation = result_1.to_input_list()

    conversation.append(
        {
            "role": "user",
            "content": message_2,
        }
    )

    result_2 = await Runner.run(
        recovery_agent,
        conversation
    )

    response_2 = result_2.final_output

    print("\nAI RESPONSE - TURN 2:")
    print("------------------------------------------")
    print(response_2)

    # ---------------------------------------------------------
    # TURN 2 ASSERTIONS
    # ---------------------------------------------------------
    response_2_lower = response_2.lower()

    assert (
        "already" in response_2_lower
        and (
            "approved" in response_2_lower
            or "in place" in response_2_lower
            or "no need" in response_2_lower
        )
    ), (
        "FAIL: Agent did not correctly recognize that the "
        "payment plan was already approved."
    )

    # ---------------------------------------------------------
    # TEST COMPLETE
    # ---------------------------------------------------------
    print("\n==========================================")
    print("ALL AI AGENT TESTS PASSED")
    print("==========================================")


if __name__ == "__main__":
    asyncio.run(main())