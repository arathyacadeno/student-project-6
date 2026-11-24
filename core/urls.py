from django.contrib.auth import views as auth_views
from django.urls import path

from . import views as v

urlpatterns = [
    path("", v.home, name="home"),
    path("register/", v.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("after-login/", v.after_login, name="after_login"),

    path("destinations/", v.destination_list, name="destinations"),
    path("destinations/<int:pk>/", v.destination_detail, name="destination_detail"),
    path("packages/", v.package_list, name="packages"),

    path("dashboard/", v.dashboard, name="dashboard"),
    path("profile/", v.profile_view, name="profile"),
    path("recommendations/", v.recommendations, name="recommendations"),
    path("planner/", v.planner, name="planner"),
    path("itineraries/<int:pk>/", v.itinerary_detail, name="itinerary_detail"),
    path("book/", v.book, name="book"),
    path("bookings/", v.my_bookings, name="my_bookings"),
    path("bookings/<int:pk>/cancel/", v.cancel_booking, name="cancel_booking"),

    path("tools/", v.tools_index, name="tools"),
    path("tools/outfit/", v.tool_outfit, name="tool_outfit"),
    path("tools/nearby/", v.tool_nearby, name="tool_nearby"),
    path("tools/documents/", v.tool_documents, name="tool_documents"),
    path("tools/buddies/", v.tool_buddies, name="tool_buddies"),
    path("tools/safety/", v.tool_safety, name="tool_safety"),
    path("tools/hidden-places/", v.tool_hidden, name="tool_hidden"),
    path("tools/cost-optimizer/", v.tool_cost, name="tool_cost"),
    path("tools/best-time/", v.tool_best_time, name="tool_best_time"),
    path("tools/translator/", v.tool_translator, name="tool_translator"),
    path("tools/sustainable/", v.tool_eco, name="tool_eco"),
    path("tools/reviews/", v.tool_reviews, name="tool_reviews"),
    path("tools/multi-destination/", v.tool_multi, name="tool_multi"),

    # Admin dashboard (staff only)
    path("manage/", v.admin_dashboard, name="admin_dashboard"),
    path("manage/bookings/", v.admin_bookings, name="admin_bookings"),
    path("manage/customers/", v.admin_customers, name="admin_customers"),
    path("manage/reports/", v.admin_reports, name="admin_reports"),
    path("manage/train-model/", v.admin_train, name="admin_train"),
    path("manage/<str:key>/", v.admin_list, name="admin_list"),
    path("manage/<str:key>/add/", v.admin_edit, name="admin_add"),
    path("manage/<str:key>/<int:pk>/edit/", v.admin_edit, name="admin_edit"),
    path("manage/<str:key>/<int:pk>/delete/", v.admin_delete, name="admin_delete"),
]
