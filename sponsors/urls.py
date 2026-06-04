from django.urls import path

from . import views

app_name = "sponsors"

urlpatterns = [
    path("", views.puzzle_page, name="puzzle"),
    path("annual-contract/", views.AnnualContractView.as_view(), name="annual_contract"),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("checkout/cancel/", views.checkout_cancel, name="checkout_cancel"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("cell/<int:cell_id>/", views.cell_detail, name="cell_detail"),
    path("cell/<int:cell_id>/enquire/", views.cell_enquire, name="cell_enquire"),
    path("cell/<int:cell_id>/moderate/", views.cell_moderate, name="cell_moderate"),
    path("moderation/applications/", views.moderation_applications, name="moderation_applications"),
    path("moderation/applications/<int:application_id>/", views.moderation_application_detail, name="moderation_application_detail"),
    path("moderation/cells/", views.moderation_cells, name="moderation_cells"),
    path("moderation/roadmap/", views.sponsor_roadmap, name="sponsor_roadmap"),
]
