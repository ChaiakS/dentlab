import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, MediaGroup

# Вставьте ваш токен бота здесь
API_TOKEN = '8039553499:AAHonILU7zeqifS7qc631xwche7UHMeVq4w'

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Подключение к базе данных SQLite
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц, если они не существуют
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    profile_name TEXT,
    user_group TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS works (
    work_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT,
    patient_phone TEXT,
    work_type TEXT,
    work_name TEXT,
    deadline TEXT,
    cost TEXT,
    status TEXT,
    dentist_id INTEGER,
    technician_id INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS photos (
    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER,
    file_id TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS videos (
    video_id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER,
    file_id TEXT
)
''')
conn.commit()

# Классы состояний для машины состояний (FSM)
class Registration(StatesGroup):
    group = State()
    profile_name = State()

class NewWork(StatesGroup):
    patient_name = State()
    patient_phone = State()
    work_type = State()
    work_name = State()
    deadline = State()
    cost = State()
    photos = State()
    videos = State()
    technician = State()

# Функция проверки регистрации пользователя
def is_registered(user_id):
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
    return cursor.fetchone() is not None

# Функция получения группы пользователя
def get_user_group(user_id):
    cursor.execute("SELECT user_group FROM users WHERE telegram_id = ?", (user_id,))
    return cursor.fetchone()[0]

# Функция получения имени профиля
def get_profile_name(user_id):
    cursor.execute("SELECT profile_name FROM users WHERE telegram_id = ?", (user_id,))
    return cursor.fetchone()[0]

# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    if not is_registered(user_id):
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(KeyboardButton("Стоматолог 🦷"))
        keyboard.add(KeyboardButton("Техник 🔧"))
        await message.reply("<b>Добро пожаловать! 👋</b> Выберите вашу группу:", parse_mode="HTML", reply_markup=keyboard)
        await Registration.group.set()
    else:
        group = get_user_group(user_id)
        if group == 'dentist':
            await show_dentist_menu(message)
        elif group == 'technician':
            await show_technician_menu(message)

# Обработчик выбора группы
@dp.message_handler(state=Registration.group)
async def process_group(message: types.Message, state: FSMContext):
    if message.text not in ["Стоматолог 🦷", "Техник 🔧"]:
        await message.reply("Пожалуйста, выберите группу из предложенных кнопок.")
        return
    group = 'dentist' if message.text == "Стоматолог 🦷" else 'technician'
    async with state.proxy() as data:
        data['group'] = group
    await Registration.next()
    await message.reply("Введите ваше имя профиля:")

# Обработчик ввода имени профиля
@dp.message_handler(state=Registration.profile_name)
async def process_profile_name(message: types.Message, state: FSMContext):
    profile_name = message.text
    user_id = message.from_user.id
    async with state.proxy() as data:
        group = data['group']
    cursor.execute("INSERT INTO users (telegram_id, profile_name, user_group) VALUES (?, ?, ?)", (user_id, profile_name, group))
    conn.commit()
    await message.reply(f"Вы зарегистрированы как {group} с именем профиля: <b>{profile_name}</b>.", parse_mode="HTML")
    await state.finish()
    if group == 'dentist':
        await show_dentist_menu(message)
    else:
        await show_technician_menu(message)

# Меню стоматолога
async def show_dentist_menu(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Отправить новую работу 📤"))
    keyboard.add(KeyboardButton("Список активных работ 📋"))
    keyboard.add(KeyboardButton("Архив работ 🗄️"))
    await message.reply("<b>Выберите действие:</b>", parse_mode="HTML", reply_markup=keyboard)

# Меню техника
async def show_technician_menu(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Активные работы 📋"))
    await message.reply("<b>Выберите действие:</b>", parse_mode="HTML", reply_markup=keyboard)

# Обработчик "Отправить новую работу"
@dp.message_handler(Text(equals="Отправить новую работу 📤"), state='*')
async def start_new_work(message: types.Message):
    if get_user_group(message.from_user.id) != 'dentist':
        await message.reply("Эта функция доступна только стоматологам.")
        return
    await NewWork.patient_name.set()
    await message.reply("Введите имя пациента:")

# FSM: обработка данных новой работы
@dp.message_handler(state=NewWork.patient_name)
async def process_patient_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['patient_name'] = message.text
    await NewWork.next()
    await message.reply("Введите телефон пациента:")

@dp.message_handler(state=NewWork.patient_phone)
async def process_patient_phone(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.reply("Пожалуйста, введите корректный телефонный номер (только цифры).")
        return
    async with state.proxy() as data:
        data['patient_phone'] = message.text
    await NewWork.next()
    await message.reply("Введите тип работы:")

@dp.message_handler(state=NewWork.work_type)
async def process_work_type(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['work_type'] = message.text
    await NewWork.next()
    await message.reply("Введите название работы:")

@dp.message_handler(state=NewWork.work_name)
async def process_work_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['work_name'] = message.text
    await NewWork.next()
    await message.reply("Введите желаемый срок сдачи:")

@dp.message_handler(state=NewWork.deadline)
async def process_deadline(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['deadline'] = message.text
    await NewWork.next()
    await message.reply("Введите стоимость работы (в рублях):")

@dp.message_handler(state=NewWork.cost)
async def process_cost(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.reply("Пожалуйста, введите корректную стоимость (только цифры).")
        return
    async with state.proxy() as data:
        data['cost'] = message.text
        data['photos'] = []
        data['videos'] = []
    await NewWork.next()
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Пропустить 📸"))
    keyboard.add(KeyboardButton("Готово ✅"))
    await message.reply("Отправьте фото пациента (можно несколько). Нажмите 'Готово', когда закончите, или 'Пропустить', если фото не нужны.", reply_markup=keyboard)

# Обработка фото
@dp.message_handler(content_types=['photo'], state=NewWork.photos)
async def process_photos(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['photos'].append(message.photo[-1].file_id)
    await message.reply("Фото добавлено. Отправьте еще или нажмите 'Готово'.")

@dp.message_handler(Text(equals="Готово ✅"), state=NewWork.photos)
async def finish_photos(message: types.Message, state: FSMContext):
    await NewWork.next()
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Пропустить 📹"))
    keyboard.add(KeyboardButton("Готово ✅"))
    await message.reply("Отправьте видео (можно несколько). Нажмите 'Готово', когда закончите, или 'Пропустить', если видео не нужны.", reply_markup=keyboard)

@dp.message_handler(Text(equals="Пропустить 📸"), state=NewWork.photos)
async def skip_photos(message: types.Message, state: FSMContext):
    await NewWork.next()
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Пропустить 📹"))
    keyboard.add(KeyboardButton("Готово ✅"))
    await message.reply("Отправьте видео (можно несколько). Нажмите 'Готово', когда закончите, или 'Пропустить', если видео не нужны.", reply_markup=keyboard)

# Обработка видео
@dp.message_handler(content_types=['video'], state=NewWork.videos)
async def process_videos(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['videos'].append(message.video.file_id)
    await message.reply("Видео добавлено. Отправьте еще или нажмите 'Готово'.")

@dp.message_handler(Text(equals="Готово ✅"), state=NewWork.videos)
async def finish_videos(message: types.Message, state: FSMContext):
    await NewWork.next()
    await show_technicians(message, state)

@dp.message_handler(Text(equals="Пропустить 📹"), state=NewWork.videos)
async def skip_videos(message: types.Message, state: FSMContext):
    await NewWork.next()
    await show_technicians(message, state)

# Выбор техника
async def show_technicians(message: types.Message, state: FSMContext):
    cursor.execute("SELECT telegram_id, profile_name FROM users WHERE user_group = 'technician'")
    technicians = cursor.fetchall()
    if not technicians:
        await message.reply("Нет доступных техников.")
        await state.finish()
        return
    keyboard = InlineKeyboardMarkup()
    for tech_id, tech_name in technicians:
        keyboard.add(InlineKeyboardButton(tech_name, callback_data=f"tech_{tech_id}"))
    await message.reply("<b>Выберите техника:</b>", parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith('tech_'), state=NewWork.technician)
async def process_technician(callback_query: types.CallbackQuery, state: FSMContext):
    tech_id = int(callback_query.data.split('_')[1])
    async with state.proxy() as data:
        cursor.execute('''
        INSERT INTO works (patient_name, patient_phone, work_type, work_name, deadline, cost, status, dentist_id, technician_id)
        VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
        ''', (data['patient_name'], data['patient_phone'], data['work_type'], data['work_name'], data['deadline'], data['cost'], callback_query.from_user.id, tech_id))
        work_id = cursor.lastrowid
        for photo in data['photos']:
            cursor.execute("INSERT INTO photos (work_id, file_id) VALUES (?, ?)", (work_id, photo))
        for video in data['videos']:
            cursor.execute("INSERT INTO videos (work_id, file_id) VALUES (?, ?)", (work_id, video))
        conn.commit()
        await notify_technician(tech_id, work_id, data)
    await callback_query.message.reply(f"Работа для <b>{data['patient_name']}</b> отправлена технику.", parse_mode="HTML")
    await state.finish()
    await show_dentist_menu(callback_query.message)

# Уведомление техника
async def notify_technician(tech_id, work_id, data):
    message = f"<b>Новая работа для пациента {data['patient_name']} (ID: {work_id})</b>:\n"
    message += f"Тип работы: {data['work_type']}\n"
    message += f"Название: {data['work_name']}\n"
    message += f"Срок сдачи: {data['deadline']}\n"
    await bot.send_message(tech_id, message, parse_mode="HTML")
    if data['photos'] or data['videos']:
        media = types.MediaGroup()
        for photo in data['photos']:
            media.attach_photo(photo)
        for video in data['videos']:
            media.attach_video(video)
        await bot.send_media_group(tech_id, media)

# Список активных работ (стоматолог)
@dp.message_handler(Text(equals="Список активных работ 📋"), state='*')
async def list_active_works_dentist(message: types.Message):
    if get_user_group(message.from_user.id) != 'dentist':
        await message.reply("Эта функция доступна только стоматологам.")
        return
    cursor.execute("SELECT work_id, patient_name FROM works WHERE dentist_id = ? AND status = 'active'", (message.from_user.id,))
    works = cursor.fetchall()
    if not works:
        await message.reply("У вас нет активных работ.")
        return
    keyboard = InlineKeyboardMarkup()
    for work_id, patient_name in works:
        keyboard.add(InlineKeyboardButton(f"Работа для {patient_name}", callback_data=f"work_{work_id}"))
    await message.reply("<b>Ваши активные работы:</b>", parse_mode="HTML", reply_markup=keyboard)

# Архив работ (стоматолог)
@dp.message_handler(Text(equals="Архив работ 🗄️"), state='*')
async def list_archive_works_dentist(message: types.Message):
    if get_user_group(message.from_user.id) != 'dentist':
        await message.reply("Эта функция доступна только стоматологам.")
        return
    cursor.execute("SELECT work_id, patient_name FROM works WHERE dentist_id = ? AND status = 'archive'", (message.from_user.id,))
    works = cursor.fetchall()
    if not works:
        await message.reply("У вас нет архивных работ.")
        return
    keyboard = InlineKeyboardMarkup()
    for work_id, patient_name in works:
        keyboard.add(InlineKeyboardButton(f"Работа для {patient_name}", callback_data=f"work_{work_id}"))
    await message.reply("<b>Ваши архивные работы:</b>", parse_mode="HTML", reply_markup=keyboard)

# Активные работы (техник)
@dp.message_handler(Text(equals="Активные работы 📋"), state='*')
async def list_active_works_technician(message: types.Message):
    if get_user_group(message.from_user.id) != 'technician':
        await message.reply("Эта функция доступна только техникам.")
        return
    cursor.execute("""
    SELECT DISTINCT u.profile_name, u.telegram_id
    FROM users u
    JOIN works w ON u.telegram_id = w.dentist_id
    WHERE w.technician_id = ? AND w.status = 'active'
    """, (message.from_user.id,))
    dentists = cursor.fetchall()
    if not dentists:
        await message.reply("У вас нет активных работ.")
        return
    keyboard = InlineKeyboardMarkup()
    for dentist_name, dentist_id in dentists:
        keyboard.add(InlineKeyboardButton(dentist_name, callback_data=f"dentist_{dentist_id}"))
    await message.reply("<b>Стоматологи с активными работами:</b>", parse_mode="HTML", reply_markup=keyboard)

# Обработчик выбора стоматолога для техника
@dp.callback_query_handler(lambda c: c.data.startswith('dentist_'))
async def list_works_by_dentist(callback_query: types.CallbackQuery):
    dentist_id = int(callback_query.data.split('_')[1])
    technician_id = callback_query.from_user.id
    cursor.execute("SELECT work_id, patient_name FROM works WHERE dentist_id = ? AND technician_id = ? AND status = 'active'", (dentist_id, technician_id))
    works = cursor.fetchall()
    if not works:
        await callback_query.message.reply("У этого стоматолога нет активных работ для вас.")
        return
    keyboard = InlineKeyboardMarkup()
    for work_id, patient_name in works:
        keyboard.add(InlineKeyboardButton(f"Работа для {patient_name}", callback_data=f"work_{work_id}"))
    await callback_query.message.reply(f"<b>Активные работы от {get_profile_name(dentist_id)}:</b>", parse_mode="HTML", reply_markup=keyboard)

# Детали работы
@dp.callback_query_handler(lambda c: c.data.startswith('work_'))
async def show_work_details(callback_query: types.CallbackQuery):
    work_id = int(callback_query.data.split('_')[1])
    cursor.execute("SELECT * FROM works WHERE work_id = ?", (work_id,))
    work = cursor.fetchone()
    if not work:
        await callback_query.message.reply("Работа не найдена.")
        return
    user_group = get_user_group(callback_query.from_user.id)
    message = f"<b>Работа для пациента {work[1]} (ID: {work[0]})</b>\n"
    if user_group == 'dentist':
        message += f"Телефон: {work[2]}\n"
    message += f"Тип работы: {work[3]}\n"
    message += f"Название: {work[4]}\n"
    message += f"Срок сдачи: {work[5]}\n"
    if user_group == 'dentist':
        message += f"Стоимость: {work[6]} руб.\n"
    message += f"Статус: {work[7]}\n"
    cursor.execute("SELECT profile_name FROM users WHERE telegram_id = ?", (work[8],))
    dentist_name = cursor.fetchone()[0]
    message += f"Стоматолог: {dentist_name}\n"
    await bot.send_message(callback_query.from_user.id, message, parse_mode="HTML")
    cursor.execute("SELECT file_id FROM photos WHERE work_id = ?", (work_id,))
    photos = cursor.fetchall()
    cursor.execute("SELECT file_id FROM videos WHERE work_id = ?", (work_id,))
    videos = cursor.fetchall()
    if photos or videos:
        media = types.MediaGroup()
        for photo in photos:
            media.attach_photo(photo[0])
        for video in videos:
            media.attach_video(video[0])
        await bot.send_media_group(callback_query.from_user.id, media)
    if user_group == 'technician' and work[7] == 'active':
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Готово ✅", callback_data=f"done_{work_id}"))
        keyboard.add(InlineKeyboardButton("Задерживается ⏳", callback_data=f"delay_{work_id}"))
        await bot.send_message(callback_query.from_user.id, "<b>Действия с работой:</b>", parse_mode="HTML", reply_markup=keyboard)

# Обработчик "Готово"
@dp.callback_query_handler(lambda c: c.data.startswith('done_'))
async def mark_work_done(callback_query: types.CallbackQuery):
    work_id = int(callback_query.data.split('_')[1])
    cursor.execute("UPDATE works SET status = 'archive' WHERE work_id = ?", (work_id,))
    conn.commit()
    cursor.execute("SELECT dentist_id, patient_name FROM works WHERE work_id = ?", (work_id,))
    dentist_id, patient_name = cursor.fetchone()
    await bot.send_message(dentist_id, f"Работа для <b>{patient_name}</b> выполнена. ✅", parse_mode="HTML")
    await callback_query.message.reply("Работа помечена как выполненная.")

# Обработчик "Задерживается"
@dp.callback_query_handler(lambda c: c.data.startswith('delay_'))
async def mark_work_delayed(callback_query: types.CallbackQuery):
    work_id = int(callback_query.data.split('_')[1])
    cursor.execute("SELECT dentist_id, patient_name FROM works WHERE work_id = ?", (work_id,))
    dentist_id, patient_name = cursor.fetchone()
    await bot.send_message(dentist_id, f"Работа для <b>{patient_name}</b> задерживается. ⏳", parse_mode="HTML")
    await callback_query.message.reply("Стоматолог уведомлен о задержке.")

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)