# TravelMate AI - AI-Powered Travel Planning System
Django + HTML/CSS project built from the TravelMate AI project document.

## Run it
```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data        # Kerala sample data, demo users, trains the ML model
python manage.py clear_demo_data  # Remove all demo data (bookings, users, destinations)
export GEMINI_API_KEY=your-key    # Windows: set GEMINI_API_KEY=your-key
python manage.py runserver
```
Open http://127.0.0.1:8000/

| Role | Login |
|------|-------|
| Admin | `admin` / `admin123` (change this!) |
| Traveller | `demo` / `demo12345` |

## What's included
**Admin dashboard** (`/manage/`, staff only): destinations, categories, packages, hotels, activities (add/edit/delete), booking management with status updates, customers, reports, model retraining.
**User dashboard**: register/login, travel preferences, search and explore destinations, book trips (dates, budget, travellers), booking history and cancel, AI trip planner, personalised recommendations.

**Module 3 - AI & ML**
- `core/ml.py` - content-based recommender: Pandas dataset -> TF-IDF features -> K-Nearest Neighbours (cosine) -> saved with joblib to `ml_models/`. Uses preferences + interests + past bookings. Retrain: `python manage.py train_model`.
- `core/ai.py` - Google Gemini REST API for itineraries, budget estimates and Q&A. Without `GEMINI_API_KEY` it falls back to a built-in offline planner so the app still works.

**Smart tools** (`/tools/`, from the feature slides in the PDF): outfit recommendation, nearby places (map), document reminder, travel buddy matching, safety info, hidden places, cost optimizer, best time to visit, local phrases (Malayalam/Hindi/Tamil), sustainable travel, review sentiment, multi-destination explorer (Alappuzha, Athirappilly, Palakkad, Wayanad, Idukki data).

## Use PostgreSQL
`pip install psycopg2-binary`, then set `DB_ENGINE=postgres` and `DB_NAME/DB_USER/DB_PASSWORD/DB_HOST`.

## Deploy (Render / VPS)
`pip install gunicorn`, set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `GEMINI_API_KEY`; run `python manage.py collectstatic` and `gunicorn travelmate.wsgi`.

## Notes
- The ML "Jupyter Notebook" step in the document: the same pipeline lives in `core/ml.py`; copy `build_dataframe()` / `train()` into a notebook to experiment (add Decision Tree etc.).
- Sentiment analysis is a simple word-list model; swap in scikit-learn or Gemini for better accuracy.
- Seed data (costs, safety scores, hotels) is sample data - replace it via the admin dashboard.
