"""Простой i18n: русский по умолчанию, остальные из словаря."""

SUPPORTED = {"ru", "en", "es", "pt", "de", "fr"}


def pick_lang(accept_language: str | None) -> str:
    if not accept_language:
        return "en"
    code = (
        accept_language.split(",")[0]
        .strip().split(";")[0].strip().split("-")[0].lower()[:2]
    )
    return code if code in SUPPORTED else "en"


# Переводы названий сцен: ru -> {en, es, pt, de, fr}
SCENE_TITLES: dict[str, dict[str, str]] = {
    "Деловой (светлый фон)":     {"en": "Business (light)",     "es": "Negocios (claro)",       "pt": "Negócios (claro)",    "de": "Business (hell)",         "fr": "Business (clair)"},
    "Корпоративный синий":       {"en": "Corporate Navy",       "es": "Corporativo azul",       "pt": "Corporativo azul",    "de": "Corporate Navy",          "fr": "Corporate marine"},
    "LinkedIn Classic":          {"en": "LinkedIn Classic",     "es": "LinkedIn Clásico",       "pt": "LinkedIn Clássico",   "de": "LinkedIn Classic",        "fr": "LinkedIn Classique"},
    "В офисе у окна":            {"en": "Office by window",     "es": "Oficina junto a ventana","pt": "Escritório na janela","de": "Büro am Fenster",         "fr": "Bureau près fenêtre"},
    "Чистая студия":             {"en": "Clean studio",         "es": "Estudio limpio",         "pt": "Estúdio limpo",       "de": "Sauberes Studio",         "fr": "Studio épuré"},
    "Smart Casual":              {"en": "Smart Casual",         "es": "Smart Casual",           "pt": "Smart Casual",        "de": "Smart Casual",            "fr": "Smart Casual"},
    "Тёплый офис":               {"en": "Warm office",          "es": "Oficina cálida",         "pt": "Escritório aconchegante","de": "Warmes Büro",          "fr": "Bureau chaleureux"},
    "Минимал серый":             {"en": "Minimal grey",         "es": "Gris minimalista",       "pt": "Cinza minimalista",   "de": "Minimal grau",            "fr": "Gris minimal"},
    "Стекло/офис-небоскрёб":     {"en": "Glass skyscraper",     "es": "Rascacielos de cristal", "pt": "Arranha-céu de vidro","de": "Glas-Hochhaus",           "fr": "Gratte-ciel en verre"},
    "У книжной полки":           {"en": "By the bookshelf",     "es": "Junto a estantería",     "pt": "Perto da estante",    "de": "Am Bücherregal",          "fr": "Près de la bibliothèque"},

    "Tech (тёмный фон)":         {"en": "Tech (dark)",          "es": "Tech (oscuro)",          "pt": "Tech (escuro)",       "de": "Tech (dunkel)",           "fr": "Tech (sombre)"},
    "Крыша города":              {"en": "City rooftop",         "es": "Azotea de la ciudad",    "pt": "Telhado da cidade",   "de": "Stadtdach",               "fr": "Toit de la ville"},
    "Креативная студия":         {"en": "Creative studio",      "es": "Estudio creativo",       "pt": "Estúdio criativo",    "de": "Kreativstudio",           "fr": "Studio créatif"},
    "Подкаст-студия":            {"en": "Podcast studio",       "es": "Estudio de podcast",     "pt": "Estúdio de podcast",  "de": "Podcast-Studio",          "fr": "Studio de podcast"},
    "Кафе у окна":               {"en": "Cafe by window",       "es": "Café en la ventana",     "pt": "Café na janela",      "de": "Café am Fenster",         "fr": "Café à la fenêtre"},
    "Городская улица":           {"en": "Urban street",         "es": "Calle urbana",           "pt": "Rua urbana",          "de": "Stadtstraße",             "fr": "Rue urbaine"},
    "Тёмная библиотека":         {"en": "Dark library",         "es": "Biblioteca oscura",      "pt": "Biblioteca escura",   "de": "Dunkle Bibliothek",       "fr": "Bibliothèque sombre"},
    "Арт-галерея":               {"en": "Art gallery",          "es": "Galería de arte",        "pt": "Galeria de arte",     "de": "Kunstgalerie",            "fr": "Galerie d'art"},
    "Современный лобби":         {"en": "Modern lobby",         "es": "Vestíbulo moderno",      "pt": "Lobby moderno",       "de": "Modernes Lobby",          "fr": "Lobby moderne"},
    "Кирпичная стена":           {"en": "Brick wall",           "es": "Pared de ladrillo",      "pt": "Parede de tijolos",   "de": "Ziegelwand",              "fr": "Mur de briques"},

    "Обложка журнала":           {"en": "Magazine cover",       "es": "Portada de revista",     "pt": "Capa de revista",     "de": "Magazin-Cover",           "fr": "Couverture de magazine"},
    "CEO в переговорке":         {"en": "CEO boardroom",        "es": "CEO en sala de juntas",  "pt": "CEO na sala",         "de": "CEO im Boardroom",        "fr": "PDG en salle de réunion"},
    "Кинематографический":       {"en": "Cinematic",            "es": "Cinematográfico",        "pt": "Cinematográfico",     "de": "Kinematographisch",       "fr": "Cinématographique"},
    "Fashion Editorial":         {"en": "Fashion Editorial",    "es": "Editorial de moda",      "pt": "Editorial de moda",   "de": "Fashion Editorial",       "fr": "Éditorial mode"},
    "Tech с голограммой":        {"en": "Tech hologram",        "es": "Tech con holograma",     "pt": "Tech com holograma",  "de": "Tech mit Hologramm",      "fr": "Tech hologramme"},
    "Частный джет":              {"en": "Private jet",          "es": "Jet privado",            "pt": "Jato particular",     "de": "Privatjet",               "fr": "Jet privé"},
    "В музее":                   {"en": "At the museum",        "es": "En el museo",            "pt": "No museu",            "de": "Im Museum",               "fr": "Au musée"},
    "Горная вершина":            {"en": "Mountain top",         "es": "Cumbre",                 "pt": "Topo da montanha",    "de": "Berggipfel",              "fr": "Sommet de montagne"},
    "Cyberpunk":                 {"en": "Cyberpunk",            "es": "Cyberpunk",              "pt": "Cyberpunk",           "de": "Cyberpunk",               "fr": "Cyberpunk"},
    "Пляж на закате":            {"en": "Beach at sunset",      "es": "Playa al atardecer",     "pt": "Praia ao pôr-do-sol", "de": "Strand bei Sonnenuntergang","fr": "Plage au coucher"},
    "Работа за компьютером":     {"en": "At the computer",      "es": "En la computadora",      "pt": "No computador",       "de": "Am Computer",             "fr": "À l'ordinateur"},
    "Изучаю документы":          {"en": "Reviewing documents",  "es": "Revisando documentos",   "pt": "Analisando documentos","de": "Dokumente prüfen",       "fr": "Étude des documents"},
    "Разговор по телефону":      {"en": "On the phone",         "es": "Al teléfono",            "pt": "Ao telefone",         "de": "Am Telefon",              "fr": "Au téléphone"},
    "У маркерной доски":         {"en": "At the whiteboard",    "es": "En la pizarra",          "pt": "No quadro branco",    "de": "Am Whiteboard",           "fr": "Au tableau blanc"},
    "На сцене (Keynote)":        {"en": "On stage (Keynote)",   "es": "En el escenario",        "pt": "No palco (Keynote)",  "de": "Auf der Bühne (Keynote)", "fr": "Sur scène (Keynote)"},
    "Стратегическая встреча":    {"en": "Strategy meeting",     "es": "Reunión estratégica",    "pt": "Reunião estratégica", "de": "Strategiemeeting",        "fr": "Réunion stratégique"},
    "С чашкой кофе":             {"en": "With a coffee cup",    "es": "Con una taza de café",   "pt": "Com uma xícara de café","de": "Mit einer Tasse Kaffee","fr": "Avec une tasse de café"},
    "Домашний офис":             {"en": "Home office",          "es": "Oficina en casa",        "pt": "Home office",         "de": "Homeoffice",              "fr": "Télétravail"},
    "В университете":            {"en": "At the university",    "es": "En la universidad",      "pt": "Na universidade",     "de": "An der Universität",      "fr": "À l'université"},
    "Агент недвижимости":        {"en": "Real estate agent",    "es": "Agente inmobiliario",    "pt": "Corretor de imóveis", "de": "Immobilienmakler",        "fr": "Agent immobilier"},
    "С наградой":                {"en": "With an award",        "es": "Con un premio",          "pt": "Com um prêmio",       "de": "Mit einer Auszeichnung",  "fr": "Avec un prix"},
    "На яхте":                   {"en": "On a yacht",           "es": "En un yate",             "pt": "Em um iate",          "de": "Auf einer Yacht",         "fr": "Sur un yacht"},
    "Праздничная (Xmas)":        {"en": "Christmas festive",    "es": "Festivo (Navidad)",      "pt": "Festivo (Natal)",     "de": "Weihnachtsfestlich",      "fr": "Festif (Noël)"},
    "Бизнес-ужин":               {"en": "Business dinner",      "es": "Cena de negocios",       "pt": "Jantar de negócios",  "de": "Geschäftsessen",          "fr": "Dîner d'affaires"},
    "Гала-ужин (Black tie)":     {"en": "Gala dinner (Black tie)","es": "Cena de gala (Etiqueta)","pt": "Jantar de gala",     "de": "Galadiner",               "fr": "Dîner de gala"},
    "Винодельня":                {"en": "Vineyard",             "es": "Bodega de vinos",        "pt": "Vinícola",            "de": "Weingut",                 "fr": "Vignoble"},
    "Гольф-клуб":                {"en": "Golf club",            "es": "Club de golf",           "pt": "Clube de golfe",      "de": "Golfclub",                "fr": "Club de golf"},
}

PACKAGE_TITLES: dict[str, dict[str, str]] = {
    "Базовый":  {"en": "Basic",    "es": "Básico",  "pt": "Básico",  "de": "Basic",     "fr": "Basique"},
    "Стандарт": {"en": "Standard", "es": "Estándar","pt": "Padrão",  "de": "Standard",  "fr": "Standard"},
    "Премиум":  {"en": "Premium",  "es": "Premium", "pt": "Premium", "de": "Premium",   "fr": "Premium"},
}


def tr_scene(title_ru: str, lang: str) -> str:
    if lang == "ru":
        return title_ru
    return SCENE_TITLES.get(title_ru, {}).get(lang, title_ru)


def tr_package(title_ru: str, lang: str) -> str:
    if lang == "ru":
        return title_ru
    return PACKAGE_TITLES.get(title_ru, {}).get(lang, title_ru)


# Карта: язык -> код валюты (для отображения)
LANG_CURRENCY = {
    "ru": "RUB",
    "en": "USD",
    "es": "USD",   # LATAM/Espanya — доллар как безопасный дефолт для стора
    "pt": "USD",
    "de": "EUR",
    "fr": "EUR",
}

# Региональные прайсы: sku -> {currency: (amount_int, display_string)}
# amount — целое в основной единице валюты (для аналитики), display — уже готовая строка.
REGIONAL_PRICES = {
    "pack_basic": {
        "RUB": (990,   "990 ₽"),
        "USD": (10,    "$9.99"),
        "EUR": (9,     "€9,99"),
    },
    "pack_standard": {
        "RUB": (1890,  "1 890 ₽"),
        "USD": (20,    "$19.99"),
        "EUR": (19,    "€19,99"),
    },
    "pack_premium": {
        "RUB": (2990,  "2 990 ₽"),
        "USD": (30,    "$29.99"),
        "EUR": (29,    "€29,99"),
    },
}


def currency_for_lang(lang: str) -> str:
    return LANG_CURRENCY.get(lang, "USD")


def price_for(sku: str, lang: str) -> tuple[int, str, str]:
    """Возвращает (amount, currency, display) для пакета в валюте пользователя."""
    currency = currency_for_lang(lang)
    prices = REGIONAL_PRICES.get(sku, {})
    if currency in prices:
        amt, disp = prices[currency]
        return amt, currency, disp
    # fallback на USD, если нет региональной цены
    amt, disp = prices.get("USD", (0, "—"))
    return amt, "USD", disp
