import aiohttp
import json
from asyncio import run

API_BASE_URL = "https://calls.okcdn.ru"
API_APPLICATION_KEY = "1"


async def check_telega_user(telegram_id: int) -> bool:
    async with aiohttp.ClientSession() as session:
        auth_data = {
            "application_key": API_APPLICATION_KEY,
            "session_data": json.dumps({
                "device_id": "test",
                "version": 2,
                "client_version": "android_8",
                "client_type": "SDK_ANDROID",
            }),
        }

        async with session.post(
            f"{API_BASE_URL}/api/auth/anonymLogin",
            data=auth_data
        ) as resp:
            auth_response = await resp.json()
            session_key = auth_response.get("session_key")
            if not session_key:
                return False

        lookup_data = {
            "application_key": API_APPLICATION_KEY,
            "session_key": session_key,
            "externalIds": json.dumps([
                {"id": str(telegram_id), "ok_anonym": False}
            ]),
        }

        async with session.post(
            f"{API_BASE_URL}/api/vchat/getOkIdsByExternalIds",
            data=lookup_data
        ) as resp:
            result = await resp.json()
            ids = result.get("ids", [])
            return any(
                item.get("external_user_id", {}).get("id") == str(telegram_id)
                for item in ids
            )


async def main():
    test_telegram_id = 1
    print(await check_telega_user(test_telegram_id))


if __name__ == "__main__":
    run(main())
