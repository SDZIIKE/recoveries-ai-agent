import asyncio
from agent_modules.recovery_agent import extract_payment_plan_proposal

async def main():
    result = await extract_payment_plan_proposal.on_invoke_tool(
        None,
        {
            "customer_message": (
                "My National ID is 00-000001A00 and my date of birth is "
                "1990-01-15. I would like to request a new payment plan "
                "of $800 per month for 6 months, starting October 15, 2026."
            )
        }
    )
    print(result)

asyncio.run(main())
