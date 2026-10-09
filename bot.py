import io, re, zipfile, threading, json, os, time, logging, aiohttp, asyncio, random, string
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ChatMemberHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("LeakDetector")

# ==================== CONFIG ====================
BOT_TOKEN = os.getenv("TELEBOT_TOKEN", "8790444916:AAGY-hShJbwabbzo1GQhL66iEKP8HYXQ6Dk")
DEVELOPER_NAME = "@skyler"
RAW_ADMIN = os.getenv("ADMIN_IDS", "1134471909")
ADMIN_IDS = [int(x.strip()) for x in RAW_ADMIN.split(",") if x.strip().isdigit()]
RESTRICTED_IDS = []
IST = ZoneInfo("Asia/Kolkata")

DEFAULT_APIS = {
    "phone": "API",
    "hi_tek": "API",
    "pan": "API",
    "vehicle": "API",
    "vehicle2": "API",
    "upi": "API",
    "pak": "API",
    "ip": "API",
    "family": "API",
    "tg": "API",
    "aadhar": "API",
    "instagram": "API",
    "gst": "API",
    "pan_to_gst": "API",
    "ifsc": "API",
    "tower": "API",
    "rc_pdf": "API",
}

DEFAULT_PREFIX_MODES = {
    "phone": "with_91", "hi_tek": "without_91", "tower": "with_91",
    "pak": "as_is", "aadhar": "as_is", "tg": "as_is", "family": "as_is",
}

DATA_FILE="user_data.json"; BLOCK_FILE="blocked_users.json"; PENDING_FILE="pending_users.json"
APPROVED_FILE="approved_users.json"; QUERY_LOG_FILE="query_log.json"; CUSTOM_BUTTONS_FILE="custom_buttons.json"
FORCE_JOIN_FILE="force_join.json"; DM_PERMISSION_FILE="dm_permission.json"; DM_MODE_FILE="dm_mode.json"
ALL_USERS_FILE="all_users.json"; EXTRA_ADMIN_FILE="extra_admins.json"; HIDDEN_FIELDS_FILE="hidden_fields.json"
PER_BUTTON_FILE="per_button_settings.json"; STATS_FILE="button_stats.json"; BAN_REASON_FILE="ban_reasons.json"
USER_NOTES_FILE="user_notes.json"; MAINTENANCE_FILE="maintenance.json"; WELCOME_FILE="welcome.json"
FLOOD_FILE="flood_control.json"; API_OVERRIDES_FILE="api_overrides.json"; API_BACKUP_FILE="api_backup.json"
ADMIN_PERMS_FILE="admin_permissions.json"; GROUP_TRACK_FILE="group_tracking.json"; GLOBAL_MODE_FILE="global_mode.json"
BOMB_APIS_FILE="bomb_apis.json"; HIDDEN_BUTTONS_FILE="hidden_buttons.json"; LINK_BUTTONS_FILE="link_buttons.json"
PAYMENT_FILE="payment_methods.json"; APPROVALS_FILE="approvals.json"; PAYMENT_VERIFY_FILE="payment_verify.json"
PREMIUM_PENDING_FILE="premium_pending.json"; CONFIG_FILE="bot_config.json"; PREFIX_MODES_FILE="prefix_modes.json"
REFERRAL_FILE="referrals.json"; REDEEM_FILE="redeem_codes.json"

RC_CACHE = {}; RC_CACHE_LOCK = threading.Lock(); RC_CACHE_MAX_AGE = 3600
def cleanup_rc_cache():
    now = time.time()
    with RC_CACHE_LOCK:
        for k in [k for k, v in RC_CACHE.items() if now - v.get("created", 0) > RC_CACHE_MAX_AGE]: RC_CACHE.pop(k, None)
try:
    from PIL import Image as PILImage; HAS_PIL = True
except ImportError: HAS_PIL = False

_MENU_CACHE = {}; _MENU_CACHE_TIME = 0; _MENU_CACHE_TTL = 5
def invalidate_menu_cache():
    global _MENU_CACHE_TIME; _MENU_CACHE_TIME = 0
def get_cached_menu():
    global _MENU_CACHE, _MENU_CACHE_TIME
    now = time.time()
    if now - _MENU_CACHE_TIME > _MENU_CACHE_TTL or not _MENU_CACHE:
        _MENU_CACHE = get_bot_management_menu(); _MENU_CACHE_TIME = now
    return _MENU_CACHE

# ==================== FILE CACHE ====================
_file_cache = {}; _cache_lock = threading.Lock()
def load_json(fp, default):
    with _cache_lock:
        if fp in _file_cache: return _file_cache[fp]
    if os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f: data = json.load(f)
            with _cache_lock: _file_cache[fp] = data
            return data
        except Exception as e: logger.warning(f"load_json {fp}: {e}"); return default
    return default
def save_json(fp, data):
    with _cache_lock: _file_cache[fp] = data
    try:
        tmp = fp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, fp)
    except Exception as e: logger.error(f"save_json {fp}: {e}")

def load_data(): return load_json(DATA_FILE, {})
def save_data(d): save_json(DATA_FILE, d)
def load_blocked(): return set(load_json(BLOCK_FILE, []))
def save_blocked(d): save_json(BLOCK_FILE, list(d))
def load_pending(): return set(load_json(PENDING_FILE, []))
def save_pending(d): save_json(PENDING_FILE, list(d))
def load_approved(): return set(load_json(APPROVED_FILE, []))
def save_approved(d): save_json(APPROVED_FILE, list(d))
def load_query_log(): return load_json(QUERY_LOG_FILE, [])
def save_query_log(d): save_json(QUERY_LOG_FILE, d)
def load_custom_buttons(): return load_json(CUSTOM_BUTTONS_FILE, {})
def save_custom_buttons(d): save_json(CUSTOM_BUTTONS_FILE, d)
def load_force_joins(): return load_json(FORCE_JOIN_FILE, [])
def save_force_joins(d): save_json(FORCE_JOIN_FILE, d)
def load_dm_perm(): return set(load_json(DM_PERMISSION_FILE, []))
def save_dm_perm(d): save_json(DM_PERMISSION_FILE, list(d))
def load_dm_mode(): return load_json(DM_MODE_FILE, {"enabled": True})
def save_dm_mode(d): save_json(DM_MODE_FILE, d)
def load_all_users(): return load_json(ALL_USERS_FILE, {})
def save_all_users(d): save_json(ALL_USERS_FILE, d)
def load_extra_admins(): return set(load_json(EXTRA_ADMIN_FILE, []))
def save_extra_admins(d): save_json(EXTRA_ADMIN_FILE, list(d))
def load_stats(): return load_json(STATS_FILE, {})
def save_stats(d): save_json(STATS_FILE, d)
def load_ban_reason(): return load_json(BAN_REASON_FILE, {})
def save_ban_reason(d): save_json(BAN_REASON_FILE, d)
def load_user_notes(): return load_json(USER_NOTES_FILE, {})
def save_user_notes(d): save_json(USER_NOTES_FILE, d)
def load_maintenance(): return load_json(MAINTENANCE_FILE, {"enabled": False, "message": "🛠️ Bot is under maintenance."})
def save_maintenance(d): save_json(MAINTENANCE_FILE, d)
def load_welcome(): return load_json(WELCOME_FILE, {"message": "", "enabled": False})
def save_welcome(d): save_json(WELCOME_FILE, d)
def load_flood(): return load_json(FLOOD_FILE, {})
def save_flood(d): save_json(FLOOD_FILE, d)
def load_api_overrides(): return load_json(API_OVERRIDES_FILE, {})
def save_api_overrides(d): save_json(API_OVERRIDES_FILE, d)
def load_api_backup(): return load_json(API_BACKUP_FILE, {})
def save_api_backup(d): save_json(API_BACKUP_FILE, d)
def load_admin_perms(): return load_json(ADMIN_PERMS_FILE, {})
def save_admin_perms(d): save_json(ADMIN_PERMS_FILE, d)
def load_group_track(): return load_json(GROUP_TRACK_FILE, {})
def save_group_track(d): save_json(GROUP_TRACK_FILE, d)
def load_global_mode(): return load_json(GLOBAL_MODE_FILE, {"everyone_approved": False})
def save_global_mode(d): save_json(GLOBAL_MODE_FILE, d)
def load_custom_bomb_apis(): return load_json(BOMB_APIS_FILE, [])
def save_custom_bomb_apis(d): save_json(BOMB_APIS_FILE, d)
def load_hidden_buttons(): return set(load_json(HIDDEN_BUTTONS_FILE, []))
def save_hidden_buttons(d): save_json(HIDDEN_BUTTONS_FILE, list(d))
def load_link_buttons(): return load_json(LINK_BUTTONS_FILE, {})
def save_link_buttons(d): save_json(LINK_BUTTONS_FILE, d)
def load_payment():
    return load_json(PAYMENT_FILE, {"enabled": False, "text": "💰 Complete payment below and send screenshot to owner:", "methods": [], "qr_image_file_id": None, "premium_plans": [], "global_credit_grant": 0, "global_credit_set_at": None})
def save_payment(d): save_json(PAYMENT_FILE, d)
def load_approvals(): return load_json(APPROVALS_FILE, {})
def save_approvals(d): save_json(APPROVALS_FILE, d)
def load_payment_verify():
    return load_json(PAYMENT_VERIFY_FILE, {"auto_verify_enabled": True, "default_duration_days": 30, "notify_admin_on_payment": True, "auto_verify_mode": "manual"})
def save_payment_verify(d): save_json(PAYMENT_VERIFY_FILE, d)
def load_premium_pending(): return load_json(PREMIUM_PENDING_FILE, {})
def save_premium_pending(d): save_json(PREMIUM_PENDING_FILE, d)
def load_referrals(): return load_json(REFERRAL_FILE, {})
def save_referrals(d): save_json(REFERRAL_FILE, d)
def load_redeem_codes(): return load_json(REDEEM_FILE, {})
def save_redeem_codes(d): save_json(REDEEM_FILE, d)

def load_config():
    cfg = load_json(CONFIG_FILE, {})
    defaults = {
        "owner_username": "DarkWorld233",
        "owner_display": "𝔻𝕒̼𝕣̼𝕜̼ℙ̼𝕝̼𝕦̼𝕤̼𝕖̼𝟜̼𝟜̼𝟜̼☠",
        "owner2_username": "Hittadmin",
        "owner2_display": "█▬█ █ ▀█▀-ADMIN",
        "owner2_id": 8761086213,
        "default_credits": 5,
        "referral_credits": 3,
        "powered_by": "✨ *Powered by {owner}*",
        "powered_by_enabled": True,
    }
    for k, v in defaults.items():
        if k not in cfg: cfg[k] = v
    return cfg
def save_config(d): save_json(CONFIG_FILE, d)
def load_prefix_modes():
    d = load_json(PREFIX_MODES_FILE, None)
    if d is None: save_json(PREFIX_MODES_FILE, DEFAULT_PREFIX_MODES); return dict(DEFAULT_PREFIX_MODES)
    merged = dict(DEFAULT_PREFIX_MODES); merged.update(d); return merged
def save_prefix_modes(d): save_json(PREFIX_MODES_FILE, d)

def get_owner_username(): return load_config().get("owner_username", "DarkWorld233")
def get_owner_display(): return load_config().get("owner_display", "𝔻𝕒̼𝕣̼𝕜̼ℙ̼𝕝̼𝕦̼𝕤̼𝕖̼𝟜̼𝟜̼𝟜̼☠")
def get_owner2_username(): return load_config().get("owner2_username", "Hittadmin")
def get_owner2_display(): return load_config().get("owner2_display", "█▬█ █ ▀█▀-ADMIN")
def get_default_credits(): return int(load_config().get("default_credits", 5))
def get_referral_credits(): return int(load_config().get("referral_credits", 3))

def powered_by_text(prefix="\n\n"):
    cfg = load_config()
    if not cfg.get("powered_by_enabled", True):
        return ""
    txt = cfg.get("powered_by", "✨ *Powered by {owner}*")
    txt = txt.replace("{owner}", get_owner_username()).replace("{display}", get_owner_display())
    if not txt.strip(): return ""
    return prefix + txt

def generate_redeem_code(length=10):
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
        existing = load_redeem_codes()
        if code not in existing:
            return code

def add_premium_pending(uid, username=None, full_name=None):
    pp = load_premium_pending(); uid_str = str(uid)
    if uid_str in pp:
        pp[uid_str]["username"] = username or pp[uid_str].get("username", "N/A")
        pp[uid_str]["full_name"] = full_name or pp[uid_str].get("full_name", "Unknown")
    else:
        pp[uid_str] = {"user_id": uid, "username": username or "N/A", "full_name": full_name or "Unknown", "requested_at": now_ist().isoformat(), "status": "pending"}
    save_premium_pending(pp)

def remove_premium_pending(uid):
    pp = load_premium_pending()
    if str(uid) in pp: pp.pop(str(uid)); save_premium_pending(pp)

# ==================== GLOBAL CREDIT ====================
def set_global_credit_grant(amount):
    pay = load_payment(); pay["global_credit_grant"] = amount; pay["global_credit_set_at"] = now_ist().isoformat(); save_payment(pay)
def get_global_credit_grant(): return load_payment().get("global_credit_grant", 0)
def apply_global_credit_to_new_user(user_id):
    uid = str(user_id); data = load_data(); grant = get_global_credit_grant()
    if grant <= 0: return 0
    if data.get(uid, {}).get("global_credit_applied"): return 0
    if uid not in data: data[uid] = {"name": "Unknown", "bomb_credits": 0, "username": None}
    data[uid]["bomb_credits"] = data[uid].get("bomb_credits", 0) + grant
    data[uid]["global_credit_applied"] = True
    save_data(data); return grant

PERMISSION_LEVELS = {"full": "👑 Full Access", "manager": "🔧 Manager", "readonly": "👁️ Read-Only", "credits": "🎫 Credits Only"}

def now_ist(): return datetime.now(IST)
def to_ist_str(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(IST).strftime("%d-%m-%Y %I:%M:%S %p IST")
    except: return str(iso_str)

# ==================== APPROVAL ====================
def set_approval(user_id, days=30):
    a = load_approvals(); uid = str(user_id)
    if days <= 0: a[uid] = {"approved": True, "expires": None, "duration_days": 0, "approved_at": now_ist().isoformat()}
    else: a[uid] = {"approved": True, "expires": (now_ist() + timedelta(days=days)).isoformat(), "duration_days": days, "approved_at": now_ist().isoformat()}
    save_approvals(a)
    ap = load_approved(); ap.add(int(user_id)); save_approved(ap)
    p = load_pending(); p.discard(int(user_id)); save_pending(p)
    remove_premium_pending(user_id)

def is_user_approved(user_id):
    uid = str(user_id); a = load_approvals()
    if uid in a:
        info = a[uid]
        if not info.get("approved"): return False
        exp = info.get("expires")
        if exp:
            try:
                if now_ist() >= datetime.fromisoformat(exp):
                    info["approved"] = False; save_approvals(a)
                    ap = load_approved(); ap.discard(int(user_id)); save_approved(ap)
                    return False
            except: pass
        return True
    return int(user_id) in load_approved()

def remove_approval(user_id):
    a = load_approvals(); a.pop(str(user_id), None); save_approvals(a)
    ap = load_approved(); ap.discard(int(user_id)); save_approved(ap)

def cleanup_expired_approvals():
    a = load_approvals(); ap = load_approved(); removed = 0
    for uid, info in list(a.items()):
        exp = info.get("expires")
        if exp:
            try:
                if now_ist() >= datetime.fromisoformat(exp): a.pop(uid, None); ap.discard(int(uid)); removed += 1
            except: pass
    if removed: save_approvals(a); save_approved(ap)
    return removed

def add_credits_all(amount):
    users = load_all_users(); data = load_data(); count = 0
    for uid_str in users.keys():
        if uid_str not in data: data[uid_str] = {"name": "Unknown", "bomb_credits": 0, "username": None}
        data[uid_str]["bomb_credits"] = data[uid_str].get("bomb_credits", 0) + amount
        data[uid_str]["global_credit_applied"] = True; count += 1
    save_data(data); set_global_credit_grant(amount); return count

# ==================== PHONE NORMALIZER ====================
def normalize_phone(raw, mode="with_91"):
    c = re.sub(r'[^0-9]', '', str(raw).strip())
    if not c: return None
    c = c.lstrip("0") or c
    if len(c) == 12 and c.startswith("91"): c10 = c[2:]
    elif len(c) == 11 and c.startswith("91"): c10 = c[2:]
    elif len(c) == 10: c10 = c
    elif len(c) > 10: c10 = c[-10:]
    else: c10 = c
    if mode == "with_91":
        return "91" + c10 if len(c10) == 10 else c10
    elif mode == "without_91":
        return c10
    return c10

# ==================== HTTP ====================
_aio_session = None
async def get_aio_session():
    global _aio_session
    if _aio_session is None or _aio_session.closed:
        connector = aiohttp.TCPConnector(limit=300, limit_per_host=60, ttl_dns_cache=300, enable_cleanup_closed=True, force_close=False)
        _aio_session = aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15, connect=8), headers={"User-Agent": "Mozilla/5.0 (Linux; Android 10)"})
    return _aio_session
async def close_aio_session():
    global _aio_session
    if _aio_session and not _aio_session.closed: await _aio_session.close()

class FetchResponse:
    __slots__ = ("status_code", "text")
    def __init__(self, sc, t): self.status_code = sc; self.text = t
    def json(self): return json.loads(self.text)

async def async_fetch(url, headers=None, timeout=15):
    session = await get_aio_session()
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            return FetchResponse(r.status, await r.text())
    except Exception as e: logger.debug(f"fetch: {e}"); return FetchResponse(0, "")

def _has_real_data(d):
    if not isinstance(d, dict) or not d: return False
    meta_keys = {'status','success','message','error','req_left','req_total','credit','credits','developer','note','notes','api','apikey','cached','cache'}
    for k, v in d.items():
        if k.lower() in meta_keys: continue
        if v in (None, '', [], {}): continue
        if isinstance(v, str) and len(v.strip()) < 2: continue
        return True
    return False

# ==================== TRACKING ====================
def track_group(chat):
    if chat.type not in ["group", "supergroup", "channel"]: return
    groups = load_group_track(); cid = str(chat.id)
    if cid not in groups:
        groups[cid] = {"title": chat.title or "Unknown", "type": chat.type, "added_at": now_ist().isoformat(), "searches": 0, "last_active": now_ist().isoformat()}
    else: groups[cid]["title"] = chat.title or groups[cid].get("title", "Unknown"); groups[cid]["last_active"] = now_ist().isoformat()
    save_group_track(groups)

def track_group_search(chat_id):
    groups = load_group_track(); cid = str(chat_id)
    if cid in groups:
        groups[cid]["searches"] = groups[cid].get("searches", 0) + 1; groups[cid]["last_active"] = now_ist().isoformat(); save_group_track(groups)

def get_api_url(button_key):
    ov = load_api_overrides()
    if button_key in ov: return ov[button_key]
    cb = load_custom_buttons()
    if button_key.startswith("custom_"):
        bn = button_key[7:]
        if bn in cb: return cb[bn].get("api", "")
    return DEFAULT_APIS.get(button_key, "")

def set_api_override(bk_key, new_url):
    ov = load_api_overrides(); bk = load_api_backup()
    if bk_key not in ov:
        if bk_key in DEFAULT_APIS: bk[bk_key] = DEFAULT_APIS[bk_key]
        save_api_backup(bk)
    ov[bk_key] = new_url; save_api_overrides(ov)

def undo_api_override(bk_key):
    ov = load_api_overrides(); bk = load_api_backup()
    if bk_key in ov: ov.pop(bk_key); save_api_overrides(ov)
    if bk_key in bk: bk.pop(bk_key); save_api_backup(bk); return True
    return False

def track_button_use(button_key):
    s = load_stats(); s[button_key] = s.get(button_key, 0) + 1; save_stats(s)

def check_flood(uid, query):
    if is_admin(uid): return False
    flood = load_flood(); uid_str = str(uid); now = now_ist()
    ud = flood.get(uid_str, {"queries": [], "blocked_until": None})
    if ud.get("blocked_until"):
        try:
            if now < datetime.fromisoformat(ud["blocked_until"]): return True
        except: pass
    queries = [q for q in ud.get("queries", []) if (now - datetime.fromisoformat(q["time"])).total_seconds() < 60]
    if sum(1 for q in queries if q["query"] == query) >= 3:
        ud["blocked_until"] = (now + timedelta(seconds=60)).isoformat(); ud["queries"] = queries; flood[uid_str] = ud; save_flood(flood); return True
    queries.append({"query": query, "time": now.isoformat()})
    ud["queries"] = queries; ud.pop("blocked_until", None); flood[uid_str] = ud; save_flood(flood); return False

# ==================== HIDDEN FIELDS ====================
DEFAULT_HIDDEN = ["req_left","req_total","expiry","cached","cache","credit","credits","note","notes","support","description","desc","title","website","site","status","buy apis","buy_apis","buy","developer","Developer","DEVELOPER","owner","Owner","OWNER","author","Author","AUTHOR","developer name","powered by","Powered By","Powered by","apikey","api_key","API Key","API_KEY","viraj","Viraj","viraj_prajapati","Viraj_Prajapati","abhigyan","Abhigyan","dark-info.site","hittadmin","hittadmin","success_count","fail_count","error_count","inputed number","Inputed Number"]
_DEFAULT_HIDDEN_SET = set(DEFAULT_HIDDEN)

def load_hidden_fields():
    data = load_json(HIDDEN_FIELDS_FILE, None)
    if data is None: save_json(HIDDEN_FIELDS_FILE, DEFAULT_HIDDEN); return set(DEFAULT_HIDDEN)
    return set(data) | _DEFAULT_HIDDEN_SET
def save_hidden_fields(d): save_json(HIDDEN_FIELDS_FILE, list(d))

def load_per_button():
    d = load_json(PER_BUTTON_FILE, None) or {}
    for k in ["hidden","add_words","protected","set_words","specific_set_words","group_only","json_add","prompts"]: d.setdefault(k, {})
    return d
def save_per_button(d): save_json(PER_BUTTON_FILE, d)

def get_button_hidden_fields(b): return load_per_button().get("hidden", {}).get(b, [])
def set_button_hidden_field(b, f):
    d = load_per_button(); d.setdefault("hidden", {}).setdefault(b, [])
    if f not in d["hidden"][b]: d["hidden"][b].append(f)
    save_per_button(d)
def get_button_add_word(b): return load_per_button().get("add_words", {}).get(b, "")
def set_add_word(b, t): d = load_per_button(); d.setdefault("add_words", {})[b] = t; save_per_button(d)
def remove_add_word(b):
    d = load_per_button()
    if b in d.get("add_words", {}): d["add_words"].pop(b); save_per_button(d); return True
    return False
def get_button_protected(b): return load_per_button().get("protected", {}).get(b, [])
def protect_value(b, v):
    d = load_per_button(); d.setdefault("protected", {}).setdefault(b, [])
    vu = v.strip().upper()
    if vu not in d["protected"][b]: d["protected"][b].append(vu)
    save_per_button(d)
def unprotect_value(b, v):
    d = load_per_button(); vu = v.strip().upper()
    if b in d.get("protected", {}) and vu in d["protected"][b]:
        d["protected"][b].remove(vu); save_per_button(d); return True
    return False
def get_button_set_word(b): return load_per_button().get("set_words", {}).get(b, "")
def set_set_word(b, t): d = load_per_button(); d.setdefault("set_words", {})[b] = t; save_per_button(d)
def remove_set_word(b):
    d = load_per_button()
    if b in d.get("set_words", {}): d["set_words"].pop(b); save_per_button(d); return True
    return False
def remove_all_set_words(): d = load_per_button(); d["set_words"] = {}; save_per_button(d)
def get_specific_set_word(b, v):
    d = load_per_button(); return d.get("specific_set_words", {}).get(b, {}).get(v.strip().upper(), "")
def add_specific_set_word(b, v, m):
    d = load_per_button(); d.setdefault("specific_set_words", {}).setdefault(b, {})
    d["specific_set_words"][b][v.strip().upper()] = m; save_per_button(d)
def remove_specific_set_word(b, v):
    d = load_per_button(); vu = v.strip().upper()
    if b in d.get("specific_set_words", {}) and vu in d["specific_set_words"][b]:
        d["specific_set_words"][b].pop(vu); save_per_button(d); return True
    return False
def remove_all_specific_set_words(b=None):
    d = load_per_button()
    if b: d.setdefault("specific_set_words", {})[b] = {}
    else: d["specific_set_words"] = {}
    save_per_button(d)
def is_group_only(b): return load_per_button().get("group_only", {}).get(b, False)
def set_group_only(b, v): d = load_per_button(); d.setdefault("group_only", {})[b] = v; save_per_button(d)
def get_json_add(b):
    d = load_per_button(); base = dict(d.get("json_add", {}).get("__global__", {})); base.update(d.get("json_add", {}).get(b, {})); return base
def set_json_add(b, k, v):
    d = load_per_button(); d.setdefault("json_add", {}).setdefault(b, {}); d["json_add"][b][k] = v; save_per_button(d)
def remove_json_add(b, k):
    d = load_per_button()
    if b in d.get("json_add", {}) and k in d["json_add"][b]: d["json_add"][b].pop(k); save_per_button(d); return True
    return False

DEFAULT_PROMPTS = {
    "phone": "📱 **PHONE INTELLIGENCE MODULE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** Mobile number\n📝 **Examples:** `9826XXXXXX` or `919826XXXXXX`\n⚙️ `91` prefix auto-handled\n✍️ *Send now...*",
    "hi_tek": "📱 **HI TEK INTELLIGENCE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** 10-digit mobile number\n📝 **Example:** `9826XXXXXX`\n⚙️ Only 10 digits (no 91)\n✍️ *Send now...*",
    "aadhar": "🆔 **AADHAR MODULE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** 12-digit Aadhar\n📝 **Example:** `123456789012`",
    "pan": "💳 **PAN CARD MODULE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** 10-char PAN\n📝 **Example:** `ABCDE1234F`",
    "vehicle": "🚗 **VEHICLE RC MODULE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** RC number\n📝 **Example:** `HR26BT2009`",
    "vehicle2": "🚗 **VEHICLE2 (VAHANX)**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** RC number\n📝 **Example:** `HR26BT2009`",
    "upi": "💳 **UPI MODULE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** VPA\n📝 **Example:** `user@upi`",
    "tg": "🕵️ **TELEGRAM OSINT**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** Numeric ID or Username\n📝 **Examples:** `5227406810` or `@username`",
    "ip": "🌍 **IP GEOLOCATION**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** IP or domain\n📝 **Example:** `8.8.8.8`",
    "pak": "🇵🇰 **PAKISTAN NUMBER**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** Pak number\n📝 **Example:** `03359736848`",
    "family": "👨‍👩‍👧 **FAMILY MODULE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** Numeric Family ID\n📝 **Example:** `657559107999`",
    "instagram": "📸 **INSTAGRAM MODULE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** Username (no @)\n📝 **Example:** `katrinakaif`",
    "gst": "🏢 **GST MODULE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** GSTIN\n📝 **Example:** `09AAYFK4129N1ZF`",
    "pan_to_gst": "📄 **PAN → GST**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** 10-char PAN\n📝 **Example:** `AAYFK4129N`",
    "ifsc": "🏦 **IFSC MODULE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** 11-char IFSC\n📝 **Example:** `SBIN0001234`",
    "tower": "📡 **CALL TOWER MODULE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** Mobile number\n📝 **Examples:** `9826XXXXXX` or `919826XXXXXX`\n⚙️ `91` prefix auto-handled\n✍️ *Send now...*",
    "rc_pdf": "📄 **RC TO PDF / IMAGE**\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 **Input:** RC number (no spaces)\n📝 **Example:** `MH12DE1433`\n📥 PDF/Image via secure download buttons\n✍️ *Send now...*",
}
def get_button_prompt(b): return load_per_button().get("prompts", {}).get(b, DEFAULT_PROMPTS.get(b, "📝 Send the required input:"))
def set_button_prompt(b, p): d = load_per_button(); d.setdefault("prompts", {})[b] = p; save_per_button(d)

def is_admin(user_id): return user_id in ADMIN_IDS or user_id in load_extra_admins()
def build_api_url(t, inp):
    if "{input}" in t: return t.replace("{input}", inp)
    tr = t.rstrip()
    if tr.endswith(('=', '&', '?/')): return tr + inp
    if re.search(r'[?&][^=&]+=$', tr): return tr + inp
    return t

def track_user(user):
    users = load_all_users(); uid = str(user.id); is_new = uid not in users
    users[uid] = {"name": user.first_name or "", "last_name": user.last_name or "", "username": user.username or "N/A", "full_name": user.full_name, "chat_id": user.id, "first_seen": users.get(uid, {}).get("first_seen", now_ist().isoformat()), "last_seen": now_ist().isoformat()}
    save_all_users(users)
    if is_new: apply_global_credit_to_new_user(user.id)

def get_user_data(user_id, name=None):
    data = load_data(); uid = str(user_id)
    if uid not in data:
        default_credits = get_default_credits()
        data[uid] = {"name": name or "Unknown", "bomb_credits": default_credits, "username": None, "signup_credits_given": True, "signup_at": now_ist().isoformat()}
        save_data(data)
    elif name and data[uid].get("name") != name:
        data[uid]["name"] = name; save_data(data)
    if "bomb_credits" not in data[uid]:
        data[uid]["bomb_credits"] = 0; save_data(data)
    return data[uid]

def add_credits(user_id, amount):
    data = load_data(); uid = str(user_id)
    if uid not in data: data[uid] = {"name": "Unknown", "bomb_credits": 0, "username": None}
    data[uid]["bomb_credits"] = data[uid].get("bomb_credits", 0) + amount; save_data(data)
    a = load_approved(); a.add(int(user_id)); save_approved(a)
    p = load_pending(); p.discard(int(user_id)); save_pending(p)

def remove_credits(user_id, amount=None):
    data = load_data(); uid = str(user_id)
    if uid in data:
        if amount is None: data[uid]["bomb_credits"] = 0
        else: data[uid]["bomb_credits"] = max(0, data[uid].get("bomb_credits", 0) - amount)
        save_data(data)

def get_credits(user_id): return load_data().get(str(user_id), {}).get("bomb_credits", 0)

def log_query(user_id, name, query_type, query_input):
    log = load_query_log()
    log.append({"timestamp": now_ist().isoformat(), "user_id": user_id, "name": name or "Unknown", "type": query_type, "query": query_input})
    save_query_log(log)

# ==================== BOMB PARSER ====================
def parse_bomb_api_line(line):
    line = line.strip()
    if not line or line.startswith("#"): return None
    um = re.search(r'(https?://[^\s|,\t;]+)', line)
    if not um: return None
    url = um.group(1).rstrip(",;|")
    before = line[:um.start()].strip(" |,;-\t:")
    name = before if before else re.search(r'https?://([^/]+)', url).group(1)[:40]
    after = line[um.end():].strip(" |,;-\t:")
    method = "POST"; headers = {}; data = None
    if after:
        for p in [p.strip() for p in re.split(r'[|,\t]', after) if p.strip()]:
            pu = p.upper()
            if pu in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"): method = pu
            elif p.startswith("{") or p.startswith("["):
                try:
                    parsed = json.loads(p)
                    if isinstance(parsed, dict):
                        if "{phone}" in p or "phone" in str(parsed).lower():
                            if data is None: data = p
                        elif not headers: headers = parsed
                        else: data = p
                except Exception:
                    if "{phone}" in p and data is None: data = p
    if data is None: data = '{"phone":"{phone}"}'
    return {"name": name.strip()[:60] or "Custom API", "url": url.strip(), "method": method, "headers": headers if headers else {}, "data": data}

def add_bomb_apis_from_text(text):
    existing = load_custom_bomb_apis(); names = {a["name"] for a in existing}; urls = {a["url"] for a in existing}
    added = 0; skipped = 0; invalid = 0; new_apis = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        p = parse_bomb_api_line(line)
        if not p: invalid += 1; continue
        if p["name"] in names or p["url"] in urls: skipped += 1; continue
        existing.append(p); new_apis.append(p); names.add(p["name"]); urls.add(p["url"]); added += 1
    save_custom_bomb_apis(existing)
    return {"added": added, "skipped": skipped, "invalid": invalid, "list": new_apis}

def get_all_bomb_apis():
    apis = list(BOMB_APIS)
    for c in load_custom_bomb_apis():
        def _mk(ds):
            def _f(phone):
                if ds is None: return None
                return ds.replace("{phone}", phone) if isinstance(ds, str) else ds
            return _f
        apis.append({"name": c.get("name", "Custom"), "url": c["url"], "method": c.get("method", "POST"), "headers": c.get("headers", {}), "data": _mk(c.get("data"))})
    return apis

# ==================== REPLY ====================
async def reply_message(update, context, text, reply_markup=None, parse_mode="Markdown", include_user_tag=True):
    if include_user_tag:
        user = update.effective_user
        formatted_text = f"🔍 **LEAK DETECTOR** 🔍\n👤 **Operator:** [{user.first_name}](tg://user?id={user.id})\n━━━━━━━━━━━━━━━━━━━━━━\n\n{text}"
    else: formatted_text = text
    return await update.message.reply_text(formatted_text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)

async def send_simple(update, text, parse_mode="Markdown"):
    return await update.message.reply_text(text, parse_mode=parse_mode, disable_web_page_preview=True)

async def check_force_join(user_id, context):
    joins = load_force_joins()
    if not joins: return True
    for ch in joins:
        try:
            m = await context.bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if m.status in ['left', 'kicked']: return False
        except: return False
    return True

def force_join_keyboard():
    kb = [[InlineKeyboardButton(f"➡️ Join {ch['name']}", url=ch["link"])] for ch in load_force_joins()]
    kb.append([InlineKeyboardButton("✅ Verify", callback_data="verify_join")])
    return InlineKeyboardMarkup(kb)

def build_features_list():
    hidden = load_hidden_buttons()
    features_map = {
        "📱 Phone Lookup": "📱 Number Info",
        "📱 Hi Tek": "🔎 DeepSearch (Hi Tek)",
        "🆔 Aadhar": "🪪 Aadhaar Info",
        "💳 PAN Lookup": "💳 PAN Card Info",
        "🚗 Vehicle Lookup": "🚗 Vehicle Info",
        "🚗 Vehicle2 Lookup": "🚘 Vehicle VAHANX",
        "💳 UPI Lookup": "⚡ UPI Info",
        "🕵️ Telegram ID Lookup": "🐙 Telegram OSINT",
        "🌍 IP Lookup": "🌍 IP Info",
        "🇵🇰 Pak Lookup": "🇵🇰 PK Number Info",
        "👨‍👩‍👧 Family Lookup": "👥 Family Info",
        "📸 Instagram Lookup": "📸 Instagram Info",
        "🏢 GST Lookup": "🏢 GST Info",
        "📄 PAN to GST": "📄 PAN → GST",
        "🏦 IFSC Lookup": "🏦 IFSC Info",
        "📡 Call Tower Lookup": "📡 Tower Location",
        "📄 RC to PDF": "📄 RC to PDF/Image",
        "💣 Call/SMS Bomb": "💣 Call/SMS Bomb",
    }
    lines = []
    for btn, label in features_map.items():
        if btn not in hidden: lines.append(f"• {label}")
    for n in load_custom_buttons().keys():
        if n not in hidden: lines.append(f"• ⚙️ {n}")
    for n in load_link_buttons().keys():
        if n not in hidden: lines.append(f"• 🔗 {n}")
    return "\n".join(lines)

def build_payment_message():
    pay = load_payment()
    if not pay.get("enabled"): return ""
    methods = pay.get("methods", []); plans = pay.get("premium_plans", [])
    if not methods and not plans: return ""
    parts = ["━━━━━━━━━━━━━━━━━━━━━━", "💰 **PAYMENT OPTIONS** 💰", "━━━━━━━━━━━━━━━━━━━━━━"]
    if pay.get("text", "").strip(): parts.append(pay["text"].strip())
    if methods:
        parts.append("\n💳 **PAYMENT METHODS:**")
        for m in methods:
            line = f"\n{m.get('emoji','💰')} **{m.get('name','')}:** `{m.get('value','')}`"
            if m.get('note'): line += f"\n   📝 _{m['note']}_"
            parts.append(line)
    if plans:
        parts.append("\n━━━━━━━━━━━━━━━━━━━━━━")
        parts.append("⭐ **PREMIUM PLANS** ⭐")
        parts.append("━━━━━━━━━━━━━━━━━━━━━━")
        for p in plans:
            parts.append(f"\n📅 **{p.get('label','')}** – ₹`{p.get('price','0')}`")
            if p.get('note'): parts.append(f"   _{p['note']}_")
    return "\n".join(parts)

def _build_redeem_menu_view():
    """Helper: return (text, keyboard) for redeem menu (image-style)."""
    codes = load_redeem_codes()
    txt = "🎁 **Redeem Codes**\n\n"
    txt += f"**Total:** {len(codes)}\n\n"
    if not codes:
        txt += "_No codes yet. Tap GENERATE to create one._"
    else:
        for code, info in codes.items():
            used = len(info.get("used_by", []))
            mx = info.get("max_users", 0)
            credits = info.get("credits", 0)
            left = max(0, mx - used)
            icon = "✅" if left > 0 else "❌"
            created = info.get("created_at", "")
            time_str = ""
            try:
                dt = datetime.fromisoformat(created)
                time_str = dt.astimezone(IST).strftime("%H:%M")
            except: pass
            txt += f"{icon} `{code}` — {credits}c ({left} left) {time_str}\n"
    kb = [
        [InlineKeyboardButton("GENERATE", callback_data="admin_redeem_create")],
        [InlineKeyboardButton("DELETE", callback_data="admin_redeem_delete_menu")],
        [InlineKeyboardButton("BACK", callback_data="admin_back")]
    ]
    return txt, InlineKeyboardMarkup(kb)

# ==================== KEYBOARDS ====================
def build_main_buttons(user_id):
    hidden = load_hidden_buttons()
    buttons = [
        ["📱 Phone Lookup", "📱 Hi Tek"], ["🆔 Aadhar", "💳 PAN Lookup"],
        ["🚗 Vehicle Lookup", "🚗 Vehicle2 Lookup"], ["💳 UPI Lookup", "🕵️ Telegram ID Lookup"],
        ["🌍 IP Lookup", "🇵🇰 Pak Lookup"], ["👨‍👩‍👧 Family Lookup", "📸 Instagram Lookup"],
        ["🏢 GST Lookup", "📄 PAN to GST"], ["🏦 IFSC Lookup", "📡 Call Tower Lookup"],
        ["📄 RC to PDF"],
    ]
    names = list(load_custom_buttons().keys())
    for i in range(0, len(names), 2):
        row = [names[i]]
        if i+1 < len(names): row.append(names[i+1])
        buttons.append(row)
    lnames = list(load_link_buttons().keys())
    for i in range(0, len(lnames), 2):
        row = [lnames[i]]
        if i+1 < len(lnames): row.append(lnames[i+1])
        buttons.append(row)
    buttons.append(["💣 Call/SMS Bomb"])
    buttons.append(["🔗 Refer & Earn", "🎟️ Redeem Code"])
    buttons.append(["👤 Owner", "ℹ️ Bot Help"])
    buttons.append(["👤 My Account"])
    if is_admin(user_id): buttons.append(["🛠️ Bot Management"])
    return [[b for b in row if b not in hidden] for row in buttons if [b for b in row if b not in hidden]]

def get_user_keyboard(user_id): return ReplyKeyboardMarkup(build_main_buttons(user_id), resize_keyboard=True)
def get_stop_keyboard(): return ReplyKeyboardMarkup([["🛑 Stop Bomb"]], resize_keyboard=True)
def get_keyboard(user_id): return get_user_keyboard(user_id)

BUTTON_LOOKUP_MAP = {
    "📱 Phone Lookup": "phone", "📱 Hi Tek": "hi_tek", "🆔 Aadhar": "aadhar",
    "💳 PAN Lookup": "pan", "🚗 Vehicle Lookup": "vehicle", "🚗 Vehicle2 Lookup": "vehicle2",
    "💳 UPI Lookup": "upi", "🕵️ Telegram ID Lookup": "tg", "🌍 IP Lookup": "ip",
    "🇵🇰 Pak Lookup": "pak", "👨‍👩‍👧 Family Lookup": "family", "📸 Instagram Lookup": "instagram",
    "🏢 GST Lookup": "gst", "📄 PAN to GST": "pan_to_gst", "🏦 IFSC Lookup": "ifsc",
    "📡 Call Tower Lookup": "tower", "📄 RC to PDF": "rc_pdf",
}
LOOKUP_TO_DISPLAY = {v: k for k, v in BUTTON_LOOKUP_MAP.items()}

def get_bot_management_menu():
    dm_s = "✅ ON" if load_dm_mode().get("enabled", True) else "🚫 OFF"
    mt_s = "🛠️ ON" if load_maintenance().get("enabled") else "✅ OFF"
    gm_s = "🟢" if load_global_mode().get("everyone_approved") else "⚪"
    pay = load_payment(); pay_s = "✅ ON" if pay.get("enabled") else "🚫 OFF"
    pv = load_payment_verify(); av_s = "✅" if pv.get("auto_verify_enabled", True) else "🚫"
    pp_count = len(load_premium_pending())
    pp_badge = f" ({pp_count})" if pp_count > 0 else ""
    cfg = load_config()
    dc = cfg.get("default_credits", 5)
    rc = cfg.get("referral_credits", 3)
    pb_s = "✅ ON" if cfg.get("powered_by_enabled", True) else "🚫 OFF"
    redeem_count = len(load_redeem_codes())
    kb = [
        [InlineKeyboardButton("🤖 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📈 Button Usage", callback_data="admin_usage")],
        [InlineKeyboardButton("⏰ Recent Active", callback_data="admin_recent")],
        [InlineKeyboardButton("👥 All Users", callback_data="admin_all_users")],
        [InlineKeyboardButton("🔍 View Logs (In-Bot)", callback_data="admin_query_view"), InlineKeyboardButton("⬇️ Download Logs", callback_data="admin_query_scope")],
        [InlineKeyboardButton("🔎 Find by Username", callback_data="admin_find_user")],
        [InlineKeyboardButton("🏘️ Group Tracking", callback_data="admin_group_track")],
        [InlineKeyboardButton("━━━ 🎁 CREDIT SETTINGS ━━━", callback_data="admin_noop")],
        [InlineKeyboardButton(f"🎁 Default Signup Credits: {dc}", callback_data="admin_set_default_credits")],
        [InlineKeyboardButton(f"🔗 Referral Credits: {rc}", callback_data="admin_set_referral_credits")],
        [InlineKeyboardButton("📊 Top Referrers", callback_data="admin_top_referrers")],
        [InlineKeyboardButton(f"🎟️ Redeem Codes Manager ({redeem_count})", callback_data="admin_redeem_menu")],
        [InlineKeyboardButton("━━━ 🎨 BRANDING ━━━", callback_data="admin_noop")],
        [InlineKeyboardButton(f"✨ Powered-By: {pb_s}", callback_data="admin_toggle_poweredby")],
        [InlineKeyboardButton("✏️ Edit Powered-By Text", callback_data="admin_edit_poweredby")],
        [InlineKeyboardButton("━━━ ⭐ PREMIUM SYSTEM ━━━", callback_data="admin_noop")],
        [InlineKeyboardButton(f"⭐ Premium Pending Users{pp_badge}", callback_data="admin_premium_pending")],
        [InlineKeyboardButton("👑 Premium Users List", callback_data="admin_premium_users_list")],
        [InlineKeyboardButton("💎 Premium Plans", callback_data="admin_premium_plans")],
        [InlineKeyboardButton("💳 Payment Manager", callback_data="admin_payment_menu"),
         InlineKeyboardButton(f"🤖 Auto-Verify {av_s}", callback_data="admin_autoverify")],
        [InlineKeyboardButton("━━━ 👤 USER MGMT ━━━", callback_data="admin_noop")],
        [InlineKeyboardButton("⏰ Approve (Duration)", callback_data="admin_approve_duration")],
        [InlineKeyboardButton("✅ Approve (Bulk)", callback_data="admin_approve_menu"), InlineKeyboardButton("❌ Unapprove", callback_data="admin_unapprove_menu")],
        [InlineKeyboardButton(f"✅ Approve All {gm_s}", callback_data="admin_approve_all"), InlineKeyboardButton("❌ Unapprove All", callback_data="admin_unapprove_all")],
        [InlineKeyboardButton("📋 Approved", callback_data="admin_list_approved"), InlineKeyboardButton("📋 Pending", callback_data="admin_list_pending")],
        [InlineKeyboardButton("🚫 Block (Reason)", callback_data="admin_block"), InlineKeyboardButton("✅ Unblock", callback_data="admin_unblock")],
        [InlineKeyboardButton("📋 Blocked", callback_data="admin_list_blocked")],
        [InlineKeyboardButton("📝 User Notes", callback_data="admin_user_notes")],
        [InlineKeyboardButton("🎫 Add Credits", callback_data="admin_addcredits"), InlineKeyboardButton("🗑️ Remove Credits", callback_data="admin_removecredits")],
        [InlineKeyboardButton("💰 Credit ALL Users", callback_data="admin_credit_all")],
        [InlineKeyboardButton("🔄 Reset Global Credit", callback_data="admin_reset_global_credit")],
        [InlineKeyboardButton("📋 Credits List", callback_data="admin_credits_list")],
        [InlineKeyboardButton("👤 User Details", callback_data="admin_user_details")],
        [InlineKeyboardButton("👑 Promote Admin", callback_data="admin_promote"), InlineKeyboardButton("🚫 Demote", callback_data="admin_demote")],
        [InlineKeyboardButton("📋 List Admins", callback_data="admin_list_admins")],
        [InlineKeyboardButton("━━━ 🔗 LINK BUTTONS ━━━", callback_data="admin_noop")],
        [InlineKeyboardButton("➕ Add Link Button", callback_data="admin_add_link"), InlineKeyboardButton("🗑️ Remove Link", callback_data="admin_del_link")],
        [InlineKeyboardButton("📋 List Link Buttons", callback_data="admin_list_links")],
        [InlineKeyboardButton("━━━ 🎛️ BUTTON CONTROL ━━━", callback_data="admin_noop")],
        [InlineKeyboardButton("➕ Add Button", callback_data="admin_add_button"), InlineKeyboardButton("🗑️ Delete Button", callback_data="admin_delete_button")],
        [InlineKeyboardButton("📋 List Buttons", callback_data="admin_list_buttons")],
        [InlineKeyboardButton("💣 Bomb API Manager", callback_data="admin_bomb_menu")],
        [InlineKeyboardButton("🔄 Replace API", callback_data="admin_replace_api"), InlineKeyboardButton("↩️ Undo API", callback_data="admin_undo_api")],
        [InlineKeyboardButton("📋 List API Overrides", callback_data="admin_list_api_overrides")],
        [InlineKeyboardButton("⚙️ Prefix Modes (91)", callback_data="admin_prefix_modes")],
        [InlineKeyboardButton("✏️ Set Prompt", callback_data="admin_set_prompt")],
        [InlineKeyboardButton("🙈 Hide Field", callback_data="admin_hide_field"), InlineKeyboardButton("👁️ Unhide Field", callback_data="admin_unhide_field")],
        [InlineKeyboardButton("📋 List Hidden", callback_data="admin_list_hidden")],
        [InlineKeyboardButton("━━━ 📝 RESPONSE CONTROL ━━━", callback_data="admin_noop")],
        [InlineKeyboardButton("📝 Add Word (Global)", callback_data="admin_addword_global")],
        [InlineKeyboardButton("📝 Add Word (Per-Btn)", callback_data="admin_addword_button")],
        [InlineKeyboardButton("🎯 Set Button Response", callback_data="admin_setword")],
        [InlineKeyboardButton("🎯 Set Word (Specific)", callback_data="admin_setword_specific")],
        [InlineKeyboardButton("🗑️ Remove Set Word", callback_data="admin_remove_setword")],
        [InlineKeyboardButton("📝 Add to JSON", callback_data="admin_json_add")],
        [InlineKeyboardButton("🗑️ Remove JSON Add", callback_data="admin_json_remove")],
        [InlineKeyboardButton("📋 List JSON Adds", callback_data="admin_json_list")],
        [InlineKeyboardButton("🗑️ Remove Add Word", callback_data="admin_remove_addword")],
        [InlineKeyboardButton("📋 List Add Words", callback_data="admin_list_addwords")],
        [InlineKeyboardButton("🛡️ Protect Value", callback_data="admin_protect_value")],
        [InlineKeyboardButton("🔓 Unprotect", callback_data="admin_unprotect_value")],
        [InlineKeyboardButton("📋 List Protected", callback_data="admin_list_protected")],
        [InlineKeyboardButton("━━━ 🚦 ACCESS CONTROL ━━━", callback_data="admin_noop")],
        [InlineKeyboardButton("👥 Group Only", callback_data="admin_group_only")],
        [InlineKeyboardButton("📋 List Group Only", callback_data="admin_list_grouponly")],
        [InlineKeyboardButton("📢 Add Force Join", callback_data="admin_add_forcejoin"), InlineKeyboardButton("🗑️ Remove FJ", callback_data="admin_remove_forcejoin")],
        [InlineKeyboardButton("📋 List Force Joins", callback_data="admin_list_forcejoins")],
        [InlineKeyboardButton("🔓 Grant DM", callback_data="admin_grant_dm"), InlineKeyboardButton("🔒 Revoke DM", callback_data="admin_revoke_dm")],
        [InlineKeyboardButton("📋 DM Grant List", callback_data="admin_dm_list")],
        [InlineKeyboardButton(f"📩 DM Mode: {dm_s}", callback_data="admin_toggle_dm")],
        [InlineKeyboardButton("━━━ 🛠️ SYSTEM ━━━", callback_data="admin_noop")],
        [InlineKeyboardButton(f"🔧 Maintenance: {mt_s}", callback_data="admin_toggle_maintenance")],
        [InlineKeyboardButton(f"👤 Owner 1: @{get_owner_username()}", callback_data="admin_set_owner_username")],
        [InlineKeyboardButton(f"👤 Owner 2: @{get_owner2_username()}", callback_data="admin_set_owner2_username")],
        [InlineKeyboardButton("👋 Custom Welcome", callback_data="admin_set_welcome")],
        [InlineKeyboardButton("💾 Backup Data", callback_data="admin_backup")],
        [InlineKeyboardButton("🗑️ Clear Logs", callback_data="admin_clear_logs")],
        [InlineKeyboardButton("❌ Close Panel", callback_data="admin_close")]
    ]
    return InlineKeyboardMarkup(kb)

def get_back_keyboard(): return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Return", callback_data="admin_back")]])

def button_selector_keyboard(prefix):
    kb = [[InlineKeyboardButton(d, callback_data=f"{prefix}:{l}")] for d, l in BUTTON_LOOKUP_MAP.items()]
    for n in load_custom_buttons().keys(): kb.append([InlineKeyboardButton(f"⚙️ {n}", callback_data=f"{prefix}:custom_{n}")])
    kb.append([InlineKeyboardButton("🌍 GLOBAL (all)", callback_data=f"{prefix}:__global__")])
    kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
    return InlineKeyboardMarkup(kb)

# ==================== BOMB APIS ====================
# CALL_APIS = [
#     APIs
# ]
# WHATSAPP_APIS = [
#     APIs
# ]
# SMS_APIS = [
# APIs ]
# BOMB_APIS = CALL_APIS + SMS_APIS + WHATSAPP_APIS
# active_bombs = {}

# async def bomb_loop(update, context, phone, message):
#     user_id = update.effective_user.id
#     apis = get_all_bomb_apis(); total_apis = len(apis)
#     total_success = 0; total_fail = 0; iteration = 0; start_time = datetime.now()
#     while True:
#         if context.user_data.get("stop_bomb", False): break
#         iteration += 1
#         results = await asyncio.gather(*[send_one_bomb(api, phone) for api in apis], return_exceptions=True)
#         success = sum(1 for r in results if r is True); failed = total_apis - success
#         total_success += success; total_fail += failed
#         elapsed = int((datetime.now() - start_time).total_seconds())
#         try: await message.edit_text(f"💣 **BOMB LIVE** 💣\n━━━━━━━━━━━━━━━━━━━━━━\n📞 `{phone}`\n⏱️ `{elapsed}s` | 🔄 `#{iteration}`\n✅ `{success}/{total_apis}` | ❌ `{failed}`\n📊 Total ✅ `{total_success}` | ❌ `{total_fail}`\n━━━━━━━━━━━━━━━━━━━━━━\n⏳ Press **🛑 Stop Bomb**", parse_mode="Markdown")
#         except: pass
#         await asyncio.sleep(0.05)
#     try: await message.edit_text(f"✅ **Bomb Stopped**\n━━━━━━━━━━━━━━━━━━━━━━\n📞 `{phone}`\n🔄 Cycles: `{iteration}`\n✅ Hits: `{total_success}`\n❌ Failed: `{total_fail}`\n⏱️ `{int((datetime.now() - start_time).total_seconds())}s`", parse_mode="Markdown", reply_markup=get_keyboard(user_id))
#     except: await context.bot.send_message(chat_id=user_id, text=f"✅ Bomb stopped. Hits: {total_success}", reply_markup=get_keyboard(user_id))
#     active_bombs.pop(user_id, None)

# async def send_one_bomb(api, phone):
#     try:
#         session = await get_aio_session()
#         url = api["url"]
#         if callable(url): url = url(phone)
#         elif isinstance(url, str) and "{phone}" in url: url = url.format(phone=phone)
#         data = api.get("data")
#         if data is not None and callable(data): data = data(phone)
#         elif isinstance(data, str) and "{phone}" in data: data = data.replace("{phone}", phone)
#         headers = api.get("headers", {}); method = api.get("method", "GET").upper()
#         timeout = aiohttp.ClientTimeout(total=8)
#         if method == "GET":
#             async with session.get(url, headers=headers, timeout=timeout) as r: return r.status < 400
#         elif method == "POST":
#             ct = headers.get("Content-Type", "")
#             if ct.startswith("application/json"):
#                 try: js = json.loads(data) if data else None
#                 except: js = None
#                 async with session.post(url, json=js, headers=headers, timeout=timeout) as r: return r.status < 400
#             async with session.post(url, data=data, headers=headers, timeout=timeout) as r: return r.status < 400
#         return False
#     except Exception: return False

# ==================== CLEANER ====================
def clean_response_data(data, button=None):
    if not isinstance(data, dict): return data
    hidden = {h.lower().strip() for h in load_hidden_fields()}
    if button: hidden.update({h.lower().strip() for h in get_button_hidden_fields(button)})
    junk = ["demo","tg id to num","family-info","this is demo","sample","abhigyan","viraj","dark-info.site","hittadmin","https://t.me/","apikey","api key","powered by","buy apis","ifsc-info","gst-to-info"]
    cleaned = {}
    for k, v in data.items():
        if k.lower().strip() in hidden or k in ["N-A","n-a"] or "\u3164" in k: continue
        if isinstance(v, str):
            if any(kw in v.lower() for kw in junk): continue
            cleaned[k] = v
        elif isinstance(v, dict):
            cn = clean_response_data(v, button)
            if cn: cleaned[k] = cn
        elif isinstance(v, list):
            cl = []
            for item in v:
                if isinstance(item, dict):
                    ci = clean_response_data(item, button)
                    if ci: cl.append(ci)
                elif isinstance(item, str):
                    if not any(kw in item.lower() for kw in junk): cl.append(item)
                else: cl.append(item)
            if cl: cleaned[k] = cl
        else: cleaned[k] = v
    return cleaned

def apply_json_add(data, button):
    if not isinstance(data, dict): return data
    for k, v in get_json_add(button).items(): data[k] = v
    return data

# ==================== APPROVAL REQUIRED ====================
async def show_approval_required(update):
    cfg = load_config()
    owner1_uname = cfg.get("owner_username", "DarkWorld233")
    owner1_disp = cfg.get("owner_display", "Owner 1")
    owner2_uname = cfg.get("owner2_username", "Hittadmin")
    owner2_disp = cfg.get("owner2_display", "█▬█ █ ▀█▀-ADMIN")
    pay = load_payment()
    pay_block = build_payment_message()

    msg = ("🔐 **ACCESS REQUIRED**\n"
           "━━━━━━━━━━━━━━━━━━━━━━\n\n"
           "👋 **Welcome to the Intelligence System!**\n\n"
           "⚠️ **Your credits are exhausted** (or your account is pending approval).\n\n"
           "📌 **How to get access:**\n"
           "• 🔗 Use **Refer & Earn** to get free credits\n"
           "• 🎟️ Use **Redeem Code** for instant credits\n"
           "• 💳 Choose a premium plan below\n"
           "• 💰 Complete payment & click **I Have Paid**\n"
           "• 👤 Contact owner for manual approval\n\n"
           "━━━ 👑 **OWNERS** 👑 ━━━\n"
           f"👤 **Owner 1:** [{owner1_disp}](https://t.me/{owner1_uname})\n"
           f"👤 **Owner 2:** [{owner2_disp}](https://t.me/{owner2_uname})\n"
           "━━━━━━━━━━━━━━━━━━━━━━")

    if pay_block:
        msg += "\n\n" + pay_block + "\n\n📸 *After payment, click below:*"
    else:
        msg += "\n\n💡 *Contact owners for payment details.*"

    payment_active = pay.get("enabled") and (pay.get("methods") or pay.get("premium_plans") or pay.get("qr_image_file_id"))
    kb_rows = []
    kb_rows.append([InlineKeyboardButton("🔗 Refer & Earn (Free Credits)", callback_data="show_referral")])
    if payment_active:
        kb_rows.append([InlineKeyboardButton("✅ I Have Paid – Request Access", callback_data="ipaid_request")])
    kb_rows.append([
        InlineKeyboardButton(f"💬 {owner1_disp[:15]}", url=f"https://t.me/{owner1_uname}"),
        InlineKeyboardButton(f"💬 {owner2_disp[:15]}", url=f"https://t.me/{owner2_uname}")
    ])
    kb = InlineKeyboardMarkup(kb_rows)

    qr_file_id = pay.get("qr_image_file_id")
    if payment_active and qr_file_id:
        try:
            caption = msg if len(msg) <= 1024 else msg[:1000] + "...\n\n_(more below)_"
            await update.message.reply_photo(photo=qr_file_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
            if len(msg) > 1024:
                await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
            return
        except: pass
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

async def show_referral_message(update, context, uid):
    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
    except:
        bot_username = "YourBot"
    ref_link = f"https://t.me/{bot_username}?start=ref_{uid}"
    ref_credits = get_referral_credits()
    refs = load_referrals()
    my_refs = refs.get(str(uid), [])
    ref_count = len(my_refs)

    msg = ("🔗 **REFER & EARN** 🔗\n"
           "━━━━━━━━━━━━━━━━━━━━━━\n\n"
           f"🎁 **Earn `{ref_credits}` credits per successful referral!**\n\n"
           "📌 **How it works:**\n"
           "1️⃣ Share your referral link with friends\n"
           "2️⃣ They start the bot using your link\n"
           f"3️⃣ You instantly get `{ref_credits}` credits! 🎉\n\n"
           "━━━━━━━━━━━━━━━━━━━━━━\n"
           f"👥 **Your Referrals:** `{ref_count}`\n"
           f"💳 **Total Credits Earned:** `{ref_count * ref_credits}`\n"
           "━━━━━━━━━━━━━━━━━━━━━━\n\n"
           "📤 **Your Referral Link:**\n"
           f"`{ref_link}`\n\n"
           "💡 _Share this link anywhere! No approval or credits required to refer._")

    share_text = "🚀 Join this amazing OSINT bot! Get free credits on signup!"
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text.replace(' ', '%20')}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Link", url=share_url)],
        [InlineKeyboardButton("📋 Copy Link", callback_data="show_ref_link")]
    ])
    await reply_message(update, context, msg, reply_markup=kb, include_user_tag=False)

# ==================== LOOKUP ====================
async def perform_lookup(update, context, lookup_type, input_text):
    user = update.effective_user; user_id = str(user.id); uid = int(user_id)
    chat = update.effective_chat; chat_type = chat.type
    if chat_type in ["group", "supergroup"]: track_group_search(chat.id)
    if check_flood(user_id, f"{lookup_type}:{input_text}"): await send_simple(update, "⚠️ **Slow down!** Try again in 60s."); return
    track_button_use(lookup_type)
    if is_group_only(lookup_type) and chat_type == "private": await send_simple(update, "🚫 **Group only.**"); return
    protected = get_button_protected(lookup_type)
    if protected and input_text.strip().upper() in protected: await send_simple(update, "🛡️ **Access Denied**"); return
    spec = get_specific_set_word(lookup_type, input_text)
    if spec: await send_simple(update, spec); log_query(user_id, user.first_name, f"{lookup_type}_spec", input_text); return
    sw = get_button_set_word(lookup_type)
    if sw: await send_simple(update, sw); log_query(user_id, user.first_name, f"{lookup_type}_setword", input_text); return

    gm = load_global_mode()
    is_perm = uid in ADMIN_IDS or is_user_approved(uid) or gm.get("everyone_approved", False)
    remaining_credit_msg = ""
    if not is_perm:
        current = get_credits(uid)
        if current <= 0:
            await show_approval_required(update); return
        remove_credits(uid, 1)
        remaining = get_credits(uid)
        remaining_credit_msg = (
            "╔══════════════════════════╗\n"
            f"║  💳 **1 CREDIT USED**           ║\n"
            f"║  🔥 **LEFT: `{remaining}`**              ║\n"
            "╚══════════════════════════╝\n\n"
        )

    loading = await update.message.reply_text(f"⏳ {user.first_name}, Fetching...", parse_mode="Markdown")
    fj = ""; rt = ""
    try:
        prefix_modes = load_prefix_modes()
        if lookup_type == "vehicle":
            rc = input_text.replace(" ", "").upper()
            r = await async_fetch(f"{get_api_url('vehicle')}{rc}")
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"🚗 **VEHICLE RC**\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "vehicle2":
            rc = input_text.replace(" ", "").upper()
            r = await async_fetch(f"{get_api_url('vehicle2')}{rc}")
            if r and r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser'); ex = {}
                main = soup.find('main') or soup.find('div', class_=lambda c: c and 'result' in c.lower()) or soup
                for row in main.find_all(['tr','li','div','p']):
                    t = row.get_text(separator=':', strip=True)
                    if ':' in t:
                        p = t.split(':',1); k=p[0].strip().title(); v=p[1].strip()
                        if k and v and len(k)<30 and len(v)<80 and k not in ex: ex[k]=v
                if ex: ex = apply_json_add(ex, lookup_type)
                card = "".join([f"▫️ **{k}:** `{v}`\n" for k,v in ex.items()]) or f"▫️ **RC:** `{rc}`\n"
                fj = json.dumps(ex or {"rc":rc}, indent=2); rt = f"🚗 **VEHICLE2**\n{card}{powered_by_text()}"
            else: raise Exception("VAHANX failed")
        elif lookup_type == "pan":
            r = await async_fetch(f"{get_api_url('pan')}{input_text.upper()}")
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"💳 **PAN CARD**\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "phone":
            mode = prefix_modes.get("phone", "with_91")
            c = normalize_phone(input_text, mode)
            if not c or len(c) < 10:
                await loading.edit_text("❌ **Invalid number.**\n\nSend 10-digit mobile (e.g. `9826XXXXXX` or `919826XXXXXX`)")
                return
            r = await async_fetch(f"{get_api_url('phone')}{c}", timeout=20)
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            if not _has_real_data(d):
                alt = normalize_phone(input_text, "without_91" if mode == "with_91" else "with_91")
                if alt and alt != c:
                    r2 = await async_fetch(f"{get_api_url('phone')}{alt}", timeout=20)
                    try: d2 = r2.json()
                    except: d2 = None
                    if d2 and isinstance(d2, dict):
                        d2 = apply_json_add(clean_response_data(d2, lookup_type), lookup_type)
                        if _has_real_data(d2): d = d2
            if not _has_real_data(d):
                await loading.edit_text(f"⚠️ **No data found** for `{c}`\n\n_Number may not be in database. Try another format._")
                return
            fj = json.dumps(d, indent=2); rt = f"📱 **PHONE INFO**\n📞 `{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "hi_tek":
            mode = prefix_modes.get("hi_tek", "without_91")
            c = normalize_phone(input_text, mode)
            if not c or len(c) < 10: await loading.edit_text("❌ Invalid number.\n\nSend 10-digit."); return
            r = await async_fetch(f"{get_api_url('hi_tek')}{c}", timeout=20)
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            if not _has_real_data(d):
                alt = normalize_phone(input_text, "with_91" if mode == "without_91" else "without_91")
                if alt and alt != c:
                    r2 = await async_fetch(f"{get_api_url('hi_tek')}{alt}", timeout=20)
                    try: d2 = r2.json()
                    except: d2 = None
                    if d2 and isinstance(d2, dict):
                        d2 = apply_json_add(clean_response_data(d2, lookup_type), lookup_type)
                        if _has_real_data(d2): d = d2
            if not _has_real_data(d):
                await loading.edit_text(f"⚠️ **No data found** for `{c}`"); return
            fj = json.dumps(d, indent=2); rt = f"🔎 **DEEPSEARCH (HI TEK)**\n📞 `{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "aadhar":
            c = input_text.replace(" ","").replace("+","")
            if not c.isdigit() or len(c)!=12: await loading.edit_text("❌ Invalid 12-digit."); return
            r = await async_fetch(f"{get_api_url('aadhar')}{c}")
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"🪪 **AADHAAR**\n🔢 `{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "pak":
            c = input_text.replace(" ","").replace("+","")
            r = await async_fetch(f"{get_api_url('pak')}{c}")
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"🇵🇰 **PK NUMBER INFO**\n📞 `{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "family":
            c = input_text.strip()
            if not c.isdigit(): await loading.edit_text("❌ Numeric ID."); return
            r = await async_fetch(f"{get_api_url('family')}{c}")
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"👥 **FAMILY INFO**\n🔢 `{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "upi":
            if "@" not in input_text: await loading.edit_text("❌ Invalid UPI."); return
            r = await async_fetch(f"{get_api_url('upi')}{input_text}")
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"⚡ **UPI INFO**\n🆔 `{input_text}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "tg":
            c = input_text.strip().lstrip("@")
            if not c: await loading.edit_text("❌ Send ID/username."); return
            if c in RESTRICTED_IDS: await loading.edit_text("❌ Restricted."); return
            r = await async_fetch(f"{get_api_url('tg')}{c}")
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            if not d: await loading.edit_text(f"⚠️ **No Data** `{c}`"); return
            fj = json.dumps(d, indent=2)
            rt = f"🐙 **TELEGRAM OSINT**\n🎯 `{c}` ({'ID' if c.isdigit() else 'Username'})\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "ip":
            c = input_text.strip()
            r = await async_fetch(f"{get_api_url('ip')}{c}?fields=status,message,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as,query")
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict):
                d = {"error": d.get("message","Invalid IP")} if d.get("status") == "fail" else {"data": d}
                d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"🌍 **IP INFO**\n🌐 `{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "instagram":
            c = input_text.strip().lstrip("@")
            if not c: await loading.edit_text("❌ Username required."); return
            r = await async_fetch(get_api_url('instagram').format(c))
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"📸 **INSTAGRAM**\n👤 `@{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "gst":
            c = input_text.strip().upper()
            if not c: await loading.edit_text("❌ GSTIN required."); return
            r = await async_fetch(get_api_url('gst').format(c))
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"🏢 **GST**\n🔢 `{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "pan_to_gst":
            c = input_text.strip().upper()
            if len(c)!=10: await loading.edit_text("❌ 10-char PAN."); return
            r = await async_fetch(get_api_url('pan_to_gst').format(c))
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"📄 **PAN → GST**\n🆔 `{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "ifsc":
            c = input_text.strip().upper()
            if len(c)!=11: await loading.edit_text("❌ 11-char IFSC."); return
            r = await async_fetch(get_api_url('ifsc').format(c))
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict):
                if "data" in d and isinstance(d["data"], dict): d["data"] = apply_json_add(clean_response_data(d["data"], lookup_type), lookup_type)
                d = clean_response_data(d, lookup_type)
            fj = json.dumps(d, indent=2); rt = f"🏦 **IFSC**\n🔢 `{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "tower":
            mode = prefix_modes.get("tower", "with_91")
            c = normalize_phone(input_text, mode)
            if not c or len(c) < 10: await loading.edit_text("❌ Invalid number."); return
            r = await async_fetch(get_api_url('tower').format(c), timeout=20)
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict):
                if "fields" in d and isinstance(d["fields"], dict): d["fields"] = apply_json_add(clean_response_data(d["fields"], lookup_type), lookup_type)
                d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            if not _has_real_data(d):
                alt = normalize_phone(input_text, "without_91" if mode == "with_91" else "with_91")
                if alt and alt != c:
                    r2 = await async_fetch(get_api_url('tower').format(alt), timeout=20)
                    try: d2 = r2.json()
                    except: d2 = None
                    if d2 and isinstance(d2, dict):
                        d2 = apply_json_add(clean_response_data(d2, lookup_type), lookup_type)
                        if _has_real_data(d2): d = d2
            if not _has_real_data(d):
                await loading.edit_text(f"⚠️ **No data found** for `{c}`"); return
            fj = json.dumps(d, indent=2); rt = f"📡 **TOWER LOCATION**\n📞 `{c}`\n\n```json\n{fj}\n```{powered_by_text()}"
        elif lookup_type == "rc_pdf":
            c = input_text.strip().upper().replace(" ", "")
            if not c: await loading.edit_text("❌ RC number required."); return
            url = f"{get_api_url('rc_pdf')}{c}"
            session = await get_aio_session()
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status != 200: await loading.edit_text(f"⚠️ API: `{r.status}`"); return
                    content = await r.read(); ct = r.headers.get("Content-Type", "").lower()
                await loading.delete()
                cleanup_rc_cache()
                cache_id = f"{uid}_{int(time.time())}_{c}"
                with RC_CACHE_LOCK:
                    RC_CACHE[cache_id] = {"content": content, "rc": c, "user_id": uid, "created": time.time(), "content_type": ct}
                dl_kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("📥 Download Image", callback_data=f"rcdl_img:{cache_id}"),
                    InlineKeyboardButton("📥 Download PDF", callback_data=f"rcdl_pdf:{cache_id}")]])
                caption_text = (f"📄 **RC Report Ready** – `{c}`\n━━━━━━━━━━━━━━━━━━━━━━\n✅ Report generated!\n\n📥 **Use buttons below**\n🔒 Secure download (no external links){powered_by_text()}")
                is_pdf = content[:4] == b"%PDF" or "pdf" in ct
                is_img = (not is_pdf) and (content[:3] in (b"\xff\xd8\xff", b"\x89PN") or "image" in ct)
                if is_pdf:
                    fd = io.BytesIO(content); fd.name = f"RC_{c}.pdf"
                    await update.message.reply_document(document=fd, caption=caption_text, parse_mode="Markdown", reply_markup=dl_kb)
                elif is_img:
                    fd = io.BytesIO(content); fd.name = f"RC_{c}.jpg"
                    try: await update.message.reply_photo(photo=fd, caption=caption_text, parse_mode="Markdown", reply_markup=dl_kb)
                    except:
                        fd.seek(0); fd.name = f"RC_{c}.jpg"
                        await update.message.reply_document(document=fd, caption=caption_text, parse_mode="Markdown", reply_markup=dl_kb)
                else:
                    fd = io.BytesIO(content); fd.name = f"RC_{c}.bin"
                    await update.message.reply_document(document=fd, caption=caption_text, parse_mode="Markdown", reply_markup=dl_kb)
                log_query(user_id, user.first_name, "rc_pdf", c); return
            except Exception as e: await loading.edit_text(f"⚠️ Error: `{str(e)}`"); return
        elif lookup_type.startswith("custom_"):
            bn = lookup_type[7:]; cb = load_custom_buttons()
            if bn not in cb: await loading.edit_text("❌ Not found."); return
            api = get_api_url(lookup_type)
            if not api: await loading.edit_text(f"ℹ️ **{bn}** – No API."); return
            url = build_api_url(api, input_text.strip())
            r = await async_fetch(url)
            try: d = r.json()
            except: d = {"raw_response": r.text}
            if isinstance(d, dict): d = apply_json_add(clean_response_data(d, lookup_type), lookup_type)
            fj = json.dumps(d, indent=2); rt = f"⚙️ **{bn.upper()}**\n🔍 `{input_text}`\n\n```json\n{fj}\n```{powered_by_text()}"
    except Exception as e: await loading.edit_text(f"⚠️ **Error:** `{str(e)}`"); return
    gw = get_button_add_word("__global__"); bw = get_button_add_word(lookup_type)
    if gw: rt += f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n📢 {gw}"
    if bw: rt += f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n📌 {bw}"
    log_query(user_id, user.first_name, lookup_type, input_text)
    final_rt = remaining_credit_msg + rt
    if len(final_rt) > 4000:
        fd = io.BytesIO(fj.encode('utf-8')); fd.name = f"{lookup_type}.txt"
        await loading.delete()
        await update.message.reply_document(document=fd, caption=f"{remaining_credit_msg}📄 Report", parse_mode="Markdown")
    else: await loading.edit_text(final_rt, parse_mode="Markdown", disable_web_page_preview=True)

# ==================== RC DOWNLOAD ====================
async def rc_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id; data = q.data
    if not data.startswith("rcdl_"): return
    parts = data.split(":", 1)
    if len(parts) != 2: await q.answer("❌ Invalid", show_alert=True); return
    action = parts[0]; cache_id = parts[1]
    entry = RC_CACHE.get(cache_id)
    if not entry: await q.answer("⚠️ File expired.", show_alert=True); return
    if entry["user_id"] != uid: await q.answer("🚫 Not yours.", show_alert=True); return
    content = entry["content"]; c = entry["rc"]; ct = entry.get("content_type", "").lower()
    is_pdf = content[:4] == b"%PDF" or "pdf" in ct
    is_img = (not is_pdf) and (content[:3] in (b"\xff\xd8\xff", b"\x89PN") or "image" in ct)
    await q.answer("📤 Preparing...")
    try:
        if action == "rcdl_pdf":
            if is_pdf:
                fd = io.BytesIO(content); fd.name = f"RC_{c}.pdf"
                await context.bot.send_document(chat_id=uid, document=fd, caption=f"📄 **RC PDF** `{c}`{powered_by_text()}", parse_mode="Markdown")
            elif is_img and HAS_PIL:
                try:
                    img = PILImage.open(io.BytesIO(content))
                    if img.mode in ("RGBA", "P", "LA"): img = img.convert("RGB")
                    pdf_buf = io.BytesIO(); img.save(pdf_buf, "PDF", resolution=100.0); pdf_buf.seek(0); pdf_buf.name = f"RC_{c}.pdf"
                    await context.bot.send_document(chat_id=uid, document=pdf_buf, caption=f"📄 **RC PDF** `{c}`{powered_by_text()}", parse_mode="Markdown")
                except Exception as e: await q.message.reply_text(f"⚠️ PDF convert failed: `{e}`", parse_mode="Markdown")
            else:
                fd = io.BytesIO(content); fd.name = f"RC_{c}.pdf"
                await context.bot.send_document(chat_id=uid, document=fd, caption=f"📄 **RC Report** `{c}`{powered_by_text()}", parse_mode="Markdown")
        elif action == "rcdl_img":
            if is_img:
                fd = io.BytesIO(content); fd.name = f"RC_{c}.jpg"
                try: await context.bot.send_photo(chat_id=uid, photo=fd, caption=f"🖼️ **RC Image** `{c}`{powered_by_text()}", parse_mode="Markdown")
                except:
                    fd.seek(0); fd.name = f"RC_{c}.jpg"
                    await context.bot.send_document(chat_id=uid, document=fd, caption=f"🖼️ **RC Image** `{c}`{powered_by_text()}", parse_mode="Markdown")
            else:
                fd = io.BytesIO(content); fd.name = f"RC_{c}.jpg"
                await context.bot.send_document(chat_id=uid, document=fd, caption=f"🖼️ **RC File** `{c}`\n_(PDF format)_{powered_by_text()}", parse_mode="Markdown")
    except Exception as e:
        try: await q.message.reply_text(f"⚠️ Error: `{e}`", parse_mode="Markdown")
        except: pass

# ==================== I PAID ====================
async def ipaid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id; user = q.from_user
    await q.answer("✅ Request sent!")
    track_user(user)
    p = load_pending()
    if uid not in p: p.add(uid); save_pending(p)
    add_premium_pending(uid, user.username, user.full_name)

    cfg = load_config()
    owner1_uname = cfg.get("owner_username", "DarkWorld233")
    owner2_uname = cfg.get("owner2_username", "Hittadmin")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Contact Owner 1", url=f"https://t.me/{owner1_uname}")],
        [InlineKeyboardButton("💬 Contact Owner 2", url=f"https://t.me/{owner2_uname}")],
        [InlineKeyboardButton("👤 My Profile", callback_data="my_profile_user")]
    ])
    await q.edit_message_text(
        "✅ **PAYMENT REQUEST SENT!**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Your payment request has been submitted.\n\n"
        "⏳ **Status:** Pending Verification\n"
        "🔔 **Admin will verify shortly**\n\n"
        "📌 **Next Steps:**\n"
        "• Owner will review your request\n"
        "• You'll be notified once approved\n"
        "• For urgent help, contact any owner\n\n"
        "👇 **Click below to contact owner:**",
        parse_mode="Markdown", reply_markup=kb)

async def my_profile_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id
    await q.answer()
    a_info = load_approvals().get(str(uid), {})
    exp_txt = ""
    if a_info.get("expires"): exp_txt = f"\n⏰ Expires: `{to_ist_str(a_info['expires'])}`"
    elif a_info.get("duration_days", 0) == 0 and a_info.get("approved"): exp_txt = "\n⏰ Permanent"
    status = "✅ Approved" if is_user_approved(uid) else "⏳ Pending"
    credits = get_credits(uid)
    refs = load_referrals().get(str(uid), [])
    await q.edit_message_text(
        f"👤 **MY PROFILE**\n━━━━━━━━━━━━━━━━━━━━━━\n🆔 `{uid}`\n📛 {q.from_user.full_name}\n"
        f"🌐 @{q.from_user.username or 'N/A'}\n📊 {status}{exp_txt}\n\n"
        f"🔥 **💳 Credits: `{credits}`** 🔥\n"
        f"🔗 Referrals: `{len(refs)}`",
        parse_mode="Markdown")

async def show_referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id
    await q.answer()
    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
    except:
        bot_username = "YourBot"
    ref_link = f"https://t.me/{bot_username}?start=ref_{uid}"
    ref_credits = get_referral_credits()
    refs = load_referrals()
    my_refs = refs.get(str(uid), [])
    ref_count = len(my_refs)

    msg = ("🔗 **REFER & EARN** 🔗\n"
           "━━━━━━━━━━━━━━━━━━━━━━\n\n"
           f"🎁 **Earn `{ref_credits}` credits per successful referral!**\n\n"
           "📌 **How it works:**\n"
           "1️⃣ Share your referral link with friends\n"
           "2️⃣ They start the bot using your link\n"
           f"3️⃣ You instantly get `{ref_credits}` credits! 🎉\n\n"
           "━━━━━━━━━━━━━━━━━━━━━━\n"
           f"👥 **Your Referrals:** `{ref_count}`\n"
           f"💳 **Total Credits Earned:** `{ref_count * ref_credits}`\n"
           "━━━━━━━━━━━━━━━━━━━━━━\n\n"
           "📤 **Your Referral Link:**\n"
           f"`{ref_link}`\n\n"
           "💡 _No approval or credits required to use referrals!_")
    share_url = f"https://t.me/share/url?url={ref_link}&text=Join%20this%20bot!"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📤 Share Link", url=share_url)]])
    await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

async def show_ref_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id
    await q.answer("📋 Long-press to copy")
    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
    except:
        bot_username = "YourBot"
    ref_link = f"https://t.me/{bot_username}?start=ref_{uid}"
    await q.message.reply_text(f"🔗 **Your Referral Link**\n\n`{ref_link}`", parse_mode="Markdown")

# ==================== PREMIUM PENDING ====================
async def premium_pending_view(q, page=0):
    pp = load_premium_pending()
    if not pp:
        await q.edit_message_text("📭 **No pending premium users.**", reply_markup=get_back_keyboard()); return
    ul = list(pp.items()); PER_PAGE = 8
    total = max(1, (len(ul) + PER_PAGE - 1) // PER_PAGE)
    if page >= total: page = total - 1
    if page < 0: page = 0
    s_idx = page * PER_PAGE; e_idx = s_idx + PER_PAGE; pg = ul[s_idx:e_idx]
    kb = []
    for uid_str, info in pg:
        name = info.get("full_name", "Unknown"); uname = info.get("username", "N/A")
        kb.append([InlineKeyboardButton(f"👤 {name} (@{uname})", callback_data=f"pp_user:{uid_str}")])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"pp_page:{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total}", callback_data="admin_noop"))
    if page < total - 1: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"pp_page:{page+1}"))
    kb.append(nav)
    kb.append([InlineKeyboardButton("🔄 Refresh", callback_data="admin_premium_pending")])
    kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
    await q.edit_message_text(
        f"⭐ **PREMIUM PENDING USERS**\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Total: `{len(pp)}` | Page `{page+1}/{total}`\n\n👇 **Click a user to manage:**",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def premium_user_view(q, target_uid):
    pp = load_premium_pending(); info = pp.get(str(target_uid))
    if not info:
        await q.edit_message_text("❌ User no longer pending.", reply_markup=get_back_keyboard()); return
    user = info.get("full_name", "Unknown"); uname = info.get("username", "N/A")
    req_time = to_ist_str(info.get("requested_at", ""))
    kb = [
        [InlineKeyboardButton("💬 Open DM", url=f"tg://user?id={target_uid}")],
        [InlineKeyboardButton("📅 1 Month", callback_data=f"pp_app:{target_uid}:30"), InlineKeyboardButton("📅 2 Months", callback_data=f"pp_app:{target_uid}:60")],
        [InlineKeyboardButton("📅 3 Months", callback_data=f"pp_app:{target_uid}:90"), InlineKeyboardButton("📅 6 Months", callback_data=f"pp_app:{target_uid}:180")],
        [InlineKeyboardButton("📅 1 Year", callback_data=f"pp_app:{target_uid}:365"), InlineKeyboardButton("📅 2 Years", callback_data=f"pp_app:{target_uid}:730")],
        [InlineKeyboardButton("♾️ Permanent", callback_data=f"pp_app:{target_uid}:0")],
        [InlineKeyboardButton("❌ Reject", callback_data=f"pp_rej:{target_uid}")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_premium_pending")]
    ]
    await q.edit_message_text(
        f"⭐ **PREMIUM USER DETAILS**\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Name:** {user}\n🆔 **TG ID:** `{target_uid}`\n🌐 **Username:** @{uname}\n"
        f"🕐 **Requested:** {req_time}\n\n**👇 Approve with duration or DM user:**",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

# ==================== ADMIN CALLBACK ====================
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if not is_admin(uid): return
    data = q.data
    if data not in ("admin_back", "admin_noop"): invalidate_menu_cache()

    if data == "admin_noop": await q.answer("ℹ️", show_alert=False); return
    if data == "admin_close": await q.edit_message_text("🔒 Closed.")

    # Credit settings
    elif data == "admin_set_default_credits":
        cfg = load_config()
        context.user_data["admin_action"] = "set_default_credits"
        await q.edit_message_text(
            f"🎁 **DEFAULT SIGNUP CREDITS**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Current: `{cfg.get('default_credits', 5)}` credits\n\n"
            "📌 New users will receive this many credits on first /start.\n\n"
            "Send new value (e.g. `5`):",
            parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_set_referral_credits":
        cfg = load_config()
        context.user_data["admin_action"] = "set_referral_credits"
        await q.edit_message_text(
            f"🔗 **REFERRAL CREDITS**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Current: `{cfg.get('referral_credits', 3)}` credits\n\n"
            "📌 Referrer gets this many credits per successful referral.\n\n"
            "Send new value (e.g. `3`):",
            parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_top_referrers":
        refs = load_referrals(); users = load_all_users()
        if not refs:
            await q.edit_message_text("📭 **No referrals yet.**", reply_markup=get_back_keyboard()); return
        sorted_refs = sorted(refs.items(), key=lambda x: len(x[1]), reverse=True)[:20]
        txt = f"📊 **TOP REFERRERS**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, (rid, rlist) in enumerate(sorted_refs, 1):
            au = users.get(rid, {})
            txt += f"**{i}.** {au.get('full_name','?')} (`{rid}`)\n   👥 Referrals: `{len(rlist)}`\n\n"
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=get_back_keyboard())
    # REDEEM CODES
    elif data == "admin_redeem_menu":
        txt, kb = _build_redeem_menu_view()
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)
    elif data == "admin_redeem_create":
        context.user_data["admin_action"] = "redeem_credits"
        context.user_data.pop("redeem_credits", None)
        context.user_data.pop("redeem_max_users", None)
        await q.edit_message_text(
            "🎁 **CREATE REDEEM CODE** — Step 1/2\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💰 **How many credits should this code give?**\n\n"
            "📝 Send a number (e.g. `50`, `100`, `200`):",
            parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_redeem_delete_menu":
        codes = load_redeem_codes()
        if not codes:
            txt, kb = _build_redeem_menu_view()
            await q.edit_message_text("📭 **No codes to delete.**\n\n" + txt, parse_mode="Markdown", reply_markup=kb)
            return
        txt = "🎁 **Redeem Codes — Delete**\n\n"
        txt += f"**Total:** {len(codes)}\n\n_Tap a code below to delete it:_"
        kb = []
        for code, info in codes.items():
            used = len(info.get("used_by", []))
            mx = info.get("max_users", 0)
            credits = info.get("credits", 0)
            left = max(0, mx - used)
            icon = "✅" if left > 0 else "❌"
            kb.append([InlineKeyboardButton(f"🗑️ {icon} {code} — {credits}c ({left} left)", callback_data=f"admin_redeem_del:{code}")])
        kb.append([InlineKeyboardButton("⬅️ BACK", callback_data="admin_redeem_menu")])
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("admin_redeem_del:"):
        code = data.split(":", 1)[1]
        codes = load_redeem_codes()
        if code in codes:
            codes.pop(code); save_redeem_codes(codes)
            await q.answer(f"✅ Deleted {code}", show_alert=True)
        else:
            await q.answer("❌ Code not found", show_alert=True)
        txt, kb = _build_redeem_menu_view()
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

    elif data == "admin_stats":
        ad = load_data(); tc = sum(u.get("bomb_credits",0) for u in ad.values())
        gm = load_global_mode(); gms = "🟢 ON" if gm.get("everyone_approved") else "⚪ OFF"
        pay = load_payment(); pp = load_premium_pending()
        refs = load_referrals()
        total_refs = sum(len(v) for v in refs.values())
        rc_count = len(load_redeem_codes())
        await q.edit_message_text(
            f"📊 **Stats**\n👥 Users: `{len(load_all_users())}`\n✅ Approved: `{len(load_approved())}`\n"
            f"⏳ Pending: `{len(load_pending())}`\n⭐ Premium Pending: `{len(pp)}`\n🚫 Blocked: `{len(load_blocked())}`\n"
            f"🎫 Credits: `{tc}`\n🔗 Total Referrals: `{total_refs}`\n🎟️ Redeem Codes: `{rc_count}`\n🌍 Global: **{gms}**\n💰 Payments: `{len(pay.get('methods',[]))}`\n"
            f"💎 Plans: `{len(pay.get('premium_plans',[]))}`\n📋 Logs: `{len(load_query_log())}`\n"
            f"⚙️ Custom: `{len(load_custom_buttons())}`\n💣 Bomb: `{len(BOMB_APIS) + len(load_custom_bomb_apis())}`",
            parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_usage":
        stats = load_stats()
        if not stats: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = "📈 **Usage**\n\n"
        for k, v in sorted(stats.items(), key=lambda x: x[1], reverse=True): txt += f"• {LOOKUP_TO_DISPLAY.get(k,k)}: `{v}`\n"
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_recent":
        kb = [[InlineKeyboardButton("⏱️ 1h", callback_data="recent:1h"), InlineKeyboardButton("⏱️ 2h", callback_data="recent:2h")],
              [InlineKeyboardButton("📅 1d", callback_data="recent:1d"), InlineKeyboardButton("📅 7d", callback_data="recent:7d")],
              [InlineKeyboardButton("🌐 All", callback_data="recent:all")], [InlineKeyboardButton("🔙 Return", callback_data="admin_back")]]
        await q.edit_message_text("⏰ Range:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("recent:"):
        rk = data.split(":")[1]; ranges = {"1h": 3600, "2h": 7200, "1d": 86400, "7d": 604800, "all": 10**12}
        max_sec = ranges.get(rk, 3600); users = load_all_users(); now = now_ist(); active = []
        for us, info in users.items():
            try:
                last = datetime.fromisoformat(info.get("last_seen", ""))
                if last.tzinfo is None: last = last.replace(tzinfo=IST)
                diff = (now - last).total_seconds()
                if diff <= max_sec: active.append((info, diff))
            except: pass
        if not active: await q.edit_message_text(f"📭 None in {rk}.", reply_markup=get_back_keyboard()); return
        active.sort(key=lambda x: x[1]); txt = f"⏰ **Active ({rk})** — `{len(active)}`\n\n"
        for info, diff in active[:40]:
            d = f"{int(diff)}s" if diff < 60 else f"{int(diff//60)}m" if diff < 3600 else f"{int(diff//3600)}h" if diff < 86400 else f"{int(diff//86400)}d"
            txt += f"• {info.get('full_name','?')} (`{info.get('chat_id')}`) – {d} ago\n"
        if len(txt) > 4000:
            fd = io.BytesIO(txt.encode()); fd.name = f"active_{rk}.txt"
            await q.message.reply_document(document=fd, caption=f"⏰ Active ({rk})")
            await q.edit_message_text(f"✅ Sent `{len(active)}`.", reply_markup=get_back_keyboard())
        else: await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_all_users":
        users = load_all_users()
        if not users: await q.edit_message_text("📭 No users.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton("👁️ Show List (In-Bot)", callback_data="admin_users_show:0")],
              [InlineKeyboardButton("📥 Download Full List (.txt)", callback_data="admin_users_download")],
              [InlineKeyboardButton("🔙 Return", callback_data="admin_back")]]
        await q.edit_message_text(f"👥 **ALL USERS**\n━━━━━━━━━━━━━━━━━━━━━━\n\n📊 Total: `{len(users)}`\n\nChoose:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_users_download":
        users = load_all_users()
        if not users: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = "========== ALL USERS ==========\n" + f"Generated: {now_ist().strftime('%d-%m-%Y %I:%M:%S %p IST')}\nTotal: {len(users)}\n================================\n\n"
        approved = load_approved(); pending = load_pending(); blocked = load_blocked(); admins = load_extra_admins(); data_db = load_data(); approvals = load_approvals()
        for i, (us, info) in enumerate(users.items(), 1):
            u_id = int(us)
            st = "👑 Admin" if (u_id in ADMIN_IDS or u_id in admins) else "✅ Approved" if u_id in approved else "🚫 Blocked" if u_id in blocked else "⏳ Pending" if u_id in pending else "🆕 New"
            credits = data_db.get(us, {}).get("bomb_credits", 0); a_info = approvals.get(us, {})
            exp = a_info.get("expires"); expiry = to_ist_str(exp) if exp else ("Permanent" if a_info.get("duration_days", 0) == 0 and a_info.get("approved") else "-")
            txt += (f"[{i}] {st}\n    Name: {info.get('full_name','N/A')}\n    TG ID: {u_id}\n    Username: @{info.get('username','N/A')}\n"
                    f"    Credits: {credits}\n    Expiry: {expiry}\n    Joined: {to_ist_str(info.get('first_seen',''))}\n    Last: {to_ist_str(info.get('last_seen',''))}\n{'-'*40}\n")
        fd = io.BytesIO(txt.encode('utf-8')); fd.name = f"all_users_{now_ist().strftime('%Y%m%d_%H%M')}.txt"
        await q.message.reply_document(document=fd, caption=f"👥 `{len(users)}` users", parse_mode="Markdown")
        await q.edit_message_text(f"✅ Downloaded `{len(users)}`.", reply_markup=get_back_keyboard())
    elif data.startswith("admin_users_show:"):
        page = int(data.split(":")[1]); users = load_all_users()
        if not users: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        ul = list(users.items()); ul.sort(key=lambda x: x[1].get("first_seen", ""), reverse=True)
        PER_PAGE = 6; total = max(1, (len(ul) + PER_PAGE - 1) // PER_PAGE)
        if page >= total: page = total - 1
        if page < 0: page = 0
        s_idx = page * PER_PAGE; e_idx = s_idx + PER_PAGE; pg = ul[s_idx:e_idx]
        approved = load_approved(); pending = load_pending(); blocked = load_blocked(); admins = load_extra_admins()
        data_db = load_data(); approvals = load_approvals()
        txt = f"👥 **ALL USERS** — Page `{page+1}/{total}`\n━━━━━━━━━━━━━━━━━━━━━━\n📊 Total: `{len(users)}` | Showing `{s_idx+1}-{min(e_idx, len(ul))}`\n\n"
        for i, (us, info) in enumerate(pg, start=s_idx+1):
            u_id = int(us)
            st = "👑" if (u_id in ADMIN_IDS or u_id in admins) else "✅" if u_id in approved else "🚫" if u_id in blocked else "⏳" if u_id in pending else "🆕"
            j = to_ist_str(info.get('first_seen','')).split()[0] if info.get('first_seen') else 'N/A'
            l = to_ist_str(info.get('last_seen','')).split()[0] if info.get('last_seen') else 'N/A'
            credits = data_db.get(us, {}).get("bomb_credits", 0); a = approvals.get(us, {}); exp = a.get("expires")
            expiry_short = "♾️" if a.get("duration_days", 0) == 0 and a.get("approved") else (to_ist_str(exp).split()[0] if exp else "-")
            txt += f"**{i}.** {st} **{info.get('full_name','N/A')}**\n   🆔 `{u_id}` | 🌐 @{info.get('username','N/A')}\n   💳 `{credits}` | ⏰ `{expiry_short}` | 📅 `{j}`\n\n"
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_users_show:{page-1}"))
        nav.append(InlineKeyboardButton(f"📄 {page+1}/{total}", callback_data="admin_noop"))
        if page < total - 1: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_users_show:{page+1}"))
        jump = []
        if total > 5:
            if page > 2: jump.append(InlineKeyboardButton("⏮️ First", callback_data="admin_users_show:0"))
            if page < total - 3: jump.append(InlineKeyboardButton("Last ⏭️", callback_data=f"admin_users_show:{total-1}"))
        kb = [nav]
        if jump: kb.append(jump)
        kb.append([InlineKeyboardButton("📥 Download Full List", callback_data="admin_users_download")])
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_query_view":
        log = load_query_log()
        if not log: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        lines = [f"📋 **LOGS** (`{len(log)}`)\n"]
        for e in log[-25:]: lines.append(f"🕐 `{to_ist_str(e['timestamp'])}`\n👤 {e['name']} (`{e['user_id']}`)\n🔍 {e['type'].upper()} | `{e['query']}`\n")
        txt = "\n".join(lines)
        if len(txt) > 4000: txt = txt[:4000] + "\n..."
        kb = [[InlineKeyboardButton("⬇️ Download", callback_data="admin_query_scope")], [InlineKeyboardButton("🔙 Return", callback_data="admin_back")]]
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_query_scope":
        log = load_query_log()
        if not log: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = "===== QUERY LOG =====\n\n"
        for e in log: txt += f"{to_ist_str(e['timestamp'])} | {e['name']} ({e['user_id']}) | {e['type'].upper()} | {e['query']}\n"
        fd = io.BytesIO(txt.encode()); fd.name = f"query_log_{now_ist().strftime('%Y%m%d_%H%M')}.txt"
        await q.message.reply_document(document=fd, caption=f"📄 `{len(log)}` logs")
        await q.edit_message_text(f"✅ Sent `{len(log)}`.", reply_markup=get_back_keyboard())
    # PREMIUM
    elif data == "admin_premium_pending": await premium_pending_view(q, 0)
    elif data.startswith("pp_page:"): await premium_pending_view(q, int(data.split(":")[1]))
    elif data.startswith("pp_user:"): await premium_user_view(q, data.split(":")[1])
    elif data.startswith("pp_app:"):
        parts = data.split(":"); target_uid = int(parts[1]); days = int(parts[2])
        label = "♾️ Permanent" if days == 0 else f"{days} days"
        set_approval(target_uid, days)
        try: await context.bot.send_message(chat_id=target_uid, text=f"🎉 **ACCESS GRANTED!**\n━━━━━━━━━━━━━━━━━━━━━━\n\n✅ Your account has been approved!\n⏰ Duration: **{label}**\n\nSelect any module below to begin.", parse_mode="Markdown", reply_markup=get_keyboard(target_uid))
        except: pass
        await q.answer(f"✅ Approved {label}", show_alert=True)
        await premium_user_view(q, target_uid)
    elif data.startswith("pp_rej:"):
        target_uid = int(data.split(":")[1])
        try: await context.bot.send_message(chat_id=target_uid, text="❌ **Request Rejected**\n\nContact owner for details.", parse_mode="Markdown")
        except: pass
        remove_premium_pending(target_uid); await q.answer("❌ Rejected", show_alert=True)
        await premium_pending_view(q, 0)
    elif data == "admin_premium_users_list":
        approvals = load_approvals(); users = load_all_users()
        active = []
        for uid_str, info in approvals.items():
            if info.get("approved"):
                exp = info.get("expires")
                if exp:
                    try:
                        if now_ist() >= datetime.fromisoformat(exp): continue
                    except: continue
                active.append((uid_str, info))
        if not active:
            await q.edit_message_text("📭 No active premium users.", reply_markup=get_back_keyboard()); return
        txt = f"👑 **PREMIUM USERS** ({len(active)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, (uid_str, info) in enumerate(active, 1):
            au = users.get(uid_str, {}); exp = info.get("expires"); duration_days = info.get("duration_days", 0)
            if duration_days == 0 and info.get("approved"): expiry = "♾️ Permanent"
            elif exp:
                try:
                    remaining = (datetime.fromisoformat(exp) - now_ist()).days
                    expiry = f"{to_ist_str(exp).split()[0]} ({remaining}d left)"
                except: expiry = to_ist_str(exp)
            else: expiry = "-"
            name = au.get("full_name") or "Unknown"; uname = au.get("username", "N/A")
            txt += f"**{i}.** {name}\n   🆔 `{uid_str}` | 🌐 @{uname}\n   ⏰ {expiry}\n\n"
        if len(txt) > 4000:
            fd = io.BytesIO(txt.encode()); fd.name = f"premium_users_{now_ist().strftime('%Y%m%d')}.txt"
            await q.message.reply_document(document=fd, caption=f"👑 {len(active)} premium users")
            await q.edit_message_text("✅ Sent as file.", reply_markup=get_back_keyboard())
        else: await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_premium_plans":
        pay = load_payment(); plans = pay.get("premium_plans", [])
        kb = [[InlineKeyboardButton("➕ Add Plan", callback_data="admin_plan_add")],
              [InlineKeyboardButton("🗑️ Remove Plan", callback_data="admin_plan_remove")],
              [InlineKeyboardButton("🔙 Return", callback_data="admin_back")]]
        txt = f"💎 **PREMIUM PLANS** ({len(plans)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if plans:
            for i, p in enumerate(plans, 1): txt += f"{i}. 📅 **{p.get('label','')}** – ₹`{p.get('price','0')}`\n"
        else: txt += "_No plans added yet._"
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_plan_add":
        context.user_data["admin_action"] = "plan_add_label"
        await q.edit_message_text("💎 **ADD PLAN** – 1/3\n\nSend **label** (e.g. `1 Month`):", reply_markup=get_back_keyboard())
    elif data == "admin_plan_remove":
        pay = load_payment(); plans = pay.get("premium_plans", [])
        if not plans: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton(f"🗑️ {p.get('label','?')}", callback_data=f"delplan:{i}")] for i, p in enumerate(plans)]
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🗑️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("delplan:"):
        i = int(data.split(":")[1]); pay = load_payment(); plans = pay.get("premium_plans", [])
        if 0 <= i < len(plans):
            nm = plans.pop(i).get("label", "?"); pay["premium_plans"] = plans; save_payment(pay); invalidate_menu_cache()
            await q.edit_message_text(f"🗑️ Removed `{nm}`.", reply_markup=get_back_keyboard())
    # PAYMENT
    elif data == "admin_payment_menu":
        pay = load_payment(); enabled = "✅ ON" if pay.get("enabled") else "🚫 OFF"
        cnt = len(pay.get("methods", [])); has_qr = "✅" if pay.get("qr_image_file_id") else "❌"
        kb = [[InlineKeyboardButton(f"🔘 Toggle ({enabled})", callback_data="admin_payment_toggle")],
              [InlineKeyboardButton("➕ Add Method", callback_data="admin_payment_add"), InlineKeyboardButton("📋 List", callback_data="admin_payment_list")],
              [InlineKeyboardButton("🗑️ Remove Method", callback_data="admin_payment_remove")],
              [InlineKeyboardButton("✏️ Edit Text", callback_data="admin_payment_text")],
              [InlineKeyboardButton("👁️ Preview", callback_data="admin_payment_preview")],
              [InlineKeyboardButton("🔙 Return", callback_data="admin_back")]]
        await q.edit_message_text(f"💰 **PAYMENT MANAGER**\nStatus: **{enabled}**\nMethods: `{cnt}`\nQR: {has_qr}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_payment_toggle":
        pay = load_payment(); pay["enabled"] = not pay.get("enabled", False); save_payment(pay); invalidate_menu_cache()
        s = "✅ ON" if pay["enabled"] else "🚫 OFF"
        note = "\n\n💡 ON: 'I Have Paid' shows.\n💡 OFF: Only 'Contact Owner'." if pay["enabled"] else ""
        await q.edit_message_text(f"💰 Payment: **{s}**{note}", parse_mode="Markdown", reply_markup=get_cached_menu())
    elif data == "admin_payment_add":
        context.user_data["admin_action"] = "pay_add_name"
        await q.edit_message_text("💰 **ADD PAYMENT** – 1/5\n\nSend **method name**:", reply_markup=get_back_keyboard())
    elif data == "admin_payment_list":
        pay = load_payment(); methods = pay.get("methods", [])
        if not methods: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = f"💰 **METHODS** ({len(methods)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, m in enumerate(methods, 1):
            txt += f"{i}. {m.get('emoji','💰')} **{m.get('name','')}**\n   💳 `{m.get('value','')}`\n"
            if m.get('note'): txt += f"   📝 _{m['note']}_\n"
            txt += "\n"
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_payment_remove":
        pay = load_payment(); methods = pay.get("methods", [])
        if not methods: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton(f"🗑️ {m.get('emoji','💰')} {m.get('name','')}", callback_data=f"delpay:{i}")] for i, m in enumerate(methods)]
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🗑️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("delpay:"):
        i = int(data.split(":")[1]); pay = load_payment(); methods = pay.get("methods", [])
        if 0 <= i < len(methods):
            nm = methods.pop(i).get("name", "?"); pay["methods"] = methods; save_payment(pay); invalidate_menu_cache()
            await q.edit_message_text(f"🗑️ Removed `{nm}`.", reply_markup=get_back_keyboard())
    elif data == "admin_payment_text":
        pay = load_payment(); context.user_data["admin_action"] = "pay_set_text"
        await q.edit_message_text(f"✏️ **EDIT TEXT**\n\nCurrent:\n`{pay.get('text','')}`\n\nSend new:", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_payment_preview":
        msg = build_payment_message()
        if not msg: await q.edit_message_text("📭 Disabled.", reply_markup=get_back_keyboard()); return
        await q.edit_message_text(f"👁️ **PREVIEW:**\n\n{msg}", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_autoverify":
        pv = load_payment_verify()
        av = "✅ ON" if pv.get("auto_verify_enabled", True) else "🚫 OFF"
        kb = [[InlineKeyboardButton(f"🔘 Auto-Verify: {av}", callback_data="admin_autoverify_toggle")], [InlineKeyboardButton("🔙 Return", callback_data="admin_back")]]
        await q.edit_message_text("⚙️ **AUTO-VERIFY**\n\nUser clicks 'I Paid' → Added to Premium Pending", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_autoverify_toggle":
        pv = load_payment_verify(); pv["auto_verify_enabled"] = not pv.get("auto_verify_enabled", True); save_payment_verify(pv)
        await q.edit_message_text(f"🔘 Auto-Verify: **{'✅ ON' if pv['auto_verify_enabled'] else '🚫 OFF'}**", parse_mode="Markdown", reply_markup=get_back_keyboard())
    # PREFIX MODES
    elif data == "admin_prefix_modes":
        modes = load_prefix_modes(); kb = []
        for lookup, mode in modes.items():
            display = LOOKUP_TO_DISPLAY.get(lookup, lookup)
            icon = "🔹" if mode == "with_91" else "🔸" if mode == "without_91" else "⚪"
            kb.append([InlineKeyboardButton(f"{icon} {display}: {mode}", callback_data=f"setprefix:{lookup}")])
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        txt = ("⚙️ **PREFIX MODES (91 Handling)**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
               "🔹 `with_91` → Auto-add 91\n🔸 `without_91` → Strip 91\n⚪ `as_is` → Pass as-is\n\n👇 Click to cycle:")
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("setprefix:"):
        lookup = data.split(":", 1)[1]; modes = load_prefix_modes(); cur = modes.get(lookup, "with_91")
        order = ["with_91", "without_91", "as_is"]
        nxt = order[(order.index(cur) + 1) % 3] if cur in order else "with_91"
        modes[lookup] = nxt; save_prefix_modes(modes)
        await q.answer(f"✅ {lookup}: {nxt}", show_alert=True)
        kb = []
        for lk, m in modes.items():
            display = LOOKUP_TO_DISPLAY.get(lk, lk)
            icon = "🔹" if m == "with_91" else "🔸" if m == "without_91" else "⚪"
            kb.append([InlineKeyboardButton(f"{icon} {display}: {m}", callback_data=f"setprefix:{lk}")])
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        txt = f"⚙️ **PREFIX MODES**\n\n✅ `{lookup}` → `{nxt}`"
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    # USER MGMT
    elif data == "admin_approve_duration":
        kb = [[InlineKeyboardButton("1️⃣ 1 Month", callback_data="appdur:30"), InlineKeyboardButton("2️⃣ 2 Months", callback_data="appdur:60")],
              [InlineKeyboardButton("3️⃣ 3 Months", callback_data="appdur:90"), InlineKeyboardButton("6️⃣ 6 Months", callback_data="appdur:180")],
              [InlineKeyboardButton("📅 1 Year", callback_data="appdur:365"), InlineKeyboardButton("📅 2 Years", callback_data="appdur:730")],
              [InlineKeyboardButton("♾️ Permanent", callback_data="appdur:0")],
              [InlineKeyboardButton("🔙 Return", callback_data="admin_back")]]
        await q.edit_message_text("⏰ **APPROVE WITH DURATION**", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("appdur:"):
        days = int(data.split(":")[1]); context.user_data["approve_duration"] = days; context.user_data["admin_action"] = "approve_with_duration"
        label = "♾️ Permanent" if days == 0 else f"{days} days"
        await q.edit_message_text(f"⏰ **{label}**\n\nSend **User ID(s)**:", reply_markup=get_back_keyboard())
    elif data == "admin_credit_all":
        context.user_data["admin_action"] = "credit_all_amount"
        cnt = len(load_all_users()); cur = get_global_credit_grant()
        await q.edit_message_text(f"💰 **CREDIT ALL**\n\n👥 Users: `{cnt}`\n📌 Current global: `{cur}`\n\nSend amount:", reply_markup=get_back_keyboard())
    elif data == "admin_reset_global_credit":
        set_global_credit_grant(0)
        await q.edit_message_text("🔄 **Global credit reset!**", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_find_user":
        context.user_data["admin_action"] = "find_user"
        await q.edit_message_text("🔎 Send username:", reply_markup=get_back_keyboard())
    elif data == "admin_broadcast":
        context.user_data["admin_action"] = "broadcast"
        await q.edit_message_text("📢 Send message:", reply_markup=get_back_keyboard())
    elif data == "admin_approve_menu":
        context.user_data["admin_action"] = "approve_user"
        await q.edit_message_text("✅ Send IDs:", reply_markup=get_back_keyboard())
    elif data == "admin_unapprove_menu":
        context.user_data["admin_action"] = "unapprove_user"
        await q.edit_message_text("❌ Send IDs:", reply_markup=get_back_keyboard())
    elif data == "admin_approve_all":
        gm = load_global_mode(); gm["everyone_approved"] = True; save_global_mode(gm)
        p = load_pending(); a = load_approved(); cnt = len(p)
        for u in list(p): a.add(u)
        save_approved(a); save_pending(set())
        await q.edit_message_text(f"✅ **APPROVE ALL ON**\nApproved `{cnt}`.\n🌍 Global: 🟢 ON", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_unapprove_all":
        gm = load_global_mode(); gm["everyone_approved"] = False; save_global_mode(gm)
        save_approved(set()); save_pending(set())
        await q.edit_message_text("❌ **UNAPPROVE ALL ON**\n🌍 Global: ⚪ OFF", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_block":
        context.user_data["admin_action"] = "block_id"
        await q.edit_message_text("🚫 Send IDs:", reply_markup=get_back_keyboard())
    elif data == "admin_unblock":
        context.user_data["admin_action"] = "unblock"
        await q.edit_message_text("✅ Send IDs:", reply_markup=get_back_keyboard())
    elif data == "admin_user_notes":
        context.user_data["admin_action"] = "view_notes"
        await q.edit_message_text("📝 Send User ID:", reply_markup=get_back_keyboard())
    elif data == "admin_addcredits":
        context.user_data["admin_action"] = "addcredits"
        await q.edit_message_text("🎫 Send User ID(s):", reply_markup=get_back_keyboard())
    elif data == "admin_removecredits":
        context.user_data["admin_action"] = "removecredits_id"
        await q.edit_message_text("🗑️ Send User ID(s):", reply_markup=get_back_keyboard())
    elif data == "admin_credits_list":
        all_data = load_data(); users = load_all_users()
        lines = ["💳 **CREDITS**\n"]; count = 0
        for us, ud in all_data.items():
            c = ud.get("bomb_credits", 0)
            if c > 0:
                count += 1; au = users.get(us, {})
                lines.append(f"{count}. `{us}` – {au.get('full_name') or ud.get('name','Unknown')} – 💳 `{c}`\n")
        txt = "\n".join(lines) if count > 0 else "📭 None."
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_user_details":
        context.user_data["admin_action"] = "user_details"
        await q.edit_message_text("👤 Send User ID:", reply_markup=get_back_keyboard())
    elif data == "admin_promote":
        kb = [[InlineKeyboardButton(pn, callback_data=f"promoteperm:{pk}")] for pk, pn in PERMISSION_LEVELS.items()]
        kb.append([InlineKeyboardButton("👑 Promote ALL as Full", callback_data="promoteperm:all_full")])
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("👑 **PROMOTE**", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_demote":
        context.user_data["admin_action"] = "demote_admin"
        await q.edit_message_text("🚫 Send User ID:", reply_markup=get_back_keyboard())
    elif data == "admin_list_admins":
        extra = list(load_extra_admins()); users = load_all_users(); perms = load_admin_perms()
        txt = "👑 **SUPER ADMINS**\n" + "\n".join([f"• `{a}`" for a in ADMIN_IDS])
        txt += f"\n\n👑 **EXTRA ADMINS** ({len(extra)})\n"
        if not extra: txt += "None"
        else:
            for i, a in enumerate(extra, 1):
                au = users.get(str(a), {}); perm = perms.get(str(a), "full")
                txt += f"{i}. `{a}` – {au.get('full_name','?')}\n   🔐 {PERMISSION_LEVELS.get(perm,perm)}\n\n"
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data.startswith("promoteperm:"):
        perm = data.split(":",1)[1]
        if perm == "all_full":
            apr = load_approved(); ea = load_extra_admins(); perms = load_admin_perms(); cnt = 0
            for u in apr:
                if u not in ADMIN_IDS: ea.add(u); perms[str(u)] = "full"; cnt += 1
            save_extra_admins(ea); save_admin_perms(perms)
            await q.edit_message_text(f"👑 `{cnt}` users promoted!", reply_markup=get_back_keyboard())
        else:
            context.user_data["promote_perm"] = perm; context.user_data["admin_action"] = "promote_with_perm"
            await q.edit_message_text(f"👑 {PERMISSION_LEVELS[perm]}\n\nSend User ID:", reply_markup=get_back_keyboard())
    elif data == "admin_list_approved":
        lst = list(load_approved())
        if not lst: await q.edit_message_text("📋 None.", reply_markup=get_back_keyboard()); return
        users = load_all_users(); approvals = load_approvals()
        txt = f"📋 **APPROVED** ({len(lst)})\n\n"
        for i, u in enumerate(lst, 1):
            au = users.get(str(u), {}); a_info = approvals.get(str(u), {})
            exp = a_info.get("expires"); expiry = "♾️" if a_info.get("duration_days", 0) == 0 and a_info.get("approved") else (to_ist_str(exp) if exp else "-")
            txt += f"{i}. `{u}` – {au.get('full_name','?')}\n   ⏰ {expiry}\n\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_list_pending":
        lst = list(load_pending())
        if not lst: await q.edit_message_text("📋 None.", reply_markup=get_back_keyboard()); return
        users = load_all_users()
        txt = f"⏳ **PENDING** ({len(lst)})\n\n"
        for i, u in enumerate(lst, 1):
            au = users.get(str(u), {})
            txt += f"{i}. `{u}` – {au.get('full_name','?')} (@{au.get('username','N/A')})\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_list_blocked":
        lst = list(load_blocked())
        if not lst: await q.edit_message_text("📋 None.", reply_markup=get_back_keyboard()); return
        users = load_all_users(); br = load_ban_reason()
        txt = f"🚫 **BLOCKED** ({len(lst)})\n\n"
        for i, u in enumerate(lst, 1):
            au = users.get(str(u), {}); reason = br.get(str(u), 'No reason')
            txt += f"{i}. `{u}` – {au.get('full_name','?')}\n   📌 _{reason}_\n\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_clear_logs":
        save_query_log([]); await q.edit_message_text("🗑️ Cleared.", reply_markup=get_back_keyboard())
    elif data == "admin_toggle_maintenance":
        mt = load_maintenance(); mt["enabled"] = not mt.get("enabled", False); save_maintenance(mt); invalidate_menu_cache()
        await q.edit_message_text(f"🔧 Maintenance: **{'🛠️ ON' if mt['enabled'] else '✅ OFF'}**", parse_mode="Markdown", reply_markup=get_cached_menu())
    elif data == "admin_set_owner_username":
        cfg = load_config(); context.user_data["admin_action"] = "set_owner_username"
        await q.edit_message_text(f"👤 **SET OWNER 1 USERNAME**\n\nCurrent: `@{cfg.get('owner_username','DarkWorld233')}`\n\nSend new username without @:", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_set_owner2_username":
        cfg = load_config(); context.user_data["admin_action"] = "set_owner2_username"
        await q.edit_message_text(f"👤 **SET OWNER 2 USERNAME**\n\nCurrent: `@{cfg.get('owner2_username','Hittadmin')}`\n\nSend new username without @:", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_set_welcome":
        w = load_welcome(); context.user_data["admin_action"] = "set_welcome"
        await q.edit_message_text(f"👋 **Welcome**\n\nStatus: `{'✅ ON' if w.get('enabled') else '🚫 OFF'}`\nMsg: `{w.get('message','')[:100]}`\n\nSend new (or `off`):", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_backup":
        try:
            zip_buf = io.BytesIO()
            files = [DATA_FILE, BLOCK_FILE, PENDING_FILE, APPROVED_FILE, QUERY_LOG_FILE, CUSTOM_BUTTONS_FILE, FORCE_JOIN_FILE, DM_PERMISSION_FILE, DM_MODE_FILE, ALL_USERS_FILE, EXTRA_ADMIN_FILE, HIDDEN_FIELDS_FILE, PER_BUTTON_FILE, STATS_FILE, BAN_REASON_FILE, USER_NOTES_FILE, MAINTENANCE_FILE, WELCOME_FILE, API_OVERRIDES_FILE, API_BACKUP_FILE, ADMIN_PERMS_FILE, GROUP_TRACK_FILE, GLOBAL_MODE_FILE, BOMB_APIS_FILE, HIDDEN_BUTTONS_FILE, LINK_BUTTONS_FILE, PAYMENT_FILE, APPROVALS_FILE, PAYMENT_VERIFY_FILE, PREMIUM_PENDING_FILE, CONFIG_FILE, PREFIX_MODES_FILE, REFERRAL_FILE, REDEEM_FILE]
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as z:
                for f in files:
                    if os.path.exists(f): z.write(f)
            zip_buf.seek(0); zip_buf.name = f"backup_{now_ist().strftime('%Y%m%d_%H%M%S')}.zip"
            await q.message.reply_document(document=zip_buf, caption="💾 Backup")
        except Exception as e: await q.edit_message_text(f"❌ {e}")
    # LINK / BUTTONS / BOMB
    elif data == "admin_add_link":
        context.user_data["admin_action"] = "add_link_name"
        await q.edit_message_text("🔗 **ADD LINK** – 1/4\n\nSend **button name**:", reply_markup=get_back_keyboard())
    elif data == "admin_list_links":
        lb = load_link_buttons()
        if not lb: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = f"🔗 **LINKS** ({len(lb)})\n\n"
        for n, e in lb.items(): txt += f"📛 **{n}**\n   🔘 `{e.get('btn_text','Open')}`\n   🔗 `{e.get('url','')[:60]}`\n\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_del_link":
        lb = load_link_buttons()
        if not lb: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton(f"🗑️ {n}", callback_data=f"dellink:{n}")] for n in lb.keys()]
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🗑️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("dellink:"):
        n = data[8:]; lb = load_link_buttons(); lb.pop(n, None); save_link_buttons(lb); invalidate_menu_cache()
        await q.edit_message_text(f"🗑️ Removed `{n}`.", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_add_button":
        context.user_data["admin_action"] = "add_button_name"
        await q.edit_message_text("➕ **1/3** Send button name:", reply_markup=get_back_keyboard())
    elif data == "admin_remove_button":
        cb = load_custom_buttons()
        if not cb: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton(f"🗑️ {n}", callback_data=f"delbtn_{n}")] for n in cb.keys()]
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🗑️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_delete_button":
        kb = [[InlineKeyboardButton("⚙️ Remove Custom", callback_data="admin_remove_button")],
              [InlineKeyboardButton("🎯 Hide Default", callback_data="admin_hide_default_btn")],
              [InlineKeyboardButton("👁️ Show Hidden", callback_data="admin_show_default_btn")],
              [InlineKeyboardButton("🔙 Return", callback_data="admin_back")]]
        await q.edit_message_text("🗑️ **Delete Menu**", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_hide_default_btn":
        kb = []; all_d = list(BUTTON_LOOKUP_MAP.keys()) + ["💣 Call/SMS Bomb", "👤 Owner", "ℹ️ Bot Help", "👤 My Account", "🔗 Refer & Earn", "🎟️ Redeem Code"]
        h = load_hidden_buttons()
        for d in all_d:
            if d not in h: kb.append([InlineKeyboardButton(f"🙈 {d}", callback_data=f"hidebtn:{d}")])
        for n in load_custom_buttons().keys():
            if n not in h: kb.append([InlineKeyboardButton(f"🙈 ⚙️ {n}", callback_data=f"hidebtn:{n}")])
        for n in load_link_buttons().keys():
            if n not in h: kb.append([InlineKeyboardButton(f"🙈 🔗 {n}", callback_data=f"hidebtn:{n}")])
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        if len(kb) == 1: await q.edit_message_text("📭 All hidden.", reply_markup=get_back_keyboard()); return
        await q.edit_message_text("🎯 Select to hide:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("hidebtn:"):
        n = data.split(":", 1)[1]; h = load_hidden_buttons(); h.add(n); save_hidden_buttons(h)
        await q.edit_message_text(f"🙈 `{n}` hidden.", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_show_default_btn":
        h = load_hidden_buttons()
        if not h: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton(f"👁️ {n}", callback_data=f"showbtn:{n}")] for n in h]
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("👁️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("showbtn:"):
        n = data.split(":", 1)[1]; h = load_hidden_buttons(); h.discard(n); save_hidden_buttons(h)
        await q.edit_message_text(f"👁️ `{n}` visible.", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_list_buttons":
        cb = load_custom_buttons()
        if not cb: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = "📋 **Custom Buttons:**\n\n"
        for n, i in cb.items(): txt += f"• **{n}**\n  API: `{(i.get('api') or 'No API')[:60]}`\n\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_bomb_menu":
        custom = load_custom_bomb_apis()
        kb = [[InlineKeyboardButton(f"➕ Add Bomb APIs ({len(custom)})", callback_data="admin_add_bomb_api")],
              [InlineKeyboardButton("📋 List", callback_data="admin_list_bomb_api"), InlineKeyboardButton("🗑️ Remove", callback_data="admin_remove_bomb_api")],
              [InlineKeyboardButton("🧹 Clear ALL", callback_data="admin_clear_bomb_api")],
              [InlineKeyboardButton("🔙 Return", callback_data="admin_back")]]
        await q.edit_message_text(f"💣 **BOMB API**\n📦 Default: `{len(BOMB_APIS)}`\n⚙️ Custom: `{len(custom)}`\n📊 Total: `{len(BOMB_APIS) + len(custom)}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_add_bomb_api":
        context.user_data["admin_action"] = "add_bomb_api_text"
        await q.edit_message_text("💣 **Add Bomb APIs**\n\n**Formats (auto-detect):**\n`Name | URL | METHOD | {headers} | {data}`\n`Name | URL`\n`https://api.com/send`\n\nSend now:", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_list_bomb_api":
        custom = load_custom_bomb_apis()
        if not custom: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = f"💣 **CUSTOM** ({len(custom)})\n\n"
        for i, c in enumerate(custom, 1): txt += f"**{i}. {c['name']}**\n🔗 `{c['url'][:70]}`\n📮 {c.get('method','POST')}\n\n"
        if len(txt) > 4000:
            fd = io.BytesIO(txt.encode()); fd.name = "bomb_apis.txt"
            await q.message.reply_document(document=fd, caption="💣")
            await q.edit_message_text(f"📋 `{len(custom)}` sent.", reply_markup=get_back_keyboard())
        else: await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_remove_bomb_api":
        custom = load_custom_bomb_apis()
        if not custom: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton(f"🗑️ {c['name']}", callback_data=f"delbomb:{i}")] for i, c in enumerate(custom)]
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🗑️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_clear_bomb_api":
        save_custom_bomb_apis([]); await q.edit_message_text("🧹 Cleared.", reply_markup=get_back_keyboard())
    elif data.startswith("delbomb:"):
        i = int(data.split(":")[1]); custom = load_custom_bomb_apis()
        if 0 <= i < len(custom):
            name = custom.pop(i)["name"]; save_custom_bomb_apis(custom)
            await q.edit_message_text(f"🗑️ Removed `{name}`.", reply_markup=get_back_keyboard())
    elif data == "admin_replace_api":
        context.user_data["admin_action"] = "replace_api_select"
        await q.edit_message_text("🔄 Select:", reply_markup=button_selector_keyboard("replapi"))
    elif data == "admin_undo_api":
        ov = load_api_overrides()
        if not ov: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton(f"↩️ {LOOKUP_TO_DISPLAY.get(k,k)}", callback_data=f"undoapi:{k}")] for k in ov.keys()]
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("↩️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_list_api_overrides":
        ov = load_api_overrides()
        if not ov: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = "📋 **API Overrides:**\n\n"
        for k, v in ov.items(): txt += f"• **{LOOKUP_TO_DISPLAY.get(k,k)}**\n  `{v[:80]}`\n\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_set_prompt":
        context.user_data["admin_action"] = "set_prompt_select"
        await q.edit_message_text("✏️ Select:", reply_markup=button_selector_keyboard("setprompt"))
    elif data == "admin_hide_field":
        context.user_data["admin_action"] = "hide_field_select"
        await q.edit_message_text("🙈 Select:", reply_markup=button_selector_keyboard("hidefield"))
    elif data == "admin_unhide_field":
        h = load_hidden_fields(); pb = load_per_button()
        txt = "👁️ **Global Hidden:**\n" + ("\n".join([f"• `{x}`" for x in h]) if h else "None") + "\n\n📌 **Per-Button:**\n"
        for btn, flds in pb.get("hidden", {}).items(): txt += f"• `{btn}`: {', '.join(f'`{f}`' for f in flds)}\n"
        txt += "\n\n_Send field name to unhide:_"
        context.user_data["admin_action"] = "unhide_field"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_list_hidden":
        h = load_hidden_fields(); pb = load_per_button()
        txt = "🙈 **Global:**\n" + ("\n".join([f"• `{x}`" for x in h]) if h else "None") + "\n\n📌 **Per-Button:**\n"
        for btn, flds in pb.get("hidden", {}).items(): txt += f"• `{btn}`: {', '.join(f'`{f}`' for f in flds)}\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_addword_global":
        context.user_data["admin_action"] = "set_global_addword"
        await q.edit_message_text("📝 Send text for ALL responses:", reply_markup=get_back_keyboard())
    elif data == "admin_addword_button":
        context.user_data["admin_action"] = "addword_button_select"
        await q.edit_message_text("📝 Select:", reply_markup=button_selector_keyboard("addwordbtn"))
    elif data == "admin_remove_addword":
        pb = load_per_button(); aw = pb.get("add_words", {})
        if not aw: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton(f"🗑️ {('🌍 GLOBAL' if k=='__global__' else k)}", callback_data=f"delaw:{k}")] for k in aw.keys()]
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🗑️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_list_addwords":
        pb = load_per_button(); aw = pb.get("add_words", {})
        if not aw: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = "📋 **Add Words:**\n\n"
        for k, v in aw.items():
            label = "🌍 GLOBAL" if k == "__global__" else f"📌 {LOOKUP_TO_DISPLAY.get(k,k)}"
            txt += f"{label}:\n`{v}`\n\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_setword":
        context.user_data["admin_action"] = "setword_select"
        await q.edit_message_text("🎯 Select:", reply_markup=button_selector_keyboard("setwordbtn"))
    elif data == "admin_setword_specific":
        context.user_data["admin_action"] = "setword_spec_select"
        await q.edit_message_text("🎯 Select:", reply_markup=button_selector_keyboard("setwordspecbtn"))
    elif data == "admin_remove_setword":
        kb = [[InlineKeyboardButton("🎯 Remove Specific", callback_data="remsw_spec")],
              [InlineKeyboardButton("📌 Remove Button", callback_data="remsw_button")],
              [InlineKeyboardButton("🗑️ Remove ALL", callback_data="remsw_all")],
              [InlineKeyboardButton("🔙 Return", callback_data="admin_back")]]
        await q.edit_message_text("🗑️ **Remove Set Word**", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "remsw_spec":
        pb = load_per_button(); ssw = pb.get("specific_set_words", {})
        if not ssw: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = []
        for btn, vals in ssw.items():
            for v in vals.keys(): kb.append([InlineKeyboardButton(f"🗑️ {LOOKUP_TO_DISPLAY.get(btn,btn)} | {v}", callback_data=f"delssw:{btn}|{v}")])
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🗑️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "remsw_button":
        pb = load_per_button(); sw = pb.get("set_words", {})
        if not sw: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton(f"🗑️ {LOOKUP_TO_DISPLAY.get(k,k)}", callback_data=f"delsw:{k}")] for k in sw.keys()]
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🗑️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "remsw_all":
        remove_all_set_words(); remove_all_specific_set_words()
        await q.edit_message_text("🗑️ All removed.", reply_markup=get_back_keyboard())
    elif data == "admin_json_add":
        context.user_data["admin_action"] = "json_add_select"
        await q.edit_message_text("📝 Select:", reply_markup=button_selector_keyboard("jsonadd"))
    elif data == "admin_json_remove":
        pb = load_per_button(); ja = pb.get("json_add", {})
        if not ja: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = []
        for btn, kv in ja.items():
            for k in kv.keys():
                label = "🌍 GLOBAL" if btn == "__global__" else LOOKUP_TO_DISPLAY.get(btn, btn)
                kb.append([InlineKeyboardButton(f"🗑️ {label} | {k}", callback_data=f"deljson:{btn}|{k}")])
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🗑️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_json_list":
        pb = load_per_button(); ja = pb.get("json_add", {})
        if not ja: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = "📋 **JSON Adds:**\n\n"
        for btn, kv in ja.items():
            label = "🌍 GLOBAL" if btn == "__global__" else LOOKUP_TO_DISPLAY.get(btn, btn)
            txt += f"**{label}:**\n"
            for k, v in kv.items(): txt += f"  • `{k}`: `{v}`\n"
            txt += "\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_protect_value":
        context.user_data["admin_action"] = "protect_select"
        await q.edit_message_text("🛡️ Select:", reply_markup=button_selector_keyboard("protectbtn"))
    elif data == "admin_unprotect_value":
        pb = load_per_button(); prot = pb.get("protected", {})
        if not prot: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = []
        for btn, vals in prot.items():
            for v in vals: kb.append([InlineKeyboardButton(f"🔓 {LOOKUP_TO_DISPLAY.get(btn,btn)} | {v}", callback_data=f"delprot:{btn}|{v}")])
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🔓 Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_list_protected":
        pb = load_per_button(); prot = pb.get("protected", {})
        if not prot: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = "🛡️ **Protected:**\n\n"
        for btn, vals in prot.items():
            txt += f"**{LOOKUP_TO_DISPLAY.get(btn,btn)}:**\n"
            for v in vals: txt += f"  • `{v}`\n"
            txt += "\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_group_only":
        context.user_data["admin_action"] = "grouponly_select"
        await q.edit_message_text("👥 Toggle:", reply_markup=button_selector_keyboard("grouponlybtn"))
    elif data == "admin_list_grouponly":
        pb = load_per_button(); go = pb.get("group_only", {})
        active = [k for k, v in go.items() if v]
        if not active: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = "👥 **Group-Only:**\n\n"
        for k in active: txt += f"• {LOOKUP_TO_DISPLAY.get(k,k)}\n"
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_add_forcejoin":
        context.user_data["admin_action"] = "add_forcejoin"
        await q.edit_message_text("📢 Format: `Chat_ID | Link | Name`", reply_markup=get_back_keyboard())
    elif data == "admin_remove_forcejoin":
        js = load_force_joins()
        if not js: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        kb = [[InlineKeyboardButton(f"🗑️ {j['name']}", callback_data=f"delfj_{i}")] for i, j in enumerate(js)]
        kb.append([InlineKeyboardButton("🔙 Return", callback_data="admin_back")])
        await q.edit_message_text("🗑️ Select:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "admin_list_forcejoins":
        js = load_force_joins()
        if not js: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = "📋 **Force Joins:**\n\n" + "\n".join([f"• **{j['name']}** – `{j['chat_id']}`\n  {j['link']}" for j in js])
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_grant_dm":
        context.user_data["admin_action"] = "grant_dm"
        await q.edit_message_text("🔓 Send User ID:", reply_markup=get_back_keyboard())
    elif data == "admin_revoke_dm":
        context.user_data["admin_action"] = "revoke_dm"
        await q.edit_message_text("🔒 Send User ID:", reply_markup=get_back_keyboard())
    elif data == "admin_dm_list":
        dm_users = list(load_dm_perm())
        if not dm_users: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        users = load_all_users()
        txt = f"📩 **DM GRANTED** ({len(dm_users)})\n\n"
        for i, u in enumerate(dm_users, 1):
            au = users.get(str(u), {}); txt += f"{i}. `{u}` – {au.get('full_name','?')}\n"
        await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_group_track":
        groups = load_group_track()
        if not groups: await q.edit_message_text("📭 None.", reply_markup=get_back_keyboard()); return
        txt = f"🏘️ **GROUPS** ({len(groups)})\n\n"
        for i, (cid, g) in enumerate(groups.items(), 1):
            icon = "📢" if g.get("type") == "channel" else "👥"
            txt += f"{i}. {icon} **{g.get('title','Unknown')}**\n   🆔 `{cid}`\n   📊 `{g.get('searches',0)}`\n\n"
        if len(txt) > 4000:
            fd = io.BytesIO(txt.encode()); fd.name = f"groups_{now_ist().strftime('%Y%m%d')}.txt"
            await q.message.reply_document(document=fd, caption=f"🏘️ {len(groups)}")
            await q.edit_message_text("✅ Sent.", reply_markup=get_back_keyboard())
        else: await q.edit_message_text(txt[:4000], parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data == "admin_toggle_dm":
        dm = load_dm_mode(); dm["enabled"] = not dm.get("enabled", True); save_dm_mode(dm); invalidate_menu_cache()
        await q.edit_message_text(f"📩 DM: **{'✅ ON' if dm['enabled'] else '🚫 OFF'}**", parse_mode="Markdown", reply_markup=get_cached_menu())
    elif data.startswith("hidefield:"):
        btn = data.split(":",1)[1]; context.user_data["hide_field_target"] = btn; context.user_data["admin_action"] = "hide_field_value"
        await q.edit_message_text(f"🙈 Send field for `{btn}`:", reply_markup=get_back_keyboard())
    elif data.startswith("addwordbtn:"):
        btn = data.split(":",1)[1]; context.user_data["addword_target"] = btn; context.user_data["admin_action"] = "set_button_addword"
        await q.edit_message_text(f"📝 Text for `{btn}`:", reply_markup=get_back_keyboard())
    elif data.startswith("setwordbtn:"):
        btn = data.split(":",1)[1]; context.user_data["setword_target"] = btn; context.user_data["admin_action"] = "setword_value"
        await q.edit_message_text(f"🎯 Response for `{btn}`:", reply_markup=get_back_keyboard())
    elif data.startswith("setwordspecbtn:"):
        btn = data.split(":",1)[1]; context.user_data["setword_spec_target"] = btn; context.user_data["admin_action"] = "setword_spec_value"
        await q.edit_message_text(f"🎯 `{btn}` – Send value:", reply_markup=get_back_keyboard())
    elif data.startswith("protectbtn:"):
        btn = data.split(":",1)[1]; context.user_data["protect_target"] = btn; context.user_data["admin_action"] = "protect_value"
        await q.edit_message_text(f"🛡️ Value for `{btn}`:", reply_markup=get_back_keyboard())
    elif data.startswith("grouponlybtn:"):
        btn = data.split(":",1)[1]; pb = load_per_button()
        cur = pb.get("group_only", {}).get(btn, False); set_group_only(btn, not cur)
        await q.edit_message_text(f"👥 `{btn}`: **{'✅ ON' if not cur else '🚫 OFF'}**", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif data.startswith("jsonadd:"):
        btn = data.split(":",1)[1]; context.user_data["json_add_target"] = btn; context.user_data["admin_action"] = "json_add_key"
        await q.edit_message_text(f"📝 Key for `{btn}`:", reply_markup=get_back_keyboard())
    elif data.startswith("replapi:"):
        btn = data.split(":",1)[1]; context.user_data["replace_api_target"] = btn; context.user_data["admin_action"] = "replace_api_value"
        cur = get_api_url(btn)
        await q.edit_message_text(f"🔄 **Replace `{btn}`**\n\nCurrent: `{cur}`\n\nSend new:", reply_markup=get_back_keyboard())
    elif data.startswith("undoapi:"):
        btn = data.split(":",1)[1]
        if undo_api_override(btn): await q.edit_message_text(f"↩️ Restored `{btn}`.", reply_markup=get_back_keyboard())
        else: await q.edit_message_text("❌ No backup.", reply_markup=get_back_keyboard())
    elif data.startswith("setprompt:"):
        btn = data.split(":",1)[1]; context.user_data["set_prompt_target"] = btn; context.user_data["admin_action"] = "set_prompt_value"
        cur = get_button_prompt(btn)
        await q.edit_message_text(f"✏️ **`{btn}`**\n\nCurrent:\n{cur[:200]}\n\nSend new:", reply_markup=get_back_keyboard())
    elif data.startswith("delbtn_"):
        n = data[7:]; cb = load_custom_buttons(); cb.pop(n, None); save_custom_buttons(cb); invalidate_menu_cache()
        await q.edit_message_text("🗑️ Removed.", reply_markup=get_back_keyboard())
    elif data.startswith("delfj_"):
        try:
            i = int(data[6:]); js = load_force_joins()
            if 0 <= i < len(js): js.pop(i); save_force_joins(js)
            await q.edit_message_text("🗑️ Removed.", reply_markup=get_back_keyboard())
        except: pass
    elif data.startswith("delaw:"): remove_add_word(data[6:]); await q.edit_message_text("🗑️ Removed.", reply_markup=get_back_keyboard())
    elif data.startswith("delsw:"): remove_set_word(data[6:]); await q.edit_message_text("🗑️ Removed.", reply_markup=get_back_keyboard())
    elif data.startswith("delssw:"):
        p = data[7:]
        if "|" in p: btn, v = p.split("|",1); remove_specific_set_word(btn, v)
        await q.edit_message_text("🗑️ Removed.", reply_markup=get_back_keyboard())
    elif data.startswith("delprot:"):
        p = data[8:]
        if "|" in p: btn, v = p.split("|",1); unprotect_value(btn, v)
        await q.edit_message_text("🔓 Unprotected.", reply_markup=get_back_keyboard())
    elif data.startswith("deljson:"):
        p = data[8:]
        if "|" in p: btn, k = p.split("|",1); remove_json_add(btn, k)
        await q.edit_message_text("🗑️ Removed.", reply_markup=get_back_keyboard())
    elif data == "admin_back":
        await q.edit_message_text("🛠️ **Admin Panel:**", reply_markup=get_cached_menu())

# ==================== VERIFY ====================
async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id
    if await check_force_join(uid, context):
        await q.answer("✅ Verified!", show_alert=True)
        await q.edit_message_text("✅ **Verified!**")
        await context.bot.send_message(chat_id=q.message.chat_id, text="👋 Welcome!", reply_markup=get_keyboard(uid))
    else: await q.answer("❌ Join first!", show_alert=True)

# ==================== START ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; uid = user.id

    users_before = load_all_users()
    is_new_user = str(uid) not in users_before

    if is_new_user and context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            ref_str = arg[4:]
            if ref_str.isdigit():
                referrer_id = int(ref_str)
                if referrer_id != uid:
                    try:
                        ref_credits = get_referral_credits()
                        rd = load_data()
                        rid = str(referrer_id)
                        if rid not in rd:
                            rd[rid] = {"name": "Unknown", "bomb_credits": 0, "username": None}
                        rd[rid]["bomb_credits"] = rd[rid].get("bomb_credits", 0) + ref_credits
                        rd[rid]["referral_count"] = rd[rid].get("referral_count", 0) + 1
                        save_data(rd)
                        refs = load_referrals()
                        refs.setdefault(rid, []).append({
                            "user_id": uid,
                            "name": user.full_name,
                            "username": user.username or "N/A",
                            "at": now_ist().isoformat()
                        })
                        save_referrals(refs)
                        try:
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=(f"🎉 **NEW REFERRAL!**\n━━━━━━━━━━━━━━━━━━━━━━\n"
                                      f"👤 **{user.full_name}** just joined via your link!\n"
                                      f"🆔 `{uid}`\n🌐 @{user.username or 'N/A'}\n\n"
                                      f"💳 **+`{ref_credits}` credits added to your account!**"),
                                parse_mode="Markdown"
                            )
                        except: pass
                    except Exception as e:
                        logger.error(f"Referral credit error: {e}")

    track_user(user); track_group(update.effective_chat)
    ud = get_user_data(uid, user.first_name); ud["username"] = user.username or "NoUsername"; save_data(load_data())

    mt = load_maintenance()
    if mt.get("enabled") and not is_admin(uid):
        await reply_message(update, context, mt.get("message", "🛠️ Maintenance."), include_user_tag=False); return
    if not is_admin(uid) and not await check_force_join(uid, context):
        await reply_message(update, context, "⚠️ **Verification Required!**", reply_markup=force_join_keyboard(), include_user_tag=False); return
    if uid in load_blocked():
        br = load_ban_reason().get(str(uid), "")
        msg = "⛔ **Blocked.**"
        if br: msg += f"\n\n📌 Reason: _{br}_"
        await reply_message(update, context, msg); return

    if is_admin(uid):
        await reply_message(update, context,
            "👑 **ADMIN ACCESS**\n━━━━━━━━━━━━━━━━━━━━━━\n\n🎯 **Welcome back, Commander!**\n\n"
            "**Actions:**\n• 🎛️ Manage buttons & APIs\n• 👥 Approve/Block users\n• 🎫 Grant credits\n"
            "• 💰 Manage payments\n• ⭐ Premium system\n• 🔗 Referral settings\n• 🎟️ Redeem codes\n• 🎨 Branding\n• 📊 Analytics\n\n🛠️ Select option below:",
            reply_markup=get_keyboard(uid)); return

    gm = load_global_mode()
    is_approved = is_user_approved(uid) or get_credits(uid) > 0 or gm.get("everyone_approved", False)
    if not is_approved:
        p = load_pending(); is_first = uid not in p
        if uid not in p: p.add(uid); save_pending(p)
        add_premium_pending(uid, user.username, user.full_name)
        if is_first:
            try:
                notify_txt = (f"🔔 **NEW USER STARTED BOT**\n━━━━━━━━━━━━━━━━━━━━━━\n"
                              f"👤 **Name:** {user.full_name}\n🆔 `{uid}`\n🌐 @{user.username or 'N/A'}\n"
                              f"🕐 {now_ist().strftime('%d-%m-%Y %I:%M:%S %p IST')}\n\n⭐ Added to Premium Pending.")
                kb_notify = InlineKeyboardMarkup([[InlineKeyboardButton("⭐ View Premium Pending", callback_data="admin_premium_pending")]])
                for aid in ADMIN_IDS + list(load_extra_admins()):
                    try: await context.bot.send_message(chat_id=aid, text=notify_txt, parse_mode="Markdown", reply_markup=kb_notify)
                    except: pass
            except: pass

    w = load_welcome()
    if w.get("enabled") and w.get("message") and is_approved:
        await reply_message(update, context, w["message"], reply_markup=get_keyboard(uid)); return

    a_info = load_approvals().get(str(uid), {})
    exp_txt = ""
    if a_info.get("expires"): exp_txt = f"\n⏰ **Expires:** `{to_ist_str(a_info['expires'])}`"
    elif a_info.get("duration_days", 0) == 0 and a_info.get("approved"): exp_txt = "\n⏰ **Duration:** ♾️ Permanent"
    credits = get_credits(uid)
    features = build_features_list()

    header = "🔍 **LEAK DETECTOR — INTELLIGENCE SYSTEM** 🔍\n━━━━━━━━━━━━━━━━━━━━━━"
    msg = (
        f"{header}\n\n"
        f"👤 **Welcome, {user.full_name}!**{exp_txt}\n\n"
        f"╔════════════════════════╗\n"
        f"║  💰 **YOUR CREDITS: `{credits}`**\n"
        f"╚════════════════════════╝\n\n"
        f"📋 **AVAILABLE FEATURES:**\n"
        f"{features}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 **Select any feature below to start:**"
    )

    await reply_message(update, context, msg, reply_markup=get_keyboard(uid))

# ==================== HANDLE PHOTO ====================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id): return
    if context.user_data.get("admin_action") != "pay_add_qr": return
    msg = update.message
    if not msg.photo: return
    try:
        file_id = msg.photo[-1].file_id
        pay = load_payment(); pay["qr_image_file_id"] = file_id; save_payment(pay)
        context.user_data.pop("admin_action", None); invalidate_menu_cache()
        await msg.reply_photo(photo=file_id, caption="✅ **QR Image Saved!**", reply_markup=get_back_keyboard())
    except Exception as e: await msg.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")

# ==================== HANDLE DOCUMENT ====================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id): return
    if context.user_data.get("admin_action") != "add_bomb_api_text": return
    doc = update.message.document
    if not doc: return
    if not doc.file_name.lower().endswith((".txt", ".csv", ".json", ".log")):
        await update.message.reply_text("❌ Send only `.txt/.csv/.json`", parse_mode="Markdown"); return
    try:
        file = await context.bot.get_file(doc.file_id)
        content = await file.download_as_bytearray(); text = content.decode("utf-8", errors="ignore")
        if doc.file_name.lower().endswith(".json"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    lines = []
                    for obj in parsed:
                        if isinstance(obj, dict) and "url" in obj:
                            nm = obj.get("name", obj["url"][:40]); mn = obj.get("method", "POST")
                            hd = json.dumps(obj.get("headers", {})); dt = json.dumps(obj.get("data", {"phone": "{phone}"}))
                            lines.append(f"{nm} | {obj['url']} | {mn} | {hd} | {dt}")
                    text = "\n".join(lines)
            except: pass
        result = add_bomb_apis_from_text(text)
        context.user_data.pop("admin_action", None)
        report = (f"✅ **IMPORT COMPLETE**\n✅ Added: `{result['added']}` | ⏭️ Skipped: `{result['skipped']}` | ❌ Invalid: `{result['invalid']}`\n📦 Total: `{len(load_custom_bomb_apis())}`")
        await update.message.reply_text(report, parse_mode="Markdown")
    except Exception as e: await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")

# ==================== HANDLE MESSAGE ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; uid = user.id
    chat_type = update.effective_chat.type
    text = update.message.text.strip() if update.message.text else ""
    track_user(user); track_group(update.effective_chat)

    mt = load_maintenance()
    if mt.get("enabled") and not is_admin(uid): await reply_message(update, context, mt.get("message", "🛠️ Maintenance."), include_user_tag=False); return
    if chat_type == "private" and not is_admin(uid):
        dm = load_dm_mode().get("enabled", True); dmp = load_dm_perm()
        if not dm and uid not in dmp: await reply_message(update, context, "🚫 **DM disabled.**", include_user_tag=False); return
    if not is_admin(uid) and not await check_force_join(uid, context):
        await reply_message(update, context, "⚠️ **Join Required:**", reply_markup=force_join_keyboard(), include_user_tag=False); return

    # Referral accessible without approval
    if text == "🔗 Refer & Earn":
        await show_referral_message(update, context, uid)
        return

    # Redeem Code accessible without approval
    if text == "🎟️ Redeem Code":
        context.user_data["awaiting_redeem"] = True
        await reply_message(update, context,
            "🎟️ **REDEEM CODE**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 **Send your redeem code below:**\n\n"
            "💡 _Example:_ `ABC123XY45`\n\n"
            "⚠️ Code is case-sensitive.\n"
            "✅ You'll get credits instantly!",
            include_user_tag=False)
        return

    # Handle redeem code input
    if context.user_data.get("awaiting_redeem"):
        context.user_data.pop("awaiting_redeem", None)
        code = text.strip().upper()
        codes = load_redeem_codes()
        if code not in codes:
            await reply_message(update, context, "❌ **Invalid redeem code.**\n\nPlease check and try again.", include_user_tag=False)
            return
        info = codes[code]
        used_by = info.get("used_by", [])
        max_users = info.get("max_users", 0)
        if uid in used_by:
            await reply_message(update, context, "⚠️ **You already used this code!**\n\nEach code can be used only once per user.", include_user_tag=False)
            return
        if len(used_by) >= max_users:
            await reply_message(update, context, "🔴 **This code has reached its maximum usage limit.**\n\nTry another code.", include_user_tag=False)
            return
        credits_amt = info.get("credits", 0)
        data = load_data(); uid_str = str(uid)
        if uid_str not in data:
            data[uid_str] = {"name": user.full_name, "bomb_credits": 0, "username": user.username or "N/A"}
        data[uid_str]["bomb_credits"] = data[uid_str].get("bomb_credits", 0) + credits_amt
        data[uid_str]["username"] = user.username or "N/A"
        save_data(data)
        used_by.append(uid)
        info["used_by"] = used_by
        codes[code] = info
        save_redeem_codes(codes)
        remaining_uses = max_users - len(used_by)
        new_balance = data[uid_str]["bomb_credits"]
        await reply_message(update, context,
            f"🎉 **REDEEM SUCCESSFUL!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎟️ **Code:** `{code}`\n"
            f"💰 **Added:** `+{credits_amt}` credits\n"
            f"🔥 **New Balance:** `{new_balance}` credits 🔥\n\n"
            f"📊 **Code Uses Left:** `{remaining_uses}/{max_users}`\n\n"
            f"✅ _Start using the bot now!_",
            include_user_tag=False)
        log_query(uid, user.first_name, "redeem", code)
        return

    def access():
        if is_admin(uid): return True, None, True
        if uid in load_blocked(): return False, "⛔ Blocked.", False
        gm = load_global_mode()
        if gm.get("everyone_approved", False):
            d = get_user_data(uid); return (True, d, False) if d.get("bomb_credits", 0) > 0 else (True, None, True)
        if is_user_approved(uid): return True, None, True
        d = get_user_data(uid); c = d.get("bomb_credits", 0)
        if c > 0: return True, d, False
        return False, "⛔ **Access Denied**", False

    ok, ud, perm = access()

    if not ok and not is_admin(uid):
        feature_clicked = (
            text in BUTTON_LOOKUP_MAP or
            text in load_custom_buttons() or
            text in load_link_buttons() or
            text == "💣 Call/SMS Bomb" or
            text in ["📱 Phone Lookup", "📱 Hi Tek", "🆔 Aadhar", "💳 PAN Lookup",
                     "🚗 Vehicle Lookup", "🚗 Vehicle2 Lookup", "💳 UPI Lookup",
                     "🕵️ Telegram ID Lookup", "🌍 IP Lookup", "🇵🇰 Pak Lookup",
                     "👨‍👩‍👧 Family Lookup", "📸 Instagram Lookup", "🏢 GST Lookup",
                     "📄 PAN to GST", "🏦 IFSC Lookup", "📡 Call Tower Lookup",
                     "📄 RC to PDF"]
        )
        if feature_clicked:
            await show_approval_required(update); return
        await show_approval_required(update); return

    if is_admin(uid) and context.user_data.get("admin_action"):
        a = context.user_data.get("admin_action")
        if a == "pay_add_name":
            context.user_data["pay_new_name"] = text; context.user_data["admin_action"] = "pay_add_value"
            await reply_message(update, context, f"💰 **2/5** – Name: `{text}`\n\nSend **value**:"); return
        elif a == "pay_add_value":
            context.user_data["pay_new_value"] = text; context.user_data["admin_action"] = "pay_add_emoji"
            await reply_message(update, context, f"💰 **3/5** – Send **emoji** (or `skip`):"); return
        elif a == "pay_add_emoji":
            emoji = "💰" if text.lower() == "skip" else text; context.user_data["pay_new_emoji"] = emoji
            context.user_data["admin_action"] = "pay_add_note"
            await reply_message(update, context, f"💰 **4/5** – Send **note** (or `skip`):"); return
        elif a == "pay_add_note":
            note = "" if text.lower() == "skip" else text; context.user_data["pay_new_note"] = note
            context.user_data["admin_action"] = "pay_add_qr"
            await reply_message(update, context, f"💰 **5/5** – Send **QR image** _(as photo)_ OR `skip`:"); return
        elif a == "pay_add_qr":
            if text.lower() == "skip":
                context.user_data.pop("admin_action", None)
                name = context.user_data.pop("pay_new_name", "?"); value = context.user_data.pop("pay_new_value", "")
                emoji = context.user_data.pop("pay_new_emoji", "💰"); note = context.user_data.pop("pay_new_note", "")
                pay = load_payment(); pay.setdefault("methods", []).append({"name": name, "value": value, "emoji": emoji, "note": note}); pay["enabled"] = True; save_payment(pay); invalidate_menu_cache()
                await reply_message(update, context, f"✅ **METHOD ADDED**\n\n{emoji} **{name}**\n💳 `{value}`"); return
            else: await reply_message(update, context, "📸 Send **photo** or `skip`:"); return
        elif a == "plan_add_label":
            context.user_data["plan_label"] = text; context.user_data["admin_action"] = "plan_add_price"
            await reply_message(update, context, f"💎 **2/3** – Send **price**:"); return
        elif a == "plan_add_price":
            if not text.isdigit(): await reply_message(update, context, "❌ Numeric only."); return
            context.user_data["plan_price"] = text; context.user_data["admin_action"] = "plan_add_note"
            await reply_message(update, context, f"💎 **3/3** – Send **note** (or `skip`):"); return
        elif a == "plan_add_note":
            note = "" if text.lower() == "skip" else text
            label = context.user_data.pop("plan_label", "?"); price = context.user_data.pop("plan_price", "0"); context.user_data.pop("admin_action", None)
            pay = load_payment(); pay.setdefault("premium_plans", []).append({"label": label, "price": price, "note": note}); pay["enabled"] = True; save_payment(pay); invalidate_menu_cache()
            await reply_message(update, context, f"✅ **PLAN ADDED**\n📅 {label} – ₹`{price}`"); return
        elif a == "pay_set_text":
            context.user_data.pop("admin_action", None); pay = load_payment(); pay["text"] = text; save_payment(pay)
            await reply_message(update, context, f"✅ Updated:\n\n`{text}`"); return
        elif a == "set_default_credits":
            context.user_data.pop("admin_action", None)
            if not text.isdigit(): await reply_message(update, context, "❌ Send number."); return
            cfg = load_config(); cfg["default_credits"] = int(text); save_config(cfg); invalidate_menu_cache()
            await reply_message(update, context, f"✅ **Default signup credits set to `{text}`**"); return
        elif a == "set_referral_credits":
            context.user_data.pop("admin_action", None)
            if not text.isdigit(): await reply_message(update, context, "❌ Send number."); return
            cfg = load_config(); cfg["referral_credits"] = int(text); save_config(cfg); invalidate_menu_cache()
            await reply_message(update, context, f"✅ **Referral credits set to `{text}`**"); return
        # REDEEM CODE ADMIN FLOW
        elif a == "redeem_credits":
            if not text.isdigit() or int(text) <= 0:
                await reply_message(update, context, "❌ Send a positive number."); return
            context.user_data["redeem_credits"] = int(text)
            context.user_data["admin_action"] = "redeem_max_users"
            await reply_message(update, context,
                f"🎁 **CREATE REDEEM CODE** — Step 2/2\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 Credits: `{text}`\n\n"
                f"👥 **Max how many users can use this code?**\n\n"
                f"📝 Send a number (e.g. `1`, `5`, `10`, `100`):")
            return
        elif a == "redeem_max_users":
            if not text.isdigit() or int(text) <= 0:
                await reply_message(update, context, "❌ Send a positive number."); return
            credits = context.user_data.pop("redeem_credits", 0)
            max_users = int(text)
            code = generate_redeem_code(10)
            codes = load_redeem_codes()
            codes[code] = {
                "credits": credits,
                "max_users": max_users,
                "used_by": [],
                "created_at": now_ist().isoformat(),
                "created_by": uid
            }
            save_redeem_codes(codes)
            context.user_data.pop("admin_action", None)
            txt, kb = _build_redeem_menu_view()
            await reply_message(update, context,
                f"✅ **CODE CREATED:** `{code}`\n\n" + txt,
                reply_markup=kb)
            return
        elif a == "edit_poweredby":
            context.user_data.pop("admin_action", None)
            cfg = load_config()
            if text.lower() == "default":
                cfg["powered_by"] = "✨ *Powered by {owner}*"
            else:
                cfg["powered_by"] = text
            cfg["powered_by_enabled"] = True
            save_config(cfg); invalidate_menu_cache()
            preview = powered_by_text(prefix="")
            await reply_message(update, context, f"✅ **Powered-By updated!**\n\nPreview:\n{preview}"); return
        elif a == "set_owner_username":
            context.user_data.pop("admin_action", None)
            uname = text.strip().lstrip("@")
            if not uname or " " in uname or len(uname) < 4: await reply_message(update, context, "❌ Invalid."); return
            cfg = load_config(); cfg["owner_username"] = uname; save_config(cfg)
            await reply_message(update, context, f"✅ **OWNER 1 UPDATED**\n👤 `@{uname}`\n🔗 `https://t.me/{uname}`"); return
        elif a == "set_owner2_username":
            context.user_data.pop("admin_action", None)
            uname = text.strip().lstrip("@")
            if not uname or " " in uname or len(uname) < 4: await reply_message(update, context, "❌ Invalid."); return
            cfg = load_config(); cfg["owner2_username"] = uname; save_config(cfg)
            await reply_message(update, context, f"✅ **OWNER 2 UPDATED**\n👤 `@{uname}`\n🔗 `https://t.me/{uname}`"); return
        elif a == "credit_all_amount":
            context.user_data.pop("admin_action", None)
            if not text.isdigit(): await reply_message(update, context, "❌ Send number."); return
            amt = int(text); cnt = add_credits_all(amt)
            await reply_message(update, context, f"✅ **CREDIT ALL**\n👥 Users: `{cnt}`\n💳 Each: `{amt}`"); return
        elif a == "approve_with_duration":
            context.user_data.pop("admin_action", None)
            days = context.user_data.pop("approve_duration", 30); ids = re.findall(r'\d+', text)
            if not ids: await reply_message(update, context, "❌ No IDs."); return
            label = "♾️ Permanent" if days == 0 else f"{days} days"
            for tid in ids:
                t = int(tid); set_approval(t, days)
                try: await context.bot.send_message(chat_id=t, text=f"🎉 **ACCESS GRANTED!**\n⏰ **{label}**", parse_mode="Markdown", reply_markup=get_keyboard(t))
                except: pass
            await reply_message(update, context, f"✅ **APPROVED** `{len(ids)}` for {label}"); return
        elif a == "add_bomb_api_text":
            context.user_data.pop("admin_action", None); result = add_bomb_apis_from_text(text)
            await reply_message(update, context, f"✅ Added: `{result['added']}` | ⏭️ Skipped: `{result['skipped']}` | ❌ Invalid: `{result['invalid']}`"); return
        elif a == "broadcast":
            context.user_data.pop("admin_action"); data = load_data(); cnt = 0
            for u in data:
                try: await context.bot.send_message(chat_id=int(u), text=f"📢 {text}"); cnt += 1
                except: pass
            await reply_message(update, context, f"✅ Sent `{cnt}`."); return
        elif a == "find_user":
            context.user_data.pop("admin_action"); uname = text.lstrip("@").lower(); users = load_all_users(); found = []
            for us, info in users.items():
                if info.get("username","").lower() == uname: found.append((us, info))
            if not found: await reply_message(update, context, "❌ No user."); return
            txt = f"🔎 **Found {len(found)}:**\n\n"
            for us, info in found: txt += f"• `{us}` – {info.get('full_name','?')}\n  @{info.get('username')}\n  Credits: `{get_credits(int(us))}`\n\n"
            await reply_message(update, context, txt); return
        elif a == "approve_user":
            context.user_data.pop("admin_action"); ids = re.findall(r'\d+', text)
            if not ids: await reply_message(update, context, "❌ No IDs."); return
            lst = []
            for tid in ids:
                t = int(tid); set_approval(t, 0); lst.append(str(t))
                try: await context.bot.send_message(chat_id=t, text="🎉 **Approved!**")
                except: pass
            await reply_message(update, context, f"✅ **Bulk Approved** `{len(lst)}`"); return
        elif a == "unapprove_user":
            context.user_data.pop("admin_action"); ids = re.findall(r'\d+', text)
            for tid in ids: remove_approval(int(tid))
            await reply_message(update, context, f"❌ Unapproved `{len(ids)}`."); return
        elif a == "block_id":
            context.user_data["block_targets"] = re.findall(r'\d+', text); context.user_data["admin_action"] = "block_reason"
            await reply_message(update, context, "🎫 Send reason (or `-`):"); return
        elif a == "block_reason":
            ids = context.user_data.pop("block_targets", []); context.user_data.pop("admin_action", None)
            b = load_blocked(); br = load_ban_reason()
            for tid in ids:
                t = int(tid); b.add(t)
                if text and text != "-": br[str(t)] = text
                try: await context.bot.send_message(chat_id=t, text="⛔ Blocked.")
                except: pass
            save_blocked(b); save_ban_reason(br)
            await reply_message(update, context, f"🚫 Blocked `{len(ids)}`."); return
        elif a == "view_notes" and text.isdigit():
            context.user_data["notes_target"] = int(text); context.user_data["admin_action"] = "add_note"
            t = int(text); notes = load_user_notes().get(str(t), [])
            txt = f"📝 **Notes for `{t}`:**\n\n" + ("\n".join([f"{i}. {n}" for i, n in enumerate(notes, 1)]) if notes else "None") + "\n\nSend new (or `clear`):"
            await reply_message(update, context, txt); return
        elif a == "add_note":
            t = context.user_data.pop("notes_target", None); context.user_data.pop("admin_action", None)
            if not t: return
            notes = load_user_notes()
            if text.lower() == "clear": notes.pop(str(t), None); save_user_notes(notes); await reply_message(update, context, "🗑️ Cleared."); return
            notes.setdefault(str(t), []).append(f"[{now_ist().strftime('%Y-%m-%d %H:%M')} IST] {text}")
            save_user_notes(notes); await reply_message(update, context, "📝 Added."); return
        elif a == "set_welcome":
            context.user_data.pop("admin_action"); w = load_welcome()
            if text.lower() == "off": w["enabled"] = False; save_welcome(w); await reply_message(update, context, "👋 Disabled."); return
            w["message"] = text; w["enabled"] = True; save_welcome(w)
            await reply_message(update, context, f"👋 Set:\n\n`{text}`"); return
        elif a == "unblock":
            context.user_data.pop("admin_action"); ids = re.findall(r'\d+', text)
            b = load_blocked(); br = load_ban_reason()
            for tid in ids: b.discard(int(tid)); br.pop(str(int(tid)), None)
            save_blocked(b); save_ban_reason(br)
            await reply_message(update, context, f"✅ Unblocked `{len(ids)}`."); return
        elif a == "addcredits":
            if not context.user_data.get("credit_targets"):
                ids = re.findall(r'\d+', text)
                if not ids: await reply_message(update, context, "❌ No IDs."); return
                context.user_data["credit_targets"] = ids
                await reply_message(update, context, f"🎫 Send amount:")
            else:
                if text.isdigit():
                    context.user_data.pop("admin_action"); ids = context.user_data.pop("credit_targets"); amt = int(text)
                    for tid in ids:
                        t = int(tid); add_credits(t, amt)
                        try: await context.bot.send_message(chat_id=t, text=f"🎉 +{amt} credits! Balance: `{get_credits(t)}`")
                        except: pass
                    await reply_message(update, context, f"✅ Added `{amt}` to `{len(ids)}` user(s).")
                else: await reply_message(update, context, "❌ Invalid.")
            return
        elif a == "removecredits_id":
            context.user_data.pop("admin_action"); ids = re.findall(r'\d+', text)
            for tid in ids: remove_credits(int(tid), None)
            await reply_message(update, context, f"🗑️ Removed from `{len(ids)}`."); return
        elif a == "user_details" and text.isdigit():
            context.user_data.pop("admin_action"); t = int(text)
            ud2 = get_user_data(t); au = load_all_users().get(str(t), {}); a_info = load_approvals().get(str(t), {})
            s = "✅ Approved" if is_user_approved(t) else ("🚫 Blocked" if t in load_blocked() else "⏳ Pending")
            if t in ADMIN_IDS or t in load_extra_admins(): s = "👑 Admin"
            exp_txt = ""
            if a_info.get("expires"): exp_txt = f"\n⏰ Expires: `{to_ist_str(a_info['expires'])}`"
            elif a_info.get("duration_days", 0) == 0 and a_info.get("approved"): exp_txt = "\n⏰ Permanent"
            refs_count = len(load_referrals().get(str(t), []))
            msg = (f"👤 **USER**\n\n🆔 `{t}`\n📛 {au.get('full_name','N/A')}\n🌐 @{au.get('username','N/A')}\n"
                   f"🔥 **💳 Credits: `{ud2.get('bomb_credits',0)}`** 🔥\n🔗 Referrals: `{refs_count}`\n📊 {s}{exp_txt}")
            await reply_message(update, context, msg); return
        elif a == "promote_with_perm" and text.isdigit():
            perm2 = context.user_data.pop("promote_perm", "full"); context.user_data.pop("admin_action", None)
            t = int(text)
            if t in ADMIN_IDS: await reply_message(update, context, "ℹ️ Super Admin."); return
            ea = load_extra_admins(); ea.add(t); save_extra_admins(ea); perms = load_admin_perms(); perms[str(t)] = perm2; save_admin_perms(perms)
            await reply_message(update, context, f"👑 `{t}` promoted!"); return
        elif a == "demote_admin" and text.isdigit():
            context.user_data.pop("admin_action"); t = int(text)
            if t in ADMIN_IDS: await reply_message(update, context, "⚠️ Cannot demote."); return
            ea = load_extra_admins(); ea.discard(t); save_extra_admins(ea)
            await reply_message(update, context, f"🚫 `{t}` demoted."); return
        elif a == "add_link_name":
            context.user_data["new_link_name"] = text; context.user_data["admin_action"] = "add_link_url"
            await reply_message(update, context, f"🔗 **2/4** Send **URL**:"); return
        elif a == "add_link_url":
            if not (text.startswith("http://") or text.startswith("https://")):
                await reply_message(update, context, "❌ Must start with http:// or https://"); return
            context.user_data["new_link_url"] = text; context.user_data["admin_action"] = "add_link_btn_text"
            await reply_message(update, context, f"🔗 **3/4** Send **button text**:"); return
        elif a == "add_link_btn_text":
            context.user_data["new_link_btn_text"] = text; context.user_data["admin_action"] = "add_link_message"
            await reply_message(update, context, f"🔗 **4/4** Send **message**:"); return
        elif a == "add_link_message":
            name = context.user_data.pop("new_link_name", None); url = context.user_data.pop("new_link_url", None)
            btn = context.user_data.pop("new_link_btn_text", "Open Link"); context.user_data.pop("admin_action", None)
            if not name or not url: return
            lb = load_link_buttons(); lb[name] = {"url": url, "btn_text": btn, "message": text, "created": now_ist().isoformat()}; save_link_buttons(lb); invalidate_menu_cache()
            kb = [[InlineKeyboardButton(f"🌐 {btn}", url=url)]]
            try: await context.bot.send_message(chat_id=uid, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown", disable_web_page_preview=True)
            except: pass
            await reply_message(update, context, f"✅ **LINK CREATED**\n📛 `{name}`", reply_markup=get_keyboard(uid)); return
        elif a == "add_button_name":
            context.user_data["new_button_name"] = text; context.user_data["admin_action"] = "add_button_api"
            await reply_message(update, context, f"➕ **2/3** Send API URL (`{{input}}` or `skip`):"); return
        elif a == "add_button_api":
            context.user_data["new_button_api"] = "" if text.lower() == "skip" else text; context.user_data["admin_action"] = "add_button_prompt"
            await reply_message(update, context, "➕ **3/3** Send prompt (or `default`):"); return
        elif a == "add_button_prompt":
            nm = context.user_data.pop("new_button_name", None); api = context.user_data.pop("new_button_api", ""); context.user_data.pop("admin_action", None)
            if not nm: return
            cb = load_custom_buttons(); entry = {"api": api}
            if text.lower() != "default": entry["prompt"] = text
            cb[nm] = entry; save_custom_buttons(cb); invalidate_menu_cache()
            await reply_message(update, context, f"✅ Created `{nm}`", reply_markup=get_keyboard(uid)); return
        elif a == "replace_api_value":
            target = context.user_data.pop("replace_api_target", None); context.user_data.pop("admin_action", None)
            if not target: return
            set_api_override(target, text.strip()); await reply_message(update, context, f"✅ Replaced `{target}`."); return
        elif a == "set_prompt_value":
            target = context.user_data.pop("set_prompt_target", None); context.user_data.pop("admin_action", None)
            if not target: return
            set_button_prompt(target, text); await reply_message(update, context, f"✏️ Set `{target}`."); return
        elif a == "hide_field_value":
            target = context.user_data.pop("hide_field_target", None); context.user_data.pop("admin_action", None)
            if not target: return
            if target == "__global__":
                h = load_hidden_fields(); h.add(text.strip()); save_hidden_fields(h); await reply_message(update, context, f"🙈 Hidden globally.")
            else:
                set_button_hidden_field(target, text.strip()); await reply_message(update, context, f"🙈 Hidden `{target}`.")
            return
        elif a == "set_global_addword":
            context.user_data.pop("admin_action"); set_add_word("__global__", text); await reply_message(update, context, f"📝 Global:\n\n`{text}`"); return
        elif a == "set_button_addword":
            target = context.user_data.pop("addword_target", None); context.user_data.pop("admin_action", None)
            if not target: return
            set_add_word(target, text); await reply_message(update, context, f"📝 Set `{target}`."); return
        elif a == "setword_value":
            target = context.user_data.pop("setword_target", None); context.user_data.pop("admin_action", None)
            if not target: return
            set_set_word(target, text); await reply_message(update, context, f"🎯 Set `{target}`."); return
        elif a == "setword_spec_value":
            target = context.user_data.get("setword_spec_target")
            if not target: return
            context.user_data["setword_spec_value_input"] = text; context.user_data["admin_action"] = "setword_spec_message"
            await reply_message(update, context, f"🎯 Send response:"); return
        elif a == "setword_spec_message":
            target = context.user_data.pop("setword_spec_target", None); value = context.user_data.pop("setword_spec_value_input", None); context.user_data.pop("admin_action", None)
            if not target or not value: return
            add_specific_set_word(target, value, text); await reply_message(update, context, "✅ Added"); return
        elif a == "json_add_key":
            target = context.user_data.get("json_add_target")
            if not target: return
            context.user_data["json_add_key_input"] = text; context.user_data["admin_action"] = "json_add_value"
            await reply_message(update, context, f"📝 Send value:"); return
        elif a == "json_add_value":
            target = context.user_data.pop("json_add_target", None); key = context.user_data.pop("json_add_key_input", None); context.user_data.pop("admin_action", None)
            if not target or not key: return
            set_json_add(target, key, text); await reply_message(update, context, "✅ Added"); return
        elif a == "protect_value":
            target = context.user_data.pop("protect_target", None); context.user_data.pop("admin_action", None)
            if not target: return
            protect_value(target, text); await reply_message(update, context, f"🛡️ Protected."); return
        elif a == "unhide_field":
            context.user_data.pop("admin_action"); h = load_hidden_fields()
            if text in h: h.discard(text); save_hidden_fields(h); await reply_message(update, context, f"👁️ `{text}` visible.")
            else: await reply_message(update, context, "ℹ️ Not found.")
            return
        elif a == "add_forcejoin":
            context.user_data.pop("admin_action"); parts = [x.strip() for x in text.split("|")]
            if len(parts) != 3: await reply_message(update, context, "❌ Format: `Chat_ID | Link | Name`"); return
            try: cid = int(parts[0])
            except: await reply_message(update, context, "❌ Chat ID numeric."); return
            js = load_force_joins(); js.append({"chat_id": cid, "link": parts[1], "name": parts[2]}); save_force_joins(js)
            await reply_message(update, context, f"✅ Force join added."); return
        elif a == "grant_dm" and text.isdigit():
            context.user_data.pop("admin_action"); d = load_dm_perm(); d.add(int(text)); save_dm_perm(d)
            await reply_message(update, context, f"🔓 DM granted."); return
        elif a == "revoke_dm" and text.isdigit():
            context.user_data.pop("admin_action"); d = load_dm_perm(); d.discard(int(text)); save_dm_perm(d)
            await reply_message(update, context, f"🔒 DM revoked."); return

    if text == "🛑 Stop Bomb":
        if uid in active_bombs:
            context.user_data["stop_bomb"] = True
            await reply_message(update, context, "🛑 Stopping...", reply_markup=get_keyboard(uid))
        else: await reply_message(update, context, "❌ No bomb.", reply_markup=get_keyboard(uid))
        return

    if context.user_data.get("bomb_mode"):
        context.user_data.pop("bomb_mode")
        phone = ''.join(filter(str.isdigit, text))
        if len(phone) < 10: await reply_message(update, context, "❌ 10-digit required."); return
        if uid in active_bombs: await reply_message(update, context, "⏳ Already bombing."); return
        if not perm:
            if ud["bomb_credits"] <= 0:
                await show_approval_required(update); return
            ud["bomb_credits"] -= 1; save_data(load_data()); left = ud["bomb_credits"]
        else: left = "∞"
        track_button_use("bomb")
        msg = await reply_message(update, context, f"💣 **BOMB ACTIVATED**\n📞 `{phone}`\n🎫 Left: `{left}`\n\n⏳ Press **🛑 Stop Bomb**", reply_markup=get_stop_keyboard())
        context.user_data["stop_bomb"] = False
        active_bombs[uid] = asyncio.create_task(bomb_loop(update, context, phone, msg))
        return

    if context.user_data.get("lookup_type"):
        lt = context.user_data.pop("lookup_type")
        await perform_lookup(update, context, lt, text); return

    if text in BUTTON_LOOKUP_MAP:
        lt = BUTTON_LOOKUP_MAP[text]; context.user_data["lookup_type"] = lt
        await reply_message(update, context, get_button_prompt(lt)); return

    cb = load_custom_buttons()
    if text in cb:
        if cb[text].get("api"):
            context.user_data["lookup_type"] = f"custom_{text}"
            prompt = cb[text].get("prompt") or get_button_prompt(f"custom_{text}")
            await reply_message(update, context, prompt if prompt != "📝 Send the required input:" else f"⚙️ **{text}**\n\nSend input:")
        else: await reply_message(update, context, f"⚙️ **{text}** – Info-only.")
        return

    lb_all = load_link_buttons()
    if text in lb_all:
        e = lb_all[text]; kb = [[InlineKeyboardButton(e.get("btn_text", "Open Link"), url=e["url"])]]
        try: await update.message.reply_text(e.get("message", "Click below:"), reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown", disable_web_page_preview=True)
        except: await update.message.reply_text(e.get("message", "Click below:"), reply_markup=InlineKeyboardMarkup(kb), disable_web_page_preview=True)
        return

    if text == "👤 Owner":
        cfg = load_config()
        await reply_message(update, context,
            f"👑 **OWNERS**\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Owner 1:** [{cfg.get('owner_display','?')}](https://t.me/{cfg.get('owner_username','?')})\n"
            f"👤 **Owner 2:** [{cfg.get('owner2_display','?')}](https://t.me/{cfg.get('owner2_username','?')})")
    elif text == "ℹ️ Bot Help":
        await reply_message(update, context,
            f"ℹ️ **FEATURES**\n━━━━━━━━━━━━━━━━━━━━━━\n{build_features_list()}\n\n"
            f"💳 1 credit per search\n"
            f"🔗 Refer & Earn for free credits\n"
            f"🎟️ Redeem code for instant credits"
            f"{powered_by_text()}")
    elif text == "👤 My Account":
        s = "Permanent ✅" if is_user_approved(uid) else "Credit"
        if is_admin(uid): s = "👑 Admin"
        if uid in load_blocked(): s = "🚫 Blocked"
        gm = load_global_mode()
        if gm.get("everyone_approved") and s == "Credit": s = "Global 🟢"
        a_info = load_approvals().get(str(uid), {}); exp_txt = ""
        if a_info.get("expires"): exp_txt = f"\n⏰ Expires: `{to_ist_str(a_info['expires'])}`"
        refs_count = len(load_referrals().get(str(uid), []))
        await reply_message(update, context,
            f"👤 **Account**\n🆔 `{uid}`\n📛 {user.full_name}\n🌐 @{user.username or 'N/A'}\n📊 {s}\n\n"
            f"🔥 **💳 Credits: `{get_credits(uid)}`** 🔥\n"
            f"🔗 Referrals: `{refs_count}`{exp_txt}")
    elif text == "🛠️ Bot Management" and is_admin(uid):
        await reply_message(update, context, "🛠️ **Admin Panel:**", reply_markup=get_cached_menu(), include_user_tag=False)
    elif text == "💣 Call/SMS Bomb":
        if not perm and ud["bomb_credits"] <= 0:
            await show_approval_required(update); return
        context.user_data["bomb_mode"] = True
        await reply_message(update, context, "💣 Send 10-digit number:")
    else: await reply_message(update, context, "⚠️ Select a command first.")

# ==================== CHAT MEMBER ====================
async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm = update.my_chat_member
    if not cm: return
    if cm.new_chat_member.status in ["member", "administrator", "creator"]:
        groups = load_group_track(); cid = str(cm.chat.id)
        groups[cid] = {"title": cm.chat.title or "Unknown", "type": cm.chat.type, "added_at": groups.get(cid, {}).get("added_at", now_ist().isoformat()), "searches": groups.get(cid, {}).get("searches", 0), "last_active": now_ist().isoformat()}
        save_group_track(groups); logger.info(f"Bot added: {cm.chat.title}")

# ==================== LIFECYCLE ====================
async def approval_cleanup_loop():
    while True:
        try:
            removed = cleanup_expired_approvals()
            if removed > 0: logger.info(f"🧹 Cleaned {removed}")
        except Exception as e: logger.error(f"Cleanup: {e}")
        await asyncio.sleep(3600)

async def post_init(application: Application):
    await application.bot.set_my_commands([BotCommand("start", "Launch bot"), BotCommand("addcredits", "Admin: Add credits")])
    await get_aio_session(); asyncio.create_task(approval_cleanup_loop())
    logger.info("✅ Leak Detector Bot initialized")

async def post_shutdown(application: Application): await close_aio_session()

# ==================== FLASK ====================
app_flask = Flask(__name__)
@app_flask.route("/")
def home(): return "OK"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app_flask.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)

async def addcredits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid): return
    if len(context.args) < 2: await reply_message(update, context, "⚠️ `/addcredits <id> <amt>`"); return
    try:
        t = int(context.args[0]); a = int(context.args[1]); add_credits(t, a)
        await reply_message(update, context, f"✅ +`{a}` → `{t}`. Balance: `{get_credits(t)}`")
    except: await reply_message(update, context, "❌ Invalid.")

# ==================== MAIN ====================
def main():
    threading.Thread(target=run_flask, daemon=True, name="flask").start()
    application = (Application.builder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).concurrent_updates(True).build())
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addcredits", addcredits_command))
    application.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify_join$"))
    application.add_handler(CallbackQueryHandler(rc_download_callback, pattern="^rcdl_"))
    application.add_handler(CallbackQueryHandler(my_profile_user_callback, pattern="^my_profile_user$"))
    application.add_handler(CallbackQueryHandler(ipaid_callback, pattern="^ipaid_request$"))
    application.add_handler(CallbackQueryHandler(show_referral_callback, pattern="^show_referral$"))
    application.add_handler(CallbackQueryHandler(show_ref_link_callback, pattern="^show_ref_link$"))
    application.add_handler(CallbackQueryHandler(admin_callback,
        pattern="^admin_|^delbtn_|^delfj_|^hidefield:|^addwordbtn:|^setwordbtn:|^setwordspecbtn:|"
                "^protectbtn:|^grouponlybtn:|^jsonadd:|^delaw:|^delsw:|^delssw:|^delprot:|^deljson:|"
                "^remsw_|^replapi:|^undoapi:|^setprompt:|^promoteperm:|^recent:|^delbomb:|^hidebtn:|^showbtn:|"
                "^dellink:|^delpay:|^appdur:|^pp_|^delplan:|^setprefix:"))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🔍 Leak Detector Bot running")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()