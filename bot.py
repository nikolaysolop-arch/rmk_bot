import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler

BOT_TOKEN = "8716121180:AAH65vB8TdRtniRGn41XSIVZx5QZ6UmHY8w"
ADMIN_ID = 6127276408

LOGIN, PASSWORD = range(2)
BASE_URL = "https://rmk.stavedu.ru:8010"

def init_db():
    conn = sqlite3.connect('rmk_student.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  login TEXT,
                  password TEXT,
                  last_update TEXT)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('rmk_student.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def save_user(user_id, username, login, password):
    conn = sqlite3.connect('rmk_student.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, username, login, password, last_update) VALUES (?,?,?,?,?)",
              (user_id, username, login, password, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

def parse_rmk_student(login, password):
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    try:
        resp = session.get(f"{BASE_URL}/", verify=False, timeout=30)
        login_data = {'login': login, 'password': password, 'submit': 'Войти'}
        resp = session.post(f"{BASE_URL}/login", data=login_data, verify=False, timeout=30)
        if "неверный" in resp.text.lower() or "error" in resp.text.lower():
            return None, "Ошибка авторизации"
        soup = BeautifulSoup(resp.text, 'html.parser')
        name_elem = soup.find('div', class_='student-name')
        student_name = name_elem.text.strip() if name_elem else "Студент"
        grades = []
        grades_table = soup.find('table', class_='journal')
        if grades_table:
            for row in grades_table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    subject = cells[0].text.strip()
                    grade = cells[1].text.strip()
                    date = cells[2].text.strip()
                    if subject and grade:
                        grades.append({'subject': subject, 'grade': grade, 'date': date})
        numeric_grades = []
        for g in grades:
            try:
                num = int(''.join(filter(str.isdigit, g['grade']))[0]) if g['grade'] else 0
                if num in [2,3,4,5]:
                    numeric_grades.append(num)
            except:
                pass
        avg_score = round(sum(numeric_grades)/len(numeric_grades),2) if numeric_grades else 0
        absences = {'total': 0, 'excused': 0, 'unexcused': 0}
        homework = []
        return {'name': student_name, 'grades': grades[:15], 'avg_score': avg_score, 'absences': absences, 'homework': homework}, None
    except Exception as e:
        return None, f"Ошибка: {str(e)}"

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📚 Оценки"), KeyboardButton("📊 Средний балл")],
        [KeyboardButton("📖 Пропуски"), KeyboardButton("📝 Домашка")],
        [KeyboardButton("🔗 Привязать аккаунт"), KeyboardButton("🔄 Обновить")],
        [KeyboardButton("❓ Помощь")]
    ], resize_keyboard=True)

def start(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    if user and user[2]:
        update.message.reply_text("🎓 Добро пожаловать! Аккаунт привязан.", parse_mode="HTML", reply_markup=get_main_keyboard())
    else:
        update.message.reply_text("🎓 Кабинет студента РМК\n\nНажми «Привязать аккаунт» и введи логин и пароль.", parse_mode="HTML", reply_markup=get_main_keyboard())

def handle_buttons(update, context):
    text = update.message.text
    uid = update.effective_user.id
    if text == "🔗 Привязать аккаунт":
        update.message.reply_text("Введи логин:")
        return LOGIN
    user = get_user(uid)
    if not user or not user[2]:
        update.message.reply_text("❌ Сначала привяжи аккаунт.")
        return
    if text == "📚 Оценки":
        update.message.reply_text("Загружаю...")
        data, err = parse_rmk_student(user[2], user[3])
        if err:
            update.message.reply_text(f"❌ {err}")
            return
        msg = f"🎓 {data['name']}\n\n📚 Оценки:\n"
        for g in data['grades'][:10]:
            msg += f"📖 {g['subject']}: {g['grade']} ({g['date']})\n"
        update.message.reply_text(msg)
    elif text == "📊 Средний балл":
        data, err = parse_rmk_student(user[2], user[3])
        if err:
            update.message.reply_text(f"❌ {err}")
            return
        update.message.reply_text(f"🎓 {data['name']}\n\nСредний балл: {data['avg_score']}")
    elif text == "📖 Пропуски":
        data, err = parse_rmk_student(user[2], user[3])
        if err:
            update.message.reply_text(f"❌ {err}")
            return
        update.message.reply_text(f"🎓 {data['name']}\n\nПропуски:\n• Всего: {data['absences']['total']}\n• Уважительных: {data['absences']['excused']}\n• Неуважительных: {data['absences']['unexcused']}")
    elif text == "📝 Домашка":
        data, err = parse_rmk_student(user[2], user[3])
        if err:
            update.message.reply_text(f"❌ {err}")
            return
        if not data['homework']:
            update.message.reply_text("Домашних заданий пока нет.")
        else:
            msg = "📝 Домашка:\n" + "\n".join(data['homework'][:10])
            update.message.reply_text(msg)
    elif text == "🔄 Обновить":
        update.message.reply_text("Данные обновлены!")
    elif text == "❓ Помощь":
        update.message.reply_text("❓ Помощь\n\nКнопки:\n📚 Оценки\n📊 Средний балл\n📖 Пропуски\n📝 Домашка\n🔗 Привязать аккаунт\n🔄 Обновить")

def handle_login(update, context):
    context.user_data['login'] = update.message.text.strip()
    update.message.reply_text("Введи пароль:")
    return PASSWORD

def handle_password(update, context):
    uid = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    login = context.user_data.get('login')
    password = update.message.text.strip()
    update.message.reply_text("Проверяю...")
    data, err = parse_rmk_student(login, password)
    if err:
        update.message.reply_text(f"❌ {err}\nПопробуй ещё раз.")
        return ConversationHandler.END
    save_user(uid, username, login, password)
    update.message.reply_text(f"✅ Аккаунт привязан!\nПривет, {data['name']}!", reply_markup=get_main_keyboard())
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("❌ Отменено.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

if __name__ == "__main__":
    init_db()
    from telegram.ext import Updater, CommandHandler, ConversationHandler
    updater = Updater(token=BOT_TOKEN)
    dp = updater.dispatcher
    conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('🔗 Привязать аккаунт'), handle_buttons)],
        states={LOGIN: [MessageHandler(Filters.text & ~Filters.command, handle_login)], PASSWORD: [MessageHandler(Filters.text & ~Filters.command, handle_password)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_buttons))
    dp.add_handler(conv)
    updater.start_polling()
    print("Бот запущен!")
    updater.idle()
