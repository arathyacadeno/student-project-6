import json
import math
import os
import uuid
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import ai, ml, tools_logic as tl
from .forms import BookingForm, PlannerForm, ProfileForm, RegisterForm, ReviewForm
from .models import Activity, Booking, Category, CLIMATES, Destination, Hotel, Itinerary, Package, Profile, Review

staff_required = user_passes_test(lambda u: u.is_authenticated and u.is_staff, login_url="login")


def get_profile(user):
    return Profile.objects.get_or_create(user=user)[0]


# ------------------------------------------------------------------ public
def home(request):
    featured = Destination.objects.select_related("category").order_by("-rating")[:4]
    all_dests = Destination.objects.select_related("category").order_by("name")
    q = request.GET.get("q", "").strip()
    cat_id = request.GET.get("cat", "").strip()
    selected_cat = int(cat_id) if cat_id.isdigit() else None
    if q:
        all_dests = all_dests.filter(Q(name__icontains=q) | Q(district__icontains=q) | Q(attractions__icontains=q))
    if selected_cat:
        all_dests = all_dests.filter(category_id=selected_cat)

    return render(request, "home.html", {
        "featured": featured,
        "all_destinations": all_dests,
        "categories": Category.objects.all(),
        "q": q,
        "selected_cat": selected_cat,
        "dest_count": Destination.objects.count(),
        "package_count": Package.objects.filter(is_active=True).count(),
    })


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        get_profile(user)
        login(request, user)
        messages.success(request, "Welcome to Beyond Destination AI! Tell us what you like so we can recommend places.")
        return redirect("profile")
    return render(request, "registration/register.html", {"form": form})


@login_required
def after_login(request):
    return redirect("admin_dashboard" if request.user.is_staff else "dashboard")


def destination_list(request):
    qs = Destination.objects.select_related("category")
    q, cat = request.GET.get("q", "").strip(), request.GET.get("category", "")
    max_cost = request.GET.get("max_cost", "")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(district__icontains=q) | Q(attractions__icontains=q) | Q(tags__icontains=q))
    if cat.isdigit():
        qs = qs.filter(category_id=cat)
    if max_cost.isdigit():
        qs = qs.filter(avg_daily_cost__lte=int(max_cost))
    return render(request, "destinations.html", {"destinations": qs, "categories": Category.objects.all(),
                                                 "q": q, "cat": cat, "max_cost": max_cost})


def destination_detail(request, pk):
    dest = get_object_or_404(Destination.objects.select_related("category"), pk=pk)
    related = Destination.objects.filter(category=dest.category).exclude(pk=dest.pk).order_by("-rating")[:3]
    return render(request, "destination_detail.html", {
        "d": dest, "hotels": dest.hotels.all(), "packages": dest.packages.filter(is_active=True),
        "activities": dest.activities.all(), "reviews": dest.reviews.select_related("user")[:5],
        "related": related,
    })


def package_list(request):
    return render(request, "packages.html", {"packages": Package.objects.filter(is_active=True).select_related("destination")})


# ------------------------------------------------------------------ user
@login_required
def dashboard(request):
    profile = get_profile(request.user)
    bookings = request.user.bookings.select_related("destination")
    return render(request, "dashboard.html", {
        "profile": profile, "upcoming": bookings.exclude(status="cancelled").filter(end_date__gte=date.today()).order_by("start_date")[:3],
        "booking_count": bookings.count(), "itineraries": request.user.itineraries.select_related("destination")[:3],
        "recs": ml.recommend(request.user, 3)})


@login_required
def profile_view(request):
    profile = get_profile(request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Travel preferences saved.")
        return redirect("recommendations")
    return render(request, "profile.html", {"form": form})


@login_required
def recommendations(request):
    return render(request, "recommendations.html", {"recs": ml.recommend(request.user, 8), "profile": get_profile(request.user)})


@login_required
def planner(request):
    answer = None
    if request.method == "POST" and "question" in request.POST:
        q = request.POST["question"].strip()[:300]
        ans_text = ai.answer_question(q) if q else ""
        if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
            from django.http import JsonResponse
            return JsonResponse({"q": q, "a": ans_text})
        answer = {"q": q, "a": ans_text} if q else None
        form = PlannerForm(initial={"destination": request.GET.get("dest")})
    else:
        form = PlannerForm(request.POST or None, initial={"destination": request.GET.get("dest")})
        if request.method == "POST" and form.is_valid():
            c = form.cleaned_data
            text, source = ai.generate_itinerary(c["destination"], c["days"], c["travellers"], c["budget"],
                                                 c["interests"], c.get("start_date"))
            it = Itinerary.objects.create(user=request.user, destination=c["destination"], days=c["days"],
                                          travellers=c["travellers"], budget=c["budget"], interests=c["interests"],
                                          content=text, source=source)
            return redirect("itinerary_detail", pk=it.pk)
    return render(request, "planner.html", {"form": form, "answer": answer,
                                            "history": request.user.itineraries.select_related("destination")[:5]})


@login_required
def itinerary_detail(request, pk):
    it = get_object_or_404(Itinerary, pk=pk, user=request.user)
    return render(request, "itinerary_detail.html", {"it": it})


def compute_total(b):
    n = b.travellers
    if b.package:
        total = b.package.price * n
    else:
        total = b.destination.avg_daily_cost * n * b.days
    if b.hotel:
        total += b.hotel.price_per_night * math.ceil(n / 2) * max(b.days - 1, 1)
    return total


@login_required
def book(request):
    initial = {}
    if request.GET.get("dest", "").isdigit():
        initial["destination"] = request.GET["dest"]
    if request.GET.get("package", "").isdigit():
        pkg = Package.objects.filter(pk=request.GET["package"]).first()
        if pkg:
            initial.update(package=pkg.pk, destination=pkg.destination_id)
            if pkg.days:
                initial.setdefault("start_date", date.today())
                initial.setdefault("end_date", initial["start_date"] + timedelta(days=pkg.days - 1))
    if "start_date" not in initial:
        initial["start_date"] = date.today()
    if "end_date" not in initial:
        initial["end_date"] = initial["start_date"] + timedelta(days=2)

    form = BookingForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        b = form.save(commit=False)
        b.user = request.user
        b.total_cost = compute_total(b)
        b.save()
        warn = " Note: the estimate is above your budget." if b.budget and b.total_cost > b.budget else ""
        messages.success(request, f"Booking requested. Estimated cost ₹{b.total_cost:,}.{warn}")
        return redirect("my_bookings")

    destinations_data = {
        str(d.pk): {
            "id": d.pk,
            "name": d.name,
            "district": d.district,
            "state": d.state or "Kerala",
            "avg_daily_cost": d.avg_daily_cost,
            "image_url": d.image.url if d.image else d.image_url,
        }
        for d in Destination.objects.all()
    }
    packages_data = {
        str(p.pk): {
            "id": p.pk,
            "title": p.title,
            "price": p.price,
            "days": p.days,
            "destination_id": str(p.destination_id),
            "includes": p.includes,
        }
        for p in Package.objects.all()
    }
    hotels_data = {
        str(h.pk): {
            "id": h.pk,
            "name": h.name,
            "price_per_night": h.price_per_night,
            "destination_id": str(h.destination_id),
            "eco_friendly": h.eco_friendly,
        }
        for h in Hotel.objects.all()
    }

    return render(request, "book.html", {
        "form": form,
        "destinations_json": json.dumps(destinations_data),
        "packages_json": json.dumps(packages_data),
        "hotels_json": json.dumps(hotels_data),
    })


@login_required
def my_bookings(request):
    return render(request, "my_bookings.html", {"bookings": request.user.bookings.select_related("destination", "package")})


@login_required
@require_POST
def cancel_booking(request, pk):
    b = get_object_or_404(Booking, pk=pk, user=request.user)
    if b.status != "cancelled":
        b.status = "cancelled"
        b.save()
        messages.info(request, "Booking cancelled.")
    return redirect("my_bookings")


# ------------------------------------------------------------------ smart tools
TOOLS = [
    ("tool_outfit", "👕", "AI Outfit Recommendation", "What to pack for the weather and activities."),
    ("tool_nearby", "📍", "Nearby Places Finder", "Restaurants, hospitals, ATMs and attractions on a map."),
    ("tool_documents", "🛂", "Travel Document Reminder", "Passport expiry check and a document checklist."),
    ("tool_buddies", "🤝", "Travel Buddy Matching", "Find travellers with similar interests and trips."),
    ("tool_safety", "🛡️", "Travel Safety Score", "Safety score, emergency numbers and tips."),
    ("tool_hidden", "🗺️", "Hidden Places", "Peaceful, lesser-known spots picked for you."),
    ("tool_cost", "💰", "Travel Cost Optimizer", "Compare budget, standard and comfort plans."),
    ("tool_best_time", "📅", "Best Time to Visit", "Month-by-month weather and crowd guide."),
    ("tool_translator", "🗣️", "Local Language Translator", "Handy phrases in Malayalam, Hindi and Tamil."),
    ("tool_eco", "🌿", "Sustainable Travel", "Eco-friendly stays and responsible tourism."),
    ("tool_reviews", "💬", "Review Sentiment Analysis", "What travellers like and dislike."),
    ("tool_multi", "🧭", "Multi-Destination Explorer", "Chain several places into one route and budget."),
]


def _pick_dest(request):
    pk = request.GET.get("dest", "")
    dests = Destination.objects.all()
    dest = dests.filter(pk=pk).first() if pk.isdigit() else None
    return dest or dests.first(), dests


@login_required
def tools_index(request):
    return render(request, "tools/index.html", {"tools": TOOLS})


@login_required
def tool_outfit(request):
    dest, dests = _pick_dest(request)
    month = int(request.GET["month"]) if request.GET.get("month", "").isdigit() and 1 <= int(request.GET["month"]) <= 12 else date.today().month
    data = tl.outfit_for(dest, month) if dest else None
    return render(request, "tools/outfit.html", {"dest": dest, "dests": dests, "month": month, "months": list(enumerate(tl.MONTHS, 1)), "data": data})


@login_required
def tool_nearby(request):
    dest, dests = _pick_dest(request)
    kinds = [("restaurants", "Restaurants"), ("hospitals", "Hospitals"), ("pharmacies", "Pharmacies"),
             ("tourist attractions", "Attractions"), ("ATMs", "ATMs")]
    kind = request.GET.get("kind", "restaurants")
    if kind not in dict(kinds):
        kind = "restaurants"
    return render(request, "tools/nearby.html", {"dest": dest, "dests": dests, "kinds": kinds, "kind": kind})


@login_required
def tool_documents(request):
    profile = get_profile(request.user)
    travel = request.GET.get("travel_date")
    try:
        travel_date = date.fromisoformat(travel) if travel else None
    except ValueError:
        travel_date = None
    upcoming = request.user.bookings.exclude(status="cancelled").filter(start_date__gte=date.today()).order_by("start_date").first()
    status = tl.passport_status(profile.passport_expiry, travel_date or (upcoming.start_date if upcoming else None))
    return render(request, "tools/documents.html", {"profile": profile, "status": status, "checklist": tl.DOC_CHECKLIST,
                                                    "upcoming": upcoming, "travel_date": travel or ""})


@login_required
def tool_buddies(request):
    me = get_profile(request.user)
    mine = set(me.interest_list) | {c.name.lower() for c in me.preferred_categories.all()}
    my_trips = list(request.user.bookings.exclude(status="cancelled"))
    matches = []
    for p in Profile.objects.exclude(user=request.user).select_related("user"):
        theirs = set(p.interest_list) | {c.name.lower() for c in p.preferred_categories.all()}
        union = mine | theirs
        score = len(mine & theirs) / len(union) if union else 0
        shared = []
        for t in p.user.bookings.exclude(status="cancelled").select_related("destination"):
            for m in my_trips:
                if t.destination_id == m.destination_id and t.start_date <= m.end_date and m.start_date <= t.end_date:
                    shared.append(t)
        pct = min(100, round(score * 70) + (30 if shared else 0))
        if pct:
            matches.append({"user": p.user, "profile": p, "pct": pct, "common": sorted(mine & theirs), "trip": shared[0] if shared else None})
    matches.sort(key=lambda m: -m["pct"])
    return render(request, "tools/buddies.html", {"matches": matches[:8], "me": me})


@login_required
def tool_safety(request):
    dest, dests = _pick_dest(request)
    tips = tl.SAFETY_TIPS.get(dest.climate, []) + ["Share your live location with someone you trust.", "Keep digital copies of your IDs."] if dest else []
    return render(request, "tools/safety.html", {"dest": dest, "dests": dests, "tips": tips, "emergency": tl.EMERGENCY})


@login_required
def tool_hidden(request):
    return render(request, "tools/hidden.html", {"recs": ml.recommend(request.user, 6, hidden_only=True) or
                                                 [(d, None, "A quiet, lesser-known place") for d in Destination.objects.filter(is_hidden_gem=True)]})


@login_required
def tool_cost(request):
    dest, dests = _pick_dest(request)
    def num(key, default):
        return int(request.GET[key]) if request.GET.get(key, "").isdigit() and int(request.GET[key]) > 0 else default
    days, travellers, budget = num("days", 3), num("travellers", 2), num("budget", 20000)
    options = tl.cost_options(dest, days, travellers) if dest else []
    for o in options:
        o["fits"] = o["total"] <= budget
        o["diff"] = abs(budget - o["total"])
    best = next((o for o in reversed(options) if o["fits"]), options[0] if options else None)
    return render(request, "tools/cost.html", {"dest": dest, "dests": dests, "days": days, "travellers": travellers,
                                               "budget": budget, "options": options, "best": best})


@login_required
def tool_best_time(request):
    dest, dests = _pick_dest(request)
    months, top = tl.best_time(dest) if dest else ([], [])
    return render(request, "tools/best_time.html", {"dest": dest, "dests": dests, "months": months, "top": top})


@login_required
def tool_translator(request):
    langs = [("ml", "Malayalam"), ("hi", "Hindi"), ("ta", "Tamil")]
    return render(request, "tools/translator.html", {"phrases": tl.PHRASES, "langs": langs})


@login_required
def tool_eco(request):
    return render(request, "tools/eco.html", {
        "hotels": Hotel.objects.filter(eco_friendly=True).select_related("destination"),
        "dests": Destination.objects.filter(eco_friendly=True)})


@login_required
def tool_reviews(request):
    dest, dests = _pick_dest(request)
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and dest and form.is_valid():
        r = form.save(commit=False)
        r.user, r.destination, r.sentiment = request.user, dest, tl.sentiment(form.cleaned_data["text"])
        r.save()
        messages.success(request, "Thanks - your review was added.")
        return redirect(f"{request.path}?dest={dest.pk}")
    reviews = list(dest.reviews.select_related("user")) if dest else []
    counts = {s: sum(r.sentiment == s for r in reviews) for s in ("Positive", "Neutral", "Negative")}
    total = len(reviews) or 1
    pos_kw, neg_kw = tl.keywords([r.text for r in reviews])
    return render(request, "tools/reviews.html", {"dest": dest, "dests": dests, "reviews": reviews, "form": form,
                                                  "counts": counts, "pct": {k: round(v * 100 / total) for k, v in counts.items()},
                                                  "pos_kw": pos_kw, "neg_kw": neg_kw})


@login_required
def tool_multi(request):
    ids = [int(i) for i in request.GET.getlist("d") if i.isdigit()]
    travellers = int(request.GET["travellers"]) if request.GET.get("travellers", "").isdigit() and int(request.GET["travellers"]) > 0 else 2
    chosen = list(Destination.objects.filter(pk__in=ids))
    chosen.sort(key=lambda d: ids.index(d.pk))
    plan = tl.plan_route(chosen, travellers) if chosen else None
    return render(request, "tools/multi.html", {"all": Destination.objects.all(), "ids": ids, "plan": plan, "travellers": travellers})


# ------------------------------------------------------------------ admin dashboard
CRUD = {
    "destinations": (Destination, "Destinations"), "packages": (Package, "Packages"), "hotels": (Hotel, "Hotels"),
    "activities": (Activity, "Activities"), "categories": (Category, "Categories"),
}


@staff_required
def admin_dashboard(request):
    ctx = {
        "stats": [("Destinations", Destination.objects.count()), ("Packages", Package.objects.count()),
                  ("Hotels", Hotel.objects.count()), ("Customers", User.objects.filter(is_staff=False).count()),
                  ("Bookings", Booking.objects.count()),
                  ("Pending", Booking.objects.filter(status="pending").count())],
        "recent": Booking.objects.select_related("user", "destination")[:6],
        "revenue": Booking.objects.filter(status="confirmed").aggregate(s=Sum("total_cost"))["s"] or 0,
    }
    return render(request, "manage/dashboard.html", ctx)


@staff_required
def admin_list(request, key):
    if key not in CRUD:
        return redirect("admin_dashboard")
    model, title = CRUD[key]
    return render(request, "manage/list.html", {"key": key, "title": title, "objects": model.objects.all()})


@staff_required
def admin_edit(request, key, pk=None):
    if key not in CRUD:
        return redirect("admin_dashboard")
    model, title = CRUD[key]
    obj = get_object_or_404(model, pk=pk) if pk else None
    fields = "__all__"
    if model == Destination:
        fields = [f.name for f in Destination._meta.fields if f.name not in ("id", "created_at", "emoji")]
    Form = modelform_factory(model, fields=fields)

    post_data = request.POST.copy() if request.method == "POST" else None
    if post_data is not None and model == Destination:
        if not post_data.get("attractions", "").strip():
            fallback = post_data.get("attractions_input", "").strip()
            if fallback:
                post_data["attractions"] = fallback

    # Shorten/sanitize overly long uploaded filenames to prevent Django max_length validation errors
    files = request.FILES.copy() if request.FILES else None
    if files and "image" in files:
        f = files["image"]
        if len(f.name) > 60:
            base, ext = os.path.splitext(f.name)
            f.name = f"{base[:35]}_{uuid.uuid4().hex[:6]}{ext.lower()[:6]}"

    form = Form(post_data or None, files or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{title[:-1] if title.endswith('s') else title} saved.")
        return redirect("admin_list", key=key)
    template = "manage/destination_form.html" if key == "destinations" else "manage/form.html"
    return render(request, template, {
        "form": form, "key": key, "title": title, "obj": obj,
        "categories": Category.objects.all(), "climates": CLIMATES,
    })


@staff_required
def admin_delete(request, key, pk):
    if key not in CRUD:
        return redirect("admin_dashboard")
    model, title = CRUD[key]
    obj = get_object_or_404(model, pk=pk)
    if request.method == "POST":
        try:
            obj.delete()
            messages.success(request, "Deleted.")
        except Exception:
            messages.error(request, "This item is used by other records (for example bookings) and cannot be deleted.")
        return redirect("admin_list", key=key)
    return render(request, "manage/confirm_delete.html", {"obj": obj, "key": key, "title": title})


@staff_required
def admin_bookings(request):
    if request.method == "POST":
        b = get_object_or_404(Booking, pk=request.POST.get("id"))
        action = request.POST.get("action")
        if action == "delete":
            b_id = b.pk
            b.delete()
            messages.success(request, f"Booking #{b_id} deleted.")
            return redirect("admin_bookings")
        status = request.POST.get("status")
        if status in dict(Booking.STATUS):
            b.status = status
            b.save()
            messages.success(request, f"Booking #{b.pk} marked {status}.")
        return redirect("admin_bookings")
    status = request.GET.get("status", "")
    qs = Booking.objects.select_related("user", "destination", "package")
    if status in dict(Booking.STATUS):
        qs = qs.filter(status=status)
    return render(request, "manage/bookings.html", {"bookings": qs, "status": status, "statuses": Booking.STATUS})


@staff_required
def admin_customers(request):
    if request.method == "POST":
        uid = request.POST.get("id")
        action = request.POST.get("action")
        if action == "delete" and uid:
            user = get_object_or_404(User, pk=uid, is_staff=False)
            uname = user.username
            user.delete()
            messages.success(request, f"Customer '{uname}' deleted.")
            return redirect("admin_customers")
    customers = User.objects.filter(is_staff=False).annotate(n=Count("bookings"), spent=Sum("bookings__total_cost")).order_by("-date_joined")
    return render(request, "manage/customers.html", {"customers": customers})


@staff_required
def admin_reports(request):
    by_dest = Destination.objects.annotate(n=Count("bookings")).filter(n__gt=0).order_by("-n")[:8]
    by_status = {s: Booking.objects.filter(status=s).count() for s, _ in Booking.STATUS}
    by_cat = Category.objects.annotate(n=Count("destinations__bookings")).filter(n__gt=0).order_by("-n")
    top = max([d.n for d in by_dest] + [1])
    return render(request, "manage/reports.html", {
        "by_dest": [(d, round(d.n * 100 / top)) for d in by_dest], "by_status": by_status, "by_cat": by_cat,
        "revenue": Booking.objects.exclude(status="cancelled").aggregate(s=Sum("total_cost"))["s"] or 0,
        "total": Booking.objects.count()})


@staff_required
@require_POST
def admin_train(request):
    try:
        m = ml.train()
        messages.success(request, f"Recommendation model retrained on {m['destinations']} destinations "
                                  f"(category agreement {m['category_agreement']:.0%}).")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("admin_dashboard")


def wishlist_view(request):
    destinations = Destination.objects.select_related("category").all()
    return render(request, "wishlist.html", {"destinations": destinations})
