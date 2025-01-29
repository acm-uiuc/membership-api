from logging import Logger
import aiohttp
import asyncio
import os


def provision_membership_pkpass(email: str, logger: Logger):
    """Call Core API to email a new member that they're now a member."""
    core_api_url = os.environ.get("CoreApiUrl")
    if not core_api_url:
        raise ValueError("Could not find Core API base URL")

    async def _request():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{core_api_url}/api/v1/mobileWallet/membership?email={email}",
                headers={"Content-Type": "application/json"},
            ) as s:
                logger.info(
                    f"Core API membership pkpass/email ID: {s.headers['x-amzn-requestid']}"
                )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(_request())
