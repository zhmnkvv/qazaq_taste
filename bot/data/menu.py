"""Static business data for the fictional restaurant Qazaq Taste.

This module is the single source of truth for dishes, prices, restaurant
facts and event tariffs. Telegram handlers never hard-code these values;
the AI receives them as a knowledge base; all calculations use them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def t(ru: str, kk: str, en: str) -> dict[str, str]:
    return {"ru": ru, "kk": kk, "en": en}


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
CATEGORIES: dict[str, dict[str, str]] = {
    "national": t("🐎 Национальные блюда", "🐎 Ұлттық тағамдар", "🐎 National dishes"),
    "main": t("🍖 Основные блюда", "🍖 Негізгі тағамдар", "🍖 Main courses"),
    "starters": t("🥟 Закуски", "🥟 Тіскебасарлар", "🥟 Starters"),
    "salads": t("🥗 Салаты", "🥗 Салаттар", "🥗 Salads"),
    "drinks": t("🥛 Напитки", "🥛 Сусындар", "🥛 Drinks"),
    "desserts": t("🍯 Десерты", "🍯 Десерттер", "🍯 Desserts"),
}

TAG_LABELS: dict[str, dict[str, str]] = {
    "vegetarian": t("вегетарианское", "вегетариандық", "vegetarian"),
    "spicy": t("острое", "ащы", "spicy"),
    "gluten": t("содержит глютен", "глютені бар", "contains gluten"),
    "dairy": t("содержит молочные продукты", "сүт өнімдері бар", "contains dairy"),
    "nuts": t("содержит орехи", "жаңғақ бар", "contains nuts"),
    "horse_meat": t("конина", "жылқы еті", "horse meat"),
    "fish": t("рыба", "балық", "fish"),
    "alcohol_trace": t(
        "натуральное брожение, следы алкоголя (до 1–2%)",
        "табиғи ашыту, алкоголь іздері (1–2% дейін)",
        "naturally fermented, trace alcohol (up to 1–2%)",
    ),
}


@dataclass(frozen=True)
class Dish:
    id: str
    category: str
    name: dict[str, str]
    description: dict[str, str]
    ingredients: dict[str, str]
    price: int  # KZT per portion
    weight: str  # portion size
    tags: frozenset[str] = field(default_factory=frozenset)

    def localized(self, attr: str, lang: str) -> str:
        values: dict[str, str] = getattr(self, attr)
        return values.get(lang) or values["ru"]

    @property
    def is_vegetarian(self) -> bool:
        return "vegetarian" in self.tags


def _d(id_: str, category: str, name, description, ingredients, price: int, weight: str, *tags: str) -> Dish:
    return Dish(id_, category, name, description, ingredients, price, weight, frozenset(tags))


# --------------------------------------------------------------------------- #
# Dishes
# --------------------------------------------------------------------------- #
DISHES: list[Dish] = [
    # ---- National dishes ---------------------------------------------------
    _d(
        "beshbarmak", "national",
        t("Бешбармак", "Бесбармақ", "Beshbarmak"),
        t(
            "Главное блюдо казахского дастархана: отварное мясо на тонком домашнем тесте с луковым соусом тузлык.",
            "Қазақ дастарханының басты тағамы: жұқа үй қамырындағы асып пісірілген ет пен пиязды тұздық.",
            "The signature dish of the Kazakh table: boiled meat on thin homemade pasta with tuzdyk onion sauce.",
        ),
        t(
            "конина и говядина, казы, домашнее тесто, лук, сорпа (бульон), чёрный перец",
            "жылқы еті мен сиыр еті, қазы, үй қамыры, пияз, сорпа, қара бұрыш",
            "horse meat and beef, kazy, homemade pasta, onion, sorpa broth, black pepper",
        ),
        5900, "450 г", "gluten", "horse_meat",
    ),
    _d(
        "kazy_karta", "national",
        t("Ассорти казы-карта", "Қазы-қарта табағы", "Kazy & karta platter"),
        t(
            "Традиционные деликатесы из конины домашнего приготовления с горчичным соусом.",
            "Үйде дайындалған жылқы етінен жасалған дәстүрлі тағамдар, қыша тұздығымен.",
            "Traditional homemade horse-meat delicacies served with mustard sauce.",
        ),
        t(
            "казы, карта, жал-жая, маринованный лук, горчичный соус",
            "қазы, қарта, жал-жая, маринадталған пияз, қыша тұздығы",
            "kazy sausage, karta, zhal-zhaya, pickled onion, mustard sauce",
        ),
        4900, "250 г", "horse_meat",
    ),
    _d(
        "kuyrdak", "national",
        t("Куырдак", "Қуырдақ", "Kuyrdak"),
        t(
            "Обжаренная баранина с субпродуктами, картофелем и луком, подаётся в чугунной сковороде.",
            "Қой еті мен ішек-қарын, картоп пен пияз қосып қуырылған, шойын табада беріледі.",
            "Pan-fried lamb with offal, potatoes and onion, served in a cast-iron pan.",
        ),
        t(
            "баранина, печень, сердце, картофель, лук, зира, зелень",
            "қой еті, бауыр, жүрек, картоп, пияз, зире, көк",
            "lamb, liver, heart, potatoes, onion, cumin, herbs",
        ),
        4500, "350 г",
    ),
    _d(
        "manty", "national",
        t("Манты с тыквой и говядиной", "Асқабақ пен сиыр еті қосылған манты", "Manty with pumpkin and beef"),
        t(
            "Паровые манты ручной лепки с сочной начинкой, подаются со сметаной и острым соусом.",
            "Қолмен түйілген буға пісірілген манты, қаймақ пен ащы тұздықпен беріледі.",
            "Hand-made steamed dumplings with a juicy filling, served with sour cream and chili sauce.",
        ),
        t(
            "говядина, тыква, лук, тесто, сметана, острый соус",
            "сиыр еті, асқабақ, пияз, қамыр, қаймақ, ащы тұздық",
            "beef, pumpkin, onion, dough, sour cream, chili sauce",
        ),
        3200, "5 шт", "gluten", "dairy",
    ),
    _d(
        "plov", "national",
        t("Плов по-алматински", "Алматы палауы", "Almaty-style plov"),
        t(
            "Рассыпчатый плов в казане с бараниной, жёлтой морковью, нутом и головкой чеснока.",
            "Қазанда пісірілген қой еті, сары сәбіз, ноқат және сарымсақ қосылған палау.",
            "Fluffy kazan plov with lamb, yellow carrots, chickpeas and a whole garlic bulb.",
        ),
        t(
            "рис девзира, баранина, жёлтая морковь, нут, чеснок, зира, барбарис",
            "девзира күріші, қой еті, сары сәбіз, ноқат, сарымсақ, зире, бөріқарақат",
            "devzira rice, lamb, yellow carrot, chickpeas, garlic, cumin, barberry",
        ),
        3800, "400 г",
    ),
    _d(
        "baursak", "national",
        t("Баурсаки", "Бауырсақ", "Baursaks"),
        t(
            "Пышные жареные пончики — символ гостеприимства, подаются с маслом и мёдом.",
            "Қонақжайлылықтың белгісі — үлпілдек бауырсақ, сары май мен баллен беріледі.",
            "Fluffy fried dough — a symbol of hospitality, served with butter and honey.",
        ),
        t(
            "мука, молоко, дрожжи, сливочное масло, мёд",
            "ұн, сүт, ашытқы, сары май, бал",
            "flour, milk, yeast, butter, honey",
        ),
        900, "10 шт", "vegetarian", "gluten", "dairy",
    ),
    # ---- Main courses ------------------------------------------------------
    _d(
        "horse_medallions", "main",
        t("Медальоны из конины с облепиховым соусом", "Шырғанақ тұздығы бар жылқы етінен медальондар",
          "Horse-meat medallions with sea-buckthorn sauce"),
        t(
            "Нежная вырезка конины medium, облепиховый соус и пюре из запечённой тыквы.",
            "Жылқы етінің жұмсақ сүбесі, шырғанақ тұздығы және пісірілген асқабақ езбесі.",
            "Tender horse tenderloin cooked medium, sea-buckthorn sauce and roasted pumpkin purée.",
        ),
        t(
            "вырезка конины, облепиха, тыква, сливочное масло, тимьян",
            "жылқы етінің сүбесі, шырғанақ, асқабақ, сары май, тимьян",
            "horse tenderloin, sea buckthorn, pumpkin, butter, thyme",
        ),
        7900, "300 г", "horse_meat", "dairy",
    ),
    _d(
        "lagman", "main",
        t("Лагман", "Лағман", "Lagman"),
        t(
            "Тянутая вручную лапша с говядиной и овощами в насыщенном соусе.",
            "Сиыр еті мен көкөніс қосылған, қолмен созылған кеспе.",
            "Hand-pulled noodles with beef and vegetables in a rich sauce.",
        ),
        t(
            "тянутая лапша, говядина, болгарский перец, редька, томаты, чеснок, перец чили",
            "созба кеспе, сиыр еті, болгар бұрышы, шалғам, қызанақ, сарымсақ, чили",
            "hand-pulled noodles, beef, bell pepper, radish, tomatoes, garlic, chili",
        ),
        3400, "400 г", "gluten", "spicy",
    ),
    _d(
        "lamb_shashlik", "main",
        t("Шашлык из ягнёнка", "Қозы етінен кәуап", "Lamb shashlik"),
        t(
            "Каре и мякоть ягнёнка на углях с маринованным луком и лавашом.",
            "Шоқта пісірілген қозы еті, маринадталған пияз бен лаваш.",
            "Charcoal-grilled lamb with pickled onions and lavash.",
        ),
        t(
            "ягнёнок, лук, зира, кориандр, лаваш, соус ткемали",
            "қозы еті, пияз, зире, кориандр, лаваш, ткемали тұздығы",
            "lamb, onion, cumin, coriander, lavash, tkemali sauce",
        ),
        4800, "300 г", "gluten",
    ),
    _d(
        "balkhash_zander", "main",
        t("Судак с Балхаша", "Балқаш көксеркесі", "Balkhash zander"),
        t(
            "Филе судака на гриле с запечёнными овощами и лимонно-укропным соусом.",
            "Грильде пісірілген көксерке филесі, пісірілген көкөністер мен лимон-аскөк тұздығы.",
            "Grilled zander fillet with roasted vegetables and lemon-dill sauce.",
        ),
        t(
            "филе судака, кабачок, перец, морковь, лимон, укроп, сливки",
            "көксерке филесі, асқабақша, бұрыш, сәбіз, лимон, аскөк, кілегей",
            "zander fillet, zucchini, pepper, carrot, lemon, dill, cream",
        ),
        5200, "320 г", "fish", "dairy",
    ),
    _d(
        "pumpkin_chickpea", "main",
        t("Томлёная тыква с нутом", "Ноқат қосылған бұқтырылған асқабақ", "Slow-cooked pumpkin with chickpeas"),
        t(
            "Вегетарианское блюдо: тыква и нут, томлённые с томатами и специями, с лепёшкой.",
            "Вегетариандық тағам: қызанақ пен дәмдеуіш қосылған асқабақ пен ноқат, нанмен.",
            "Vegetarian: pumpkin and chickpeas slow-cooked with tomatoes and spices, with flatbread.",
        ),
        t(
            "тыква, нут, томаты, лук, зира, кинза, лепёшка",
            "асқабақ, ноқат, қызанақ, пияз, зире, кинза, нан",
            "pumpkin, chickpeas, tomatoes, onion, cumin, coriander leaves, flatbread",
        ),
        3000, "350 г", "vegetarian", "gluten",
    ),
    # ---- Starters ----------------------------------------------------------
    _d(
        "samsa", "starters",
        t("Самса с бараниной", "Қой етінен самса", "Lamb samsa"),
        t(
            "Слоёная самса из тандыра с сочной рубленой бараниной.",
            "Тандырда пісірілген қатпарлы самса, туралған қой етімен.",
            "Flaky tandoor-baked samsa with juicy chopped lamb.",
        ),
        t(
            "слоёное тесто, баранина, курдючный жир, лук, зира, кунжут",
            "қатпарлы қамыр, қой еті, құйрық май, пияз, зире, күнжіт",
            "puff pastry, lamb, tail fat, onion, cumin, sesame",
        ),
        1200, "1 шт", "gluten",
    ),
    _d(
        "horse_tartare", "starters",
        t("Тартар из конины", "Жылқы етінен тартар", "Horse-meat tartare"),
        t(
            "Рубленая вырезка конины с каперсами, желтком и хрустящими баурсаками.",
            "Каперс, сарыуыз және қытырлақ бауырсақ қосылған туралған жылқы еті.",
            "Chopped horse tenderloin with capers, egg yolk and crispy baursak croutons.",
        ),
        t(
            "вырезка конины, каперсы, шалот, желток, горчица, баурсаки",
            "жылқы етінің сүбесі, каперс, шалот, сарыуыз, қыша, бауырсақ",
            "horse tenderloin, capers, shallot, egg yolk, mustard, baursaks",
        ),
        4200, "180 г", "horse_meat", "gluten",
    ),
    _d(
        "kurt_platter", "starters",
        t("Ассорти курта и иримшика", "Құрт пен ірімшік табағы", "Kurt & irimshik platter"),
        t(
            "Традиционные казахские сыры: солёный курт, сладкий иримшик и свежий балкаймак.",
            "Дәстүрлі қазақ сүт тағамдары: тұзды құрт, тәтті ірімшік және балқаймақ.",
            "Traditional Kazakh dairy snacks: salty kurt, sweet irimshik and fresh balkaymak.",
        ),
        t(
            "курт, иримшик, балкаймак, мёд, грецкий орех",
            "құрт, ірімшік, балқаймақ, бал, грек жаңғағы",
            "kurt, irimshik, balkaymak, honey, walnuts",
        ),
        2200, "200 г", "vegetarian", "dairy", "nuts",
    ),
    _d(
        "chebureki", "starters",
        t("Чебуреки с говядиной", "Сиыр етінен шебурек", "Beef chebureki"),
        t(
            "Хрустящие чебуреки с сочной начинкой, подаются с айраном.",
            "Шырынды толтырмасы бар қытырлақ шебуректер, айранмен беріледі.",
            "Crispy fried pastries with a juicy filling, served with ayran.",
        ),
        t(
            "тесто, говядина, лук, зелень, айран",
            "қамыр, сиыр еті, пияз, көк, айран",
            "dough, beef, onion, herbs, ayran",
        ),
        1600, "2 шт", "gluten", "dairy",
    ),
    # ---- Salads ------------------------------------------------------------
    _d(
        "achichuk", "salads",
        t("Салат Ачичук", "Ачичук салаты", "Achichuk salad"),
        t(
            "Лёгкий салат из сладких томатов и лука с кинзой — классика к плову.",
            "Тәтті қызанақ пен пияздан жасалған жеңіл салат — палауға классикалық қосымша.",
            "Light salad of sweet tomatoes, onion and coriander — a classic with plov.",
        ),
        t(
            "томаты, сладкий лук, кинза, острый перец, соль",
            "қызанақ, тәтті пияз, кинза, ащы бұрыш, тұз",
            "tomatoes, sweet onion, coriander leaves, hot pepper, salt",
        ),
        1900, "250 г", "vegetarian", "spicy",
    ),
    _d(
        "kazy_salad", "salads",
        t("Салат с казы и печёным перцем", "Қазы мен пісірілген бұрыш салаты", "Kazy and roasted pepper salad"),
        t(
            "Тёплый салат с ломтиками казы, печёным перцем, руколой и гранатовым соусом.",
            "Қазы тілімдері, пісірілген бұрыш, рукола және анар тұздығы бар жылы салат.",
            "Warm salad with kazy slices, roasted pepper, arugula and pomegranate dressing.",
        ),
        t(
            "казы, печёный болгарский перец, руккола, гранат, кунжут, наршараб",
            "қазы, пісірілген болгар бұрышы, рукола, анар, күнжіт, наршараб",
            "kazy, roasted bell pepper, arugula, pomegranate, sesame, narsharab",
        ),
        3200, "220 г", "horse_meat",
    ),
    _d(
        "beet_kurt_salad", "salads",
        t("Свёкла с куртом и орехами", "Құрт пен жаңғақ қосылған қызылша", "Beetroot with kurt and walnuts"),
        t(
            "Запечённая свёкла с кремом из курта, грецким орехом и мёдом.",
            "Құрт кремі, грек жаңғағы және бал қосылған пісірілген қызылша.",
            "Roasted beetroot with kurt cream, walnuts and honey.",
        ),
        t(
            "свёкла, крем из курта, грецкий орех, мёд, микрозелень",
            "қызылша, құрт кремі, грек жаңғағы, бал, микрокөк",
            "beetroot, kurt cream, walnuts, honey, microgreens",
        ),
        2400, "200 г", "vegetarian", "dairy", "nuts",
    ),
    # ---- Drinks ------------------------------------------------------------
    _d(
        "kumys", "drinks",
        t("Кумыс", "Қымыз", "Kumys"),
        t(
            "Традиционный напиток из кобыльего молока с лёгкой кислинкой.",
            "Бие сүтінен жасалған дәстүрлі қышқылтым сусын.",
            "Traditional fermented mare's milk with a light tang.",
        ),
        t("кобылье молоко (ферментированное)", "бие сүті (ашытылған)", "fermented mare's milk"),
        1500, "300 мл", "dairy", "alcohol_trace",
    ),
    _d(
        "shubat", "drinks",
        t("Шубат", "Шұбат", "Shubat"),
        t(
            "Густой ферментированный напиток из верблюжьего молока.",
            "Түйе сүтінен жасалған қою ашытылған сусын.",
            "Thick fermented camel milk drink.",
        ),
        t("верблюжье молоко (ферментированное)", "түйе сүті (ашытылған)", "fermented camel milk"),
        1600, "300 мл", "dairy", "alcohol_trace",
    ),
    _d(
        "kazakh_tea", "drinks",
        t("Чай по-казахски с молоком", "Сүтті қазақша шай", "Kazakh milk tea"),
        t(
            "Крепкий чёрный чай с молоком в чайнике на компанию, с сухофруктами.",
            "Сүт қосылған қою қара шай, кәмпит пен кептірілген жемістермен, шәйнекпен.",
            "Strong black tea with milk, served in a pot for sharing, with dried fruit.",
        ),
        t("чёрный чай, молоко, сухофрукты, сахар", "қара шай, сүт, кептірілген жемістер, қант",
          "black tea, milk, dried fruit, sugar"),
        1200, "800 мл", "vegetarian", "dairy",
    ),
    _d(
        "ayran", "drinks",
        t("Айран", "Айран", "Ayran"),
        t("Освежающий кисломолочный напиток.", "Сергітетін қышқыл сүт сусыны.", "Refreshing fermented yogurt drink."),
        t("кисломолочная закваска, вода, соль", "қышқыл сүт ұйытқысы, су, тұз", "cultured milk, water, salt"),
        900, "300 мл", "vegetarian", "dairy",
    ),
    _d(
        "sea_buckthorn_mors", "drinks",
        t("Облепиховый морс", "Шырғанақ шырыны", "Sea-buckthorn mors"),
        t(
            "Домашний морс из облепихи с мёдом, подаётся холодным или тёплым.",
            "Бал қосылған үй шырғанақ шырыны, суық немесе жылы беріледі.",
            "Homemade sea-buckthorn drink with honey, served cold or warm.",
        ),
        t("облепиха, мёд, вода, мята", "шырғанақ, бал, су, жалбыз", "sea buckthorn, honey, water, mint"),
        1100, "400 мл", "vegetarian",
    ),
    # ---- Desserts ----------------------------------------------------------
    _d(
        "chak_chak", "desserts",
        t("Чак-чак", "Шақ-шақ", "Chak-chak"),
        t(
            "Хрустящие медовые палочки с орехами и сухофруктами.",
            "Жаңғақ пен кептірілген жемістер қосылған қытырлақ балды таяқшалар.",
            "Crispy honey-coated dough with nuts and dried fruit.",
        ),
        t("мука, яйца, мёд, фундук, курага", "ұн, жұмыртқа, бал, орман жаңғағы, өрік",
          "flour, eggs, honey, hazelnuts, dried apricots"),
        1800, "150 г", "vegetarian", "gluten", "nuts",
    ),
    _d(
        "zhent", "desserts",
        t("Жент с мороженым", "Балмұздақ қосылған жент", "Zhent with ice cream"),
        t(
            "Традиционный десерт из толокна, мёда и масла с пломбиром.",
            "Талқан, бал және майдан жасалған дәстүрлі десерт, балмұздақпен.",
            "Traditional dessert of toasted millet, honey and butter with vanilla ice cream.",
        ),
        t("талкан (толокно), мёд, сливочное масло, изюм, пломбир", "талқан, бал, сары май, мейіз, балмұздақ",
          "talkan (toasted millet), honey, butter, raisins, ice cream"),
        2200, "160 г", "vegetarian", "dairy",
    ),
    _d(
        "talkan_tiramisu", "desserts",
        t("Тирамису с талканом", "Талқанды тирамису", "Talkan tiramisu"),
        t(
            "Авторский десерт: нежный крем маскарпоне и талкан вместо какао.",
            "Авторлық десерт: маскарпоне кремі және какао орнына талқан.",
            "Signature dessert: mascarpone cream layered with talkan instead of cocoa.",
        ),
        t("маскарпоне, савоярди, кофе, талкан, сливки", "маскарпоне, савоярди, кофе, талқан, кілегей",
          "mascarpone, savoiardi, coffee, talkan, cream"),
        2600, "170 г", "vegetarian", "gluten", "dairy",
    ),
]

DISHES_BY_ID: dict[str, Dish] = {d.id: d for d in DISHES}


# --------------------------------------------------------------------------- #
# Restaurant facts (fictional demo data)
# --------------------------------------------------------------------------- #
RESTAURANT: dict = {
    "name": "Qazaq Taste",
    "city": t("Алматы, Казахстан", "Алматы, Қазақстан", "Almaty, Kazakhstan"),
    "address": t(
        "пр. Абая, 150 (демо-адрес вымышленного ресторана)",
        "Абай даңғылы, 150 (ойдан шығарылған мейрамхананың демо-мекенжайы)",
        "150 Abay Ave. (demo address of a fictional restaurant)",
    ),
    "phone": "+7 (727) 000-00-00",
    "email": "hello@qazaqtaste.example",
    "instagram": "@qazaqtaste.demo",
    "hours": t(
        "Пн–Чт, Вс: 11:00–23:00; Пт–Сб: 11:00–00:00",
        "Дс–Бс, Жс: 11:00–23:00; Жм–Сб: 11:00–00:00",
        "Mon–Thu, Sun: 11:00–23:00; Fri–Sat: 11:00–00:00",
    ),
    "about": t(
        "Qazaq Taste — ресторан современной казахской кухни в Алматы. Мы переосмысливаем рецепты "
        "степного дастархана: бешбармак, казы, баурсаки и кумыс — в современной подаче из локальных "
        "продуктов. Вся мясная продукция халяль, свинина не используется.",
        "Qazaq Taste — Алматыдағы заманауи қазақ асханасының мейрамханасы. Біз дала дастарханының "
        "рецепттерін жаңаша ұсынамыз: бесбармақ, қазы, бауырсақ пен қымыз — жергілікті өнімдерден "
        "заманауи безендіруде. Барлық ет өнімдері халал, шошқа еті қолданылмайды.",
        "Qazaq Taste is a modern Kazakh cuisine restaurant in Almaty. We reinterpret the recipes of the "
        "steppe dastarkhan — beshbarmak, kazy, baursaks and kumys — in a contemporary style using local "
        "produce. All meat is halal; no pork is used.",
    ),
    "halls": t(
        "Основной зал — до 80 гостей, VIP-зал «Юрта» — до 20 гостей, летняя терраса — до 40 гостей (май–сентябрь).",
        "Негізгі зал — 80 қонаққа дейін, «Киіз үй» VIP-залы — 20 қонаққа дейін, жазғы терраса — 40 қонаққа дейін (мамыр–қыркүйек).",
        "Main hall — up to 80 guests, VIP hall \"Yurt\" — up to 20 guests, summer terrace — up to 40 guests (May–September).",
    ),
    "features": t(
        "Живая домбра по пятницам и субботам с 19:00, детское меню по запросу, Wi-Fi, парковка.",
        "Жұма мен сенбі күндері 19:00-ден бастап домбыра, сұраныс бойынша балалар мәзірі, Wi-Fi, тұрақ.",
        "Live dombra on Fridays and Saturdays from 19:00, kids menu on request, Wi-Fi, parking.",
    ),
}

# Opening hours used for booking validation: weekday() -> (open_hour, close_hour)
# close hour 24 means midnight.
OPENING_HOURS: dict[int, tuple[int, int]] = {0: (11, 23), 1: (11, 23), 2: (11, 23), 3: (11, 23),
                                             4: (11, 24), 5: (11, 24), 6: (11, 23)}

# The same capacities as in RESTAURANT["halls"], in a form the program can compare with.
HALL_CAPACITY: dict[str, dict] = {
    "main": {"capacity": 80, "name": t("Основной зал", "Негізгі зал", "Main hall"), "season": None},
    "vip": {"capacity": 20, "name": t("VIP-зал «Юрта»", "«Киіз үй» VIP-залы", "VIP hall \"Yurt\""), "season": None},
    "terrace": {"capacity": 40, "name": t("Летняя терраса", "Жазғы терраса", "Summer terrace"),
                "season": (5, 9)},  # May–September
}

BOOKING_MAX_GUESTS = 20  # larger groups go through the event request flow
BOOKING_MAX_DAYS_AHEAD = 90
SERVICE_CHARGE_PERCENT = 10

# --------------------------------------------------------------------------- #
# Event tariffs
# --------------------------------------------------------------------------- #
EVENT_TYPES: dict[str, dict] = {
    "corporate": {
        "name": t("Корпоратив", "Корпоратив", "Corporate party"),
        "min_guests": 10,
        "included_services": ["hall_rental", "decor_basic"],
    },
    "banquet": {
        "name": t("Банкет", "Банкет", "Banquet"),
        "min_guests": 10,
        "included_services": ["hall_rental", "decor_basic"],
    },
    "birthday": {
        "name": t("День рождения", "Туған күн", "Birthday"),
        "min_guests": 5,
        "included_services": ["decor_basic"],
    },
    "wedding": {
        "name": t("Свадьба / Той", "Той / Үйлену тойы", "Wedding / Toi"),
        "min_guests": 30,
        "included_services": ["hall_rental", "decor_premium", "host"],
    },
    "business_lunch": {
        "name": t("Деловой обед / встреча", "Іскерлік түскі ас / кездесу", "Business lunch / meeting"),
        "min_guests": 5,
        "included_services": ["projector"],
    },
}

# Additional services: price is fixed per event ("fixed") or per guest ("per_guest").
ADDITIONAL_SERVICES: dict[str, dict] = {
    "hall_rental": {
        "name": t("Аренда зала (до 5 часов)", "Залды жалға алу (5 сағатқа дейін)", "Hall rental (up to 5 hours)"),
        "price": 50000, "unit": "fixed",
    },
    "decor_basic": {
        "name": t("Базовое оформление", "Негізгі безендіру", "Basic decoration"),
        "price": 30000, "unit": "fixed",
    },
    "decor_premium": {
        "name": t("Премиальное оформление в этностиле", "Этностильдегі премиум безендіру",
                  "Premium ethno-style decoration"),
        "price": 150000, "unit": "fixed",
    },
    "host": {
        "name": t("Ведущий (тамада)", "Асаба", "Host / MC (tamada)"),
        "price": 120000, "unit": "fixed",
    },
    "dombra": {
        "name": t("Живая музыка: домбра (1 час)", "Жанды музыка: домбыра (1 сағат)", "Live dombra music (1 hour)"),
        "price": 60000, "unit": "fixed",
    },
    "projector": {
        "name": t("Проектор и экран", "Проектор мен экран", "Projector and screen"),
        "price": 15000, "unit": "fixed",
    },
    "photographer": {
        "name": t("Фотограф (2 часа)", "Фотограф (2 сағат)", "Photographer (2 hours)"),
        "price": 70000, "unit": "fixed",
    },
}

# Optional services offered on top (not included by default).
OPTIONAL_SERVICES = ["dombra", "photographer", "host", "projector"]
