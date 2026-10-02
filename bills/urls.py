from django.urls import path
from . import views

urlpatterns = [
    path("", views.group_list, name="group_list"),
    path("signup/", views.signup, name="signup"),
    path("join/<str:code>/", views.join_group, name="join_group"),
    path("groups/<int:pk>/", views.group_detail, name="group_detail"),
    path("groups/<int:pk>/expenses/new/", views.add_expense, name="add_expense"),
    path("groups/<int:pk>/expenses/<int:expense_id>/delete/", views.delete_expense, name="delete_expense"),
    path("groups/<int:pk>/guests/add/", views.add_guest, name="add_guest"),
    path("groups/<int:pk>/settle/", views.settle, name="settle"),
]
