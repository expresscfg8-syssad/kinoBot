import asyncio
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import func

from config import BOT_TOKEN, ADMIN_ID
from database import init_db, SessionLocal, Movie, Rating, SavedMovie, Channel, Admin, ChannelJoinRequest

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def is_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    db = SessionLocal()
    try:
        adm = db.query(Admin).filter(Admin.user_id == user_id).first()
        return adm is not None
    finally:
        db.close()


def get_main_kb(user_id: int):
    keyboard = [
        [KeyboardButton(text="🔍 QIDIRUV"), KeyboardButton(text="🎭 JANRLAR")],
        [KeyboardButton(text="🏆 TOP KINOLAR"), KeyboardButton(text="🆕 YANGI KINOLAR")],
        [KeyboardButton(text="📂 SAQLANGANLAR"), KeyboardButton(text="👤 PROFIL")],
        [KeyboardButton(text="🎲 RANDOM KINO"), KeyboardButton(text="🎬 KINO SO'ROV")]
    ]
    if is_admin(user_id):
        keyboard.append([KeyboardButton(text="👑 ADMIN PANEL")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


class AddMovie(StatesGroup):
    waiting_for_video = State()
    waiting_for_details = State()


class MovieRequestState(StatesGroup):
    waiting_for_request = State()


class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_add_channel = State()
    waiting_for_new_admin = State()


class SearchState(StatesGroup):
    waiting_for_query = State()


async def get_unsubscribed_channels(user_id: int):
    if is_admin(user_id):
        return []

    db = SessionLocal()
    try:
        channels = db.query(Channel).all()
    finally:
        db.close()

    unsubbed = []
    for ch in channels:
        is_ok = False
        try:
            member = await bot.get_chat_member(chat_id=ch.channel_username, user_id=user_id)
            if member.status in ["creator", "administrator", "member"]:
                is_ok = True
        except Exception:
            pass

        if not is_ok:
            db = SessionLocal()
            try:
                req = db.query(ChannelJoinRequest).filter(ChannelJoinRequest.user_id == user_id).first()
            finally:
                db.close()
            if not req:
                unsubbed.append(ch.channel_username)

    return unsubbed


def get_subscribe_markup(unsubbed_list):
    kb = []
    for username in unsubbed_list:
        clean_name = username.replace("@", "")
        kb.append([InlineKeyboardButton(text="🔒 Obuna bo'lish", url=f"https://t.me/{clean_name}")])
    kb.append([InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@dp.chat_join_request()
async def auto_approve_join_request(event: ChatJoinRequest):
    try:
        await event.approve()
    except Exception:
        pass
    db = SessionLocal()
    try:
        existing = db.query(ChannelJoinRequest).filter(ChannelJoinRequest.user_id == event.from_user.id).first()
        if not existing:
            db.add(ChannelJoinRequest(user_id=event.from_user.id))
            db.commit()
    finally:
        db.close()


@dp.message(F.text == "/start")
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    init_db()

    db = SessionLocal()
    try:
        existing = db.query(ChannelJoinRequest).filter(ChannelJoinRequest.user_id == message.from_user.id).first()
        if not existing:
            db.add(ChannelJoinRequest(user_id=message.from_user.id))
            db.commit()
    finally:
        db.close()

    unsubbed = await get_unsubscribed_channels(message.from_user.id)
    if unsubbed:
        await message.answer(
            "⚠️ Botdan toʻliq foydalanish uchun quyidagi kanallarga obuna boʻling!",
            reply_markup=get_subscribe_markup(unsubbed)
        )
        return

    await message.answer(
        f"🎬 Kino Express botiga xush kelibsiz, {message.from_user.first_name}!\n\n"
        "Kinoni ko'rish uchun uning **kodini** yuboring.",
        reply_markup=get_main_kb(message.from_user.id)
    )


@dp.callback_query(F.data == "check_sub")
async def verify_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    unsubbed = await get_unsubscribed_channels(user_id)

    if not unsubbed:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "✅ Rahmat! Obuna tasdiqlandi. Endi botdan bemalol foydalanishingiz mumkin:",
            reply_markup=get_main_kb(user_id)
        )
    else:
        await callback.message.edit_reply_markup(reply_markup=get_subscribe_markup(unsubbed))
        await callback.answer("❌ Hamma kanallarga obuna bo'lmadingiz!", show_alert=True)


@dp.message(F.text == "/help")
async def help_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🤖 **Kino Express boti yordam bo'limi:**\n\n"
        "• Kinoni ko'rish uchun uning **kodini** yuboring (masalan: `1`).",
        parse_mode="Markdown",
        reply_markup=get_main_kb(message.from_user.id)
    )


@dp.message(F.text == "👑 ADMIN PANEL")
async def admin_panel_cmd(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("❌ Bu bo'lim faqat adminlar uchun.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kino qo'shish", callback_data="ap_add_movie")],
        [InlineKeyboardButton(text="📢 Kanallarni boshqarish", callback_data="ap_channels")],
        [InlineKeyboardButton(text="👥 Adminlarni boshqarish", callback_data="ap_admins")],
        [InlineKeyboardButton(text="✉️ Hammaga xabar yuborish", callback_data="ap_broadcast")],
        [InlineKeyboardButton(text="📊 Statistikani ko'rish", callback_data="ap_stats")]
    ])
    await message.answer("👑 **Admin boshqaruv paneli:**", reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data == "ap_stats")
async def admin_stats_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    db = SessionLocal()
    try:
        t_movies = db.query(Movie).count()
        t_users = db.query(ChannelJoinRequest).count()
        t_views = db.query(func.sum(Movie.views)).scalar() or 0
    finally:
        db.close()
    await callback.message.answer(
        f"📊 **Statistika:**\n\n👥 Foydalanuvchilar: `{t_users}` ta\n🎬 Kinolar: `{t_movies}` ta\n👁 Ko'rishlar: `{t_views}` marta",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(F.data == "ap_channels")
async def admin_channels_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    db = SessionLocal()
    try:
        channels = db.query(Channel).all()
    finally:
        db.close()

    text = "📢 **Majburiy obuna kanallari:**\n\n"
    kb = []
    if channels:
        for ch in channels:
            text += f"• {ch.channel_username}\n"
            kb.append(
                [InlineKeyboardButton(text=f"❌ O'chirish: {ch.channel_username}", callback_data=f"del_ch_{ch.id}")])
    else:
        text += "Hozircha kanallar yo'q.\n"

    kb.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch_prompt")])
    kb.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="ap_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "add_ch_prompt")
async def add_ch_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.answer("➕ Yangi kanal username'ini yuboring (masalan: `@kanal_nomi`):")
    await state.set_state(AdminStates.waiting_for_add_channel)
    await callback.answer()


@dp.message(AdminStates.waiting_for_add_channel, F.text)
async def save_new_channel_db(message: Message, state: FSMContext):
    ch_name = message.text.strip()
    if not ch_name.startswith("@"): ch_name = "@" + ch_name

    db = SessionLocal()
    try:
        if not db.query(Channel).filter(Channel.channel_username == ch_name).first():
            db.add(Channel(channel_username=ch_name))
            db.commit()
    finally:
        db.close()
    await state.clear()
    await message.answer(f"✅ {ch_name} majburiy obunaga qo'shildi!")


@dp.callback_query(F.data.startswith("del_ch_"))
async def delete_channel_db(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    ch_id = int(callback.data.split("_")[2])
    db = SessionLocal()
    try:
        db.query(Channel).filter(Channel.id == ch_id).delete()
        db.commit()
    finally:
        db.close()
    await callback.answer("✅ Kanal o'chirildi!", show_alert=True)
    await admin_channels_cb(callback)


@dp.callback_query(F.data == "ap_admins")
async def admin_manage_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_adm_prompt")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="ap_back")]
    ])
    await callback.message.edit_text("👥 **Adminlar boshqaruvi:**", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "add_adm_prompt")
async def add_adm_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.answer("➕ Yangi adminning Telegram **User ID** raqamini yuboring:")
    await state.set_state(AdminStates.waiting_for_new_admin)
    await callback.answer()


@dp.message(AdminStates.waiting_for_new_admin, F.text)
async def save_admin_db(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqam kiriting!")
        return
    u_id = int(message.text)
    db = SessionLocal()
    try:
        if not db.query(Admin).filter(Admin.user_id == u_id).first():
            db.add(Admin(user_id=u_id))
            db.commit()
    finally:
        db.close()
    await state.clear()
    await message.answer(f"✅ `{u_id}` ID egasi admin qilindi!", parse_mode="Markdown")


@dp.callback_query(F.data == "ap_broadcast")
async def broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.answer("✉️ Hammaga yubormoqchi bo'lgan xabaringizni yuboring:")
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()


@dp.message(AdminStates.waiting_for_broadcast)
async def send_broadcast(message: Message, state: FSMContext):
    await state.clear()
    db = SessionLocal()
    try:
        users = db.query(ChannelJoinRequest).all()
    finally:
        db.close()

    status = await message.answer("⏳ Xabar tarqatilmoqda...")
    sent, fail = 0, 0
    for u in users:
        try:
            await message.send_copy(chat_id=u.user_id)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    await status.edit_text(f"✅ Tugadi!\nYetib bordi: {sent}\nXatolik: {fail}")


@dp.callback_query(F.data == "ap_back")
async def ap_back_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kino qo'shish", callback_data="ap_add_movie")],
        [InlineKeyboardButton(text="📢 Kanallarni boshqarish", callback_data="ap_channels")],
        [InlineKeyboardButton(text="👥 Adminlarni boshqarish", callback_data="ap_admins")],
        [InlineKeyboardButton(text="✉️ Hammaga xabar yuborish", callback_data="ap_broadcast")],
        [InlineKeyboardButton(text="📊 Statistikani ko'rish", callback_data="ap_stats")]
    ])
    await callback.message.edit_text("👑 **Admin boshqaruv paneli:**", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "ap_add_movie")
async def cb_admin_add_movie(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.answer("🎬 1-qadam: Iltimos, kino **videosini** yuboring:")
    await state.set_state(AddMovie.waiting_for_video)
    await callback.answer()


@dp.message(AddMovie.waiting_for_video, F.video)
async def handle_movie_video(message: Message, state: FSMContext):
    video = message.video
    dur = video.duration
    dur_str = f"{dur // 60}:{dur % 60:02d} min" if dur else "1:30"

    await state.update_data(file_id=video.file_id, duration=dur_str)

    await message.answer(
        "✅ Video qabul qilindi!\n\n"
        "2-qadam: Ma'lumotlarni quyidagi qolipda yuboring:\n\n"
        "Adolat ligasi\n"
        "Janri: Drama, Komediya\n"
        "Yili: 2017\n"
        "Davlati: AQSH\n"
        "Tili: O'zbek\n"
        "Sifati: 1080p"
    )
    await state.set_state(AddMovie.waiting_for_details)


@dp.message(AddMovie.waiting_for_details, F.text)
async def handle_movie_details(message: Message, state: FSMContext):
    data = await state.get_data()
    lines = message.text.split("\n")
    title = lines[0].strip()
    genre, year, country, language, quality = "Drama", "2024", "AQSH", "O'zbek", "1080p"

    for l in lines[1:]:
        if "Janri:" in l or "Janr:" in l:
            genre = l.split(":")[-1].strip()
        elif "Yili:" in l or "Yil:" in l:
            year = l.split(":")[-1].strip()
        elif "Davlati:" in l or "Davlat:" in l:
            country = l.split(":")[-1].strip()
        elif "Tili:" in l:
            language = l.split(":")[-1].strip()
        elif "Sifati:" in l:
            quality = l.split(":")[-1].strip()

    db = SessionLocal()
    try:
        nm = Movie(
            title=title, genre=genre, year=year, country=country, language=language,
            quality=quality, duration=data['duration'], file_id=data['file_id']
        )
        db.add(nm)
        db.commit()
        m_id = nm.id
    finally:
        db.close()

    await state.clear()
    await message.answer(f"🎉 Kino muvaffaqiyatli bazaga qo'shildi! Kodi (ID): `{m_id}`", parse_mode="Markdown")


# --- BAHOLASH VA SAQLASH TUGMALARI ---
def get_movie_markup(movie_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Saqlash", callback_data=f"save_{movie_id}"),
         InlineKeyboardButton(text="✍️ Baholash", callback_data=f"rate_menu_{movie_id}")]
    ])


@dp.callback_query(F.data.startswith("save_"))
async def save_movie_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    movie_id = int(callback.data.split("_")[1])
    db = SessionLocal()
    try:
        existing = db.query(SavedMovie).filter(SavedMovie.user_id == user_id, SavedMovie.movie_id == movie_id).first()
        if not existing:
            db.add(SavedMovie(user_id=user_id, movie_id=movie_id))
            db.commit()
            await callback.answer("✅ Kino saqlanganlarga qo'shildi!", show_alert=True)
        else:
            await callback.answer("⚠️ Bu kino allaqachon saqlangan!", show_alert=True)
    finally:
        db.close()


@dp.callback_query(F.data.startswith("rate_menu_"))
async def rate_menu_callback(callback: CallbackQuery):
    movie_id = int(callback.data.split("_")[2])
    # 1 dan 10 gacha raqamlar chiqarish (2 qatorga bo'lib)
    row1 = [InlineKeyboardButton(text=str(i), callback_data=f"rate_{movie_id}_{i}") for i in range(1, 6)]
    row2 = [InlineKeyboardButton(text=str(i), callback_data=f"rate_{movie_id}_{i}") for i in range(6, 11)]
    back = [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"back_movie_{movie_id}")]

    kb = InlineKeyboardMarkup(inline_keyboard=[row1, row2, back])
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("back_movie_"))
async def back_movie_callback(callback: CallbackQuery):
    movie_id = int(callback.data.split("_")[2])
    await callback.message.edit_reply_markup(reply_markup=get_movie_markup(movie_id))
    await callback.answer()


@dp.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: CallbackQuery):
    parts = callback.data.split("_")
    movie_id = int(parts[1])
    score = int(parts[2])
    user_id = callback.from_user.id

    db = SessionLocal()
    try:
        existing = db.query(Rating).filter(Rating.user_id == user_id, Rating.movie_id == movie_id).first()
        movie = db.query(Movie).filter(Movie.id == movie_id).first()

        if existing:
            movie.total_rating = movie.total_rating - existing.score + score
            existing.score = score
        else:
            db.add(Rating(user_id=user_id, movie_id=movie_id, score=score))
            movie.total_rating += score
            movie.rating_count += 1
        db.commit()
    finally:
        db.close()

    await callback.answer(f"✅ Rahmat! {score}/10 baho berildi.", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=get_movie_markup(movie_id))


# --- KINO VIDEOSINI YUBORISH ---
async def send_movie_video(message: Message, movie):
    db = SessionLocal()
    try:
        m_db = db.query(Movie).filter(Movie.id == movie.id).first()
        if m_db:
            m_db.views += 1
            db.commit()
            views_count = m_db.views
        else:
            views_count = movie.views
    finally:
        db.close()

    avg = round(movie.total_rating / movie.rating_count, 1) if movie.rating_count > 0 else 0.0
    genres = " ".join([f"#{g.strip()}" for g in movie.genre.split(",")])

    caption = (
        f"🎬 **{movie.title}** ({movie.year})\n\n"
        f"🎭 Janr: {genres}\n"
        f"🌍 Davlat: {movie.country} | 🗣 Tili: {movie.language}\n"
        f"🎞 Sifati: {movie.quality} | ⏱ {movie.duration}\n"
        f"⭐ IMDb: {movie.imdb} | 🔥 Reyting: {avg}/10\n"
        f"👁 Ko'rildi: {views_count} marta\n\n"
        f"📌 Kino kodi: `{movie.id}`"
    )
    kb = get_movie_markup(movie.id)
    await message.answer_video(video=movie.file_id, caption=caption, reply_markup=kb, parse_mode="Markdown")


# --- MENYU TUGMALARI ---
@dp.message(F.text == "🏆 TOP KINOLAR")
async def top_movies_cmd(message: Message, state: FSMContext):
    await state.clear()
    db = SessionLocal()
    try:
        movies = db.query(Movie).order_by(Movie.views.desc()).limit(5).all()
    finally:
        db.close()

    if not movies:
        await message.answer("Hozircha kinolar yo'q.")
        return
    await message.answer("🏆 **Eng ko'p ko'rilgan Top kinolar (Top 5):**", parse_mode="Markdown")
    for m in movies:
        await send_movie_video(message, m)


@dp.message(F.text == "🆕 YANGI KINOLAR")
async def new_movies_cmd(message: Message, state: FSMContext):
    await state.clear()
    db = SessionLocal()
    try:
        movies = db.query(Movie).order_by(Movie.id.desc()).limit(5).all()
    finally:
        db.close()

    if not movies:
        await message.answer("Hozircha yangi kinolar yo'q.")
        return
    await message.answer("🆕 **So'nggi qo'shilgan kinolar (Top 5):**", parse_mode="Markdown")
    for m in movies:
        await send_movie_video(message, m)


# --- JANRLAR BO'LIMI (FAQAT MATNLI RO'YXAT) ---
@dp.message(F.text == "🎭 JANRLAR")
async def genres_cmd(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Drama", callback_data="genre_Drama"),
         InlineKeyboardButton(text="😂 Komediya", callback_data="genre_Komediya")],
        [InlineKeyboardButton(text="🔥 Jangari", callback_data="genre_Jangari"),
         InlineKeyboardButton(text="🚀 Fantastika", callback_data="genre_Fantastika")]
    ])
    await message.answer("🎭 Kerakli janrni tanlang:", reply_markup=kb)


@dp.callback_query(F.data.startswith("genre_"))
async def genre_filter_cb(callback: CallbackQuery):
    g_name = callback.data.split("_")[1]
    db = SessionLocal()
    try:
        movies = db.query(Movie).filter(Movie.genre.ilike(f"%{g_name}%")).limit(10).all()
    finally:
        db.close()

    if not movies:
        await callback.answer(f"'{g_name}' janrida kinolar topilmadi.", show_alert=True)
        return

    text = f"🎭 **'{g_name}' janridagi kinolar:**\n\n"
    for m in movies:
        text += f"▪️ {m.title} ({m.year}) — 📌 Kod: `{m.id}`\n"

    text += "\n👇 Kinoni ko'rish uchun uning **kodini** yuboring."
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()


@dp.message(F.text == "🔍 QIDIRUV")
async def search_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🔍 Qidirish uchun kino nomini yoki kodini yuboring:")
    await state.set_state(SearchState.waiting_for_query)


@dp.message(SearchState.waiting_for_query, F.text)
async def process_search_state(message: Message, state: FSMContext):
    await state.clear()
    text = message.text.strip()
    db = SessionLocal()
    try:
        if text.isdigit():
            movie = db.query(Movie).filter(Movie.id == int(text)).first()
            if movie:
                await send_movie_video(message, movie)
                return

        movies = db.query(Movie).filter(Movie.title.ilike(f"%{text}%")).limit(5).all()
        if movies:
            for m in movies:
                await send_movie_video(message, m)
        else:
            await message.answer("❌ Hech qanday kino topilmadi.")
    finally:
        db.close()


@dp.message(F.text == "👤 PROFIL")
async def profile_cmd(message: Message, state: FSMContext):
    await state.clear()
    db = SessionLocal()
    try:
        s_count = db.query(SavedMovie).filter(SavedMovie.user_id == message.from_user.id).count()
    finally:
        db.close()
    await message.answer(f"👤 **Profiliniz:**\n\n🆔 ID: `{message.from_user.id}`\n📂 Saqlangan kinolar: {s_count} ta",
                         parse_mode="Markdown")


@dp.message(F.text == "📂 SAQLANGANLAR")
async def saved_cmd(message: Message, state: FSMContext):
    await state.clear()
    db = SessionLocal()
    try:
        saved = db.query(SavedMovie).filter(SavedMovie.user_id == message.from_user.id).all()
        movie_ids = [s.movie_id for s in saved]
        movies = db.query(Movie).filter(Movie.id.in_(movie_ids)).all() if movie_ids else []
    finally:
        db.close()

    if not movies:
        await message.answer("📂 Saqlangan kinolaringiz yo'q.")
        return

    await message.answer("📂 **Saqlangan kinolaringiz:**", parse_mode="Markdown")
    for m in movies:
        await send_movie_video(message, m)


@dp.message(F.text == "🎲 RANDOM KINO")
async def random_cmd(message: Message, state: FSMContext):
    await state.clear()
    db = SessionLocal()
    try:
        movies = db.query(Movie).all()
    finally:
        db.close()

    if not movies:
        await message.answer("Kinolar mavjud emas.")
        return
    await send_movie_video(message, random.choice(movies))


@dp.message(F.text == "🎬 KINO SO'ROV")
async def request_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Qaysi kinoni ko'rishni xohlaysiz? Kino nomini yuboring:")
    await state.set_state(MovieRequestState.waiting_for_request)


@dp.message(MovieRequestState.waiting_for_request, F.text)
async def save_req(message: Message, state: FSMContext):
    await state.clear()
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📥 **Yangi kino so'rovi:**\n\nKino: {message.text}\nKimdan: {message.from_user.full_name} (@{message.from_user.username})"
        )
    except Exception:
        pass
    await message.answer("✅ So'rovingiz adminga yuborildi!")


@dp.message(F.text)
async def text_search(message: Message, state: FSMContext):
    if unsubbed := await get_unsubscribed_channels(message.from_user.id):
        await message.answer("⚠️ Botdan foydalanish uchun avval kanallarga obuna bo'ling!",
                             reply_markup=get_subscribe_markup(unsubbed))
        return

    text = message.text.strip()
    db = SessionLocal()
    try:
        if text.isdigit():
            movie = db.query(Movie).filter(Movie.id == int(text)).first()
            if movie:
                await send_movie_video(message, movie)
                return

        movies = db.query(Movie).filter(Movie.title.ilike(f"%{text}%")).limit(5).all()
        if movies:
            for m in movies:
                await send_movie_video(message, m)
        else:
            await message.answer("❌ Bunday kino topilmadi. Kodini to'g'ri yuboring.")
    finally:
        db.close()

import os
from aiohttp import web
async def main():
    init_db()
    print("🚀 Bot tayyor va ishga tushdi!")
    await dp.start_polling(bot)


async def handle(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main_all():
    await web_server()
    await main()

if __name__ == "__main__":
    asyncio.run(main_all())
