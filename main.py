import os, time, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN    = os.environ.get("BOT_TOKEN",    "8851824858:AAF2kcS0gbl2Sqv4jUkcw8yGAZhXg5dVA6U")
MINI_APP_URL = os.environ.get("MINI_APP_URL", "https://watchbuy-webapp.vercel.app/")
FB_DB_URL    = os.environ.get("FB_DB_URL",    "https://madhustore-34e3e-default-rtdb.firebaseio.com")
BOT_USERNAME = "Watchandbuyf_bot"
DEVELOPER    = "madhu"
BOT_TOKEN       =  "8851824858:AAF2kcS0gbl2Sqv4jUkcw8yGAZhXg5dVA6U"  # alias for notify calls

USERS    = "ds_users"
PRODUCTS = "ds_products"
SETTINGS = "ds_settings"
REFCODES = "ds_refCodes"
PROMOS   = "ds_promos"

# ── Firebase REST ─────────────────────────────────────────────
def fb_get(path):
    try:
        r = requests.get(f"{FB_DB_URL}/{path}.json", timeout=8)
        return r.json()
    except:
        return None

def fb_set(path, data):
    try: requests.put(f"{FB_DB_URL}/{path}.json", json=data, timeout=8)
    except: pass

def fb_patch(path, data):
    try: requests.patch(f"{FB_DB_URL}/{path}.json", json=data, timeout=8)
    except: pass

def fb_push(path, data):
    try: requests.post(f"{FB_DB_URL}/{path}.json", json=data, timeout=8)
    except: pass

# ── Keyboards ──────────────────────────────────────────────────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Open Store", web_app={"url": MINI_APP_URL})],
        [
            InlineKeyboardButton("🎫 Promo Code",  callback_data="menu_promo"),
            InlineKeyboardButton("👥 Refer & Earn", callback_data="menu_refer"),
        ],
        [
            InlineKeyboardButton("🪙 Earn Coins",  callback_data="menu_earn"),
            InlineKeyboardButton("📦 My Products",  callback_data="menu_products"),
        ],
    ])

# ── /start ────────────────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    tg_id = str(user.id)
    fname = user.first_name or "User"
    lname = user.last_name  or ""
    name  = (fname + (" " + lname if lname else "")).strip()
    photo = user.photo_url if hasattr(user, "photo_url") and user.photo_url else ""
    uid   = f"TG_{tg_id}"
    now   = int(time.time() * 1000)
    ref_code = context.args[0] if context.args else None

    existing = fb_get(f"{USERS}/{uid}")
    is_new   = not (existing and isinstance(existing, dict))

    if is_new:
        fb_set(f"{USERS}/{uid}", {
            "uid": uid, "username": name or f"User_{tg_id}", "photoUrl": photo,
            "coins": 0, "totalSpent": 0, "invites": 0, "purchases": 0,
            "lastAdWatch": 0, "createdAt": now, "role": "user"
        })
        # Handle referral
        if ref_code and len(str(ref_code)) == 8 and str(ref_code).isdigit():
            cdata = fb_get(f"{REFCODES}/{ref_code}")
            if cdata and isinstance(cdata, dict):
                ref_uid = cdata.get("uid")
                if ref_uid and ref_uid != uid:
                    sdata = fb_get(SETTINGS)
                    ref_coins = sdata.get("referralCoins", 2) if isinstance(sdata, dict) else 2
                    rd = fb_get(f"{USERS}/{ref_uid}")
                    if rd and isinstance(rd, dict):
                        fb_patch(f"{USERS}/{ref_uid}", {
                            "coins":   (rd.get("coins",  0) or 0) + ref_coins,
                            "invites": (rd.get("invites",0) or 0) + 1
                        })
                        fb_push(f"{USERS}/{ref_uid}/referralHistory", {
                            "joinedUser": name, "coins": ref_coins, "at": now
                        })
                        # Notify referrer in Telegram
                        ref_tg_id = ref_uid.replace("TG_", "")
                        notify_referrer(ref_tg_id, name, ref_coins)
                    fb_patch(f"{USERS}/{uid}", {"referredBy": ref_uid})
    else:
        ups = {}
        uname = existing.get("username", "")
        if name and (not uname or uname.startswith("User_") or uname.startswith("TG_")):
            ups["username"] = name
        if photo and not existing.get("photoUrl"):
            ups["photoUrl"] = photo
        if ups:
            fb_patch(f"{USERS}/{uid}", ups)

    # Fetch live stats
    user_data  = fb_get(f"{USERS}/{uid}") or {}
    user_coins = user_data.get("coins", 0) or 0
    products   = fb_get(PRODUCTS) or {}
    prod_count = len([k for k,v in products.items() if v.get("active")])
    purchases  = len(user_data.get("purchasedProducts", {}) or {})

    if is_new:
        intro = f"🎉 *Welcome to Watch \\& Buy, {esc_md(fname)}\\!*"
        extra = "\n\n🆕 *Your account has been created\\!*"
    else:
        intro = f"👋 *Hey {esc_md(fname)}\\! Welcome back\\!*"
        extra = ""

    await update.message.reply_text(
        f"{intro}{extra}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🪙 *Balance:* `{int(user_coins)} coins`\n"
        f"📦 *Purchased:* `{purchases} products`\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🛒 *{prod_count} products* available in store\n"
        f"📺 Watch ads \\= earn coins instantly\n"
        f"🎫 Use promo codes for bonus coins\n"
        f"👥 Invite friends \\= *2 coins* per join\n\n"
        f"👇 Tap *Open Store* to start\\!\n\n"
        f"💎 *Developed by {DEVELOPER}*",
        parse_mode="MarkdownV2",
        reply_markup=main_keyboard()
    )

# ── /refer ─────────────────────────────────────────────────────
async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    tg_id  = str(user.id)
    uid    = f"TG_{tg_id}"
    data   = fb_get(f"{USERS}/{uid}")
    if not data or not isinstance(data, dict):
        await update.message.reply_text(
            "Please open the store first to activate your account\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Open Store", web_app={"url": MINI_APP_URL})]])
        )
        return
    ref_code = data.get("refCode")
    invites  = int(data.get("invites", 0))
    earned   = invites * 2
    if not ref_code:
        await update.message.reply_text(
            "Open the store once to generate your referral code\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Open Store", web_app={"url": MINI_APP_URL})]])
        )
        return
    ref_link = f"https://t.me/{BOT_USERNAME}?start={ref_code}"
    # Referral history
    history = data.get("referralHistory", {}) or {}
    history_text = ""
    if history:
        recent = sorted(history.values(), key=lambda x: x.get("at",0), reverse=True)[:5]
        lines = [f"  • {esc_md(r.get('joinedUser','User'))} \\+{r.get('coins',2)} coins" for r in recent]
        history_text = "\n\n📋 *Recent Referrals:*\n" + "\n".join(lines)

    await update.message.reply_text(
        f"🔗 *Your Referral Link:*\n\n"
        f"`{ref_link}`\n\n"
        f"🎯 *Your Code:* `{ref_code}`\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 *Friends Invited:* `{invites}`\n"
        f"🪙 *Total Earned:* `{earned} coins`\n"
        f"━━━━━━━━━━━━━━━━━━"
        f"{history_text}\n\n"
        f"Share and earn *2 coins* per friend\\!",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share Link",
                switch_inline_query=f"🛒 Watch & Buy Digital Store!\n🪙 Earn coins & buy digital products!\n👉 {ref_link}")],
            [InlineKeyboardButton("🛒 Open Store", web_app={"url": MINI_APP_URL})]
        ])
    )

# ── /promo ─────────────────────────────────────────────────────
async def promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    tg_id = str(user.id)
    uid   = f"TG_{tg_id}"

    # If code passed: /promo XXXXXXXX
    if context.args:
        code = context.args[0].strip().upper()
        await apply_promo(update, uid, code, user.first_name or "User")
        return

    # Show promo input prompt
    await update.message.reply_text(
        "🎫 *Promo Code Redemption*\n\n"
        "Send your 8\\-digit promo code like this:\n\n"
        "`/promo XXXXXXXX`\n\n"
        "Or open the store and go to Promo Code section\\.",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Open Store", web_app={"url": MINI_APP_URL})]])
    )

async def apply_promo(update_or_msg, uid, code, fname):
    """Apply promo code — works from bot command"""
    is_update = hasattr(update_or_msg, 'message')
    send = update_or_msg.message.reply_text if is_update else update_or_msg.reply_text

    if len(code) != 8:
        await send("❌ Code must be exactly 8 characters\\!", parse_mode="MarkdownV2")
        return

    pdata = fb_get(f"{PROMOS}/{code}")
    if not pdata or not isinstance(pdata, dict):
        await send("❌ *Invalid promo code\\!*", parse_mode="MarkdownV2")
        return

    now = int(time.time() * 1000)
    if not pdata.get("active", True):
        await send("❌ *This promo code is inactive\\!*", parse_mode="MarkdownV2")
        return
    if pdata.get("expiresAt") and now > pdata["expiresAt"]:
        await send("⏰ *This promo code has expired\\!*", parse_mode="MarkdownV2")
        return
    max_uses = pdata.get("maxUses", 0)
    if max_uses > 0 and (pdata.get("usedCount", 0) or 0) >= max_uses:
        await send("🚫 *Promo code limit reached\\!*", parse_mode="MarkdownV2")
        return

    # Check already used
    udata = fb_get(f"{USERS}/{uid}") or {}
    used_promos = udata.get("usedPromos", {}) or {}
    if code in used_promos:
        await send("⚠️ *You already used this promo code\\!*", parse_mode="MarkdownV2")
        return

    # Apply
    coins_reward = pdata.get("coins", 0)
    new_bal      = int(udata.get("coins", 0) or 0) + coins_reward
    fb_patch(f"{USERS}/{uid}", {
        "coins": new_bal,
        f"usedPromos/{code}": {"coins": coins_reward, "at": now}
    })
    fb_patch(f"{PROMOS}/{code}", {"usedCount": (pdata.get("usedCount",0) or 0) + 1})

    await send(
        f"✅ *Promo Code Applied\\!*\n\n"
        f"🎫 Code: `{code}`\n"
        f"🪙 Reward: *\\+{coins_reward} coins*\n"
        f"💰 New Balance: *{new_bal} coins*\n\n"
        f"Keep earning more\\!",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Open Store", web_app={"url": MINI_APP_URL})]])
    )

# ── /balance ───────────────────────────────────────────────────
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = f"TG_{update.effective_user.id}"
    data  = fb_get(f"{USERS}/{uid}") or {}
    coins = int(data.get("coins", 0) or 0)
    purch = len(data.get("purchasedProducts", {}) or {})
    spent = int(data.get("totalSpent", 0) or 0)
    inv   = int(data.get("invites", 0) or 0)

    await update.message.reply_text(
        f"💰 *Your Account Stats*\n\n"
        f"🪙 *Coins Balance:* `{coins}`\n"
        f"📦 *Products Bought:* `{purch}`\n"
        f"💸 *Total Spent:* `{spent} coins`\n"
        f"👥 *Friends Invited:* `{inv}`\n"
        f"🎁 *Referral Earned:* `{inv * 2} coins`",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Open Store", web_app={"url": MINI_APP_URL})]])
    )

# ── /help ──────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Watch \\& Buy — Commands*\n\n"
        "/start — Open the store\n"
        "/refer — Your referral link \\& stats\n"
        "/promo \\<CODE\\> — Apply a promo code\n"
        "/balance — Your coins \\& stats\n"
        "/help — This message\n\n"
        "💡 *Tips:*\n"
        "• Watch ads in store to earn coins\n"
        "• Invite friends via /refer for 2 coins each\n"
        "• Use promo codes for bonus coins\n"
        "• Spend coins to buy digital products\n\n"
        "💎 *Developed by SovitX*",
        parse_mode="MarkdownV2",
        reply_markup=main_keyboard()
    )

# ── Notify referrer ────────────────────────────────────────────
def notify_referrer(tg_id, new_user_name, coins):
    try:
        msg = (
            f"🎉 *Referral Bonus\\!*\n\n"
            f"*{esc_md(new_user_name)}* joined using your link\\!\n\n"
            f"🪙 *\\+{coins} coins* added to your balance\\!"
        )
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": tg_id, "text": msg, "parse_mode": "MarkdownV2"},
            timeout=5
        )
    except:
        pass

# ── Callback buttons ───────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user  = query.from_user
    tg_id = str(user.id)
    uid   = f"TG_{tg_id}"
    cbd   = query.data

    if cbd == "menu_promo":
        await query.message.reply_text(
            "🎫 *Apply Promo Code*\n\n"
            "Send your code like this:\n\n"
            "`/promo XXXXXXXX`\n\n"
            "Or open store → Promo Code section\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Open Store", web_app={"url": MINI_APP_URL})]])
        )

    elif cbd == "menu_refer":
        # Reuse refer logic
        data = fb_get(f"{USERS}/{uid}") or {}
        ref_code = data.get("refCode")
        invites  = int(data.get("invites", 0))
        if not ref_code:
            await query.message.reply_text(
                "Open the store first to get your referral code\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Open Store", web_app={"url": MINI_APP_URL})]])
            )
            return
        ref_link = f"https://t.me/{BOT_USERNAME}?start={ref_code}"
        await query.message.reply_text(
            f"🔗 *Your Referral Link:*\n\n"
            f"`{ref_link}`\n\n"
            f"🎯 Code: `{ref_code}`\n"
            f"👥 Invites: `{invites}` \\| Earned: `{invites*2} coins`\n\n"
            f"Share and earn *2 coins* per friend\\!",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Share", switch_inline_query=f"🛒 Watch & Buy Store!\n👉 {ref_link}")],
                [InlineKeyboardButton("🛒 Open Store", web_app={"url": MINI_APP_URL})]
            ])
        )

    elif cbd == "menu_earn":
        data  = fb_get(f"{USERS}/{uid}") or {}
        coins = int(data.get("coins", 0) or 0)
        await query.message.reply_text(
            f"🪙 *Earn Coins*\n\n"
            f"Your balance: `{coins} coins`\n\n"
            f"📺 Open the store and tap *Earn Coins* to watch ads and earn coins\\!\n\n"
            f"💡 Each ad = 1 coin \\(admin can change this\\)",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Earn Coins Now", web_app={"url": MINI_APP_URL})]])
        )

    elif cbd == "menu_products":
        data  = fb_get(f"{USERS}/{uid}") or {}
        purch = data.get("purchasedProducts", {}) or {}
        if not purch:
            await query.message.reply_text(
                "📦 *My Products*\n\nYou haven't purchased any products yet\\.\n\nOpen the store to browse and buy\\!",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Browse Products", web_app={"url": MINI_APP_URL})]])
            )
        else:
            lines = [f"  • {esc_md(p.get('title','Product'))}" for p in list(purch.values())[:10]]
            await query.message.reply_text(
                f"📦 *My Products* \\({len(purch)}\\)\n\n" + "\n".join(lines) + "\n\nOpen store to access your products\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📦 Open My Products", web_app={"url": MINI_APP_URL})]])
            )

# ── Handle text messages with promo codes ──────────────────────
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text  = (update.message.text or "").strip().upper()
    user  = update.effective_user
    uid   = f"TG_{user.id}"
    fname = user.first_name or "User"

    # Auto-detect 8-digit code
    if len(text) == 8 and text.isdigit():
        await apply_promo(update, uid, text, fname)
        return

    # Default response
    await update.message.reply_text(
        "Use /help to see all commands\\.\n\nOr tap below to open the store\\!",
        parse_mode="MarkdownV2",
        reply_markup=main_keyboard()
    )

# ── Utils ──────────────────────────────────────────────────────
def esc_md(text):
    """Escape MarkdownV2 special chars"""
    special = r'\_*[]()~`>#+-=|{}.!'
    for ch in special:
        text = str(text).replace(ch, f'\\{ch}')
    return text

# ── Build app ──────────────────────────────────────────────────
def build_app():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start",   start_command))
    application.add_handler(CommandHandler("refer",   refer_command))
    application.add_handler(CommandHandler("promo",   promo_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("help",    help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    return application

if __name__ == "__main__":
    print(f"Starting @{BOT_USERNAME}")
    build_app().run_polling(drop_pending_updates=True)
