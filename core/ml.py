"""Destination recommender (content-based filtering with K-Nearest Neighbours).

Pipeline: build a Pandas dataset from destinations -> text features (TF-IDF over
category, climate, tags, attractions) -> NearestNeighbors(cosine) -> save with joblib.
"""
import joblib
import pandas as pd
from django.conf import settings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from .models import Destination


def _soup(category, climate, tags, attractions):
    # category & climate are repeated so they weigh more than individual attractions
    return " ".join([category, category, climate, climate, tags.replace(",", " "),
                     attractions.replace(",", " ")]).lower()


def build_dataframe():
    rows = [{
        "id": d.id, "name": d.name, "category": d.category.name, "climate": d.climate,
        "cost": d.avg_daily_cost, "rating": d.rating, "hidden": d.is_hidden_gem,
        "soup": _soup(d.category.name, d.climate, d.tags, d.attractions),
    } for d in Destination.objects.select_related("category")]
    return pd.DataFrame(rows)


def train():
    """Train + save the model. Returns a small metrics dict."""
    df = build_dataframe()
    if len(df) < 3:
        raise ValueError("Add at least 3 destinations before training the model.")
    vec = TfidfVectorizer(stop_words="english")
    X = vec.fit_transform(df["soup"])
    knn = NearestNeighbors(metric="cosine", algorithm="brute").fit(X)

    # Evaluation: does a destination's nearest neighbour share its category?
    k = min(2, len(df) - 1)
    _, idx = knn.kneighbors(X, n_neighbors=k + 1)
    hits = sum(df.iloc[i]["category"] == df.iloc[nbrs[1]]["category"] for i, nbrs in enumerate(idx))
    metrics = {"destinations": len(df), "category_agreement": round(hits / len(df), 3)}

    settings.ML_MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump({"vec": vec, "knn": knn, "ids": df["id"].tolist(), "soups": df["soup"].tolist(),
                 "metrics": metrics}, settings.ML_MODEL_PATH)
    return metrics


def _load():
    try:
        bundle = joblib.load(settings.ML_MODEL_PATH)
        if len(bundle["ids"]) == Destination.objects.count():
            return bundle
    except Exception:
        pass
    try:
        train()
        return joblib.load(settings.ML_MODEL_PATH)
    except Exception:
        return None


def recommend(user, n=6, hidden_only=False):
    """Return [(destination, match_percent, reason)] personalised for the user."""
    bundle = _load()
    profile = getattr(user, "profile", None)
    booked = set(user.bookings.exclude(status="cancelled").values_list("destination_id", flat=True)) if getattr(user, "is_authenticated", False) else set()
    parts, reasons = [], []
    if profile:
        cats = [c.name.lower() for c in profile.preferred_categories.all()]
        if cats:
            parts += cats * 3
            reasons.append("your preferred categories")
        if profile.interest_list:
            parts += profile.interest_list * 2
            reasons.append("your interests")
    if booked and bundle:
        soups = dict(zip(bundle["ids"], bundle["soups"]))
        parts += [soups[i] for i in booked if i in soups]
        reasons.append("places you booked before")
    qs = Destination.objects.select_related("category")
    if hidden_only:
        qs = qs.filter(is_hidden_gem=True)
    by_id = {d.id: d for d in qs}
    results = []
    if parts and bundle and len(bundle.get("ids", [])) > 0:
        try:
            q = bundle["vec"].transform([" ".join(parts)])
            dist, idx = bundle["knn"].kneighbors(q, n_neighbors=len(bundle["ids"]))
            for d, i in zip(dist[0], idx[0]):
                dest = by_id.get(bundle["ids"][i])
                if dest and dest.id not in booked:
                    results.append((dest, round((1 - d) * 100), "Matches " + " and ".join(reasons)))
        except Exception:
            results = []
    if not results:  # cold start or fallback: top rated
        for dest in sorted(by_id.values(), key=lambda x: -x.rating):
            if dest.id not in booked:
                results.append((dest, None, "Popular with travellers - set preferences for better picks"))
    return results[:n]
