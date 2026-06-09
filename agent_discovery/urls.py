from django.urls import path

from . import views

app_name = "agent_discovery"

urlpatterns = [
    path("api-catalog", views.api_catalog, name="api_catalog"),
    path("mcp/server-card.json", views.mcp_server_card, name="mcp_server_card"),
    path("agent-skills/index.json", views.agent_skills_index, name="agent_skills_index"),
]
