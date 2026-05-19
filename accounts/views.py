import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.text import slugify
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from django_ratelimit.decorators import ratelimit

from config.email_utils import send_template_mail
from config.turnstile import verify_turnstile
from recipes.models import RecipeAuthor

from .forms import SignInForm, SignUpForm

logger = logging.getLogger(__name__)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def is_moderator(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    author = getattr(user, "recipe_author_profile", None)
    return author is not None and (
        author.slug == settings.OWNER_SLUG
        or author.has_bearseeker_privileges
    )


def can_grant_bearseeker_privileges(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    author = getattr(user, "recipe_author_profile", None)
    return author is not None and author.slug == settings.OWNER_SLUG


def can_revoke_superuser_privileges(user):
    if not user or not user.is_authenticated:
        return False
    author = getattr(user, "recipe_author_profile", None)
    return author is not None and author.slug == settings.OWNER_SLUG


# ── Login ─────────────────────────────────────────────────────────────────────

class CulinEireLoginView(LoginView):
    authentication_form = SignInForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    @method_decorator(sensitive_post_parameters("password"))
    @method_decorator(ratelimit(key="ip", rate="20/10m", method="POST", block=False))
    @method_decorator(ratelimit(key="post:username", rate="20/10m", method="POST", block=False))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            user_model = get_user_model()
            username = request.POST.get("username", "")
            try:
                user = user_model.objects.get(username=username)
                if getattr(user, "is_superuser", False):
                    return super().post(request, *args, **kwargs)
            except user_model.DoesNotExist:
                pass
            messages.error(request, "Too many sign-in attempts. Please wait a few minutes and try again.")
            return redirect("login")
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        from monitoring.tracker import record_security_event
        record_security_event(self.request, "failed_login")
        return super().form_invalid(form)


# ── Sign Up ───────────────────────────────────────────────────────────────────

class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("home")

    @method_decorator(sensitive_post_parameters("password1", "password2"))
    @method_decorator(ratelimit(key="ip", rate="3/h", method="POST", block=False))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["turnstile_site_key"] = settings.TURNSTILE_SITE_KEY
        return ctx

    def post(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            messages.error(request, "Too many account creation attempts. Please try again later.")
            return redirect("signup")
        token = request.POST.get("cf-turnstile-response", "")
        if not verify_turnstile(token, request.META.get("REMOTE_ADDR", "")):
            messages.error(request, "Security check failed. Please try again.")
            return redirect("signup")
        return super().post(request, *args, **kwargs)

    @staticmethod
    def _unique_author_slug(base):
        slug = slugify(base) or "author"
        if not RecipeAuthor.objects.filter(slug=slug).exists():
            return slug
        counter = 2
        while RecipeAuthor.objects.filter(slug=f"{slug}-{counter}").exists():
            counter += 1
        return f"{slug}-{counter}"

    def form_valid(self, form):
        require_confirmation = getattr(settings, "SIGNUP_REQUIRE_EMAIL_CONFIRMATION", True)
        user = form.save(commit=False)
        user.is_active = not require_confirmation
        user.save()
        author_name = user.get_full_name() or user.username

        RecipeAuthor.objects.create(
            user=user,
            name=author_name,
            slug=self._unique_author_slug(author_name),
            default_avatar=form.cleaned_data["default_avatar"],
        )

        if not require_confirmation:
            user.backend = "django.contrib.auth.backends.ModelBackend"
            login(self.request, user)
            return render(self.request, "registration/signup_success.html", {"email": user.email})

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        activation_url = (
            f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}"
            f"/accounts/activate/{uid}/{token}/"
        )
        send_template_mail(
            subject="Confirm your CulinEire account",
            template="activation",
            context={"author_name": author_name, "activation_url": activation_url},
            recipient_list=[user.email],
            fail_silently=False,
        )
        return render(self.request, "registration/activation_pending.html", {"email": user.email})


# ── Activate account ──────────────────────────────────────────────────────────

@ratelimit(key="ip", rate="20/h", method="GET", block=True)
def activate_account(request, uidb64, token):
    user_model = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = user_model.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, user_model.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, user)
        messages.success(request, "Your email is confirmed. Welcome to CulinEire!")
        return redirect("home")

    return render(request, "registration/activation_invalid.html", status=400)


# ── Author privilege management ───────────────────────────────────────────────

def _send_moderator_granted_email(user, author_name):
    if not user.email:
        return
    moderation_url = (
        f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}/recipes/moderation/"
    )
    contact_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}/messages/contact/"
    try:
        send_template_mail(
            subject="Your CulinEire Kitchen moderator access",
            template="moderator_granted",
            context={
                "author_name": author_name,
                "moderation_url": moderation_url,
                "contact_url": contact_url,
            },
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Failed to send moderator_granted email to %s", user.email)


def _send_moderator_revoked_email(user, author_name):
    if not user.email:
        return
    contact_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}/messages/contact/"
    try:
        send_template_mail(
            subject="Your CulinEire Kitchen moderator access has been removed",
            template="moderator_revoked",
            context={
                "author_name": author_name,
                "contact_url": contact_url,
            },
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Failed to send moderator_revoked email to %s", user.email)


@require_POST
def manage_author(request, slug):
    if not is_moderator(request.user):
        raise Http404

    author = get_object_or_404(RecipeAuthor, slug=slug)
    user = author.user

    if not user:
        messages.error(request, "No linked user account found.")
        return redirect("recipes:moderation_panel")

    action = request.POST.get("action", "block")

    if action == "revoke_superuser":
        if not can_revoke_superuser_privileges(request.user):
            raise Http404
        if user.pk == request.user.pk or author.slug == settings.OWNER_SLUG or not user.is_superuser:
            raise Http404
        author.has_bearseeker_privileges = False
        author.save(update_fields=["has_bearseeker_privileges"])
        user.is_superuser = False
        user.is_staff = False
        user.is_active = True
        user.save(update_fields=["is_superuser", "is_staff", "is_active"])
        messages.warning(request, f'Superuser privileges revoked from "{author.name}".')

    elif author.slug == settings.OWNER_SLUG or user.is_superuser:
        raise Http404

    elif action == "grant_bearseeker":
        if not can_grant_bearseeker_privileges(request.user):
            raise Http404
        author.has_bearseeker_privileges = True
        author.save(update_fields=["has_bearseeker_privileges"])
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, f'Author "{author.name}" now has (Bear)seeker moderation privileges.')
        _send_moderator_granted_email(user, author.name or user.username)

    elif action == "revoke_bearseeker":
        if not can_grant_bearseeker_privileges(request.user):
            raise Http404
        author.has_bearseeker_privileges = False
        author.save(update_fields=["has_bearseeker_privileges"])
        messages.warning(request, f'(Bear)seeker privileges revoked from "{author.name}".')
        _send_moderator_revoked_email(user, author.name or user.username)

    elif action == "unblock":
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, f'User "{user.username}" has been unblocked.')

    else:  # default: block
        user.is_active = False
        user.save(update_fields=["is_active"])
        messages.warning(request, f'User "{user.username}" has been blocked.')

    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("recipes:author_detail", slug=slug)
