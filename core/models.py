from django.contrib.auth.models import User
from django.db import models

CLIMATES = [("hill", "Hill station"), ("beach", "Beach"), ("backwater", "Backwaters"),
            ("forest", "Forest / wildlife"), ("waterfall", "Waterfall"), ("plains", "Plains")]


def _split(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Destination(models.Model):
    name = models.CharField(max_length=100)
    district = models.CharField(max_length=80)
    state = models.CharField(max_length=60, default="Kerala")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="destinations")
    climate = models.CharField(max_length=20, choices=CLIMATES, default="plains")
    description = models.TextField()
    attractions = models.TextField(help_text="Comma separated list of attractions")
    tags = models.CharField(max_length=250, blank=True, help_text="Comma separated, e.g. nature,family,boating")
    best_months = models.CharField(max_length=60, default="10,11,12,1,2", help_text="Month numbers, comma separated")
    peak_months = models.CharField(max_length=60, blank=True, help_text="Crowded / expensive months")
    avg_daily_cost = models.PositiveIntegerField(default=2500, help_text="INR per person per day")
    rating = models.FloatField(default=4.2)
    safety_score = models.PositiveIntegerField(default=85, help_text="0-100")
    is_hidden_gem = models.BooleanField(default=False)
    eco_friendly = models.BooleanField(default=False)
    latitude = models.FloatField(default=10.0)
    longitude = models.FloatField(default=76.3)
    image = models.ImageField(upload_to="destinations/", blank=True, null=True, help_text="Upload destination photo")
    emoji = models.CharField(max_length=4, default="🌴", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def attraction_list(self):
        return _split(self.attractions)

    @property
    def tag_list(self):
        return _split(self.tags)

    @property
    def best_month_list(self):
        return [int(m) for m in _split(self.best_months) if m.isdigit()]

    @property
    def peak_month_list(self):
        return [int(m) for m in _split(self.peak_months) if m.isdigit()]


class Hotel(models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="hotels")
    name = models.CharField(max_length=120)
    price_per_night = models.PositiveIntegerField(help_text="INR per night")
    rating = models.FloatField(default=4.0, help_text="e.g. 4.2 (0 to 5)")
    eco_friendly = models.BooleanField(default=False)
    amenities = models.CharField(max_length=200, blank=True, help_text="Comma-separated features, e.g. Free Wi-Fi, Breakfast, Pool, AC, Parking")

    def __str__(self):
        return f"{self.name} ({self.destination})"


class Activity(models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="activities")
    name = models.CharField(max_length=120)
    cost = models.PositiveIntegerField(default=0, help_text="INR per person")
    duration_hours = models.FloatField(default=2)

    class Meta:
        verbose_name_plural = "activities"

    def __str__(self):
        return f"{self.name} ({self.destination})"


class Package(models.Model):
    title = models.CharField(max_length=140)
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="packages")
    days = models.PositiveIntegerField(default=3)
    price = models.PositiveIntegerField(help_text="INR per person")
    description = models.TextField(blank=True)
    includes = models.CharField(max_length=250, blank=True, help_text="Comma separated")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    @property
    def include_list(self):
        return _split(self.includes)


class Profile(models.Model):
    BUDGETS = [("low", "Budget"), ("mid", "Mid-range"), ("high", "Comfort")]
    STYLES = [("solo", "Solo"), ("couple", "Couple"), ("family", "Family"), ("friends", "Friends")]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=20, blank=True)
    preferred_categories = models.ManyToManyField(Category, blank=True)
    interests = models.CharField(max_length=200, blank=True, help_text="e.g. waterfalls, boating, trekking")
    budget_level = models.CharField(max_length=4, choices=BUDGETS, default="mid")
    travel_style = models.CharField(max_length=10, choices=STYLES, default="friends")
    passport_expiry = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

    @property
    def interest_list(self):
        return [i.lower() for i in _split(self.interests)]


class Booking(models.Model):
    STATUS = [("pending", "Pending"), ("confirmed", "Confirmed"), ("cancelled", "Cancelled")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    destination = models.ForeignKey(Destination, on_delete=models.PROTECT, related_name="bookings")
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True)
    hotel = models.ForeignKey(Hotel, on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    travellers = models.PositiveIntegerField(default=1)
    budget = models.PositiveIntegerField(default=0)
    total_cost = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    notes = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} → {self.destination} ({self.start_date})"

    @property
    def days(self):
        return max((self.end_date - self.start_date).days + 1, 1)


class Itinerary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="itineraries")
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE)
    days = models.PositiveIntegerField()
    travellers = models.PositiveIntegerField(default=1)
    budget = models.PositiveIntegerField(default=0)
    interests = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    source = models.CharField(max_length=20, default="gemini")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "itineraries"

    def __str__(self):
        return f"{self.days}-day plan for {self.destination}"


class Review(models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    rating = models.PositiveIntegerField(default=4)
    sentiment = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} on {self.destination}"
