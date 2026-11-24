"""Rule-based helpers behind the 'Smart Tools' pages."""
import math
import re
from datetime import date

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
RAINY = {6, 7, 8, 9}

# ---------- Outfit recommendation ----------
BASE_TEMP = {
    "cool": (14, 22), "cold": (8, 16), "tropical": (26, 33), "humid": (22, 30), "moderate": (22, 30),
    "hill": (14, 24), "beach": (26, 33), "backwater": (25, 33), "forest": (20, 30),
    "waterfall": (22, 30), "plains": (24, 35)
}
ACTIVITY_WEAR = {
    "cool": "Light jacket, full-sleeve tops and comfortable walking shoes",
    "cold": "Winter jacket, warm sweaters, thermals and boots",
    "tropical": "Breathable cotton clothes, swimwear, hat and sunglasses",
    "humid": "Quick-dry clothes, breathable t-shirts and non-slip sandals",
    "moderate": "Comfortable cotton clothes and walking sneakers",
    "hill": "Comfortable trekking shoes and a windcheater",
    "beach": "Swimwear and a hat",
    "backwater": "Light cotton clothes and a cap for the boat ride",
    "forest": "Full-sleeve shirt, long trousers and trekking shoes",
    "waterfall": "Quick-dry clothes and sandals with a good grip",
    "plains": "Light cotton clothes"
}


def outfit_for(dest, month):
    lo, hi = BASE_TEMP.get(dest.climate, (22, 30))
    cold = (dest.climate in ("cool", "cold", "hill")) and month in (11, 12, 1, 2)
    if cold:
        lo, hi = lo - 6, hi - 4
    rainy = month in RAINY
    items = []
    if dest.climate == "cold" or (cold and dest.climate != "tropical"):
        items += ["Winter jacket", "Sweaters / thermals", "Woollen cap and gloves", "Boots"]
    elif dest.climate in ("cool", "hill"):
        items += ["Light jacket for evenings", "Full-sleeve tops", "Sneakers"]
    elif dest.climate in ("tropical", "beach"):
        items += ["Breathable cotton t-shirts", "Shorts or light trousers", "Sunglasses and sunscreen", "Hat"]
    else:
        items += ["Breathable cotton t-shirts", "Shorts or light trousers", "Sunglasses and sunscreen"]
    if rainy:
        items += ["Raincoat or compact umbrella", "Quick-dry clothes", "Waterproof bag cover"]
    items.append(ACTIVITY_WEAR.get(dest.climate, "Comfortable walking shoes"))
    return {"temp": f"{lo}°C - {hi}°C", "season": "Monsoon" if rainy else ("Winter" if month in (12, 1, 2) else "Dry season"),
            "items": items}


# ---------- Best time to visit ----------
def best_time(dest):
    best, peak, out = set(dest.best_month_list), set(dest.peak_month_list), []
    for m in range(1, 13):
        weather = 90 if m in best else (45 if m in RAINY else 65)
        crowd = "Peak" if m in peak else "Off-season" if m in RAINY and m not in best else "Normal"
        score = weather - (10 if m in peak else 0)
        out.append({"month": MONTHS[m - 1], "score": score, "crowd": crowd,
                    "weather": "Ideal" if m in best else "Rainy" if m in RAINY else "Average"})
    top = [o["month"] for o in sorted(out, key=lambda x: -x["score"])[:3]]
    return out, top


# ---------- Distance / route ----------
def haversine(a, b):
    r = 6371
    p1, p2 = math.radians(a.latitude), math.radians(b.latitude)
    dphi, dl = p2 - p1, math.radians(b.longitude - a.longitude)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def plan_route(dests, travellers=2, days_each=2):
    """Order stops by nearest neighbour from the first one and cost the trip."""
    if not dests:
        return None
    left, route = list(dests[1:]), [dests[0]]
    while left:
        nxt = min(left, key=lambda d: haversine(route[-1], d))
        left.remove(nxt)
        route.append(nxt)
    legs, total_km, total_h = [], 0, 0
    for a, b in zip(route, route[1:]):
        km = round(haversine(a, b) * 1.35)  # road factor
        hrs = round(km / 40, 1)
        legs.append({"from": a, "to": b, "km": km, "hours": hrs})
        total_km += km
        total_h += hrs
    stay_food = sum(d.avg_daily_cost * days_each * travellers for d in route)
    transport = total_km * 14 * max(1, math.ceil(travellers / 4))
    return {"route": route, "legs": legs, "km": total_km, "hours": round(total_h, 1),
            "days": days_each * len(route), "budget": stay_food + transport,
            "stay_food": stay_food, "transport": transport}


# ---------- Cost optimiser ----------
def cost_options(dest, days, travellers):
    hotels = sorted(dest.hotels.all(), key=lambda h: h.price_per_night)
    rooms = math.ceil(travellers / 2)
    nights = max(days - 1, 1)
    picks = []
    if hotels:
        picks = [("Budget", hotels[0]), ("Standard", hotels[len(hotels) // 2]), ("Comfort", hotels[-1])]
    tiers = {"Budget": (300, 450, "Public bus / shared jeep"), "Standard": (800, 800, "Shared cab / auto"),
             "Comfort": (2200, 1400, "Private cab")}
    out = []
    for name, hotel in picks:
        transport, food, mode = tiers[name]
        stay = hotel.price_per_night * rooms * nights
        total = stay + transport * days + food * travellers * days
        out.append({"tier": name, "hotel": hotel, "mode": mode, "stay": stay, "transport": transport * days,
                    "food": food * travellers * days, "total": total})
    return out


# ---------- Sentiment (simple lexicon) ----------
POS = {"good", "great", "excellent", "amazing", "beautiful", "clean", "friendly", "love", "loved", "awesome", "peaceful",
       "stunning", "wonderful", "perfect", "best", "nice", "comfortable", "scenic", "fresh", "affordable", "recommended"}
NEG = {"bad", "dirty", "crowded", "expensive", "poor", "worst", "rude", "noisy", "boring", "overpriced", "slow",
       "unsafe", "disappointing", "terrible", "waste", "smelly", "difficult", "closed"}


def sentiment(text):
    words = re.findall(r"[a-z']+", text.lower())
    score = sum(w in POS for w in words) - sum(w in NEG for w in words)
    return "Positive" if score > 0 else "Negative" if score < 0 else "Neutral"


def keywords(texts):
    pos, neg = {}, {}
    for t in texts:
        for w in re.findall(r"[a-z']+", t.lower()):
            if w in POS:
                pos[w] = pos.get(w, 0) + 1
            elif w in NEG:
                neg[w] = neg.get(w, 0) + 1
    top = lambda d: sorted(d, key=d.get, reverse=True)[:5]
    return top(pos), top(neg)


# ---------- Documents ----------
def passport_status(expiry, travel_date):
    if not expiry:
        return None
    ref = travel_date or date.today()
    months = (expiry.year - ref.year) * 12 + expiry.month - ref.month
    if months < 0:
        return ("danger", "Your passport expires before the trip. Renew it first.")
    if months < 6:
        return ("warn", f"Passport valid for only {months} month(s) at travel time. Many countries need 6+ months.")
    return ("ok", f"Passport is valid for {months} months after travel starts.")


DOC_CHECKLIST = ["Government photo ID (Aadhaar / driving licence)", "Passport (international trips)", "Visa / e-visa",
                 "Train / flight / bus tickets", "Hotel booking confirmation", "Travel insurance papers",
                 "Emergency contact list", "Prescriptions and essential medicines", "Some cash + debit/credit card"]

# ---------- Safety ----------
EMERGENCY = [("All emergencies", "112"), ("Police", "100"), ("Ambulance", "108"), ("Fire", "101"),
             ("Tourist helpline", "1363"), ("Women helpline", "1091")]
SAFETY_TIPS = {
    "hill": ["Check road and weather conditions before driving at night.", "Carry warm clothes and a power bank."],
    "beach": ["Swim only in marked zones and obey lifeguard flags.", "Avoid the sea during red-flag days."],
    "backwater": ["Wear the life jacket on boats.", "Book houseboats from DTPC-approved operators."],
    "forest": ["Stay on marked trails and follow guides.", "Do not feed or approach wild animals."],
    "waterfall": ["Avoid slippery rocks near the edge.", "Stay out of the water in monsoon flood alerts."],
    "plains": ["Keep valuables out of sight.", "Use licensed taxis or app cabs."],
}

# ---------- Translator ----------
PHRASES = [
    ("Hello", {"ml": "നമസ്കാരം", "hi": "नमस्ते", "ta": "வணக்கம்"}),
    ("Thank you", {"ml": "നന്ദി", "hi": "धन्यवाद", "ta": "நன்றி"}),
    ("Yes / No", {"ml": "അതെ / അല്ല", "hi": "हाँ / नहीं", "ta": "ஆம் / இல்லை"}),
    ("How much is this?", {"ml": "ഇതിന് എത്രയാണ് വില?", "hi": "यह कितने का है?", "ta": "இது எவ்வளவு?"}),
    ("Too expensive", {"ml": "വില കൂടുതലാണ്", "hi": "यह बहुत महंगा है", "ta": "விலை அதிகம்"}),
    ("Water, please", {"ml": "കുറച്ച് വെള്ളം തരൂ", "hi": "कृपया पानी दीजिए", "ta": "தண்ணீர் கொடுங்கள்"}),
    ("I need vegetarian food", {"ml": "എനിക്ക് വെജിറ്റേറിയൻ ഭക്ഷണം വേണം", "hi": "मुझे शाकाहारी खाना चाहिए", "ta": "எனக்கு சைவ உணவு வேண்டும்"}),
    ("Where is the bus stop?", {"ml": "ബസ് സ്റ്റോപ്പ് എവിടെയാണ്?", "hi": "बस स्टॉप कहाँ है?", "ta": "பேருந்து நிறுத்தம் எங்கே?"}),
    ("Where is the toilet?", {"ml": "ശുചിമുറി എവിടെയാണ്?", "hi": "शौचालय कहाँ है?", "ta": "கழிப்பறை எங்கே?"}),
    ("Where is the hospital?", {"ml": "ആശുപത്രി എവിടെയാണ്?", "hi": "अस्पताल कहाँ है?", "ta": "மருத்துவமனை எங்கே?"}),
    ("Help!", {"ml": "സഹായിക്കണേ!", "hi": "मदद कीजिए!", "ta": "உதவி!"}),
]
