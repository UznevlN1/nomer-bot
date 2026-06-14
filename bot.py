import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from database import *

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8752829625:AAFX0gthY_SRn9xEE7PlvLpIsozbce3LVFI"
ADMIN_ID = 5383321037
PIXSIM_API = "https://pixsim.uz/api"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ===================== STATES =====================
class PaymentState(StatesGroup):
    waiting_amount = State()
    waiting_check = State()

class AdminState(StatesGroup):
    broadcast = State()
    add_balance_id = State()
    add_balance_amount = State()
    set_balance_amount = State()
    search_user = State()
    set_card = State()
    set_card_owner = State()
    set_referral_percent = State()
    set_price_markup = State()
    set_support = State()
    set_proof_channel = State()
    set_api_key = State()
    support_reply = State()

class SupportState(StatesGroup):
    waiting_message = State()

class SearchState(StatesGroup):
    waiting_country_name = State()

class RegisterState(StatesGroup):
    waiting_phone = State()

# ===================== HELPERS =====================
async def pixsim_request(action: str, **kwargs):
    api_key = get_setting("api_key")
    payload = {"key": api_key, "action": action, **kwargs}
    async with aiohttp.ClientSession() as session:
        async with session.post(PIXSIM_API, json=payload) as resp:
            return await resp.json()

def main_menu(user_id):
    kb = []
    kb.append([InlineKeyboardButton(text="📱 Nomer olish", callback_data="buy_number")])
    kb.append([
        InlineKeyboardButton(text="💵 Pul kiritish", callback_data="deposit"),
        InlineKeyboardButton(text="👤 Hisobim", callback_data="profile")
    ])
    kb.append([
        InlineKeyboardButton(text="🔥 Pul ishlash", callback_data="referral"),
        InlineKeyboardButton(text="📞 Murojaat", callback_data="support")
    ])
    kb.append([InlineKeyboardButton(text="📚 Qo'llanma", callback_data="guide")])
    if user_id == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="📋 Boshqaruv", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_btn(callback="main_menu"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=callback)]
    ])

REQUIRED_CHANNEL = "@vertual_raqmlar"

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status not in ["left", "kicked", "banned"]
    except:
        return False

def subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/vertual_raqmlar")],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")]
    ])

def format_phone(phone):
    if len(phone) >= 8:
        return phone[:-4] + "****"
    return phone

async def send_proof_channel(text):
    channel_id = get_setting("proof_channel_id")
    if channel_id:
        try:
            await bot.send_message(channel_id, text)
        except:
            pass

# ===================== START =====================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username or ""
    
    args = message.text.split()
    referred_by = None
    if len(args) > 1:
        try:
            referred_by = int(args[1])
            if referred_by == user_id:
                referred_by = None
        except:
            pass
    
    add_user(user_id, full_name, username, referred_by)
    user = get_user(user_id)
    balance = int(user['balance']) if user and user['balance'] else 0
    
    if not await check_subscription(user_id):
        await message.answer(
            f"👋 Assalomu alaykum, <b>{full_name}</b>!\n\n"
            f"Botdan foydalanish uchun avval kanalga a'zo bo'ling:",
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
        )
        return
    
    await show_main_menu(message, user_id, full_name, balance)

async def show_main_menu(message, user_id, full_name, balance):
    try:
        balance = int(balance)
    except:
        balance = 0
    await message.answer(
        f"👋 Assalomu alaykum, <b>{full_name}</b>!\n\n"
        f"💰 Balansingiz: <b>{balance:,} so'm</b>\n\n"
        f"📱 Virtual raqam sotib olish uchun quyidagi tugmalardan foydalaning:",
        reply_markup=main_menu(user_id),
        parse_mode="HTML"
    )

@dp.message(RegisterState.waiting_phone, F.contact)
async def register_phone(message: Message, state: FSMContext):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    
    # Check if phone already used by another user
    if phone_exists(phone):
        other_user = get_user(user_id)
        if other_user and other_user.get('phone') != phone:
            data = await state.get_data()
            await state.update_data(referred_by=None)
    
    save_phone(user_id, phone)
    await state.clear()
    user = get_user(user_id)
    
    await message.answer(
        "✅ Telefon raqam saqlandi!",
        reply_markup=ReplyKeyboardRemove()
    )
    bal = int(user['balance']) if user['balance'] else 0
    await message.answer(
        f"👋 Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n\n"
        f"💰 Balansingiz: <b>{bal:,} so'm</b>\n\n"
        f"📱 Virtual raqam sotib olish uchun quyidagi tugmalardan foydalaning:",
        reply_markup=main_menu(user_id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery):
    user_id = call.from_user.id
    if await check_subscription(user_id):
        user = get_user(user_id)
        if not user:
            add_user(user_id, call.from_user.full_name, call.from_user.username or "")
            user = get_user(user_id)
        balance = int(user['balance']) if user and user['balance'] else 0
        await call.message.edit_text(
            f"👋 Assalomu alaykum, <b>{call.from_user.full_name}</b>!\n\n"
            f"💰 Balansingiz: <b>{balance:,} so'm</b>\n\n"
            f"📱 Virtual raqam sotib olish uchun quyidagi tugmalardan foydalaning:",
            reply_markup=main_menu(user_id),
            parse_mode="HTML"
        )
    else:
        await call.answer("❌ Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(call.from_user.id)
    bal = int(user['balance']) if user['balance'] else 0
    await call.message.edit_text(
        f"👋 Assalomu alaykum, <b>{call.from_user.full_name}</b>!\n\n"
        f"💰 Balansingiz: <b>{bal:,} so'm</b>\n\n"
        f"📱 Virtual raqam sotib olish uchun quyidagi tugmalardan foydalaning:",
        reply_markup=main_menu(call.from_user.id),
        parse_mode="HTML"
    )

# ===================== BUY NUMBER =====================
@dp.callback_query(F.data == "buy_number")
async def buy_number(call: CallbackQuery):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user:
        add_user(user_id, call.from_user.full_name, call.from_user.username or "")
    await call.answer("⏳ Yuklanmoqda...")
    await show_countries(call, page=0)

async def show_countries(call: CallbackQuery, page=0):
    try:
        data = await pixsim_request("getCountries")
        if not data.get("ok"):
            await call.message.edit_text("❌ Xatolik! Qayta urining.", reply_markup=back_btn())
            return
        
        markup = int(get_setting("price_markup") or 2000)
        countries_raw = data["result"]["countries"]
        currency = data["result"].get("currency", "UZS")
        
        country_flags = {
            "UZ": "🇺🇿", "RU": "🇷🇺", "US": "🇺🇸", "KG": "🇰🇬",
            "AZ": "🇦🇿", "KZ": "🇰🇿", "TR": "🇹🇷", "DE": "🇩🇪",
            "GB": "🇬🇧", "FR": "🇫🇷", "IN": "🇮🇳", "CN": "🇨🇳",
            "JP": "🇯🇵", "KR": "🇰🇷", "BD": "🇧🇩", "PH": "🇵🇭",
            "CA": "🇨🇦", "AU": "🇦🇺", "BR": "🇧🇷", "MX": "🇲🇽",
            "QA": "🇶🇦", "AE": "🇦🇪", "SA": "🇸🇦", "KW": "🇰🇼",
            "IQ": "🇮🇶", "SY": "🇸🇾", "LB": "🇱🇧", "OM": "🇴🇲",
            "PS": "🇵🇸", "MM": "🇲🇲", "ZW": "🇿🇼", "ID": "🇮🇩",
            "PK": "🇵🇰", "NG": "🇳🇬", "ET": "🇪🇹", "EG": "🇪🇬",
            "TZ": "🇹🇿", "KE": "🇰🇪", "UG": "🇺🇬", "GH": "🇬🇭",
            "TH": "🇹🇭", "VN": "🇻🇳", "MY": "🇲🇾", "SG": "🇸🇬",
            "NP": "🇳🇵", "LK": "🇱🇰", "AF": "🇦🇫", "IR": "🇮🇷",
            "ES": "🇪🇸", "IT": "🇮🇹", "PT": "🇵🇹", "NL": "🇳🇱",
            "BE": "🇧🇪", "SE": "🇸🇪", "NO": "🇳🇴", "DK": "🇩🇰",
            "FI": "🇫🇮", "PL": "🇵🇱", "UA": "🇺🇦", "RO": "🇷🇴",
            "HU": "🇭🇺", "CZ": "🇨🇿", "SK": "🇸🇰", "GR": "🇬🇷",
            "AR": "🇦🇷", "CL": "🇨🇱", "CO": "🇨🇴", "PE": "🇵🇪",
            "VE": "🇻🇪", "EC": "🇪🇨", "BO": "🇧🇴", "PY": "🇵🇾",
            "JO": "🇯🇴", "YE": "🇾🇪", "IL": "🇮🇱", "MA": "🇲🇦",
            "DZ": "🇩🇿", "TN": "🇹🇳", "LY": "🇱🇾", "SD": "🇸🇩",
            "TJ": "🇹🇯", "TM": "🇹🇲", "GE": "🇬🇪", "AM": "🇦🇲",
            "MD": "🇲🇩", "BY": "🇧🇾", "LT": "🇱🇹", "LV": "🇱🇻",
            "EE": "🇪🇪", "MN": "🇲🇳", "KH": "🇰🇭", "LA": "🇱🇦",
            "MO": "🇲🇴", "HK": "🇭🇰", "TW": "🇹🇼", "NZ": "🇳🇿",
            "ZA": "🇿🇦", "MZ": "🇲🇿", "AO": "🇦🇴", "CM": "🇨🇲",
            "SN": "🇸🇳", "CI": "🇨🇮", "ML": "🇲🇱", "BF": "🇧🇫",
        }
        
        country_names = {
            "UZ": "O'zbekiston", "RU": "Rossiya", "US": "Amerika",
            "KG": "Qirg'iziston", "AZ": "Ozarbayjon", "KZ": "Qozog'iston",
            "TR": "Turkiya", "DE": "Germaniya", "GB": "Britaniya",
            "FR": "Fransiya", "IN": "Hindiston", "CN": "Xitoy",
            "JP": "Yaponiya", "KR": "Koreya", "BD": "Bangladesh",
            "PH": "Filippin", "CA": "Kanada", "AU": "Avstraliya",
            "BR": "Braziliya", "MX": "Meksika", "QA": "Qatar",
            "AE": "BAA", "SA": "Saudiya Arabistoni", "KW": "Quvayt",
            "IQ": "Iroq", "SY": "Suriya", "LB": "Livan", "OM": "Ummon",
            "PS": "Falastin", "MM": "Myanma", "ZW": "Zimbabve",
        }
        
        countries = []
        for code, price in countries_raw.items():
            flag = country_flags.get(code, "🌍")
            name = country_names.get(code, code)
            final_price = int(price) + int(markup)
            countries.append((code, name, flag, final_price))
        countries.sort(key=lambda x: x[3])
        
        per_page = 8
        total_pages = (len(countries) + per_page - 1) // per_page
        start = page * per_page
        end = start + per_page
        page_countries = countries[start:end]
        
        kb = []
        for code, name, flag, price in page_countries:
            kb.append([InlineKeyboardButton(
                text=f"{flag} {name} — {price:,} so'm",
                callback_data=f"country_{code}_{price}"
            )])
        
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"countries_page_{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="none"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"countries_page_{page+1}"))
        if nav:
            kb.append(nav)
        
        kb.append([
            InlineKeyboardButton(text="🏆 TOP 10", callback_data="top_countries"),
        ])
        kb.append([InlineKeyboardButton(text="🔍 Nom orqali qidirish", callback_data="search_country")])
        kb.append([InlineKeyboardButton(text="📋 Buyurtmalarim", callback_data="my_orders")])
        kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")])
        
        await call.message.edit_text(
            "🌍 <b>Davlatni tanlang:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    except Exception as e:
        await call.message.edit_text(f"❌ Xatolik: {e}", reply_markup=back_btn())

@dp.callback_query(F.data.startswith("countries_page_"))
async def countries_page(call: CallbackQuery):
    page = int(call.data.split("_")[-1])
    await show_countries(call, page)

@dp.callback_query(F.data == "top_countries")
async def top_countries(call: CallbackQuery):
    await call.answer("⏳ Yuklanmoqda...")
    try:
        data = await pixsim_request("getCountries")
        markup = int(get_setting("price_markup") or 2000)
        countries_raw = data["result"]["countries"]
        
        top_codes = ["UZ", "RU", "US", "KZ", "TR", "DE", "GB", "FR", "KG", "AZ"]
        country_flags = {
            "UZ": "🇺🇿", "RU": "🇷🇺", "US": "🇺🇸", "KG": "🇰🇬",
            "AZ": "🇦🇿", "KZ": "🇰🇿", "TR": "🇹🇷", "DE": "🇩🇪",
            "GB": "🇬🇧", "FR": "🇫🇷", "IN": "🇮🇳", "CN": "🇨🇳",
            "JP": "🇯🇵", "KR": "🇰🇷", "BD": "🇧🇩", "PH": "🇵🇭",
            "CA": "🇨🇦", "AU": "🇦🇺", "BR": "🇧🇷", "MX": "🇲🇽",
            "QA": "🇶🇦", "AE": "🇦🇪", "SA": "🇸🇦", "KW": "🇰🇼",
            "IQ": "🇮🇶", "SY": "🇸🇾", "LB": "🇱🇧", "OM": "🇴🇲",
            "PS": "🇵🇸", "MM": "🇲🇲", "ZW": "🇿🇼", "ID": "🇮🇩",
            "PK": "🇵🇰", "NG": "🇳🇬", "ET": "🇪🇹", "EG": "🇪🇬",
            "TZ": "🇹🇿", "KE": "🇰🇪", "UG": "🇺🇬", "GH": "🇬🇭",
            "TH": "🇹🇭", "VN": "🇻🇳", "MY": "🇲🇾", "SG": "🇸🇬",
            "NP": "🇳🇵", "LK": "🇱🇰", "AF": "🇦🇫", "IR": "🇮🇷",
            "ES": "🇪🇸", "IT": "🇮🇹", "PT": "🇵🇹", "NL": "🇳🇱",
            "BE": "🇧🇪", "SE": "🇸🇪", "NO": "🇳🇴", "DK": "🇩🇰",
            "FI": "🇫🇮", "PL": "🇵🇱", "UA": "🇺🇦", "RO": "🇷🇴",
            "AR": "🇦🇷", "CL": "🇨🇱", "CO": "🇨🇴", "PE": "🇵🇪",
            "JO": "🇯🇴", "YE": "🇾🇪", "IL": "🇮🇱", "MA": "🇲🇦",
            "DZ": "🇩🇿", "TN": "🇹🇳", "TJ": "🇹🇯", "TM": "🇹🇲",
            "GE": "🇬🇪", "AM": "🇦🇲", "BY": "🇧🇾", "MD": "🇲🇩",
            "MN": "🇲🇳", "KH": "🇰🇭", "ZA": "🇿🇦",
        }
        country_names = {
            "UZ": "O'zbekiston", "RU": "Rossiya", "US": "Amerika",
            "KG": "Qirg'iziston", "AZ": "Ozarbayjon", "KZ": "Qozog'iston",
            "TR": "Turkiya", "DE": "Germaniya", "GB": "Britaniya",
            "FR": "Fransiya", "IN": "Hindiston", "CN": "Xitoy",
            "JP": "Yaponiya", "KR": "Koreya", "BD": "Bangladesh",
            "PH": "Filippin", "CA": "Kanada", "AU": "Avstraliya",
            "BR": "Braziliya", "MX": "Meksika", "QA": "Qatar",
            "AE": "BAA", "SA": "Saudiya Arabistoni", "KW": "Quvayt",
            "IQ": "Iroq", "SY": "Suriya", "LB": "Livan", "OM": "Ummon",
            "PS": "Falastin", "MM": "Myanma", "ZW": "Zimbabve",
            "ID": "Indoneziya", "PK": "Pokiston", "NG": "Nigeriya",
            "ET": "Efiopiya", "EG": "Misr", "TZ": "Tanzaniya",
            "KE": "Keniya", "UG": "Uganda", "GH": "Gana",
            "TH": "Tailand", "VN": "Vyetnam", "MY": "Malayziya",
            "SG": "Singapur", "NP": "Nepal", "LK": "Shri-Lanka",
            "AF": "Afgoniston", "IR": "Eron", "ES": "Ispaniya",
            "IT": "Italiya", "PT": "Portugaliya", "NL": "Niderlandiya",
            "BE": "Belgiya", "SE": "Shvetsiya", "NO": "Norvegiya",
            "DK": "Daniya", "FI": "Finlandiya", "PL": "Polsha",
            "UA": "Ukraina", "RO": "Ruminiya", "AR": "Argentina",
            "CL": "Chili", "CO": "Kolumbiya", "PE": "Peru",
            "JO": "Iordaniya", "YE": "Yaman", "IL": "Isroil",
            "MA": "Marokash", "DZ": "Jazoir", "TN": "Tunis",
            "TJ": "Tojikiston", "TM": "Turkmaniston", "GE": "Gruziya",
            "AM": "Armaniston", "BY": "Belarus", "MD": "Moldova",
            "MN": "Moguliston", "KH": "Kambodja", "ZA": "Janubiy Afrika",
        }
        
        kb = []
        for code in top_codes:
            if code in countries_raw:
                price = int(countries_raw[code]) + int(markup)
                flag = country_flags.get(code, "🌍")
                name = country_names.get(code, code)
                kb.append([InlineKeyboardButton(
                    text=f"{flag} {name} — {price:,} so'm",
                    callback_data=f"country_{code}_{price}"
                )])
        
        kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="buy_number")])
        await call.message.edit_text(
            "🏆 <b>TOP 10 davlatlar:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    except Exception as e:
        await call.message.edit_text(f"❌ Xatolik: {e}", reply_markup=back_btn("buy_number"))

@dp.callback_query(F.data == "cheap_countries")
async def cheap_countries(call: CallbackQuery):
    await call.answer("⏳ Yuklanmoqda...")
    try:
        data = await pixsim_request("getCountries")
        markup_val = int(get_setting("price_markup") or 2000)
        countries_raw = data["result"]["countries"]
        
        country_flags = {
            "UZ": "🇺🇿", "RU": "🇷🇺", "US": "🇺🇸", "KG": "🇰🇬",
            "AZ": "🇦🇿", "KZ": "🇰🇿", "TR": "🇹🇷", "DE": "🇩🇪",
            "GB": "🇬🇧", "FR": "🇫🇷", "IN": "🇮🇳", "CN": "🇨🇳",
            "JP": "🇯🇵", "KR": "🇰🇷", "BD": "🇧🇩", "PH": "🇵🇭",
            "CA": "🇨🇦", "AU": "🇦🇺", "BR": "🇧🇷", "MX": "🇲🇽",
            "QA": "🇶🇦", "AE": "🇦🇪", "SA": "🇸🇦", "KW": "🇰🇼",
            "IQ": "🇮🇶", "SY": "🇸🇾", "LB": "🇱🇧", "OM": "🇴🇲",
            "PS": "🇵🇸", "MM": "🇲🇲", "ZW": "🇿🇼", "ID": "🇮🇩",
            "PK": "🇵🇰", "NG": "🇳🇬", "ET": "🇪🇹", "EG": "🇪🇬",
            "TZ": "🇹🇿", "KE": "🇰🇪", "UG": "🇺🇬", "GH": "🇬🇭",
            "TH": "🇹🇭", "VN": "🇻🇳", "MY": "🇲🇾", "SG": "🇸🇬",
            "NP": "🇳🇵", "LK": "🇱🇰", "AF": "🇦🇫", "IR": "🇮🇷",
            "ES": "🇪🇸", "IT": "🇮🇹", "PT": "🇵🇹", "NL": "🇳🇱",
            "BE": "🇧🇪", "SE": "🇸🇪", "NO": "🇳🇴", "DK": "🇩🇰",
            "FI": "🇫🇮", "PL": "🇵🇱", "UA": "🇺🇦", "RO": "🇷🇴",
            "AR": "🇦🇷", "CL": "🇨🇱", "CO": "🇨🇴", "PE": "🇵🇪",
            "JO": "🇯🇴", "YE": "🇾🇪", "IL": "🇮🇱", "MA": "🇲🇦",
            "DZ": "🇩🇿", "TN": "🇹🇳", "TJ": "🇹🇯", "TM": "🇹🇲",
            "GE": "🇬🇪", "AM": "🇦🇲", "BY": "🇧🇾", "MD": "🇲🇩",
            "MN": "🇲🇳", "KH": "🇰🇭", "ZA": "🇿🇦",
        }
        country_names = {
            "UZ": "O'zbekiston", "RU": "Rossiya", "US": "Amerika",
            "KG": "Qirg'iziston", "AZ": "Ozarbayjon", "KZ": "Qozog'iston",
            "TR": "Turkiya", "DE": "Germaniya", "GB": "Britaniya",
            "FR": "Fransiya", "IN": "Hindiston", "CN": "Xitoy",
            "JP": "Yaponiya", "KR": "Koreya", "BD": "Bangladesh",
            "PH": "Filippin", "CA": "Kanada", "AU": "Avstraliya",
            "BR": "Braziliya", "MX": "Meksika", "QA": "Qatar",
            "AE": "BAA", "SA": "Saudiya Arabistoni", "KW": "Quvayt",
            "IQ": "Iroq", "SY": "Suriya", "LB": "Livan", "OM": "Ummon",
            "PS": "Falastin", "MM": "Myanma", "ZW": "Zimbabve",
            "ID": "Indoneziya", "PK": "Pokiston", "NG": "Nigeriya",
            "ET": "Efiopiya", "EG": "Misr", "TZ": "Tanzaniya",
            "KE": "Keniya", "UG": "Uganda", "GH": "Gana",
            "TH": "Tailand", "VN": "Vyetnam", "MY": "Malayziya",
            "SG": "Singapur", "NP": "Nepal", "LK": "Shri-Lanka",
            "AF": "Afgoniston", "IR": "Eron", "ES": "Ispaniya",
            "IT": "Italiya", "PT": "Portugaliya", "NL": "Niderlandiya",
            "BE": "Belgiya", "SE": "Shvetsiya", "NO": "Norvegiya",
            "DK": "Daniya", "FI": "Finlandiya", "PL": "Polsha",
            "UA": "Ukraina", "RO": "Ruminiya", "AR": "Argentina",
            "CL": "Chili", "CO": "Kolumbiya", "PE": "Peru",
            "JO": "Iordaniya", "YE": "Yaman", "IL": "Isroil",
            "MA": "Marokash", "DZ": "Jazoir", "TN": "Tunis",
            "TJ": "Tojikiston", "TM": "Turkmaniston", "GE": "Gruziya",
            "AM": "Armaniston", "BY": "Belarus", "MD": "Moldova",
            "MN": "Moguliston", "KH": "Kambodja", "ZA": "Janubiy Afrika",
        }
        
        sorted_countries = sorted(countries_raw.items(), key=lambda x: x[1])[:10]
        
        kb = []
        for code, price in sorted_countries:
            final_price = int(price) + int(markup_val)
            flag = country_flags.get(code, "🌍")
            name = country_names.get(code, code)
            kb.append([InlineKeyboardButton(
                text=f"{flag} {name} — {final_price:,} so'm",
                callback_data=f"country_{code}_{final_price}"
            )])
        
        kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="buy_number")])
        await call.message.edit_text(
            "💰 <b>Eng arzon davlatlar:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    except Exception as e:
        await call.message.edit_text(f"❌ Xatolik: {e}", reply_markup=back_btn("buy_number"))

@dp.callback_query(F.data == "search_country")
async def search_country_cb(call: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_country_name)
    await call.message.edit_text(
        "🔍 Davlat nomini kiriting:\n\n"
        "Masalan: <b>Rossiya</b>, <b>Amerika</b>, <b>Turkiya</b>",
        reply_markup=back_btn("buy_number"),
        parse_mode="HTML"
    )

@dp.message(SearchState.waiting_country_name)
async def search_country_result(message: Message, state: FSMContext):
    query = message.text.strip().lower()
    await state.clear()
    
    try:
        data = await pixsim_request("getCountries")
        markup_val = int(get_setting("price_markup") or 2000)
        countries_raw = data["result"]["countries"]
        
        country_flags = {
            "UZ": "🇺🇿", "RU": "🇷🇺", "US": "🇺🇸", "KG": "🇰🇬",
            "AZ": "🇦🇿", "KZ": "🇰🇿", "TR": "🇹🇷", "DE": "🇩🇪",
            "GB": "🇬🇧", "FR": "🇫🇷", "IN": "🇮🇳", "BD": "🇧🇩",
            "MM": "🇲🇲", "ZW": "🇿🇼", "PH": "🇵🇭", "CA": "🇨🇦",
            "QA": "🇶🇦", "AE": "🇦🇪", "SA": "🇸🇦", "KW": "🇰🇼",
            "IQ": "🇮🇶", "SY": "🇸🇾", "LB": "🇱🇧", "OM": "🇴🇲",
            "PS": "🇵🇸", "JP": "🇯🇵", "KR": "🇰🇷", "CN": "🇨🇳",
        }
        country_names = {
            "UZ": "O'zbekiston", "RU": "Rossiya", "US": "Amerika",
            "KG": "Qirg'iziston", "AZ": "Ozarbayjon", "KZ": "Qozog'iston",
            "TR": "Turkiya", "DE": "Germaniya", "GB": "Britaniya",
            "FR": "Fransiya", "IN": "Hindiston", "CN": "Xitoy",
            "JP": "Yaponiya", "KR": "Koreya", "BD": "Bangladesh",
            "PH": "Filippin", "CA": "Kanada", "AU": "Avstraliya",
            "BR": "Braziliya", "MX": "Meksika", "QA": "Qatar",
            "AE": "BAA", "SA": "Saudiya Arabistoni", "KW": "Quvayt",
            "IQ": "Iroq", "SY": "Suriya", "LB": "Livan", "OM": "Ummon",
            "PS": "Falastin", "MM": "Myanma", "ZW": "Zimbabve",
            "ID": "Indoneziya", "PK": "Pokiston", "NG": "Nigeriya",
            "ET": "Efiopiya", "EG": "Misr", "TZ": "Tanzaniya",
            "KE": "Keniya", "UG": "Uganda", "GH": "Gana",
            "TH": "Tailand", "VN": "Vyetnam", "MY": "Malayziya",
            "SG": "Singapur", "NP": "Nepal", "LK": "Shri-Lanka",
            "AF": "Afgʻoniston", "IR": "Eron", "ES": "Ispaniya",
            "IT": "Italiya", "PT": "Portugaliya", "NL": "Niderlandiya",
            "BE": "Belgiya", "SE": "Shvetsiya", "NO": "Norvegiya",
            "DK": "Daniya", "FI": "Finlandiya", "PL": "Polsha",
            "UA": "Ukraina", "RO": "Ruminiya", "HU": "Vengriya",
            "CZ": "Chexiya", "SK": "Slovakiya", "GR": "Gretsiya",
            "AR": "Argentina", "CL": "Chili", "CO": "Kolumbiya",
            "PE": "Peru", "VE": "Venesuela", "EC": "Ekvador",
            "BO": "Boliviya", "PY": "Paragvay", "JO": "Iordaniya",
            "YE": "Yaman", "IL": "Isroil", "MA": "Marokash",
            "DZ": "Jazoir", "TN": "Tunis", "LY": "Liviya",
            "SD": "Sudan", "TJ": "Tojikiston", "TM": "Turkmaniston",
            "GE": "Gruziya", "AM": "Armaniston", "MD": "Moldova",
            "BY": "Belarus", "LT": "Litva", "LV": "Latviya",
            "EE": "Estoniya", "MN": "Mo'g'uliston", "KH": "Kambodja",
            "LA": "Laos", "MO": "Makao", "HK": "Gonkong",
            "TW": "Tayvan", "NZ": "Yangi Zelandiya", "ZA": "Janubiy Afrika",
            "MZ": "Mozambik", "AO": "Angola", "CM": "Kamerun",
            "SN": "Senegal", "CI": "Kot-d'Ivuar", "ML": "Mali",
            "BF": "Burkina-Faso",
        }
        
        results = []
        for code, price in countries_raw.items():
            name = country_names.get(code, code)
            if query in name.lower() or query in code.lower():
                flag = country_flags.get(code, "🌍")
                final_price = int(price) + int(markup_val)
                results.append((code, name, flag, final_price))
        
        if not results:
            await message.answer(
                f"❌ '<b>{message.text}</b>' bo'yicha natija topilmadi.",
                reply_markup=back_btn("buy_number"),
                parse_mode="HTML"
            )
            return
        
        kb = []
        for code, name, flag, price in results[:10]:
            kb.append([InlineKeyboardButton(
                text=f"{flag} {name} — {price:,} so'm",
                callback_data=f"country_{code}_{price}"
            )])
        kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="buy_number")])
        
        await message.answer(
            f"🔍 <b>'{message.text}'</b> bo'yicha natijalar:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}", reply_markup=back_btn("buy_number"))

@dp.callback_query(F.data.startswith("country_"))
async def select_country(call: CallbackQuery):
    parts = call.data.split("_")
    country_code = parts[1]
    price = int(parts[2])
    
    user = get_user(call.from_user.id)
    
    country_flags = {
        "UZ": "🇺🇿", "RU": "🇷🇺", "US": "🇺🇸", "KG": "🇰🇬",
        "AZ": "🇦🇿", "KZ": "🇰🇿", "TR": "🇹🇷", "DE": "🇩🇪",
        "GB": "🇬🇧", "FR": "🇫🇷", "IN": "🇮🇳", "CN": "🇨🇳",
        "JP": "🇯🇵", "KR": "🇰🇷", "BD": "🇧🇩", "PH": "🇵🇭",
        "CA": "🇨🇦", "AU": "🇦🇺", "BR": "🇧🇷", "MX": "🇲🇽",
        "QA": "🇶🇦", "AE": "🇦🇪", "SA": "🇸🇦", "KW": "🇰🇼",
        "IQ": "🇮🇶", "SY": "🇸🇾", "LB": "🇱🇧", "OM": "🇴🇲",
        "PS": "🇵🇸", "MM": "🇲🇲", "ZW": "🇿🇼", "ID": "🇮🇩",
        "PK": "🇵🇰", "NG": "🇳🇬", "ET": "🇪🇹", "EG": "🇪🇬",
        "TH": "🇹🇭", "VN": "🇻🇳", "MY": "🇲🇾", "SG": "🇸🇬",
        "ES": "🇪🇸", "IT": "🇮🇹", "PT": "🇵🇹", "NL": "🇳🇱",
        "PL": "🇵🇱", "UA": "🇺🇦", "AR": "🇦🇷", "CL": "🇨🇱",
        "JO": "🇯🇴", "YE": "🇾🇪", "MA": "🇲🇦", "DZ": "🇩🇿",
        "TJ": "🇹🇯", "TM": "🇹🇲", "GE": "🇬🇪", "AM": "🇦🇲",
        "BY": "🇧🇾", "IR": "🇮🇷", "ZA": "🇿🇦", "KH": "🇰🇭",
    }
    country_names = {
        "UZ": "O'zbekiston", "RU": "Rossiya", "US": "Amerika",
        "KG": "Qirg'iziston", "AZ": "Ozarbayjon", "KZ": "Qozog'iston",
        "TR": "Turkiya", "DE": "Germaniya", "GB": "Britaniya",
        "FR": "Fransiya", "IN": "Hindiston", "CN": "Xitoy",
        "JP": "Yaponiya", "KR": "Koreya", "BD": "Bangladesh",
        "PH": "Filippin", "CA": "Kanada", "AU": "Avstraliya",
        "BR": "Braziliya", "MX": "Meksika", "QA": "Qatar",
        "AE": "BAA", "SA": "Saudiya Arabistoni", "KW": "Quvayt",
        "IQ": "Iroq", "SY": "Suriya", "LB": "Livan", "OM": "Ummon",
        "PS": "Falastin", "MM": "Myanma", "ZW": "Zimbabve",
        "ID": "Indoneziya", "PK": "Pokiston", "NG": "Nigeriya",
        "ET": "Efiopiya", "EG": "Misr", "TH": "Tailand",
        "VN": "Vyetnam", "MY": "Malayziya", "SG": "Singapur",
        "ES": "Ispaniya", "IT": "Italiya", "PT": "Portugaliya",
        "NL": "Niderlandiya", "PL": "Polsha", "UA": "Ukraina",
        "AR": "Argentina", "CL": "Chili", "JO": "Iordaniya",
        "YE": "Yaman", "MA": "Marokash", "DZ": "Jazoir",
        "TJ": "Tojikiston", "TM": "Turkmaniston", "GE": "Gruziya",
        "AM": "Armaniston", "BY": "Belarus", "IR": "Eron",
        "ZA": "Janubiy Afrika", "KH": "Kambodja",
    }
    
    flag = country_flags.get(country_code, "🌍")
    name = country_names.get(country_code, country_code)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Sotib olish", callback_data=f"confirm_buy_{country_code}_{price}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="buy_number")]
    ])
    
    if int(user['balance'] or 0) >= price:
        balance_text = ""
    else:
        balance_text = "❌ Balansingiz yetarli emas! Hisob to'ldiring."
    
    await call.message.edit_text(
        f"{flag} <b>{name}</b>\n\n"
        f"💰 Narxi: <b>{price:,} so'm</b>\n"
        f"💳 Balansingiz: <b>{int(user['balance'] or 0):,} so'm</b>\n"
        f"{balance_text}",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("confirm_buy_"))
async def confirm_buy(call: CallbackQuery):
    parts = call.data.split("_")
    country_code = parts[2]
    price = int(parts[3])
    user_id = call.from_user.id
    
    user = get_user(user_id)
    if int(user['balance'] or 0) < price:
        await call.answer("❌ Balansingiz yetarli emas!", show_alert=True)
        return
    
    await call.message.edit_text("⏳ Nomer olinmoqda, iltimos kuting...")
    
    try:
        data = await pixsim_request("buyNumber", country_code=country_code)
        if not data.get("ok"):
            await call.message.edit_text(
                f"❌ Xatolik: {data.get('msg', 'Noma um xatolik')}",
                reply_markup=back_btn("buy_number")
            )
            return
        
        result = data["result"]
        order_id = str(result["order_id"])
        phone = result["phone"]
        
        country_names = {
            "UZ": "O'zbekiston", "RU": "Rossiya", "US": "Amerika",
            "KG": "Qirg'iziston", "AZ": "Ozarbayjon", "KZ": "Qozog'iston",
        }
        country_name = country_names.get(country_code, country_code)
        
        # Deduct balance
        update_balance(user_id, -price)
        add_order(user_id, order_id, phone, country_code, country_name, price)
        
        # Referral bonus — faqat birinchi xaridda
        user_data = get_user(user_id)
        if user_data['referred_by']:
            orders = get_user_orders(user_id)
            if len(orders) == 1:  # Bu birinchi buyurtma
                ref_percent = int(get_setting("referral_percent") or 10)
                ref_bonus = int(price * ref_percent / 100)
                add_referral_earning(user_data['referred_by'], ref_bonus)
                try:
                    await bot.send_message(
                        user_data['referred_by'],
                        f"🎉 Do'stingiz birinchi nomer sotib oldi!\n"
                        f"💰 Referral bonus: +{ref_bonus:,} so'm qo'shildi!"
                    )
                except:
                    pass
        
        msg = await call.message.edit_text(
            f"✅ <b>Nomer tayyor!</b>\n\n"
            f"📞 Nomer: <b>{phone}</b>\n"
            f"🌍 Davlat: <b>{country_name}</b>\n"
            f"💵 Narxi: <b>{price:,} so'm</b>\n\n"
            f"⏳ SMS kodi kutilmoqda...",
            parse_mode="HTML"
        )
        
        # Proof channel
        country_flags = {"UZ": "🇺🇿", "RU": "🇷🇺", "US": "🇺🇸"}
        flag = country_flags.get(country_code, "🌍")
        await send_proof_channel(
            f"✅ @nomerx_uzbot dan raqam olindi!\n\n"
            f"📞 Nomer: {format_phone(phone)}\n"
            f"🌍 Davlat: {flag} {country_name}\n"
            f"💵 Narxi: {price:,} so'm!"
        )
        
        # Poll for SMS code
        asyncio.create_task(poll_sms(call.message, order_id, user_id))
        
    except Exception as e:
        await call.message.edit_text(f"❌ Xatolik: {e}", reply_markup=back_btn("buy_number"))

async def poll_sms(message: Message, order_id: str, user_id: int):
    for _ in range(30):
        await asyncio.sleep(10)
        try:
            data = await pixsim_request("getCode", order_id=order_id)
            if not data.get("ok"):
                continue
            
            status = data.get("status")
            if status == "finished":
                result = data.get("result", {})
                code = result.get("code", "")
                password = result.get("password", "")
                phone = result.get("phone", "")
                
                update_order_status(order_id, "finished", code, password)
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 Buyurtmalarim", callback_data="my_orders")],
                    [InlineKeyboardButton(text="🏠 Menyu", callback_data="main_menu")]
                ])
                
                await message.edit_text(
                    f"✅ <b>SMS qabul qilindi!</b>\n\n"
                    f"📞 Nomer: <b>{phone}</b>\n"
                    f"🔑 Kod: <b>{code}</b>\n"
                    f"🔐 Parol: <b>{password}</b>",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                return
            elif status == "waiting":
                continue
        except:
            continue
    
    update_order_status(order_id, "expired")
    try:
        await message.edit_text(
            "⏰ SMS kodi vaqti o'tdi. Qayta urinib ko'ring.",
            reply_markup=back_btn("main_menu")
        )
    except:
        pass

# ===================== MY ORDERS =====================
@dp.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):
    orders = get_user_orders(call.from_user.id)
    if not orders:
        await call.message.edit_text(
            "📋 Sizda hali buyurtmalar yo'q.",
            reply_markup=back_btn("profile")
        )
        return
    
    status_icons = {
        "waiting": "⏳", "finished": "✅", "expired": "❌"
    }
    
    text = "📋 <b>Buyurtmalarim:</b>\n\n"
    for i, order in enumerate(orders[:10], 1):
        icon = status_icons.get(order['status'], "❓")
        text += f"{i}. {icon} <b>{format_phone(order['phone'])}</b> — {order['country_name']}\n"
        if order['code']:
            text += f"   🔑 Kod: <b>{order['code']}</b>"
            if order['password']:
                text += f" | 🔐 Parol: <b>{order['password']}</b>"
            text += "\n"
        text += "\n"
    
    await call.message.edit_text(
        text,
        reply_markup=back_btn("profile"),
        parse_mode="HTML"
    )

# ===================== PROFILE =====================
@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    user = get_user(call.from_user.id)
    orders = get_user_orders(call.from_user.id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton(text="🔗 Referral link", callback_data="referral")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    
    await call.message.edit_text(
        f"👤 <b>Hisobim</b>\n\n"
        f"🆔 ID: <b>{user['user_id']}</b>\n"
        f"👤 Ism: <b>{user['full_name']}</b>\n"
        f"💰 Balans: <b>{int(user['balance'] or 0):,} so'm</b>\n"
        f"📱 Buyurtmalar: <b>{len(orders)} ta</b>\n"
        f"🔗 Taklif qilganlar: <b>{user['referral_count']} ta</b>\n"
        f"💵 Referral daromad: <b>{user['referral_earnings']:,} so'm</b>\n"
        f"📅 Ro'yxatdan: <b>{user['created_at'][:10]}</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ===================== DEPOSIT =====================
@dp.callback_query(F.data == "deposit")
async def deposit(call: CallbackQuery):
    card = get_setting("card_number")
    owner = get_setting("card_owner")
    user = get_user(call.from_user.id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="10,000", callback_data="dep_10000"),
            InlineKeyboardButton(text="20,000", callback_data="dep_20000"),
        ],
        [
            InlineKeyboardButton(text="50,000", callback_data="dep_50000"),
            InlineKeyboardButton(text="100,000", callback_data="dep_100000"),
        ],
        [InlineKeyboardButton(text="✏️ Boshqa summa", callback_data="dep_custom")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    
    await call.message.edit_text(
        f"💳 <b>Hisob To'ldirish</b>\n\n"
        f"💰 Joriy balansingiz: <b>{int(user['balance'] or 0):,} so'm</b>\n\n"
        f"Quyidagi karta raqamiga pul o'tkazing:\n\n"
        f"🏦 Karta: <code>{card}</code>\n"
        f"👤 Egasi: <b>{owner}</b>\n\n"
        f"To'lov summani tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("dep_"))
async def deposit_amount(call: CallbackQuery, state: FSMContext):
    amount_str = call.data.replace("dep_", "")
    
    if amount_str == "custom":
        await state.set_state(PaymentState.waiting_amount)
        await call.message.edit_text(
            "💰 To'lov summani kiriting (so'mda):",
            reply_markup=back_btn("deposit")
        )
        return
    
    amount = int(amount_str)
    await state.update_data(amount=amount)
    await state.set_state(PaymentState.waiting_check)
    
    card = get_setting("card_number")
    owner = get_setting("card_owner")
    
    await call.message.edit_text(
        f"💰 <b>{amount:,} so'm</b> ga to'lov chekini yuboring:\n\n"
        f"🏦 Karta: <code>{card}</code>\n"
        f"👤 Egasi: <b>{owner}</b>\n\n"
        f"To'lov qilgach, chek rasmini shu yerga yuboring 👇",
        reply_markup=back_btn("deposit"),
        parse_mode="HTML"
    )

@dp.message(PaymentState.waiting_amount)
async def payment_custom_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.replace(" ", "").replace(",", ""))
        if amount < 1000:
            await message.answer("❌ Minimum summa 1,000 so'm!")
            return
        await state.update_data(amount=amount)
        await state.set_state(PaymentState.waiting_check)
        
        card = get_setting("card_number")
        owner = get_setting("card_owner")
        
        await message.answer(
            f"💰 <b>{amount:,} so'm</b> ga to'lov chekini yuboring:\n\n"
            f"🏦 Karta: <code>{card}</code>\n"
            f"👤 Egasi: <b>{owner}</b>\n\n"
            f"To'lov qilgach, chek rasmini shu yerga yuboring 👇",
            parse_mode="HTML"
        )
    except:
        await message.answer("❌ Noto'g'ri summa! Faqat raqam kiriting.")

@dp.message(PaymentState.waiting_check, F.photo)
async def payment_check(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", 0)
    user_id = message.from_user.id
    user = get_user(user_id)
    
    payment_id = add_payment(user_id, amount)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pay_approve_{payment_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"pay_reject_{payment_id}")
        ],
        [InlineKeyboardButton(text="💰 Balans o'zgartirish", callback_data=f"pay_edit_{payment_id}")]
    ])
    
    admin_msg = await bot.send_photo(
        ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=(
            f"💳 <b>Hisob to'ldirish so'rovi!</b>\n\n"
            f"👤 Ism: <b>{user['full_name']}</b>\n"
            f"🆔 ID: <b>{user_id}</b>\n"
            f"💰 Summa: <b>{amount:,} so'm</b>\n"
            f"📅 Vaqt: <b>{message.date.strftime('%d.%m.%Y %H:%M')}</b>"
        ),
        reply_markup=kb,
        parse_mode="HTML"
    )
    
    update_payment(payment_id, "pending", admin_msg.message_id)
    await state.clear()
    
    await message.answer(
        "⏳ To'lovingiz tekshirilmoqda...\n"
        "Admin tasdiqlashini kuting (10-30 daqiqa) ✅",
        reply_markup=back_btn("main_menu")
    )

# ===================== ADMIN PAYMENT ACTIONS =====================
@dp.callback_query(F.data.startswith("pay_approve_"))
async def pay_approve(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    payment_id = int(call.data.split("_")[-1])
    payment = get_payment(payment_id)
    
    if not payment or payment['status'] != 'pending':
        await call.answer("❌ Bu to'lov allaqachon ko'rilgan!", show_alert=True)
        return
    
    update_balance(payment['user_id'], payment['amount'])
    update_payment(payment_id, "approved")
    
    user = get_user(payment['user_id'])
    
    await call.message.edit_caption(
        call.message.caption + "\n\n✅ <b>TASDIQLANDI</b>",
        parse_mode="HTML"
    )
    
    try:
        await bot.send_message(
            payment['user_id'],
            f"✅ <b>Hisobingiz to'ldirildi!</b>\n\n"
            f"💰 Qo'shildi: <b>{payment['amount']:,} so'm</b>\n"
            f"💳 Joriy balans: <b>{int(user['balance'] or 0):,} so'm</b>",
            parse_mode="HTML"
        )
    except:
        pass
    
    await call.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data.startswith("pay_reject_"))
async def pay_reject(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    payment_id = int(call.data.split("_")[-1])
    payment = get_payment(payment_id)
    
    if not payment or payment['status'] != 'pending':
        await call.answer("❌ Bu to'lov allaqachon ko'rilgan!", show_alert=True)
        return
    
    update_payment(payment_id, "rejected")
    
    await call.message.edit_caption(
        call.message.caption + "\n\n❌ <b>RAD ETILDI</b>",
        parse_mode="HTML"
    )
    
    try:
        await bot.send_message(
            payment['user_id'],
            "❌ <b>To'lovingiz tasdiqlanmadi.</b>\n"
            f"📞 Murojaat uchun: {get_setting('support_username')}",
            parse_mode="HTML"
        )
    except:
        pass
    
    await call.answer("❌ Rad etildi!")

@dp.callback_query(F.data.startswith("pay_edit_"))
async def pay_edit(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    payment_id = int(call.data.split("_")[-1])
    await state.update_data(payment_id=payment_id)
    await state.set_state(AdminState.set_balance_amount)
    await call.message.answer("💰 Yangi summani kiriting:")

@dp.message(AdminState.set_balance_amount)
async def admin_set_payment_amount(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        amount = int(message.text.replace(" ", ""))
        data = await state.get_data()
        payment_id = data.get("payment_id")
        
        if payment_id:
            payment = get_payment(payment_id)
            update_balance(payment['user_id'], amount)
            update_payment(payment_id, "approved")
            user = get_user(payment['user_id'])
            await message.answer(f"✅ {user['full_name']} ga {amount:,} so'm qo'shildi!")
            try:
                await bot.send_message(
                    payment['user_id'],
                    f"✅ Hisobingizga <b>{amount:,} so'm</b> qo'shildi!\n"
                    f"💳 Joriy balans: <b>{int(user['balance'] or 0):,} so'm</b>",
                    parse_mode="HTML"
                )
            except:
                pass
        else:
            data2 = await state.get_data()
            user_id = data2.get("target_user_id")
            if user_id:
                set_balance(user_id, amount)
                user = get_user(user_id)
                await message.answer(f"✅ {user['full_name']} balansi {amount:,} so'mga o'zgartirildi!")
        
        await state.clear()
    except:
        await message.answer("❌ Noto'g'ri summa!")

# ===================== REFERRAL =====================
@dp.callback_query(F.data == "referral")
async def referral(call: CallbackQuery):
    user = get_user(call.from_user.id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    ref_percent = get_setting("referral_percent")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    
    await call.message.edit_text(
        f"🔥 <b>Pul ishlash</b>\n\n"
        f"Do'stlaringizni taklif qiling va har bir xariddan <b>{ref_percent}%</b> oling!\n\n"
        f"👥 Taklif qilganlarim: <b>{user['referral_count']} ta</b>\n"
        f"💰 Jami daromad: <b>{user['referral_earnings']:,} so'm</b>\n\n"
        f"🔗 Sizning linkingiz:\n"
        f"<code>{ref_link}</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ===================== SUPPORT =====================
@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery, state: FSMContext):
    support_username = get_setting("support_username")
    await state.set_state(SupportState.waiting_message)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="main_menu")]
    ])
    
    await call.message.edit_text(
        f"📞 <b>Murojaat</b>\n\n"
        f"Muammoingizni yozing, admin tez orada javob beradi!\n\n"
        f"Yoki to'g'ridan-to'g'ri murojaat qiling: {support_username}",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.message(SupportState.waiting_message)
async def support_message(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Javob berish", callback_data=f"reply_{message.from_user.id}")]
    ])
    
    await bot.send_message(
        ADMIN_ID,
        f"📞 <b>Yangi murojaat!</b>\n\n"
        f"👤 Ism: <b>{user['full_name']}</b>\n"
        f"🆔 ID: <b>{message.from_user.id}</b>\n"
        f"💬 Xabar: {message.text}",
        reply_markup=kb,
        parse_mode="HTML"
    )
    
    await state.clear()
    await message.answer(
        "✅ Murojaatingiz yuborildi!\nAdmin tez orada javob beradi.",
        reply_markup=back_btn("main_menu")
    )

@dp.callback_query(F.data.startswith("reply_"))
async def admin_reply_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    target_id = int(call.data.split("_")[1])
    await state.update_data(target_user_id=target_id)
    await state.set_state(AdminState.support_reply)
    await call.message.answer(f"💬 Javobingizni yozing (ID: {target_id}):")

@dp.message(AdminState.support_reply)
async def admin_reply_send(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    target_id = data.get("target_user_id")
    
    try:
        await bot.send_message(
            target_id,
            f"📞 <b>Admin javobi:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer("✅ Javob yuborildi!")
    except:
        await message.answer("❌ Foydalanuvchiga xabar yuborib bo'lmadi!")
    
    await state.clear()

# ===================== GUIDE =====================
@dp.callback_query(F.data == "guide")
async def guide(call: CallbackQuery):
    text = (
        "📚 <b>Qo'llanma</b>\n\n"
        "🚫 <b>Telegramda Akkaunt Nega Spamga Tushadi?</b>\n\n"
        "<b>1️⃣ Narx va Sifat Proporsiyasi</b>\n"
        "Eng arzon raqamlarni qidirish — bu bloklanishga chipta olish bilan barobar. "
        "Arzon raqamlar minglab odamlar tomonidan ishlatilgan va 'qora ro'yxat'ga tushgan bo'ladi.\n\n"
        "<b>2️⃣ Geografik Nomutanosiblik (IP va Raqam)</b>\n"
        "O'zbekistonda turib, uzoq davlat raqamiga kirganingizda Telegram buni shubhali harakat sifatida qayd etadi. "
        "Tizim buni 'bot' yoki 'xakerlik' signali sifatida ko'radi.\n\n"
        "<b>3️⃣ Xavfli Davlatlar Ro'yxati</b>\n"
        "Telegram kiberjinoyatchilik ko'p tarqalgan davlatlar reytingini yuritadi. "
        "Bunday davlat raqami olsangiz, hech kimga xat yozmasangiz ham profilingiz cheklovga tushishi mumkin.\n\n"
        "<b>4️⃣ Kirishdan Keyingi Xatolar</b>\n"
        "Akkauntga kirgan zahoti kimgadir xat yozish yoki guruhlarga qo'shilish — 100% bloklanishga olib keladi. "
        "Profilni rasm va ism bilan to'ldirmay harakat boshlash ham xavfli.\n\n"
        "💡 <b>Akkaunt Uzoq Yashashi Uchun:</b>\n\n"
        "1. Arzonidan qoching\n"
        "2. O'zbekiston raqami — eng ishonchli variant\n"
        "3. Yangi raqamga kirganingizdan so'ng 24 soat hech kimga yozmang\n"
        "4. Profilni rasm va ism bilan to'ldiring\n"
        "5. Bir-ikkita rasmiy kanallarga a'zo bo'ling\n\n"
        "✅ <b>Xulosa:</b> Sifatli xizmat sifatli sarmoya talab qiladi!"
    )
    
    await call.message.edit_text(
        text,
        reply_markup=back_btn("main_menu"),
        parse_mode="HTML"
    )

# ===================== ADMIN PANEL =====================
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="🔑 API sozlamalari", callback_data="admin_api"),
            InlineKeyboardButton(text="⚙️ Bot sozlamalari", callback_data="admin_settings")
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    
    await call.message.edit_text(
        "⚙️ <b>Admin Panel</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    users = get_user_count()
    orders = get_total_orders()
    revenue = get_total_revenue()
    today = get_today_orders()
    
    await call.message.edit_text(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{users}</b>\n"
        f"📱 Jami buyurtmalar: <b>{orders}</b>\n"
        f"💰 Jami daromad: <b>{revenue:,} so'm</b>\n"
        f"📅 Bugungi buyurtmalar: <b>{today}</b>",
        reply_markup=back_btn("admin_panel"),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    
    users = get_all_users()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Foydalanuvchi qidirish", callback_data="admin_search_user")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_panel")]
    ])
    
    await call.message.edit_text(
        f"👥 <b>Foydalanuvchilar: {len(users)} ta</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_search_user")
async def admin_search_user(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.search_user)
    await call.message.edit_text(
        "🔍 Foydalanuvchi ID yoki username kiriting:",
        reply_markup=back_btn("admin_users")
    )

@dp.message(AdminState.search_user)
async def admin_search_result(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    user = search_user(message.text.strip().replace("@", ""))
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi!")
        return
    
    await state.clear()
    orders = get_user_orders(user['user_id'])
    
    block_text = "🚫 Bloklash" if not user['is_blocked'] else "✅ Blokdan chiqarish"
    block_cb = f"admin_block_{user['user_id']}" if not user['is_blocked'] else f"admin_unblock_{user['user_id']}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Balans qo'shish", callback_data=f"admin_addbal_{user['user_id']}")],
        [InlineKeyboardButton(text="✏️ Balans o'zgartirish", callback_data=f"admin_setbal_{user['user_id']}")],
        [InlineKeyboardButton(text=block_text, callback_data=block_cb)],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_users")]
    ])
    
    await message.answer(
        f"👤 <b>Foydalanuvchi</b>\n\n"
        f"🆔 ID: <b>{user['user_id']}</b>\n"
        f"👤 Ism: <b>{user['full_name']}</b>\n"
        f"📱 Username: @{user['username'] or 'yoq'}\n"
        f"💰 Balans: <b>{int(user['balance'] or 0):,} so'm</b>\n"
        f"📋 Buyurtmalar: <b>{len(orders)} ta</b>\n"
        f"🔗 Referral: <b>{user['referral_count']} ta</b>\n"
        f"🚫 Holat: <b>{'Bloklangan' if user['is_blocked'] else 'Faol'}</b>\n"
        f"📅 Ro'yxatdan: <b>{user['created_at'][:10]}</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("admin_addbal_"))
async def admin_add_balance(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    target_id = int(call.data.split("_")[-1])
    await state.update_data(target_user_id=target_id, balance_mode="add")
    await state.set_state(AdminState.add_balance_amount)
    await call.message.answer("💰 Qo'shmoqchi bo'lgan summani kiriting:")

@dp.callback_query(F.data.startswith("admin_setbal_"))
async def admin_set_balance(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    target_id = int(call.data.split("_")[-1])
    await state.update_data(target_user_id=target_id, balance_mode="set")
    await state.set_state(AdminState.add_balance_amount)
    await call.message.answer("💰 Yangi balans summani kiriting:")

@dp.message(AdminState.add_balance_amount)
async def process_add_balance(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        amount = int(message.text.replace(" ", ""))
        data = await state.get_data()
        target_id = data["target_user_id"]
        mode = data.get("balance_mode", "add")
        
        if mode == "add":
            update_balance(target_id, amount)
            action = f"+{amount:,} so'm qo'shildi"
        else:
            set_balance(target_id, amount)
            action = f"balans {amount:,} so'mga o'zgartirildi"
        
        user = get_user(target_id)
        await message.answer(f"✅ {user['full_name']} — {action}!")
        
        try:
            await bot.send_message(
                target_id,
                f"💰 Hisobingiz yangilandi!\n"
                f"💳 Joriy balans: <b>{int(user['balance'] or 0):,} so'm</b>",
                parse_mode="HTML"
            )
        except:
            pass
        
        await state.clear()
    except:
        await message.answer("❌ Noto'g'ri summa!")

@dp.callback_query(F.data.startswith("admin_block_"))
async def admin_block(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    target_id = int(call.data.split("_")[-1])
    block_user(target_id)
    await call.answer("✅ Foydalanuvchi bloklandi!")
    await call.message.edit_reply_markup(reply_markup=None)

@dp.callback_query(F.data.startswith("admin_unblock_"))
async def admin_unblock(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    target_id = int(call.data.split("_")[-1])
    unblock_user(target_id)
    await call.answer("✅ Foydalanuvchi blokdan chiqarildi!")
    await call.message.edit_reply_markup(reply_markup=None)

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.broadcast)
    await call.message.edit_text(
        "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:",
        reply_markup=back_btn("admin_panel")
    )

@dp.message(AdminState.broadcast)
async def send_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    users = get_all_users()
    sent = 0
    failed = 0
    
    await message.answer(f"📢 {len(users)} ta foydalanuvchiga yuborilmoqda...")
    
    for user in users:
        try:
            await bot.send_message(user['user_id'], message.text)
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(0.05)
    
    await state.clear()
    await message.answer(f"✅ Yuborildi: {sent} ta\n❌ Xato: {failed} ta")

# ===================== ADMIN SETTINGS =====================
@dp.callback_query(F.data == "admin_settings")
async def admin_settings(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Karta raqami", callback_data="set_card")],
        [InlineKeyboardButton(text="💰 Narx ustamasi", callback_data="set_markup")],
        [InlineKeyboardButton(text="🔗 Referral foizi", callback_data="set_ref_percent")],
        [InlineKeyboardButton(text="📞 Support username", callback_data="set_support")],
        [InlineKeyboardButton(text="📢 Isbot kanal ID", callback_data="set_proof_channel")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_panel")]
    ])
    
    card = get_setting("card_number")
    markup = get_setting("price_markup")
    ref = get_setting("referral_percent")
    
    await call.message.edit_text(
        f"⚙️ <b>Bot Sozlamalari</b>\n\n"
        f"💳 Karta: <b>{card}</b>\n"
        f"💰 Narx ustamasi: <b>{markup} so'm</b>\n"
        f"🔗 Referral foizi: <b>{ref}%</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_api")
async def admin_api(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    api_key = get_setting("api_key")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 API Key o'zgartirish", callback_data="set_api_key")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_panel")]
    ])
    
    await call.message.edit_text(
        f"🔑 <b>API Sozlamalari</b>\n\n"
        f"API Key: <code>{api_key}</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "set_card")
async def set_card_cb(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.set_card)
    await call.message.edit_text("💳 Yangi karta raqamini kiriting:", reply_markup=back_btn("admin_settings"))

@dp.message(AdminState.set_card)
async def save_card(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    set_setting("card_number", message.text.strip())
    await state.clear()
    await message.answer("✅ Karta raqami saqlandi!", reply_markup=back_btn("admin_settings"))

@dp.callback_query(F.data == "set_markup")
async def set_markup_cb(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.set_price_markup)
    await call.message.edit_text("💰 Narx ustamasi (so'mda) kiriting:", reply_markup=back_btn("admin_settings"))

@dp.message(AdminState.set_price_markup)
async def save_markup(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = int(message.text.strip())
        set_setting("price_markup", str(val))
        await state.clear()
        await message.answer(f"✅ Narx ustamasi {val:,} so'mga o'rnatildi!")
    except:
        await message.answer("❌ Noto'g'ri qiymat!")

@dp.callback_query(F.data == "set_ref_percent")
async def set_ref_percent_cb(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.set_referral_percent)
    await call.message.edit_text("🔗 Referral foizi (%) kiriting:", reply_markup=back_btn("admin_settings"))

@dp.message(AdminState.set_referral_percent)
async def save_ref_percent(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = int(message.text.strip())
        set_setting("referral_percent", str(val))
        await state.clear()
        await message.answer(f"✅ Referral foizi {val}% ga o'rnatildi!")
    except:
        await message.answer("❌ Noto'g'ri qiymat!")

@dp.callback_query(F.data == "set_support")
async def set_support_cb(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.set_support)
    await call.message.edit_text("📞 Support username kiriting (@username):", reply_markup=back_btn("admin_settings"))

@dp.message(AdminState.set_support)
async def save_support(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    set_setting("support_username", message.text.strip())
    await state.clear()
    await message.answer("✅ Support username saqlandi!")

@dp.callback_query(F.data == "set_proof_channel")
async def set_proof_cb(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.set_proof_channel)
    await call.message.edit_text(
        "📢 Isbot kanal ID kiriting:\n(Kanal ID ni bilish uchun botni kanalga admin qiling va /id yuboring)",
        reply_markup=back_btn("admin_settings")
    )

@dp.message(AdminState.set_proof_channel)
async def save_proof_channel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    set_setting("proof_channel_id", message.text.strip())
    await state.clear()
    await message.answer("✅ Isbot kanal ID saqlandi!")

@dp.callback_query(F.data == "set_api_key")
async def set_api_key_cb(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.set_api_key)
    await call.message.edit_text("🔑 Yangi API Key kiriting:", reply_markup=back_btn("admin_api"))

@dp.message(AdminState.set_api_key)
async def save_api_key(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    set_setting("api_key", message.text.strip())
    await state.clear()
    await message.answer("✅ API Key saqlandi!")

@dp.callback_query(F.data == "none")
async def none_cb(call: CallbackQuery):
    await call.answer()

# ===================== MAIN =====================
import os
from aiohttp import web

async def health(request):
    return web.Response(text="OK")

async def main():
    init_db()
    
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
