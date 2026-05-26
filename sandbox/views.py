from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from recipes.forms import RecipeAuthoringForm


def _superuser_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise Http404
        return view_func(request, *args, **kwargs)
    return wrapper


def _gallery_step_rows():
    return [{"step": s, "image": None} for s in range(1, 4)]


@_superuser_required
def index(request):
    pages = [
        {"title": "Recipe Form", "url_name": "sandbox:recipe_form",
         "description": "Full recipe authoring form — test layout, validation, and behaviour."},
    ]
    return render(request, "sandbox/index.html", {"pages": pages})


@_superuser_required
def recipe_form(request):
    submitted = False
    if request.method == "POST":
        form = RecipeAuthoringForm(request.POST, request.FILES)
        form.is_valid()
        submitted = True
    else:
        form = RecipeAuthoringForm()

    context = {
        "form": form,
        "form_mode": "create",
        "gallery_step_rows": _gallery_step_rows(),
        "cancel_url": "/sandbox/",
        "can_save_draft": True,
        "can_approve": True,
        "will_return_to_review": False,
        "turnstile_site_key": None,
        "submitted": submitted,
    }
    return render(request, "sandbox/recipe_form.html", context)
