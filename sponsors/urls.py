from django.urls import path

from . import views

app_name = "sponsors"

urlpatterns = [
    path("", views.puzzle_page, name="puzzle"),
    path("annual-contract/", views.AnnualContractView.as_view(), name="annual_contract"),
    path("cell/<int:cell_id>/", views.cell_detail, name="cell_detail"),
    path("cell/<int:cell_id>/enquire/", views.cell_enquire, name="cell_enquire"),
    path("cell/<int:cell_id>/moderate/", views.cell_moderate, name="cell_moderate"),
]
