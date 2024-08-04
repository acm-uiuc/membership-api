from dataclasses import dataclass
import time
import aiohttp
import asyncio
import boto3
import os

dynamo = boto3.resource(
    "dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")
)
TOKEN_URL = "https://login.microsoftonline.com/c8d9148f-9a59-4db3-827d-42ea0c2b6e2e/oauth2/v2.0/token"
MEMBERS_URL = "https://graph.microsoft.com/v1.0/groups/172fd9ee-69f0-4384-9786-41ff1a43cf8e/members"
TABLE_NAME = "infra-membership-api-cache"
table = dynamo.Table(TABLE_NAME)


@dataclass
class Token:
    expires_in: int
    access_token: str


class GraphAPI:
    clientId: str
    clientSecret: str
    token: Token

    def __init__(self, client, secret):
        self.clientId = client
        self.clientSecret = secret
        self.token = Token(expires_in=-1, access_token="")

    async def createNewToken(self, force_new=False):
        try:
            if force_new:
                raise Exception("Forcing new access token.")
            response = table.get_item(Key={"key": "access_token"})
            parsed = response["Item"]["value"]
            self.token.access_token = parsed["access_token"]
            self.token.expires_in = response["Item"]["TimeToLive"] - int(time.time())
            print("Got AAD token from dynamo cache.")
        except:
            data: dict = {
                "grant_type": "client_credentials",
                "client_id": self.clientId,
                "scope": "https://graph.microsoft.com/.default",
                "client_secret": self.clientSecret,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(TOKEN_URL, data=data) as resp:
                    parsed = await resp.json()
                    self.token.access_token = parsed["access_token"]
                    self.token.expires_in = parsed["expires_in"]
            table.put_item(
                Item={
                    "key": "access_token",
                    "value": parsed,
                    "TimeToLive": int(time.time()) + parsed["expires_in"] - 10,
                }
            )
            print("Got AAD token from AAD itself.")

    async def isPaidMember(self, netID: str) -> bool:
        netID = netID.lower()
        await self.createNewToken()
        if self.token.expires_in <= 0:
            await self.createNewToken(force_new=True)
        headers = {
            "Authorization": f"Bearer {self.token.access_token}",
            "Content-Type": "application/json",
            "ConsistencyLevel": "eventual",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{MEMBERS_URL}?$filter=mail eq '{netID}@illinois.edu'&$count=true",
                headers=headers,
            ) as resp:
                parsed = await resp.json()
                if len(parsed["value"]) < 1:
                    return False
                return (
                    parsed["value"][0]["userPrincipalName"]
                    == f"{netID}_illinois.edu#EXT#@acmillinois.onmicrosoft.com"
                )


async def main():
    gapi = GraphAPI("CLIENT_ID", "CLIENT_SECRET")
    item = await gapi.isPaidMember("dsingh14")
    print(item)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
