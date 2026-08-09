import sys, os, django
sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from chef_battle import views
u = get_user_model().objects.filter(is_superuser=True).order_by("id").first()
rf = RequestFactory()
r = rf.get("/chef-battle/arena/")
r.user = u
resp = views.arena(r)
if hasattr(resp, "render"): resp.render()
html = resp.content.decode()
open(os.environ["OUTPATH"], "w", encoding="utf-8").write(html)
print("status", resp.status_code, "bytes", len(html), "as", u.username)
