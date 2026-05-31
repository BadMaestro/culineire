from django.urls import path

from . import views

app_name = "legal"

urlpatterns = [
    path("", views.LegalHubView.as_view(), name="legal_hub"),
    path("content-publishing-rules/", views.ContentPublishingRulesView.as_view(), name="content_publishing_rules"),
    path("author-submission-agreement/", views.AuthorSubmissionAgreementView.as_view(), name="author_submission_agreement"),
    path("copyright-image-rights-guide/", views.CopyrightImageRightsGuideView.as_view(), name="copyright_image_rights_guide"),
    path("terms/", views.TermsView.as_view(), name="terms"),
    path("cookies/", views.CookiePolicyView.as_view(), name="cookies"),
    path("company-information/", views.CompanyInformationView.as_view(), name="company_information"),
    path("report-content/", views.report_content, name="report_content"),
    path("reports/", views.reports_list, name="reports_list"),
    path("reports/<int:pk>/", views.report_detail, name="report_detail"),
]
