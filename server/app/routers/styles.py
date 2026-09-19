import os
import random
import threading
from pathlib import Path
from fastapi import APIRouter, Header, Query
from app.schemas import IndustryOut, StyleOut
from app.services.i18n import pick_lang, tr_scene

router = APIRouter()

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://89.221.203.218:8010").rstrip("/")
THUMBS_DIR = Path("./media/thumbs")


def _ph(text: str, bg: str, fg: str = "FFFFFF") -> str:
    from urllib.parse import quote
    return f"https://placehold.co/800x800/{bg}/{fg}?text={quote(text)}"


# 7 вариантов одежды на каждую сцену. Wearing = разная одежда каждый раз.
# get_prompt(scene_key, device_id) отдаёт вариант, ЕЩЁ не показанный этому устройству
# в этой сцене — пока не переберёт все 7, потом цикл сбрасывается.

_STYLES: list[dict] = [
    # ═══ ТИР 1 — БАЗОВЫЙ (14) ═══
    dict(key="business_light", title="Деловой (светлый фон)", tier=1, preview=_ph("Business Light", "3B5BFF"), prompts=[
        "Clean soft-white studio background, three-point studio lighting. Wearing a charcoal grey business suit with a white shirt and a dark navy tie. Confident subtle smile.",
        "Clean soft-white studio background, three-point studio lighting. Wearing a mid-grey two-button suit with a light blue shirt and a burgundy silk tie. Confident subtle smile.",
        "Clean soft-white studio background, three-point studio lighting. Wearing a dark navy suit with a crisp white shirt and no tie, top button unbuttoned. Confident subtle smile.",
        "Clean soft-white studio background, three-point studio lighting. Wearing a black tailored suit with a white shirt and a slim black tie. Confident subtle smile.",
        "Clean soft-white studio background, three-point studio lighting. Wearing a light grey suit with a soft pink shirt and no tie. Confident subtle smile.",
        "Clean soft-white studio background, three-point studio lighting. Wearing a beige linen suit with a white shirt and no tie. Confident subtle smile.",
        "Clean soft-white studio background, three-point studio lighting. Wearing a dark green three-piece suit with a white shirt and a dark brown tie. Confident subtle smile.",
    ]),
    dict(key="corporate_navy", title="Корпоративный синий", tier=1, preview=_ph("Corporate", "1E3A8A"), prompts=[
        "Deep navy gradient studio background, sharp studio lighting. Wearing a dark navy business suit, crisp white shirt and silk burgundy tie. Serious authoritative expression.",
        "Deep navy gradient studio background, sharp studio lighting. Wearing a charcoal three-piece suit with a white shirt and a dark grey tie. Serious authoritative expression.",
        "Deep navy gradient studio background, sharp studio lighting. Wearing a black tailored suit with a pale blue shirt and a black tie. Serious authoritative expression.",
        "Deep navy gradient studio background, sharp studio lighting. Wearing a midnight blue suit with a white shirt and a silver tie. Serious authoritative expression.",
        "Deep navy gradient studio background, sharp studio lighting. Wearing a dark grey pinstripe suit with a light blue shirt and a burgundy tie. Serious authoritative expression.",
        "Deep navy gradient studio background, sharp studio lighting. Wearing a navy double-breasted blazer over a white shirt with a dark navy tie. Serious authoritative expression.",
        "Deep navy gradient studio background, sharp studio lighting. Wearing a black three-piece suit with a white shirt and a black bow tie. Serious authoritative expression.",
    ]),
    dict(key="linkedin_classic", title="LinkedIn Classic", tier=1, preview=_ph("LinkedIn", "0A66C2"), prompts=[
        "Soft blue-grey studio background, warm studio lighting. Wearing a mid-grey wool blazer over a light blue button-down shirt, no tie. Warm approachable smile.",
        "Soft blue-grey studio background, warm studio lighting. Wearing a dark navy blazer over a white shirt, no tie. Warm approachable smile.",
        "Soft blue-grey studio background, warm studio lighting. Wearing a soft brown herringbone blazer over a cream shirt, no tie. Warm approachable smile.",
        "Soft blue-grey studio background, warm studio lighting. Wearing a light grey suit with a white shirt and a soft blue tie. Warm approachable smile.",
        "Soft blue-grey studio background, warm studio lighting. Wearing a black knit polo. Warm approachable smile.",
        "Soft blue-grey studio background, warm studio lighting. Wearing a dark grey merino sweater over a white collared shirt. Warm approachable smile.",
        "Soft blue-grey studio background, warm studio lighting. Wearing a burgundy V-neck sweater over a light blue shirt. Warm approachable smile.",
    ]),
    dict(key="at_laptop", title="Работа за компьютером", tier=1, preview=_ph("Laptop", "3B5BFF"), prompts=[
        "Bright open-plan office softly blurred behind, at a modern laptop with hands visible on the keyboard, soft window light. Wearing a light blue oxford shirt with sleeves slightly rolled. Focused productive expression.",
        "Bright open-plan office softly blurred behind, at a modern laptop, soft window light. Wearing a dark grey merino sweater over a white t-shirt. Focused productive expression.",
        "Bright open-plan office softly blurred behind, at a modern laptop, soft window light. Wearing a navy blazer over a white t-shirt. Focused productive expression.",
        "Bright open-plan office softly blurred behind, at a modern laptop, soft window light. Wearing a beige knit cardigan over a white t-shirt. Focused productive expression.",
        "Bright open-plan office softly blurred behind, at a modern laptop, soft window light. Wearing a plain black t-shirt. Focused productive expression.",
        "Bright open-plan office softly blurred behind, at a modern laptop, soft window light. Wearing a dark green button-down shirt with sleeves rolled up. Focused productive expression.",
        "Bright open-plan office softly blurred behind, at a modern laptop, soft window light. Wearing a light grey hoodie over a white t-shirt. Focused productive expression.",
    ]),
    dict(key="business_office", title="В офисе у окна", tier=1, preview=_ph("Office Window", "0F1226"), prompts=[
        "Modern glass office next to a large window with blurred city skyline behind, natural window light. Wearing a dark grey blazer over a white shirt, no tie. Confident calm expression.",
        "Modern glass office next to a large window with blurred city skyline behind, natural window light. Wearing a navy suit with a light blue shirt and a dark tie. Confident calm expression.",
        "Modern glass office next to a large window with blurred city skyline behind, natural window light. Wearing a charcoal turtleneck under a black blazer. Confident calm expression.",
        "Modern glass office next to a large window with blurred city skyline behind, natural window light. Wearing a black three-piece suit with a white shirt and no tie. Confident calm expression.",
    ]),
    dict(key="coffee_cup", title="С чашкой кофе", tier=1, preview=_ph("Coffee", "78350F"), prompts=[
        "Bright modern cafe interior softly blurred, soft morning light. Wearing a beige merino sweater over a white t-shirt, holding a warm coffee cup with both hands. Relaxed friendly expression.",
        "Bright modern cafe interior softly blurred, soft morning light. Wearing an olive green cardigan over a light grey t-shirt, holding a warm coffee cup. Relaxed friendly expression.",
        "Bright modern cafe interior softly blurred, soft morning light. Wearing a rust-orange knit sweater, holding a warm coffee cup. Relaxed friendly expression.",
        "Bright modern cafe interior softly blurred, soft morning light. Wearing a dark denim jacket over a white t-shirt, holding a warm coffee cup. Relaxed friendly expression.",
        "Bright modern cafe interior softly blurred, soft morning light. Wearing a navy henley shirt, holding a warm coffee cup. Relaxed friendly expression.",
        "Bright modern cafe interior softly blurred, soft morning light. Wearing a soft grey hoodie under a black leather jacket, holding a warm coffee cup. Relaxed friendly expression.",
        "Bright modern cafe interior softly blurred, soft morning light. Wearing a burgundy flannel shirt over a heather grey t-shirt, holding a warm coffee cup. Relaxed friendly expression.",
    ]),
    dict(key="clean_studio", title="Чистая студия", tier=1, preview=_ph("Studio", "E5E7EB", "0F1226"), prompts=[
        "Pure white seamless studio background, high-key soft lighting. Wearing a crisp white button-down shirt. Calm expression, editorial magazine quality.",
        "Pure white seamless studio background, high-key soft lighting. Wearing a light blue oxford shirt. Calm expression, editorial magazine quality.",
        "Pure white seamless studio background, high-key soft lighting. Wearing a dark charcoal fitted t-shirt. Calm expression, editorial magazine quality.",
        "Pure white seamless studio background, high-key soft lighting. Wearing a black turtleneck. Calm expression, editorial magazine quality.",
        "Pure white seamless studio background, high-key soft lighting. Wearing a plain heather grey t-shirt. Calm expression, editorial magazine quality.",
        "Pure white seamless studio background, high-key soft lighting. Wearing a soft cream cashmere sweater. Calm expression, editorial magazine quality.",
        "Pure white seamless studio background, high-key soft lighting. Wearing a navy V-neck sweater over a white shirt. Calm expression, editorial magazine quality.",
    ]),
    dict(key="reading_docs", title="Изучаю документы", tier=1, preview=_ph("Docs", "0F1226"), prompts=[
        "Warm wooden office desk with blurred bookshelves behind, soft desk-lamp light. Wearing a dark grey shirt with the top button unbuttoned. Thoughtful analytical expression.",
        "Warm wooden office desk with blurred bookshelves behind, soft desk-lamp light. Wearing a brown corduroy blazer over a cream shirt. Thoughtful analytical expression.",
        "Warm wooden office desk with blurred bookshelves behind, soft desk-lamp light. Wearing a black rollneck sweater. Thoughtful analytical expression.",
        "Warm wooden office desk with blurred bookshelves behind, soft desk-lamp light. Wearing a dark green tweed jacket over a white shirt. Thoughtful analytical expression.",
        "Warm wooden office desk with blurred bookshelves behind, soft desk-lamp light. Wearing a navy suit with a light blue shirt and rolled-up sleeves. Thoughtful analytical expression.",
        "Warm wooden office desk with blurred bookshelves behind, soft desk-lamp light. Wearing a burgundy sweater over a white collared shirt. Thoughtful analytical expression.",
        "Warm wooden office desk with blurred bookshelves behind, soft desk-lamp light. Wearing a beige cable-knit sweater over a white shirt. Thoughtful analytical expression.",
    ]),
    dict(key="casual_smart", title="Smart Casual", tier=1, preview=_ph("Smart Casual", "6B7280"), prompts=[
        "Warm neutral grey studio background, soft Rembrandt lighting. Wearing a dark charcoal shirt with the top button unbuttoned, no tie. Friendly confident expression.",
        "Warm neutral grey studio background, soft Rembrandt lighting. Wearing a khaki utility jacket over a white t-shirt. Friendly confident expression.",
        "Warm neutral grey studio background, soft Rembrandt lighting. Wearing a dark green Henley shirt. Friendly confident expression.",
        "Warm neutral grey studio background, soft Rembrandt lighting. Wearing a black t-shirt under a dark grey wool blazer. Friendly confident expression.",
        "Warm neutral grey studio background, soft Rembrandt lighting. Wearing an olive knit polo. Friendly confident expression.",
        "Warm neutral grey studio background, soft Rembrandt lighting. Wearing a beige cardigan over a white t-shirt. Friendly confident expression.",
        "Warm neutral grey studio background, soft Rembrandt lighting. Wearing a light blue denim shirt with the top button unbuttoned. Friendly confident expression.",
    ]),
    dict(key="home_office", title="Домашний офис", tier=1, preview=_ph("WFH", "B45309"), prompts=[
        "Cozy home office with a softly blurred bookshelf and green plant behind, warm natural window light. Wearing a navy thin knit sweater over a white t-shirt. Authentic focused expression.",
        "Cozy home office with a softly blurred bookshelf and green plant behind, warm natural window light. Wearing a light grey hoodie over a plain t-shirt. Authentic focused expression.",
        "Cozy home office with a softly blurred bookshelf and green plant behind, warm natural window light. Wearing a burnt orange flannel shirt. Authentic focused expression.",
        "Cozy home office with a softly blurred bookshelf and green plant behind, warm natural window light. Wearing a heather grey t-shirt under an open dark green button-down. Authentic focused expression.",
        "Cozy home office with a softly blurred bookshelf and green plant behind, warm natural window light. Wearing a beige waffle-knit crewneck. Authentic focused expression.",
        "Cozy home office with a softly blurred bookshelf and green plant behind, warm natural window light. Wearing a dark denim shirt with sleeves rolled up. Authentic focused expression.",
        "Cozy home office with a softly blurred bookshelf and green plant behind, warm natural window light. Wearing a plain black t-shirt. Authentic focused expression.",
    ]),
    dict(key="warm_office", title="Тёплый офис", tier=1, preview=_ph("Warm Office", "B45309"), prompts=[
        "Warm wood-panelled office with blurred bookshelves behind, golden hour window light. Wearing a brown corduroy blazer over a cream shirt. Slight smile.",
        "Warm wood-panelled office with blurred bookshelves behind, golden hour window light. Wearing a dark green tweed jacket over a white shirt. Slight smile.",
        "Warm wood-panelled office with blurred bookshelves behind, golden hour window light. Wearing a camel-colored cashmere sweater over a white collared shirt. Slight smile.",
        "Warm wood-panelled office with blurred bookshelves behind, golden hour window light. Wearing a burgundy velvet blazer over a black shirt. Slight smile.",
        "Warm wood-panelled office with blurred bookshelves behind, golden hour window light. Wearing a dark brown herringbone blazer over a beige turtleneck. Slight smile.",
        "Warm wood-panelled office with blurred bookshelves behind, golden hour window light. Wearing a rust-colored knit sweater over a white shirt. Slight smile.",
        "Warm wood-panelled office with blurred bookshelves behind, golden hour window light. Wearing a navy blazer over a white shirt with an amber knit tie. Slight smile.",
    ]),
    dict(key="minimal_grey", title="Минимал серый", tier=1, preview=_ph("Minimal", "9CA3AF"), prompts=[
        "Seamless light grey studio background, soft even lighting. Wearing a plain heather grey t-shirt. Calm neutral expression, minimalist magazine style.",
        "Seamless light grey studio background, soft even lighting. Wearing a plain black crewneck t-shirt. Calm neutral expression, minimalist magazine style.",
        "Seamless light grey studio background, soft even lighting. Wearing a plain white t-shirt. Calm neutral expression, minimalist magazine style.",
        "Seamless light grey studio background, soft even lighting. Wearing a plain black turtleneck. Calm neutral expression, minimalist magazine style.",
        "Seamless light grey studio background, soft even lighting. Wearing a plain cream sweater. Calm neutral expression, minimalist magazine style.",
        "Seamless light grey studio background, soft even lighting. Wearing a light beige linen shirt. Calm neutral expression, minimalist magazine style.",
        "Seamless light grey studio background, soft even lighting. Wearing a dark navy fitted t-shirt. Calm neutral expression, minimalist magazine style.",
    ]),
    dict(key="modern_glass", title="Стекло/офис-небоскрёб", tier=1, preview=_ph("Glass", "60A5FA"), prompts=[
        "Modern glass skyscraper lobby with blurred glass and steel reflections behind, cool daylight from above. Wearing a black tailored business suit with a white shirt. Confident expression.",
        "Modern glass skyscraper lobby with blurred glass and steel reflections behind, cool daylight from above. Wearing a dark grey suit with a light blue shirt and a slim black tie. Confident expression.",
        "Modern glass skyscraper lobby with blurred glass and steel reflections behind, cool daylight from above. Wearing a navy overcoat over a white shirt. Confident expression.",
        "Modern glass skyscraper lobby with blurred glass and steel reflections behind, cool daylight from above. Wearing a charcoal double-breasted blazer over a white shirt. Confident expression.",
        "Modern glass skyscraper lobby with blurred glass and steel reflections behind, cool daylight from above. Wearing a black turtleneck under a grey wool coat. Confident expression.",
        "Modern glass skyscraper lobby with blurred glass and steel reflections behind, cool daylight from above. Wearing a midnight blue three-piece suit with a white shirt and a silver tie. Confident expression.",
        "Modern glass skyscraper lobby with blurred glass and steel reflections behind, cool daylight from above. Wearing a camel wool coat over a dark grey suit. Confident expression.",
    ]),
    dict(key="bookshelf", title="У книжной полки", tier=1, preview=_ph("Bookshelf", "78350F"), prompts=[
        "Warm dark wooden bookshelf full of books behind, soft desk-lamp lighting. Wearing a dark burgundy sweater over a white collared shirt. Intelligent thoughtful expression.",
        "Warm dark wooden bookshelf full of books behind, soft desk-lamp lighting. Wearing a brown tweed blazer over a beige turtleneck. Intelligent thoughtful expression.",
        "Warm dark wooden bookshelf full of books behind, soft desk-lamp lighting. Wearing a dark grey V-neck sweater over a white shirt. Intelligent thoughtful expression.",
        "Warm dark wooden bookshelf full of books behind, soft desk-lamp lighting. Wearing a dark green cardigan over a cream shirt. Intelligent thoughtful expression.",
        "Warm dark wooden bookshelf full of books behind, soft desk-lamp lighting. Wearing a navy blazer over a white shirt with a small burgundy knit tie. Intelligent thoughtful expression.",
        "Warm dark wooden bookshelf full of books behind, soft desk-lamp lighting. Wearing a black rollneck sweater. Intelligent thoughtful expression.",
        "Warm dark wooden bookshelf full of books behind, soft desk-lamp lighting. Wearing a camel cable-knit sweater over a white collared shirt. Intelligent thoughtful expression.",
    ]),

    # ═══ ТИР 2 — СТАНДАРТ (15) ═══
    dict(key="tech_dark", title="Tech (тёмный фон)", tier=2, preview=_ph("Tech Dark", "141826"), prompts=[
        "Dark charcoal studio background, dramatic side lighting with cool blue rim light. Wearing a black turtleneck. Confident visionary expression.",
        "Dark charcoal studio background, dramatic side lighting with cool blue rim light. Wearing a dark grey merino sweater. Confident visionary expression.",
        "Dark charcoal studio background, dramatic side lighting with cool blue rim light. Wearing a black bomber jacket over a black t-shirt. Confident visionary expression.",
        "Dark charcoal studio background, dramatic side lighting with cool blue rim light. Wearing a plain black crewneck sweater. Confident visionary expression.",
        "Dark charcoal studio background, dramatic side lighting with cool blue rim light. Wearing a dark grey zip-up hoodie under a black blazer. Confident visionary expression.",
        "Dark charcoal studio background, dramatic side lighting with cool blue rim light. Wearing a black leather jacket over a black t-shirt. Confident visionary expression.",
        "Dark charcoal studio background, dramatic side lighting with cool blue rim light. Wearing a dark navy techwear jacket. Confident visionary expression.",
    ]),
    dict(key="rooftop", title="Крыша города", tier=2, preview=_ph("Rooftop", "1F2937"), prompts=[
        "Rooftop terrace at blue hour with city skyline and warm lights softly blurred behind, cinematic ambient light. Wearing a dark navy overcoat over a black shirt. Confident urban expression.",
        "Rooftop terrace at blue hour with city skyline and warm lights softly blurred behind, cinematic ambient light. Wearing a camel wool coat over a light grey turtleneck. Confident urban expression.",
        "Rooftop terrace at blue hour with city skyline and warm lights softly blurred behind, cinematic ambient light. Wearing a black leather jacket over a dark grey shirt. Confident urban expression.",
        "Rooftop terrace at blue hour with city skyline and warm lights softly blurred behind, cinematic ambient light. Wearing a dark grey trench coat over a black turtleneck. Confident urban expression.",
        "Rooftop terrace at blue hour with city skyline and warm lights softly blurred behind, cinematic ambient light. Wearing a burgundy bomber jacket over a black t-shirt. Confident urban expression.",
        "Rooftop terrace at blue hour with city skyline and warm lights softly blurred behind, cinematic ambient light. Wearing a beige wool overcoat over a white shirt. Confident urban expression.",
        "Rooftop terrace at blue hour with city skyline and warm lights softly blurred behind, cinematic ambient light. Wearing a dark green shell jacket over a heather grey sweater. Confident urban expression.",
    ]),
    dict(key="creative_studio", title="Креативная студия", tier=2, preview=_ph("Creative", "F59E0B", "0F1226"), prompts=[
        "Bright design studio with softly blurred colourful abstract art on the wall, natural window light. Wearing an olive canvas jacket over a white t-shirt. Relaxed authentic smile.",
        "Bright design studio with softly blurred colourful abstract art on the wall, natural window light. Wearing a mustard yellow cardigan over a grey t-shirt. Relaxed authentic smile.",
        "Bright design studio with softly blurred colourful abstract art on the wall, natural window light. Wearing a light denim shirt over a white t-shirt. Relaxed authentic smile.",
        "Bright design studio with softly blurred colourful abstract art on the wall, natural window light. Wearing a rust-orange chore jacket over a cream t-shirt. Relaxed authentic smile.",
        "Bright design studio with softly blurred colourful abstract art on the wall, natural window light. Wearing a black t-shirt with a beige overshirt. Relaxed authentic smile.",
        "Bright design studio with softly blurred colourful abstract art on the wall, natural window light. Wearing a striped navy-white breton sweater. Relaxed authentic smile.",
        "Bright design studio with softly blurred colourful abstract art on the wall, natural window light. Wearing a dark green corduroy overshirt over a white t-shirt. Relaxed authentic smile.",
    ]),
    dict(key="podcast_studio", title="Подкаст-студия", tier=2, preview=_ph("Podcast", "0F172A"), prompts=[
        "Dark podcast studio with blurred acoustic panels and microphone behind, warm ring light. Wearing a dark grey henley. Confident engaging expression.",
        "Dark podcast studio with blurred acoustic panels and microphone behind, warm ring light. Wearing a black hoodie over a black t-shirt. Confident engaging expression.",
        "Dark podcast studio with blurred acoustic panels and microphone behind, warm ring light. Wearing a navy button-down shirt with sleeves rolled up. Confident engaging expression.",
        "Dark podcast studio with blurred acoustic panels and microphone behind, warm ring light. Wearing a burgundy flannel shirt over a black t-shirt. Confident engaging expression.",
        "Dark podcast studio with blurred acoustic panels and microphone behind, warm ring light. Wearing a dark green bomber jacket over a grey t-shirt. Confident engaging expression.",
        "Dark podcast studio with blurred acoustic panels and microphone behind, warm ring light. Wearing a black turtleneck. Confident engaging expression.",
        "Dark podcast studio with blurred acoustic panels and microphone behind, warm ring light. Wearing a charcoal knit sweater over a white collared shirt. Confident engaging expression.",
    ]),
    dict(key="phone_call", title="Разговор по телефону", tier=2, preview=_ph("Phone", "0EA5E9"), prompts=[
        "Bright modern office softly blurred behind, natural window light. Wearing a light blue oxford shirt, holding a smartphone to the ear. Engaged listening expression.",
        "Bright modern office softly blurred behind, natural window light. Wearing a dark navy blazer over a white shirt, holding a smartphone to the ear. Engaged listening expression.",
        "Bright modern office softly blurred behind, natural window light. Wearing a charcoal knit sweater, holding a smartphone to the ear. Engaged listening expression.",
        "Bright modern office softly blurred behind, natural window light. Wearing a black turtleneck under a grey blazer, holding a smartphone to the ear. Engaged listening expression.",
        "Bright modern office softly blurred behind, natural window light. Wearing a beige cardigan over a white t-shirt, holding a smartphone to the ear. Engaged listening expression.",
        "Bright modern office softly blurred behind, natural window light. Wearing a dark grey henley, holding a smartphone to the ear. Engaged listening expression.",
        "Bright modern office softly blurred behind, natural window light. Wearing a navy suit with a light blue shirt and no tie, holding a smartphone to the ear. Engaged listening expression.",
    ]),
    dict(key="cafe_window", title="Кафе у окна", tier=2, preview=_ph("Cafe", "D97706"), prompts=[
        "Cafe window seat with soft golden afternoon light and warm background bokeh. Wearing a mustard yellow cardigan over a white t-shirt. Natural relaxed expression.",
        "Cafe window seat with soft golden afternoon light and warm background bokeh. Wearing a beige overcoat over a dark grey turtleneck. Natural relaxed expression.",
        "Cafe window seat with soft golden afternoon light and warm background bokeh. Wearing a burgundy chunky knit sweater. Natural relaxed expression.",
        "Cafe window seat with soft golden afternoon light and warm background bokeh. Wearing a dark green corduroy shirt over a cream t-shirt. Natural relaxed expression.",
        "Cafe window seat with soft golden afternoon light and warm background bokeh. Wearing a light brown suede jacket over a white t-shirt. Natural relaxed expression.",
        "Cafe window seat with soft golden afternoon light and warm background bokeh. Wearing a navy peacoat over a heather grey sweater. Natural relaxed expression.",
        "Cafe window seat with soft golden afternoon light and warm background bokeh. Wearing a dark denim jacket over a black henley. Natural relaxed expression.",
    ]),
    dict(key="university", title="В университете", tier=2, preview=_ph("Uni", "1E3A8A"), prompts=[
        "Historic university hall with ivy-covered stone walls and arched windows softly blurred behind, warm afternoon sunlight. Wearing a brown tweed blazer over a white shirt. Thoughtful intellectual expression, Ivy League aesthetic.",
        "Historic university hall with ivy-covered stone walls and arched windows softly blurred behind, warm afternoon sunlight. Wearing a navy blazer over a light blue shirt and a burgundy knit tie. Thoughtful intellectual expression.",
        "Historic university hall with ivy-covered stone walls and arched windows softly blurred behind, warm afternoon sunlight. Wearing a forest-green wool sweater over a white collared shirt. Thoughtful intellectual expression.",
        "Historic university hall with ivy-covered stone walls and arched windows softly blurred behind, warm afternoon sunlight. Wearing a charcoal corduroy blazer over a cream turtleneck. Thoughtful intellectual expression.",
        "Historic university hall with ivy-covered stone walls and arched windows softly blurred behind, warm afternoon sunlight. Wearing a dark burgundy V-neck sweater over a light blue shirt. Thoughtful intellectual expression.",
        "Historic university hall with ivy-covered stone walls and arched windows softly blurred behind, warm afternoon sunlight. Wearing a camel wool overcoat over a white shirt and a striped scarf. Thoughtful intellectual expression.",
        "Historic university hall with ivy-covered stone walls and arched windows softly blurred behind, warm afternoon sunlight. Wearing a dark grey herringbone blazer over a soft blue shirt. Thoughtful intellectual expression.",
    ]),
    dict(key="cyberpunk", title="Cyberpunk", tier=2, preview=_ph("Cyberpunk", "9333EA"), prompts=[
        "Rainy Tokyo neon street softly blurred behind with neon magenta and cyan rim lights. Wearing a black high-collar techwear jacket. Moody atmospheric expression.",
        "Rainy Tokyo neon street softly blurred behind with neon magenta and cyan rim lights. Wearing a dark grey oversized hoodie under a black long coat. Moody atmospheric expression.",
        "Rainy Tokyo neon street softly blurred behind with neon magenta and cyan rim lights. Wearing a black bomber jacket over a black turtleneck. Moody atmospheric expression.",
        "Rainy Tokyo neon street softly blurred behind with neon magenta and cyan rim lights. Wearing a dark navy trench coat over a black shirt. Moody atmospheric expression.",
        "Rainy Tokyo neon street softly blurred behind with neon magenta and cyan rim lights. Wearing a black leather jacket with a hood over a dark grey shirt. Moody atmospheric expression.",
        "Rainy Tokyo neon street softly blurred behind with neon magenta and cyan rim lights. Wearing a dark utility techwear vest over a black long-sleeve shirt. Moody atmospheric expression.",
        "Rainy Tokyo neon street softly blurred behind with neon magenta and cyan rim lights. Wearing a plain black hoodie under a wet reflective raincoat. Moody atmospheric expression.",
    ]),
    dict(key="urban_street", title="Городская улица", tier=2, preview=_ph("Urban", "4B5563"), prompts=[
        "Modern city street softly blurred behind with blurred pedestrians, overcast daylight. Wearing a dark grey overcoat over a black turtleneck. Confident urban expression.",
        "Modern city street softly blurred behind with blurred pedestrians, overcast daylight. Wearing a camel wool coat over a cream sweater. Confident urban expression.",
        "Modern city street softly blurred behind with blurred pedestrians, overcast daylight. Wearing a black leather jacket over a heather grey t-shirt. Confident urban expression.",
        "Modern city street softly blurred behind with blurred pedestrians, overcast daylight. Wearing a dark navy peacoat over a white shirt. Confident urban expression.",
        "Modern city street softly blurred behind with blurred pedestrians, overcast daylight. Wearing a burgundy bomber jacket over a black t-shirt. Confident urban expression.",
        "Modern city street softly blurred behind with blurred pedestrians, overcast daylight. Wearing a beige trench coat over a dark grey turtleneck. Confident urban expression.",
        "Modern city street softly blurred behind with blurred pedestrians, overcast daylight. Wearing a dark denim jacket over a black henley. Confident urban expression.",
    ]),
    dict(key="realtor", title="Агент недвижимости", tier=2, preview=_ph("Realtor", "0EA5E9"), prompts=[
        "Elegant modern residential home softly blurred behind, warm sunlight. Wearing a well-tailored dark navy blazer over a light blue shirt, no tie. Warm approachable smile.",
        "Elegant modern residential home softly blurred behind, warm sunlight. Wearing a light grey suit with a white shirt and no tie. Warm approachable smile.",
        "Elegant modern residential home softly blurred behind, warm sunlight. Wearing a beige linen blazer over a white polo. Warm approachable smile.",
        "Elegant modern residential home softly blurred behind, warm sunlight. Wearing a charcoal blazer over a white oxford shirt with a burgundy tie. Warm approachable smile.",
        "Elegant modern residential home softly blurred behind, warm sunlight. Wearing a dark navy suit with a soft pink shirt and no tie. Warm approachable smile.",
        "Elegant modern residential home softly blurred behind, warm sunlight. Wearing a camel blazer over a white shirt with a knit tie. Warm approachable smile.",
        "Elegant modern residential home softly blurred behind, warm sunlight. Wearing a dark grey suit with a light blue shirt and a soft blue tie. Warm approachable smile.",
    ]),
    dict(key="library_dark", title="Тёмная библиотека", tier=2, preview=_ph("Library", "3F2E1E"), prompts=[
        "Old dark wood library with blurred rows of leather-bound books behind, warm amber lamp light. Wearing a dark forest-green blazer over a white shirt. Refined intellectual look.",
        "Old dark wood library with blurred rows of leather-bound books behind, warm amber lamp light. Wearing a dark burgundy cashmere sweater over a white collared shirt. Refined intellectual look.",
        "Old dark wood library with blurred rows of leather-bound books behind, warm amber lamp light. Wearing a brown tweed jacket over a beige turtleneck. Refined intellectual look.",
        "Old dark wood library with blurred rows of leather-bound books behind, warm amber lamp light. Wearing a charcoal three-piece suit with a white shirt and a dark tie. Refined intellectual look.",
        "Old dark wood library with blurred rows of leather-bound books behind, warm amber lamp light. Wearing a navy velvet blazer over a black turtleneck. Refined intellectual look.",
        "Old dark wood library with blurred rows of leather-bound books behind, warm amber lamp light. Wearing a dark brown corduroy blazer over a cream shirt. Refined intellectual look.",
        "Old dark wood library with blurred rows of leather-bound books behind, warm amber lamp light. Wearing a heather grey wool cardigan over a white shirt with a knit tie. Refined intellectual look.",
    ]),
    dict(key="whiteboard", title="У маркерной доски", tier=2, preview=_ph("Board", "6B7280"), prompts=[
        "Bright modern office with a softly blurred whiteboard and floor-to-ceiling window behind. Wearing a light blue oxford shirt with the top button unbuttoned, no tie. Relaxed confident expression.",
        "Bright modern office with a softly blurred whiteboard and floor-to-ceiling window behind. Wearing a dark grey blazer over a white t-shirt. Relaxed confident expression.",
        "Bright modern office with a softly blurred whiteboard and floor-to-ceiling window behind. Wearing a navy knit sweater over a white collared shirt. Relaxed confident expression.",
        "Bright modern office with a softly blurred whiteboard and floor-to-ceiling window behind. Wearing a plain black t-shirt. Relaxed confident expression.",
        "Bright modern office with a softly blurred whiteboard and floor-to-ceiling window behind. Wearing a beige overshirt over a white t-shirt. Relaxed confident expression.",
        "Bright modern office with a softly blurred whiteboard and floor-to-ceiling window behind. Wearing a dark green henley shirt. Relaxed confident expression.",
        "Bright modern office with a softly blurred whiteboard and floor-to-ceiling window behind. Wearing a light grey suit with a white shirt and no tie. Relaxed confident expression.",
    ]),
    dict(key="art_gallery", title="Арт-галерея", tier=2, preview=_ph("Gallery", "F3F4F6", "0F1226"), prompts=[
        "Bright minimalist art gallery with blurred modern paintings behind, museum lighting. Wearing an elegant black rollneck. Thoughtful sophisticated expression.",
        "Bright minimalist art gallery with blurred modern paintings behind, museum lighting. Wearing a dark grey wool blazer over a black t-shirt. Thoughtful sophisticated expression.",
        "Bright minimalist art gallery with blurred modern paintings behind, museum lighting. Wearing a cream cable-knit sweater. Thoughtful sophisticated expression.",
        "Bright minimalist art gallery with blurred modern paintings behind, museum lighting. Wearing a navy velvet blazer over a white shirt. Thoughtful sophisticated expression.",
        "Bright minimalist art gallery with blurred modern paintings behind, museum lighting. Wearing a light beige linen suit with a black t-shirt. Thoughtful sophisticated expression.",
        "Bright minimalist art gallery with blurred modern paintings behind, museum lighting. Wearing a dark green wool coat over a white shirt. Thoughtful sophisticated expression.",
        "Bright minimalist art gallery with blurred modern paintings behind, museum lighting. Wearing a plain white t-shirt under a charcoal blazer. Thoughtful sophisticated expression.",
    ]),
    dict(key="modern_lobby", title="Современный лобби", tier=2, preview=_ph("Lobby", "0EA5E9"), prompts=[
        "Bright modern hotel lobby with minimalist Scandinavian design softly blurred behind, natural daylight. Wearing a light beige linen blazer over a white t-shirt. Relaxed confident expression.",
        "Bright modern hotel lobby with minimalist Scandinavian design softly blurred behind, natural daylight. Wearing a dark navy suit with a white shirt and no tie. Relaxed confident expression.",
        "Bright modern hotel lobby with minimalist Scandinavian design softly blurred behind, natural daylight. Wearing a soft grey cashmere sweater over a white collared shirt. Relaxed confident expression.",
        "Bright modern hotel lobby with minimalist Scandinavian design softly blurred behind, natural daylight. Wearing a camel overcoat over a cream turtleneck. Relaxed confident expression.",
        "Bright modern hotel lobby with minimalist Scandinavian design softly blurred behind, natural daylight. Wearing a dark green blazer over a white t-shirt. Relaxed confident expression.",
        "Bright modern hotel lobby with minimalist Scandinavian design softly blurred behind, natural daylight. Wearing a light grey suit with a soft blue shirt. Relaxed confident expression.",
        "Bright modern hotel lobby with minimalist Scandinavian design softly blurred behind, natural daylight. Wearing a burgundy knit polo. Relaxed confident expression.",
    ]),
    dict(key="brick_wall", title="Кирпичная стена", tier=2, preview=_ph("Brick", "7C2D12"), prompts=[
        "Trendy loft interior with a warm exposed red-brick accent wall, industrial pendant lamp glowing, wooden floor and modern furniture softly blurred behind, warm side natural light. Wearing a dark denim jacket over a heather grey t-shirt. Understated confident expression.",
        "Trendy loft interior with a warm exposed red-brick accent wall, industrial pendant lamp, wooden floor and vintage leather sofa softly blurred behind, warm side natural light. Wearing a camel wool overcoat over a cream turtleneck. Understated confident expression.",
        "Trendy converted-warehouse studio with a warm exposed red-brick wall, industrial pendant lamps, wooden beams softly blurred behind, warm side natural light. Wearing a black bomber jacket over a white t-shirt. Understated confident expression.",
        "Trendy loft interior with a warm exposed red-brick accent wall, industrial pendant lamp glowing, wooden floor softly blurred behind, warm side natural light. Wearing a dark green corduroy blazer over a white shirt. Understated confident expression.",
        "Trendy loft interior with a warm exposed red-brick accent wall, industrial pendant lamp, wooden floor softly blurred behind, warm side natural light. Wearing a black leather jacket over a dark grey henley. Understated confident expression.",
        "Trendy loft interior with a warm exposed red-brick accent wall, industrial pendant lamp glowing, wooden floor softly blurred behind, warm side natural light. Wearing a burgundy chunky knit sweater. Understated confident expression.",
        "Trendy loft interior with a warm exposed red-brick accent wall, industrial pendant lamp, wooden floor and green plants softly blurred behind, warm side natural light. Wearing a beige overshirt over a white t-shirt. Understated confident expression.",
    ]),

    # ═══ ТИР 3 — ПРЕМИУМ (18) ═══
    dict(key="magazine_cover", title="Обложка журнала", tier=3, preview=_ph("Magazine", "111827"), prompts=[
        "Deep black studio background, dramatic single-source Hollywood lighting. Wearing a sharp black tailored suit with a black tie. Powerful executive expression, Vanity Fair style.",
        "Deep black studio background, dramatic single-source Hollywood lighting. Wearing a midnight blue tuxedo with a white shirt and a black bow tie. Powerful executive expression, Vanity Fair style.",
        "Deep black studio background, dramatic single-source Hollywood lighting. Wearing a charcoal three-piece suit with a black shirt and no tie. Powerful executive expression, Vanity Fair style.",
        "Deep black studio background, dramatic single-source Hollywood lighting. Wearing a black turtleneck under a black blazer. Powerful executive expression, Vanity Fair style.",
        "Deep black studio background, dramatic single-source Hollywood lighting. Wearing a burgundy velvet dinner jacket over a white shirt with a black bow tie. Powerful executive expression, Vanity Fair style.",
        "Deep black studio background, dramatic single-source Hollywood lighting. Wearing a dark grey pinstripe suit with a white shirt and a dark red tie. Powerful executive expression, Vanity Fair style.",
        "Deep black studio background, dramatic single-source Hollywood lighting. Wearing a black double-breasted suit with a black shirt and a black tie. Powerful executive expression, Vanity Fair style.",
    ]),
    dict(key="ceo_boardroom", title="CEO в переговорке", tier=3, preview=_ph("Boardroom", "0F172A"), prompts=[
        "Dark modern boardroom with mahogany table softly out of focus and city view through the window behind. Wearing a sharp dark navy three-piece suit with a white shirt and grey tie. Commanding CEO expression.",
        "Dark modern boardroom with mahogany table softly out of focus and city view through the window behind. Wearing a charcoal double-breasted suit with a light blue shirt and a burgundy tie. Commanding CEO expression.",
        "Dark modern boardroom with mahogany table softly out of focus and city view through the window behind. Wearing a black tailored suit with a white shirt and a slim black tie. Commanding CEO expression.",
        "Dark modern boardroom with mahogany table softly out of focus and city view through the window behind. Wearing a dark grey pinstripe suit with a white shirt and a dark red tie. Commanding CEO expression.",
        "Dark modern boardroom with mahogany table softly out of focus and city view through the window behind. Wearing a midnight blue three-piece suit with a white shirt and a silver silk tie. Commanding CEO expression.",
        "Dark modern boardroom with mahogany table softly out of focus and city view through the window behind. Wearing a navy suit with a soft pink shirt and a navy tie. Commanding CEO expression.",
        "Dark modern boardroom with mahogany table softly out of focus and city view through the window behind. Wearing a black three-piece suit with a black shirt and a silk pocket square. Commanding CEO expression.",
    ]),
    dict(key="cinema_studio", title="Кинематографический", tier=3, preview=_ph("Cinema", "18181B"), prompts=[
        "Textured dark background with deep teal-and-orange colour grading, dramatic side key light with subtle blue rim. Wearing a black leather jacket over a dark grey shirt. Film grain, movie-poster quality.",
        "Textured dark background with deep teal-and-orange colour grading, dramatic side key light with subtle blue rim. Wearing a dark navy trench coat over a black turtleneck. Film grain, movie-poster quality.",
        "Textured dark background with deep teal-and-orange colour grading, dramatic side key light with subtle blue rim. Wearing a dark burgundy velvet blazer over a black shirt. Film grain, movie-poster quality.",
        "Textured dark background with deep teal-and-orange colour grading, dramatic side key light with subtle blue rim. Wearing a black double-breasted overcoat over a white shirt. Film grain, movie-poster quality.",
        "Textured dark background with deep teal-and-orange colour grading, dramatic side key light with subtle blue rim. Wearing a dark green wool coat over a black turtleneck. Film grain, movie-poster quality.",
        "Textured dark background with deep teal-and-orange colour grading, dramatic side key light with subtle blue rim. Wearing a charcoal wool suit with a white shirt and no tie. Film grain, movie-poster quality.",
        "Textured dark background with deep teal-and-orange colour grading, dramatic side key light with subtle blue rim. Wearing a dark brown leather trench over a black shirt. Film grain, movie-poster quality.",
    ]),
    dict(key="fashion_editorial", title="Fashion Editorial", tier=3, preview=_ph("Fashion", "F43F5E"), prompts=[
        "Bold clean saturated red background, strong beauty-dish key light. Wearing a sharp black fitted turtleneck under a structured designer blazer. Vogue-style editorial expression.",
        "Bold clean saturated red background, strong beauty-dish key light. Wearing an oversized cream wool coat over a black shirt. Vogue-style editorial expression.",
        "Bold clean saturated red background, strong beauty-dish key light. Wearing a bold designer olive blazer over a white shirt. Vogue-style editorial expression.",
        "Bold clean saturated red background, strong beauty-dish key light. Wearing a black leather trench coat over a black turtleneck. Vogue-style editorial expression.",
        "Bold clean saturated red background, strong beauty-dish key light. Wearing a pale grey wool suit with a white shirt and a black bolo. Vogue-style editorial expression.",
        "Bold clean saturated red background, strong beauty-dish key light. Wearing a dark green satin shirt with the top buttons unbuttoned. Vogue-style editorial expression.",
        "Bold clean saturated red background, strong beauty-dish key light. Wearing a black-and-white geometric print silk shirt. Vogue-style editorial expression.",
    ]),
    dict(key="keynote_stage", title="На сцене (Keynote)", tier=3, preview=_ph("Keynote", "9333EA"), prompts=[
        "Blurred dark auditorium with soft audience glow behind, dramatic single spotlight from above. Wearing a slim dark navy blazer over a black t-shirt. Mid-speech confident expression, TED-talk style.",
        "Blurred dark auditorium with soft audience glow behind, dramatic single spotlight from above. Wearing a dark grey suit with a light blue shirt and no tie. Mid-speech confident expression, TED-talk style.",
        "Blurred dark auditorium with soft audience glow behind, dramatic single spotlight from above. Wearing a black turtleneck under a charcoal blazer. Mid-speech confident expression, TED-talk style.",
        "Blurred dark auditorium with soft audience glow behind, dramatic single spotlight from above. Wearing a burgundy velvet blazer over a black shirt. Mid-speech confident expression, TED-talk style.",
        "Blurred dark auditorium with soft audience glow behind, dramatic single spotlight from above. Wearing a black suit with a white t-shirt and no tie. Mid-speech confident expression, TED-talk style.",
        "Blurred dark auditorium with soft audience glow behind, dramatic single spotlight from above. Wearing a navy zip-up sweater over a light grey t-shirt. Mid-speech confident expression, TED-talk style.",
        "Blurred dark auditorium with soft audience glow behind, dramatic single spotlight from above. Wearing a dark green blazer over a black turtleneck. Mid-speech confident expression, TED-talk style.",
    ]),
    dict(key="tech_hologram", title="Tech с голограммой", tier=3, preview=_ph("Hologram", "6366F1"), prompts=[
        "Dark tech environment with subtle holographic UI elements floating around, blue-purple accent lighting. Wearing a black minimalist zip-up jacket over a black t-shirt. Modern tech-founder look.",
        "Dark tech environment with subtle holographic UI elements floating around, blue-purple accent lighting. Wearing a dark grey techwear hoodie. Modern tech-founder look.",
        "Dark tech environment with subtle holographic UI elements floating around, blue-purple accent lighting. Wearing a black turtleneck. Modern tech-founder look.",
        "Dark tech environment with subtle holographic UI elements floating around, blue-purple accent lighting. Wearing a dark navy techwear utility jacket over a black shirt. Modern tech-founder look.",
        "Dark tech environment with subtle holographic UI elements floating around, blue-purple accent lighting. Wearing a black rollneck under a charcoal blazer. Modern tech-founder look.",
        "Dark tech environment with subtle holographic UI elements floating around, blue-purple accent lighting. Wearing a plain white t-shirt under a black leather bomber. Modern tech-founder look.",
        "Dark tech environment with subtle holographic UI elements floating around, blue-purple accent lighting. Wearing a dark green shell jacket over a black t-shirt. Modern tech-founder look.",
    ]),
    dict(key="business_dinner", title="Бизнес-ужин", tier=3, preview=_ph("Dinner", "7C2D12"), prompts=[
        "Elegant fine-dining restaurant with candles softly out of focus, warm golden ambient light. Wearing a sharp charcoal blazer over a dark grey shirt. Subtle confident smile.",
        "Elegant fine-dining restaurant with candles softly out of focus, warm golden ambient light. Wearing a navy suit with a white shirt and no tie. Subtle confident smile.",
        "Elegant fine-dining restaurant with candles softly out of focus, warm golden ambient light. Wearing a dark burgundy velvet blazer over a black shirt. Subtle confident smile.",
        "Elegant fine-dining restaurant with candles softly out of focus, warm golden ambient light. Wearing a black tuxedo jacket over a white shirt with a black bow tie. Subtle confident smile.",
        "Elegant fine-dining restaurant with candles softly out of focus, warm golden ambient light. Wearing a midnight blue three-piece suit with a white shirt and a silver tie. Subtle confident smile.",
        "Elegant fine-dining restaurant with candles softly out of focus, warm golden ambient light. Wearing a dark green velvet blazer over a cream shirt. Subtle confident smile.",
        "Elegant fine-dining restaurant with candles softly out of focus, warm golden ambient light. Wearing a charcoal double-breasted blazer over a black turtleneck. Subtle confident smile.",
    ]),
    dict(key="with_award", title="С наградой", tier=3, preview=_ph("Award", "B45309"), prompts=[
        "Elegant dark stage backdrop with soft golden bokeh lights softly blurred behind. Wearing a sharp black tailored suit with a white shirt and slim black tie, holding a modern glass award trophy. Proud confident expression.",
        "Elegant dark stage backdrop with soft golden bokeh lights softly blurred behind. Wearing a midnight blue tuxedo with a white shirt and a black bow tie, holding a modern glass award trophy. Proud confident expression.",
        "Elegant dark stage backdrop with soft golden bokeh lights softly blurred behind. Wearing a charcoal three-piece suit with a white shirt and a burgundy tie, holding a modern glass award trophy. Proud confident expression.",
        "Elegant dark stage backdrop with soft golden bokeh lights softly blurred behind. Wearing a black double-breasted tuxedo with a white shirt and a black bow tie, holding a modern glass award trophy. Proud confident expression.",
        "Elegant dark stage backdrop with soft golden bokeh lights softly blurred behind. Wearing a dark green velvet dinner jacket over a black shirt, holding a modern glass award trophy. Proud confident expression.",
        "Elegant dark stage backdrop with soft golden bokeh lights softly blurred behind. Wearing a white dinner jacket with a black bow tie over a white shirt, holding a modern glass award trophy. Proud confident expression.",
        "Elegant dark stage backdrop with soft golden bokeh lights softly blurred behind. Wearing a dark navy suit with a white shirt and a dark silk tie, holding a modern glass award trophy. Proud confident expression.",
    ]),
    dict(key="private_jet", title="Частный джет", tier=3, preview=_ph("Jet", "0F172A"), prompts=[
        "Private jet cabin with cream leather seats blurred behind, warm cabin lighting. Wearing a tailored dark grey suit with a white shirt, no tie. Subtle confident smile.",
        "Private jet cabin with cream leather seats blurred behind, warm cabin lighting. Wearing a camel cashmere overcoat over a black turtleneck. Subtle confident smile.",
        "Private jet cabin with cream leather seats blurred behind, warm cabin lighting. Wearing a dark navy blazer over a light blue shirt, no tie. Subtle confident smile.",
        "Private jet cabin with cream leather seats blurred behind, warm cabin lighting. Wearing a charcoal cashmere sweater over a white collared shirt. Subtle confident smile.",
        "Private jet cabin with cream leather seats blurred behind, warm cabin lighting. Wearing a black three-piece suit with a white shirt and no tie. Subtle confident smile.",
        "Private jet cabin with cream leather seats blurred behind, warm cabin lighting. Wearing a beige linen blazer over a soft blue shirt. Subtle confident smile.",
        "Private jet cabin with cream leather seats blurred behind, warm cabin lighting. Wearing a burgundy cashmere V-neck sweater over a white shirt. Subtle confident smile.",
    ]),
    dict(key="black_tie_gala", title="Гала-ужин (Black tie)", tier=3, preview=_ph("Gala", "111827"), prompts=[
        "Softly blurred formal ballroom with warm chandelier light behind, dramatic cinematic lighting. Wearing a classic black tuxedo with a white shirt and black bow tie. Poised sophisticated expression.",
        "Softly blurred formal ballroom with warm chandelier light behind, dramatic cinematic lighting. Wearing a midnight blue velvet dinner jacket over a black shirt. Poised sophisticated expression.",
        "Softly blurred formal ballroom with warm chandelier light behind, dramatic cinematic lighting. Wearing a white dinner jacket with a black bow tie over a white shirt. Poised sophisticated expression.",
        "Softly blurred formal ballroom with warm chandelier light behind, dramatic cinematic lighting. Wearing a black double-breasted tuxedo with a white shirt and a black bow tie. Poised sophisticated expression.",
        "Softly blurred formal ballroom with warm chandelier light behind, dramatic cinematic lighting. Wearing a burgundy velvet dinner jacket over a white shirt and a black bow tie. Poised sophisticated expression.",
        "Softly blurred formal ballroom with warm chandelier light behind, dramatic cinematic lighting. Wearing a dark green velvet dinner jacket over a cream shirt with a black bow tie. Poised sophisticated expression.",
        "Softly blurred formal ballroom with warm chandelier light behind, dramatic cinematic lighting. Wearing a black three-piece suit with a black shirt and a silk pocket square. Poised sophisticated expression.",
    ]),
    dict(key="strategy_meeting", title="Стратегическая встреча", tier=3, preview=_ph("Strategy", "1E293B"), prompts=[
        "Dark modern boardroom with softly blurred colleagues around a large table and city view through the window. Wearing a tailored charcoal suit with a light blue shirt, no tie. Commanding thoughtful expression, cinematic lighting.",
        "Dark modern boardroom with softly blurred colleagues around a large table and city view through the window. Wearing a dark navy blazer over a white shirt with a slim dark tie. Commanding thoughtful expression, cinematic lighting.",
        "Dark modern boardroom with softly blurred colleagues around a large table and city view through the window. Wearing a black turtleneck under a grey blazer. Commanding thoughtful expression, cinematic lighting.",
        "Dark modern boardroom with softly blurred colleagues around a large table and city view through the window. Wearing a midnight blue three-piece suit with a white shirt and a silver tie. Commanding thoughtful expression, cinematic lighting.",
        "Dark modern boardroom with softly blurred colleagues around a large table and city view through the window. Wearing a charcoal blazer over a black rollneck. Commanding thoughtful expression, cinematic lighting.",
        "Dark modern boardroom with softly blurred colleagues around a large table and city view through the window. Wearing a dark grey pinstripe suit with a soft blue shirt and a burgundy tie. Commanding thoughtful expression, cinematic lighting.",
        "Dark modern boardroom with softly blurred colleagues around a large table and city view through the window. Wearing a black suit with a white shirt and a slim silver tie. Commanding thoughtful expression, cinematic lighting.",
    ]),
    dict(key="museum", title="В музее", tier=3, preview=_ph("Museum", "78716C"), prompts=[
        "Classic museum hall with marble columns and softly blurred renaissance paintings behind, warm gallery lighting. Wearing a refined dark navy suit with a white shirt. Sophisticated expression.",
        "Classic museum hall with marble columns and softly blurred renaissance paintings behind, warm gallery lighting. Wearing a black rollneck under a charcoal wool coat. Sophisticated expression.",
        "Classic museum hall with marble columns and softly blurred renaissance paintings behind, warm gallery lighting. Wearing a brown tweed jacket over a cream sweater. Sophisticated expression.",
        "Classic museum hall with marble columns and softly blurred renaissance paintings behind, warm gallery lighting. Wearing a camel wool overcoat over a light grey turtleneck. Sophisticated expression.",
        "Classic museum hall with marble columns and softly blurred renaissance paintings behind, warm gallery lighting. Wearing a burgundy velvet blazer over a white shirt. Sophisticated expression.",
        "Classic museum hall with marble columns and softly blurred renaissance paintings behind, warm gallery lighting. Wearing a dark green three-piece suit with a white shirt and a knit tie. Sophisticated expression.",
        "Classic museum hall with marble columns and softly blurred renaissance paintings behind, warm gallery lighting. Wearing a dark grey herringbone blazer over a soft blue shirt. Sophisticated expression.",
    ]),
    dict(key="vineyard", title="Винодельня", tier=3, preview=_ph("Vineyard", "7C2D12"), prompts=[
        "Sun-lit vineyard with softly blurred vines and wooden barrels behind, warm golden hour light. Wearing an olive linen shirt with sleeves rolled up over dark trousers, holding a glass of red wine. Quiet-luxury aesthetic.",
        "Sun-lit vineyard with softly blurred vines and wooden barrels behind, warm golden hour light. Wearing a beige linen blazer over a white t-shirt, holding a glass of red wine. Quiet-luxury aesthetic.",
        "Sun-lit vineyard with softly blurred vines and wooden barrels behind, warm golden hour light. Wearing a white oxford shirt with sleeves rolled up under a navy sweater draped over the shoulders, holding a glass of red wine. Quiet-luxury aesthetic.",
        "Sun-lit vineyard with softly blurred vines and wooden barrels behind, warm golden hour light. Wearing a light blue chambray shirt tucked into cream chinos, holding a glass of red wine. Quiet-luxury aesthetic.",
        "Sun-lit vineyard with softly blurred vines and wooden barrels behind, warm golden hour light. Wearing a tan suede jacket over a white shirt, holding a glass of red wine. Quiet-luxury aesthetic.",
        "Sun-lit vineyard with softly blurred vines and wooden barrels behind, warm golden hour light. Wearing a soft cream cashmere sweater over a white collared shirt, holding a glass of red wine. Quiet-luxury aesthetic.",
        "Sun-lit vineyard with softly blurred vines and wooden barrels behind, warm golden hour light. Wearing a dark navy linen shirt with sleeves rolled up, holding a glass of red wine. Quiet-luxury aesthetic.",
    ]),
    dict(key="yacht", title="На яхте", tier=3, preview=_ph("Yacht", "0EA5E9"), prompts=[
        "Sleek modern yacht deck with blue Mediterranean sea and clear sky softly blurred behind, sun-kissed skin. Wearing a crisp white linen shirt with sleeves rolled up. Subtle confident smile, quiet-money aesthetic.",
        "Sleek modern yacht deck with blue Mediterranean sea and clear sky softly blurred behind, sun-kissed skin. Wearing a navy polo shirt. Subtle confident smile, quiet-money aesthetic.",
        "Sleek modern yacht deck with blue Mediterranean sea and clear sky softly blurred behind, sun-kissed skin. Wearing an unbuttoned white linen shirt over a light blue t-shirt. Subtle confident smile, quiet-money aesthetic.",
        "Sleek modern yacht deck with blue Mediterranean sea and clear sky softly blurred behind, sun-kissed skin. Wearing a light beige linen blazer over a white t-shirt. Subtle confident smile, quiet-money aesthetic.",
        "Sleek modern yacht deck with blue Mediterranean sea and clear sky softly blurred behind, sun-kissed skin. Wearing a navy Breton-striped long-sleeve shirt. Subtle confident smile, quiet-money aesthetic.",
        "Sleek modern yacht deck with blue Mediterranean sea and clear sky softly blurred behind, sun-kissed skin. Wearing a soft pink linen shirt with the top buttons unbuttoned. Subtle confident smile, quiet-money aesthetic.",
        "Sleek modern yacht deck with blue Mediterranean sea and clear sky softly blurred behind, sun-kissed skin. Wearing a white polo shirt under a light navy sweater draped over the shoulders. Subtle confident smile, quiet-money aesthetic.",
    ]),
    dict(key="mountain_top", title="Горная вершина", tier=3, preview=_ph("Mountain", "1E293B"), prompts=[
        "Mountain peak at golden hour with layered mountain silhouettes softly blurred behind, warm side light. Wearing a dark technical outdoor jacket. Adventurous confident expression.",
        "Mountain peak at golden hour with layered mountain silhouettes softly blurred behind, warm side light. Wearing a burnt-orange puffer jacket. Adventurous confident expression.",
        "Mountain peak at golden hour with layered mountain silhouettes softly blurred behind, warm side light. Wearing a heather grey wool sweater under a dark green shell jacket. Adventurous confident expression.",
        "Mountain peak at golden hour with layered mountain silhouettes softly blurred behind, warm side light. Wearing a dark blue technical windbreaker over a beige turtleneck. Adventurous confident expression.",
        "Mountain peak at golden hour with layered mountain silhouettes softly blurred behind, warm side light. Wearing a black insulated jacket with a fur-trimmed hood. Adventurous confident expression.",
        "Mountain peak at golden hour with layered mountain silhouettes softly blurred behind, warm side light. Wearing a khaki fleece over a plaid flannel shirt. Adventurous confident expression.",
        "Mountain peak at golden hour with layered mountain silhouettes softly blurred behind, warm side light. Wearing a dark red down jacket over a black thermal shirt. Adventurous confident expression.",
    ]),
    dict(key="golf_club", title="Гольф-клуб", tier=3, preview=_ph("Golf", "78350F"), prompts=[
        "Manicured golf course green with softly blurred fairway and clubhouse behind, soft afternoon light. Wearing a navy polo shirt. Subtle confident smile, quiet-money aesthetic.",
        "Manicured golf course green with softly blurred fairway and clubhouse behind, soft afternoon light. Wearing a white polo shirt with a light beige sweater draped over the shoulders. Subtle confident smile, quiet-money aesthetic.",
        "Manicured golf course green with softly blurred fairway and clubhouse behind, soft afternoon light. Wearing a burgundy polo shirt. Subtle confident smile, quiet-money aesthetic.",
        "Manicured golf course green with softly blurred fairway and clubhouse behind, soft afternoon light. Wearing a soft pink polo shirt under a light grey V-neck sweater. Subtle confident smile, quiet-money aesthetic.",
        "Manicured golf course green with softly blurred fairway and clubhouse behind, soft afternoon light. Wearing a dark green polo shirt with a beige argyle vest. Subtle confident smile, quiet-money aesthetic.",
        "Manicured golf course green with softly blurred fairway and clubhouse behind, soft afternoon light. Wearing a light blue polo shirt. Subtle confident smile, quiet-money aesthetic.",
        "Manicured golf course green with softly blurred fairway and clubhouse behind, soft afternoon light. Wearing a cream cable-knit half-zip sweater over a white polo. Subtle confident smile, quiet-money aesthetic.",
    ]),
    dict(key="christmas", title="Праздничная (Xmas)", tier=3, preview=_ph("Xmas", "7C2D12"), prompts=[
        "Warm cozy setting with a beautifully decorated Christmas tree softly blurred behind and warm golden bokeh lights. Wearing an elegant burgundy cashmere sweater. Warm genuine smile, holiday editorial aesthetic.",
        "Warm cozy setting with a beautifully decorated Christmas tree softly blurred behind and warm golden bokeh lights. Wearing a dark green wool blazer over a white shirt. Warm genuine smile, holiday editorial aesthetic.",
        "Warm cozy setting with a beautifully decorated Christmas tree softly blurred behind and warm golden bokeh lights. Wearing a soft cream cable-knit sweater over a white collared shirt. Warm genuine smile, holiday editorial aesthetic.",
        "Warm cozy setting with a beautifully decorated Christmas tree softly blurred behind and warm golden bokeh lights. Wearing a red-and-black plaid flannel shirt. Warm genuine smile, holiday editorial aesthetic.",
        "Warm cozy setting with a beautifully decorated Christmas tree softly blurred behind and warm golden bokeh lights. Wearing a dark navy Fair Isle knit sweater. Warm genuine smile, holiday editorial aesthetic.",
        "Warm cozy setting with a beautifully decorated Christmas tree softly blurred behind and warm golden bokeh lights. Wearing a charcoal turtleneck under a burgundy velvet blazer. Warm genuine smile, holiday editorial aesthetic.",
        "Warm cozy setting with a beautifully decorated Christmas tree softly blurred behind and warm golden bokeh lights. Wearing a camel cashmere overcoat over a cream turtleneck. Warm genuine smile, holiday editorial aesthetic.",
    ]),
    dict(key="beach_sunset", title="Пляж на закате", tier=3, preview=_ph("Beach", "F97316"), prompts=[
        "Tropical beach at sunset with warm orange and pink sky and gentle waves softly blurred behind. Wearing a white linen shirt open at the collar. Relaxed happy expression, golden hour glow.",
        "Tropical beach at sunset with warm orange and pink sky and gentle waves softly blurred behind. Wearing a light beige linen shirt with the top buttons unbuttoned. Relaxed happy expression, golden hour glow.",
        "Tropical beach at sunset with warm orange and pink sky and gentle waves softly blurred behind. Wearing a soft blue chambray shirt with sleeves rolled up. Relaxed happy expression, golden hour glow.",
        "Tropical beach at sunset with warm orange and pink sky and gentle waves softly blurred behind. Wearing a cream linen henley shirt. Relaxed happy expression, golden hour glow.",
        "Tropical beach at sunset with warm orange and pink sky and gentle waves softly blurred behind. Wearing an unbuttoned white linen shirt over a white t-shirt. Relaxed happy expression, golden hour glow.",
        "Tropical beach at sunset with warm orange and pink sky and gentle waves softly blurred behind. Wearing a light tan linen overshirt over a white t-shirt. Relaxed happy expression, golden hour glow.",
        "Tropical beach at sunset with warm orange and pink sky and gentle waves softly blurred behind. Wearing a soft pink linen shirt with sleeves rolled up. Relaxed happy expression, golden hour glow.",
    ]),
]


# Отслеживание использованных вариантов на устройство+сцену.
# Когда все варианты этой сцены показаны данному устройству — цикл сбрасывается.
# ═══ ОТРАСЛЕВЫЕ ПОДБОРКИ ═══
#
# Каталог из 47 сцен целиком человеку не нужен: ему нужны те, что уместны
# в его профессии. Подборка — это просто список ключей; сами сцены не
# дублируются и не меняются. Порядок внутри подборки задаёт _STYLES,
# то есть тиры идут по возрастанию — от этого зависит scenes_pool.
_INDUSTRIES: list[dict] = [
    dict(key="tech", title="IT и продукт", scenes=[
        "linkedin_classic", "at_laptop", "clean_studio", "home_office", "minimal_grey",
        "modern_glass", "tech_dark", "whiteboard", "cyberpunk",
        "tech_hologram", "keynote_stage", "magazine_cover",
    ]),
    dict(key="finance", title="Финансы и право", scenes=[
        "business_light", "corporate_navy", "business_office", "reading_docs", "bookshelf",
        "library_dark", "modern_lobby",
        "ceo_boardroom", "strategy_meeting", "business_dinner", "black_tie_gala", "private_jet",
    ]),
    dict(key="sales", title="Продажи и недвижимость", scenes=[
        "linkedin_classic", "business_light", "casual_smart", "warm_office", "modern_glass",
        "phone_call", "rooftop", "urban_street", "realtor", "modern_lobby",
        "vineyard", "golf_club", "yacht",
    ]),
    dict(key="creative", title="Креатив и медиа", scenes=[
        "clean_studio", "casual_smart", "coffee_cup",
        "creative_studio", "podcast_studio", "art_gallery", "urban_street", "brick_wall",
        "cinema_studio", "fashion_editorial", "magazine_cover", "museum",
    ]),
    dict(key="education", title="Образование и наука", scenes=[
        "clean_studio", "reading_docs", "bookshelf", "minimal_grey",
        "university", "library_dark", "whiteboard", "art_gallery",
        "keynote_stage", "strategy_meeting", "museum",
    ]),
    dict(key="executive", title="Руководство", scenes=[
        "business_light", "corporate_navy", "business_office", "modern_glass",
        "rooftop", "modern_lobby",
        "ceo_boardroom", "keynote_stage", "strategy_meeting", "with_award",
        "private_jet", "black_tie_gala", "magazine_cover",
    ]),
    dict(key="personal", title="Личный бренд", scenes=[
        "casual_smart", "coffee_cup", "home_office", "warm_office",
        "cafe_window", "urban_street", "brick_wall", "rooftop",
        "cinema_studio", "fashion_editorial", "beach_sunset", "mountain_top", "christmas",
    ]),
]

# Названия подборок. Отдельно от SCENE_TITLES: там переводы названий сцен,
# а это другой словарь и смешивать их незачем.
_INDUSTRY_TITLES: dict[str, dict[str, str]] = {
    "tech":      {"en": "Tech & product",        "es": "Tecnología y producto", "pt": "Tecnologia e produto", "de": "Tech & Produkt",        "fr": "Tech et produit"},
    "finance":   {"en": "Finance & law",         "es": "Finanzas y derecho",    "pt": "Finanças e direito",   "de": "Finanzen & Recht",      "fr": "Finance et droit"},
    "sales":     {"en": "Sales & real estate",   "es": "Ventas e inmobiliaria", "pt": "Vendas e imóveis",     "de": "Vertrieb & Immobilien", "fr": "Vente et immobilier"},
    "creative":  {"en": "Creative & media",      "es": "Creatividad y medios",  "pt": "Criativo e mídia",     "de": "Kreativ & Medien",      "fr": "Création et médias"},
    "education": {"en": "Education & science",   "es": "Educación y ciencia",   "pt": "Educação e ciência",   "de": "Bildung & Wissenschaft","fr": "Éducation et science"},
    "executive": {"en": "Executive",             "es": "Dirección",             "pt": "Direção",              "de": "Führung",               "fr": "Direction"},
    "personal":  {"en": "Personal brand",        "es": "Marca personal",        "pt": "Marca pessoal",        "de": "Personal Branding",     "fr": "Marque personnelle"},
}


def _industry_title(key: str, ru_title: str, lang: str) -> str:
    if lang == "ru":
        return ru_title
    return _INDUSTRY_TITLES.get(key, {}).get(lang, ru_title)


def _industry_scene_keys(key: str) -> list[str] | None:
    """Ключи сцен подборки в порядке каталога — то есть тиры по возрастанию.

    Порядок важен: клиент берёт первые scenes_pool сцен, и если премиальная
    окажется в начале списка, базовый тариф до неё дотянется.
    """
    industry = next((i for i in _INDUSTRIES if i["key"] == key), None)
    if industry is None:
        return None
    wanted = set(industry["scenes"])
    return [s["key"] for s in _STYLES if s["key"] in wanted]


_used_variants: dict[tuple[str, str], set[int]] = {}
_used_lock = threading.Lock()


def _to_public(s: dict, lang: str) -> StyleOut:
    if (THUMBS_DIR / f"{s['key']}.jpg").exists():
        preview_url = f"{PUBLIC_BASE_URL}/api/v1/thumbs/{s['key']}?w=600"
    else:
        preview_url = s["preview"]
    return StyleOut(
        key=s["key"],
        title=tr_scene(s["title"], lang),
        preview_url=preview_url,
        tier=s["tier"],
    )


def get_prompt(style_key: str, device_id: str = "") -> str | None:
    """
    Возвращает случайный НЕ-повторяющийся вариант промпта для данного устройства и сцены.
    После того как все варианты сцены показаны — цикл сбрасывается.
    """
    style = next((s for s in _STYLES if s["key"] == style_key), None)
    if not style:
        return None
    variants: list[str] = style["prompts"]
    key = (device_id or "_shared", style_key)
    with _used_lock:
        used = _used_variants.setdefault(key, set())
        available = [i for i in range(len(variants)) if i not in used]
        if not available:
            used.clear()
            available = list(range(len(variants)))
        idx = random.choice(available)
        used.add(idx)
    return variants[idx]


@router.get("/industries", response_model=list[IndustryOut])
def list_industries(
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
):
    """Подборки сцен по профессии. Сами сцены отдаёт /styles."""
    lang = pick_lang(accept_language)
    out: list[IndustryOut] = []
    for industry in _INDUSTRIES:
        keys = _industry_scene_keys(industry["key"]) or []
        cover = next((s for s in _STYLES if s["key"] == keys[0]), None) if keys else None
        out.append(IndustryOut(
            key=industry["key"],
            title=_industry_title(industry["key"], industry["title"], lang),
            scene_count=len(keys),
            preview_url=_to_public(cover, lang).preview_url if cover else "",
        ))
    return out


@router.get("", response_model=list[StyleOut])
def list_styles(
    max_tier: int = Query(default=3, ge=1, le=3),
    industry: str | None = Query(default=None),
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
):
    lang = pick_lang(accept_language)
    styles = [s for s in _STYLES if s["tier"] <= max_tier]
    if industry:
        keys = _industry_scene_keys(industry)
        # Неизвестная подборка — отдаём весь каталог, а не пустоту: пустой
        # экран человек прочтёт как поломку.
        if keys is not None:
            allowed = set(keys)
            styles = [s for s in styles if s["key"] in allowed]
    return [_to_public(s, lang) for s in styles]
