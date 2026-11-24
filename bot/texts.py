"""User-facing texts in Russian, Kazakh and English."""

from __future__ import annotations

LANGS = ("ru", "kk", "en")
DEFAULT_LANG = "ru"

TEXTS: dict[str, dict[str, str]] = {
    # ---- main keyboard buttons -------------------------------------------
    "btn_menu": {"ru": "🍽 Меню ресторана", "kk": "🍽 Мейрамхана мәзірі", "en": "🍽 Restaurant menu"},
    "btn_booking": {"ru": "📅 Забронировать столик", "kk": "📅 Үстел брондау", "en": "📅 Book a table"},
    "btn_ai": {"ru": "🤖 AI-консультант", "kk": "🤖 AI-кеңесші", "en": "🤖 AI consultant"},
    "btn_event": {"ru": "🎉 Организовать мероприятие", "kk": "🎉 Іс-шара ұйымдастыру", "en": "🎉 Organize an event"},
    "btn_budget": {"ru": "💰 Рассчитать бюджет", "kk": "💰 Бюджетті есептеу", "en": "💰 Budget calculator"},
    "btn_contacts": {"ru": "📍 Контакты", "kk": "📍 Байланыс", "en": "📍 Contacts"},
    "btn_about": {"ru": "ℹ️ О ресторане", "kk": "ℹ️ Мейрамхана туралы", "en": "ℹ️ About us"},
    "btn_cancel": {"ru": "❌ Отмена", "kk": "❌ Болдырмау", "en": "❌ Cancel"},
    "btn_skip": {"ru": "➡️ Пропустить", "kk": "➡️ Өткізіп жіберу", "en": "➡️ Skip"},
    "btn_share_phone": {"ru": "📱 Отправить мой номер", "kk": "📱 Нөмірімді жіберу", "en": "📱 Share my number"},
    "btn_back": {"ru": "⬅️ Назад", "kk": "⬅️ Артқа", "en": "⬅️ Back"},
    "btn_confirm": {"ru": "✅ Подтвердить", "kk": "✅ Растау", "en": "✅ Confirm"},
    "btn_restart": {"ru": "✏️ Заполнить заново", "kk": "✏️ Қайта толтыру", "en": "✏️ Start over"},
    "btn_per_person": {"ru": "👤 На человека", "kk": "👤 Адамына", "en": "👤 Per person"},
    "btn_total": {"ru": "👥 Общий бюджет", "kk": "👥 Жалпы бюджет", "en": "👥 Total budget"},
    "btn_today": {"ru": "Сегодня", "kk": "Бүгін", "en": "Today"},
    "btn_tomorrow": {"ru": "Завтра", "kk": "Ертең", "en": "Tomorrow"},
    "btn_ai_reset": {"ru": "🧹 Новый диалог", "kk": "🧹 Жаңа диалог", "en": "🧹 New chat"},
    "btn_exit_ai": {"ru": "🏠 Главное меню", "kk": "🏠 Басты мәзір", "en": "🏠 Main menu"},
    "btn_ask_ai_dish": {"ru": "🤖 Спросить AI о блюде", "kk": "🤖 AI-дан сұрау", "en": "🤖 Ask AI about it"},

    # ---- general ---------------------------------------------------------
    "choose_language": {
        "ru": "Выберите язык / Тілді таңдаңыз / Choose your language:",
        "kk": "Тілді таңдаңыз / Выберите язык / Choose your language:",
        "en": "Choose your language / Выберите язык / Тілді таңдаңыз:",
    },
    "welcome": {
        "ru": "Сәлеметсіз бе, {name}! 👋\n\nДобро пожаловать в <b>Qazaq Taste</b> — ресторан современной "
              "казахской кухни в Алматы.\n\nЯ помогу выбрать блюда, оставить заявку на бронирование, рассчитать "
              "бюджет и подготовить предложение для мероприятия. Выберите раздел в меню ниже 👇",
        "kk": "Сәлеметсіз бе, {name}! 👋\n\n<b>Qazaq Taste</b> — Алматыдағы заманауи қазақ асханасы "
              "мейрамханасына қош келдіңіз!\n\nТағам таңдауға, брондауға өтінім қалдыруға, бюджетті есептеуге "
              "және іс-шараға ұсыныс дайындауға көмектесемін. Төмендегі бөлімді таңдаңыз 👇",
        "en": "Salemetsiz be, {name}! 👋\n\nWelcome to <b>Qazaq Taste</b> — a modern Kazakh cuisine restaurant "
              "in Almaty.\n\nI can help you choose dishes, leave a booking request, calculate a budget and prepare "
              "an event proposal. Pick a section below 👇",
    },
    "help": {
        "ru": "<b>Что умеет бот</b>\n\n"
              "/start — главное меню\n/menu — меню ресторана\n/booking — заявка на бронирование\n"
              "/event — коммерческое предложение для мероприятия\n/budget — расчёт бюджета\n"
              "/ai — AI-консультант\n/reset — очистить историю диалога с AI\n/language — сменить язык\n"
              "/cancel — отменить текущее действие\n/help — эта справка\n\n"
              "В режиме AI-консультанта просто пишите вопросы о блюдах, составе, бюджете и мероприятиях.",
        "kk": "<b>Бот мүмкіндіктері</b>\n\n"
              "/start — басты мәзір\n/menu — мейрамхана мәзірі\n/booking — брондауға өтінім\n"
              "/event — іс-шараға коммерциялық ұсыныс\n/budget — бюджет есебі\n"
              "/ai — AI-кеңесші\n/reset — AI диалог тарихын тазарту\n/language — тілді ауыстыру\n"
              "/cancel — ағымдағы әрекетті болдырмау\n/help — анықтама\n\n"
              "AI-кеңесші режимінде тағамдар, құрамы, бюджет және іс-шаралар туралы сұрақ жазыңыз.",
        "en": "<b>What this bot can do</b>\n\n"
              "/start — main menu\n/menu — restaurant menu\n/booking — booking request\n"
              "/event — commercial proposal for an event\n/budget — budget calculator\n"
              "/ai — AI consultant\n/reset — clear AI chat history\n/language — change language\n"
              "/cancel — cancel the current action\n/help — this help\n\n"
              "In AI consultant mode just ask about dishes, ingredients, budgets and events.",
    },
    "main_menu": {"ru": "Главное меню 👇", "kk": "Басты мәзір 👇", "en": "Main menu 👇"},
    "language_set": {"ru": "Язык: русский 🇷🇺", "kk": "Тіл: қазақша 🇰🇿", "en": "Language: English 🇬🇧"},
    "cancelled": {"ru": "Действие отменено.", "kk": "Әрекет болдырылмады.", "en": "Cancelled."},
    "nothing_to_cancel": {"ru": "Нечего отменять.", "kk": "Болдырмайтын әрекет жоқ.", "en": "Nothing to cancel."},
    "error_generic": {
        "ru": "😔 Произошла ошибка. Попробуйте ещё раз или отправьте /start.",
        "kk": "😔 Қате орын алды. Қайталап көріңіз немесе /start жіберіңіз.",
        "en": "😔 Something went wrong. Please try again or send /start.",
    },
    "use_buttons": {
        "ru": "Пожалуйста, воспользуйтесь кнопками ниже.",
        "kk": "Төмендегі батырмаларды пайдаланыңыз.",
        "en": "Please use the buttons below.",
    },

    # ---- menu ------------------------------------------------------------
    "menu_intro": {
        "ru": "🍽 <b>Меню Qazaq Taste</b>\nВыберите категорию. 🌱 — вегетарианское, 🌶 — острое.\n"
              "Ко всем заказам добавляется обслуживание {charge}%.",
        "kk": "🍽 <b>Qazaq Taste мәзірі</b>\nСанатты таңдаңыз. 🌱 — вегетариандық, 🌶 — ащы.\n"
              "Барлық тапсырысқа {charge}% қызмет көрсету қосылады.",
        "en": "🍽 <b>Qazaq Taste menu</b>\nChoose a category. 🌱 — vegetarian, 🌶 — spicy.\n"
              "A {charge}% service charge is added to all orders.",
    },
    "dish_not_found": {"ru": "Блюдо не найдено.", "kk": "Тағам табылмады.", "en": "Dish not found."},

    # ---- booking ---------------------------------------------------------
    "booking_start": {
        "ru": "📅 <b>Заявка на бронирование</b>\nОтветьте на несколько вопросов. Отменить можно в любой момент "
              "кнопкой «❌ Отмена» или /cancel.\n\n1/6. Как к вам обращаться? Введите имя:",
        "kk": "📅 <b>Брондауға өтінім</b>\nБірнеше сұраққа жауап беріңіз. Кез келген уақытта «❌ Болдырмау» "
              "немесе /cancel арқылы тоқтатуға болады.\n\n1/6. Атыңызды енгізіңіз:",
        "en": "📅 <b>Booking request</b>\nPlease answer a few questions. You can stop any time with "
              "\"❌ Cancel\" or /cancel.\n\n1/6. What is your name?",
    },
    "ask_phone": {
        "ru": "2/6. Укажите номер телефона (например, +7 701 123 45 67) или нажмите кнопку ниже:",
        "kk": "2/6. Телефон нөміріңізді жазыңыз (мысалы, +7 701 123 45 67) немесе төмендегі батырманы басыңыз:",
        "en": "2/6. Your phone number (e.g. +7 701 123 45 67), or tap the button below:",
    },
    "ask_date": {
        "ru": "3/6. Дата визита в формате ДД.ММ.ГГГГ (например, {example}), или «Сегодня» / «Завтра»:",
        "kk": "3/6. Келу күні КК.АА.ЖЖЖЖ форматында (мысалы, {example}) немесе «Бүгін» / «Ертең»:",
        "en": "3/6. Date of visit as DD.MM.YYYY (e.g. {example}), or \"Today\" / \"Tomorrow\":",
    },
    "ask_time": {
        "ru": "4/6. Время визита (ЧЧ:ММ). В этот день бронирование доступно с {first} до {last}:",
        "kk": "4/6. Келу уақыты (СС:ММ). Бұл күні брондау {first} мен {last} аралығында қолжетімді:",
        "en": "4/6. Time of visit (HH:MM). On this day bookings are possible from {first} to {last}:",
    },
    "ask_guests": {
        "ru": "5/6. Сколько будет гостей? (1–{max})",
        "kk": "5/6. Қанша қонақ болады? (1–{max})",
        "en": "5/6. How many guests? (1–{max})",
    },
    "ask_wishes": {
        "ru": "6/6. Дополнительные пожелания (зал, детский стул, повод, аллергии) — или нажмите «Пропустить»:",
        "kk": "6/6. Қосымша тілектер (зал, балалар орындығы, себеп, аллергия) — немесе «Өткізіп жіберу»:",
        "en": "6/6. Any wishes (hall, high chair, occasion, allergies) — or tap \"Skip\":",
    },
    "booking_summary": {
        "ru": "<b>Проверьте данные заявки:</b>\n\n👤 Имя: {name}\n📱 Телефон: {phone}\n📅 Дата: {date}\n"
              "🕐 Время: {time}\n👥 Гостей: {guests}\n📝 Пожелания: {wishes}\n\nВсё верно?",
        "kk": "<b>Өтінім деректерін тексеріңіз:</b>\n\n👤 Аты: {name}\n📱 Телефон: {phone}\n📅 Күні: {date}\n"
              "🕐 Уақыты: {time}\n👥 Қонақтар: {guests}\n📝 Тілектер: {wishes}\n\nБәрі дұрыс па?",
        "en": "<b>Please check your request:</b>\n\n👤 Name: {name}\n📱 Phone: {phone}\n📅 Date: {date}\n"
              "🕐 Time: {time}\n👥 Guests: {guests}\n📝 Wishes: {wishes}\n\nIs everything correct?",
    },
    "confirm_check": {
        "ru": "Почти готово ✍️",
        "kk": "Дерлік дайын ✍️",
        "en": "Almost done ✍️",
    },
    "confirm_hint": {
        "ru": "Чтобы отправить заявку, нажмите «✅ Подтвердить» под сообщением с данными заявки "
              "(или «✏️ Заполнить заново»).",
        "kk": "Өтінімді жіберу үшін деректер жазылған хабарламаның астындағы «✅ Растау» батырмасын басыңыз "
              "(немесе «✏️ Қайта толтыру»).",
        "en": "To send the request, tap \"✅ Confirm\" under the message with your details "
              "(or \"✏️ Start over\").",
    },
    "no_wishes": {"ru": "нет", "kk": "жоқ", "en": "none"},
    "booking_done": {
        "ru": "✅ <b>Заявка на бронирование принята!</b>\n\nНомер заявки: <code>{code}</code>\n"
              "📅 {date} в {time}, гостей: {guests}\n\n"
              "⚠️ Это заявка, а не подтверждённая бронь: администратор проверит наличие свободных столов и "
              "свяжется с вами по номеру {phone} для подтверждения.\nЕсли планы изменятся — позвоните нам: {rphone}.",
        "kk": "✅ <b>Брондауға өтінім қабылданды!</b>\n\nӨтінім нөмірі: <code>{code}</code>\n"
              "📅 {date}, сағат {time}, қонақтар: {guests}\n\n"
              "⚠️ Бұл расталған бронь емес, өтінім: әкімші бос үстелдерді тексеріп, растау үшін {phone} "
              "нөміріне хабарласады.\nЖоспар өзгерсе, бізге қоңырау шалыңыз: {rphone}.",
        "en": "✅ <b>Booking request received!</b>\n\nRequest number: <code>{code}</code>\n"
              "📅 {date} at {time}, guests: {guests}\n\n"
              "⚠️ This is a request, not a confirmed reservation: our administrator will check table "
              "availability and contact you at {phone} to confirm.\nIf your plans change, call us: {rphone}.",
    },
    "booking_large_group": {
        "ru": "Для групп более {max} гостей воспользуйтесь разделом «🎉 Организовать мероприятие».",
        "kk": "{max} қонақтан көп топтар үшін «🎉 Іс-шара ұйымдастыру» бөлімін пайдаланыңыз.",
        "en": "For groups larger than {max} guests please use \"🎉 Organize an event\".",
    },
    "booking_admin": {
        "ru": "🆕 Новая заявка на бронирование {code}\n{date} {time}, гостей: {guests}\nИмя: {name}\n"
              "Телефон: {phone}\nПожелания: {wishes}",
        "kk": "🆕 Жаңа брондау өтінімі {code}\n{date} {time}, қонақтар: {guests}\nАты: {name}\n"
              "Телефон: {phone}\nТілектер: {wishes}",
        "en": "🆕 New booking request {code}\n{date} {time}, guests: {guests}\nName: {name}\n"
              "Phone: {phone}\nWishes: {wishes}",
    },
    "session_expired": {
        "ru": "Сессия устарела, начните заново.",
        "kk": "Сессия ескірді, қайтадан бастаңыз.",
        "en": "This session has expired, please start again.",
    },

    # ---- booking from free text (JSON extraction) -------------------------
    "jb_q_date": {
        "ru": "На какую дату хотите забронировать столик? (например, 25.11.2026 или «завтра»)",
        "kk": "Үстелді қай күнге брондағыңыз келеді? (мысалы, 25.11.2026 немесе «ертең»)",
        "en": "For what date would you like to book a table? (e.g. 25.11.2026 or \"tomorrow\")",
    },
    "jb_q_time": {
        "ru": "На какое время хотите забронировать столик?",
        "kk": "Үстелді қай уақытқа брондағыңыз келеді?",
        "en": "What time would you like to book the table for?",
    },
    "jb_q_guests": {
        "ru": "Сколько будет гостей?",
        "kk": "Қанша қонақ болады?",
        "en": "How many guests will there be?",
    },
    "jb_q_name": {
        "ru": "Как к вам обращаться?",
        "kk": "Сізге қалай жүгінейін?",
        "en": "What name should we put the booking under?",
    },
    "jb_q_phone": {
        "ru": "Укажите, пожалуйста, номер телефона для связи (11 цифр, например +7 701 123 45 67).",
        "kk": "Байланыс үшін телефон нөміріңізді жазыңыз (11 сан, мысалы +7 701 123 45 67).",
        "en": "Please share a contact phone number (11 digits, e.g. +7 701 123 45 67).",
    },
    "err_phone_11": {
        "ru": "Номер телефона должен содержать 11 цифр, например +7 701 123 45 67. Укажите номер ещё раз:",
        "kk": "Телефон нөмірі 11 саннан тұруы керек, мысалы +7 701 123 45 67. Нөмірді қайта жазыңыз:",
        "en": "The phone number must contain 11 digits, e.g. +7 701 123 45 67. Please enter it again:",
    },
    "jb_summary": {
        "ru": "<b>Бронирование:</b>\nДата: {date}\nВремя: {time}\nГостей: {guests}\nИмя: {name}\nТелефон: {phone}\n\n"
              "Подтверждаете? Ответьте «да» или «нет». Чтобы что-то исправить, просто напишите, например: "
              "«время 20:00».",
        "kk": "<b>Брондау:</b>\nКүні: {date}\nУақыты: {time}\nҚонақтар: {guests}\nАты: {name}\nТелефон: {phone}\n\n"
              "Растайсыз ба? «иә» немесе «жоқ» деп жауап беріңіз. Түзету үшін жазыңыз, мысалы: «уақыты 20:00».",
        "en": "<b>Booking:</b>\nDate: {date}\nTime: {time}\nGuests: {guests}\nName: {name}\nPhone: {phone}\n\n"
              "Do you confirm? Reply \"yes\" or \"no\". To change something just write, e.g. \"time 20:00\".",
    },
    "jb_saved": {
        "ru": "✅ Заявка на бронирование принята! Номер заявки: <code>{code}</code>\n"
              "⚠️ Это заявка, а не подтверждённая бронь: администратор проверит свободные столы и свяжется с вами "
              "для подтверждения.",
        "kk": "✅ Брондауға өтінім қабылданды! Өтінім нөмірі: <code>{code}</code>\n"
              "⚠️ Бұл расталған бронь емес, өтінім: әкімші бос үстелдерді тексеріп, растау үшін хабарласады.",
        "en": "✅ Booking request received! Request number: <code>{code}</code>\n"
              "⚠️ This is a request, not a confirmed reservation: our administrator will check availability and "
              "contact you to confirm.",
    },
    "jb_cancelled": {
        "ru": "Хорошо, заявка не отправлена и не сохранена.",
        "kk": "Жақсы, өтінім жіберілмеді және сақталмады.",
        "en": "OK, the request was not sent or saved.",
    },
    "jb_invalid_json": {
        "ru": "😔 Не удалось разобрать заявку. Пожалуйста, напишите её ещё раз одним сообщением, например: "
              "«Столик на завтра в 19:00 на 4 человек».",
        "kk": "😔 Өтінімді түсіну мүмкін болмады. Оны бір хабарламамен қайта жазыңыз, мысалы: "
              "«Ертеңге сағат 19:00-ге 4 адамға үстел».",
        "en": "😔 I couldn't read the request. Please write it again in one message, e.g. "
              "\"A table for 4 tomorrow at 19:00\".",
    },
    "jb_invalid_answer": {
        "ru": "😔 Не удалось разобрать ответ. Повторите, пожалуйста.",
        "kk": "😔 Жауапты түсіну мүмкін болмады. Қайталаңызшы.",
        "en": "😔 I couldn't read the answer. Please repeat it.",
    },
    "jb_not_understood": {
        "ru": "Чтобы продолжить бронирование, ответьте, пожалуйста, на вопрос (или /cancel для отмены).",
        "kk": "Брондауды жалғастыру үшін сұраққа жауап беріңіз (болдырмау үшін /cancel).",
        "en": "To continue the booking please answer the question (or /cancel to stop).",
    },
    "jb_confirm_hint": {
        "ru": "Ответьте «да», чтобы подтвердить заявку, или «нет», чтобы отменить.",
        "kk": "Өтінімді растау үшін «иә», болдырмау үшін «жоқ» деп жауап беріңіз.",
        "en": "Reply \"yes\" to confirm the request or \"no\" to cancel it.",
    },

    # ---- validation errors -----------------------------------------------
    "err_name": {
        "ru": "Имя должно содержать только буквы (2–60 символов). Попробуйте ещё раз:",
        "kk": "Атыңыз тек әріптерден тұруы керек (2–60 таңба). Қайталап көріңіз:",
        "en": "The name should contain letters only (2–60 characters). Please try again:",
    },
    "err_phone": {
        "ru": "Некорректный номер. Пример: +7 701 123 45 67",
        "kk": "Нөмір қате. Мысалы: +7 701 123 45 67",
        "en": "Invalid phone number. Example: +7 701 123 45 67",
    },
    "err_date_format": {
        "ru": "Не удалось распознать дату. Используйте формат ДД.ММ.ГГГГ, например 25.12.2026:",
        "kk": "Күнді тану мүмкін болмады. КК.АА.ЖЖЖЖ форматын қолданыңыз, мысалы 25.12.2026:",
        "en": "Could not read the date. Please use DD.MM.YYYY, e.g. 25.12.2026:",
    },
    "err_date_past": {
        "ru": "Эта дата уже прошла. Укажите сегодняшнюю или будущую дату:",
        "kk": "Бұл күн өтіп кетті. Бүгінгі немесе болашақ күнді көрсетіңіз:",
        "en": "This date is in the past. Please choose today or a future date:",
    },
    "err_date_far": {
        "ru": "Бронирование доступно не более чем на {days} дней вперёд. Укажите другую дату:",
        "kk": "Брондау {days} күннен артық алдын ала қолжетімсіз. Басқа күнді көрсетіңіз:",
        "en": "Bookings are possible at most {days} days ahead. Please choose another date:",
    },
    "err_time_format": {
        "ru": "Укажите время в формате ЧЧ:ММ, например 19:30:",
        "kk": "Уақытты СС:ММ форматында көрсетіңіз, мысалы 19:30:",
        "en": "Please enter the time as HH:MM, e.g. 19:30:",
    },
    "err_time_hours": {
        "ru": "В этот день можно забронировать столик с {first} до {last}. Укажите другое время:",
        "kk": "Бұл күні үстелді {first} мен {last} аралығында брондауға болады. Басқа уақытты көрсетіңіз:",
        "en": "On this day tables can be booked from {first} to {last}. Please choose another time:",
    },
    "err_time_past": {
        "ru": "Это время уже прошло или слишком близко (нужно минимум {minutes} минут). Укажите другое время:",
        "kk": "Бұл уақыт өтіп кетті немесе тым жақын (кемінде {minutes} минут қажет). Басқа уақытты көрсетіңіз:",
        "en": "This time has passed or is too soon (at least {minutes} minutes ahead). Please choose another time:",
    },
    "err_guests_format": {
        "ru": "Введите количество гостей числом, например 4:",
        "kk": "Қонақ санын сан түрінде енгізіңіз, мысалы 4:",
        "en": "Please enter the number of guests as a number, e.g. 4:",
    },
    "err_guests_max": {
        "ru": "Максимум {maximum} гостей. Для больших групп используйте «🎉 Организовать мероприятие». "
              "Введите другое число:",
        "kk": "Ең көбі {maximum} қонақ. Үлкен топтар үшін «🎉 Іс-шара ұйымдастыру» бөлімін пайдаланыңыз. "
              "Басқа сан енгізіңіз:",
        "en": "Maximum {maximum} guests. For larger groups use \"🎉 Organize an event\". Enter another number:",
    },
    "err_wishes_long": {
        "ru": "Слишком длинный текст (максимум {maximum} символов). Сократите, пожалуйста:",
        "kk": "Мәтін тым ұзын (ең көбі {maximum} таңба). Қысқартыңыз:",
        "en": "Text is too long (max {maximum} characters). Please shorten it:",
    },
    "err_number": {
        "ru": "Введите сумму числом в тенге, например 150000:",
        "kk": "Соманы теңгемен сан түрінде енгізіңіз, мысалы 150000:",
        "en": "Please enter the amount in tenge as a number, e.g. 150000:",
    },
    "err_budget_small": {
        "ru": "Бюджет слишком мал (минимум {min} на человека). Введите другую сумму:",
        "kk": "Бюджет тым аз (адамына кемінде {min}). Басқа соманы енгізіңіз:",
        "en": "The budget is too small (at least {min} per person). Please enter another amount:",
    },
    "err_text_expected": {
        "ru": "Пожалуйста, отправьте ответ текстом.",
        "kk": "Жауапты мәтінмен жіберіңіз.",
        "en": "Please reply with text.",
    },

    # ---- AI ----------------------------------------------------------------
    "ai_intro": {
        "ru": "🤖 <b>AI-консультант Qazaq Taste</b>\n\nЗадайте любой вопрос о меню, составе блюд, "
              "вегетарианских вариантах, бюджете или мероприятиях. Например:\n"
              "• «Что попробовать впервые?»\n• «Что есть без глютена?»\n• «Ужин на двоих до 15 000 ₸»\n\n"
              "Я — AI-ассистент, а не сотрудник ресторана. Цены и бронирования подтверждаются через кнопки бота.",
        "kk": "🤖 <b>Qazaq Taste AI-кеңесшісі</b>\n\nМәзір, тағам құрамы, вегетариандық нұсқалар, бюджет "
              "немесе іс-шаралар туралы сұрақ қойыңыз. Мысалы:\n"
              "• «Алғаш келгенде не татып көру керек?»\n• «Глютенсіз не бар?»\n• «Екі адамға 15 000 ₸-ге дейін кешкі ас»\n\n"
              "Мен мейрамхана қызметкері емес, AI-көмекшімін. Бағалар мен брондау бот батырмалары арқылы расталады.",
        "en": "🤖 <b>Qazaq Taste AI consultant</b>\n\nAsk anything about the menu, ingredients, vegetarian options, "
              "budgets or events. For example:\n"
              "• \"What should I try on my first visit?\"\n• \"What is gluten-free?\"\n"
              "• \"Dinner for two under 15 000 ₸\"\n\n"
              "I'm an AI assistant, not a restaurant employee. Prices and bookings are confirmed via the bot buttons.",
    },
    "ai_reset_done": {
        "ru": "🧹 История диалога очищена.",
        "kk": "🧹 Диалог тарихы тазартылды.",
        "en": "🧹 Chat history cleared.",
    },
    "ai_text_only": {
        "ru": "Я понимаю только текстовые сообщения 🙂",
        "kk": "Мен тек мәтіндік хабарламаларды түсінемін 🙂",
        "en": "I can only read text messages 🙂",
    },
    "ai_busy": {
        "ru": "⏳ Обрабатываю предыдущий вопрос, подождите немного…",
        "kk": "⏳ Алдыңғы сұрақты өңдеп жатырмын, күте тұрыңыз…",
        "en": "⏳ Still working on your previous question, please wait…",
    },

    # ---- events ----------------------------------------------------------
    "event_start": {
        "ru": "🎉 <b>Организация мероприятия</b>\nПодготовлю коммерческое предложение по реальным ценам меню.",
        "kk": "🎉 <b>Іс-шара ұйымдастыру</b>\nМәзірдің нақты бағалары бойынша коммерциялық ұсыныс дайындаймын.",
        "en": "🎉 <b>Event planning</b>\nI'll prepare a commercial proposal based on real menu prices.",
    },
    "event_ask_type": {
        "ru": "1/6. Выберите тип мероприятия:",
        "kk": "1/6. Іс-шара түрін таңдаңыз:",
        "en": "1/6. Choose the event type:",
    },
    "event_ask_guests": {
        "ru": "2/6. Сколько будет гостей? (1–{max})",
        "kk": "2/6. Қанша қонақ болады? (1–{max})",
        "en": "2/6. How many guests? (1–{max})",
    },
    "event_ask_date": {
        "ru": "3/6. Дата мероприятия (ДД.ММ.ГГГГ):",
        "kk": "3/6. Іс-шара күні (КК.АА.ЖЖЖЖ):",
        "en": "3/6. Event date (DD.MM.YYYY):",
    },
    "event_ask_budget_type": {
        "ru": "4/6. Как вы планируете бюджет?",
        "kk": "4/6. Бюджетті қалай жоспарлайсыз?",
        "en": "4/6. How would you like to set the budget?",
    },
    "event_ask_budget_pp": {
        "ru": "Введите бюджет на одного человека в тенге (например, 15000):",
        "kk": "Бір адамға арналған бюджетті теңгемен енгізіңіз (мысалы, 15000):",
        "en": "Enter the budget per person in tenge (e.g. 15000):",
    },
    "event_ask_budget_total": {
        "ru": "Введите общий бюджет в тенге (например, 500000):",
        "kk": "Жалпы бюджетті теңгемен енгізіңіз (мысалы, 500000):",
        "en": "Enter the total budget in tenge (e.g. 500000):",
    },
    "event_ask_wishes": {
        "ru": "5/6. Пожелания: например, «вегетарианское меню», «домбра», «фотограф», «ведущий», «проектор» — "
              "или «Пропустить»:",
        "kk": "5/6. Тілектер: мысалы, «вегетариандық мәзір», «домбыра», «фотограф», «асаба», «проектор» — "
              "немесе «Өткізіп жіберу»:",
        "en": "5/6. Wishes: e.g. \"vegetarian menu\", \"dombra\", \"photographer\", \"host\", \"projector\" — "
              "or \"Skip\":",
    },
    "event_ask_phone": {
        "ru": "6/6. Телефон для связи с менеджером (или «Пропустить»):",
        "kk": "6/6. Менеджермен байланысу үшін телефон (немесе «Өткізіп жіберу»):",
        "en": "6/6. Phone number for the manager to contact you (or \"Skip\"):",
    },
    "event_saved": {
        "ru": "✅ Заявка на мероприятие сохранена под номером <code>{code}</code>. Менеджер свяжется с вами "
              "для уточнения деталей и подтверждения доступности зала.",
        "kk": "✅ Іс-шара өтінімі <code>{code}</code> нөмірімен сақталды. Менеджер мәліметтерді нақтылау және "
              "залдың бос екенін растау үшін хабарласады.",
        "en": "✅ Event request saved as <code>{code}</code>. A manager will contact you to clarify the details "
              "and confirm hall availability.",
    },
    "event_saved_no_phone": {
        "ru": "Вы не оставили телефон — позвоните нам для подтверждения: {rphone}.",
        "kk": "Телефон қалдырмадыңыз — растау үшін бізге қоңырау шалыңыз: {rphone}.",
        "en": "You didn't leave a phone number — please call us to confirm: {rphone}.",
    },
    "event_admin": {
        "ru": "🆕 Новая заявка на мероприятие {code}\n{type}, {date}, гостей: {guests}\nИтого: {total}\nТелефон: {phone}",
        "kk": "🆕 Жаңа іс-шара өтінімі {code}\n{type}, {date}, қонақтар: {guests}\nБарлығы: {total}\nТелефон: {phone}",
        "en": "🆕 New event request {code}\n{type}, {date}, guests: {guests}\nTotal: {total}\nPhone: {phone}",
    },

    # ---- budget ----------------------------------------------------------
    "budget_start": {
        "ru": "💰 <b>Расчёт бюджета</b>\n\n1/2. Сколько будет гостей? (1–{max})",
        "kk": "💰 <b>Бюджет есебі</b>\n\n1/2. Қанша қонақ болады? (1–{max})",
        "en": "💰 <b>Budget calculator</b>\n\n1/2. How many guests? (1–{max})",
    },
    "budget_ask_amount": {
        "ru": "2/2. Какой общий бюджет в тенге? (например, 60000)",
        "kk": "2/2. Жалпы бюджет қанша теңге? (мысалы, 60000)",
        "en": "2/2. What is the total budget in tenge? (e.g. 60000)",
    },
    "budget_next": {
        "ru": "Для банкета или корпоратива с полным расчётом услуг — «🎉 Организовать мероприятие».",
        "kk": "Қызметтерді толық есептейтін банкет немесе корпоратив үшін — «🎉 Іс-шара ұйымдастыру».",
        "en": "For a banquet or corporate party with services included — \"🎉 Organize an event\".",
    },
    "err_guests_event": {
        "ru": "Введите количество гостей числом от 1 до {max}:",
        "kk": "Қонақ санын 1-ден {max}-ге дейін сан түрінде енгізіңіз:",
        "en": "Please enter the number of guests from 1 to {max}:",
    },
}


def tr(key: str, lang: str, **params) -> str:
    entry = TEXTS[key]
    text = entry.get(lang) or entry[DEFAULT_LANG]
    return text.format(**params) if params else text


def all_variants(key: str) -> set[str]:
    return set(TEXTS[key].values())


def normalize_lang(code: str | None) -> str:
    if not code:
        return DEFAULT_LANG
    code = code.lower()[:2]
    if code in ("kk", "kz"):
        return "kk"
    if code in LANGS:
        return code
    return "en" if code not in ("ru", "uk", "be") else "ru"
