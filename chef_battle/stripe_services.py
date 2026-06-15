from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


class TokenStripeConfigurationError(RuntimeError):
    pass


class TokenPaymentVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckoutSessionInfo:
    session_id: str
    checkout_url: str


def _get(obj, key, default=None):
    try:
        return obj[key]
    except (KeyError, TypeError):
        return default


def validate_stripe_config(*, require_webhook_secret: bool = False) -> None:
    secret_key = str(getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    webhook_secret = str(getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "").strip()
    mode = str(getattr(settings, "STRIPE_PRICE_MODE", "test") or "test").strip().lower()

    if not secret_key:
        raise TokenStripeConfigurationError("STRIPE_SECRET_KEY is not configured.")
    if mode == "test" and secret_key.startswith("sk_live_"):
        raise TokenStripeConfigurationError("Live Stripe key cannot be used in test mode.")
    if mode == "live" and secret_key.startswith("sk_test_"):
        raise TokenStripeConfigurationError("Test Stripe key cannot be used in live mode.")
    if require_webhook_secret and not webhook_secret:
        raise TokenStripeConfigurationError("STRIPE_WEBHOOK_SECRET is not configured.")


def _stripe():
    try:
        import stripe  # type: ignore
    except ImportError:
        raise TokenStripeConfigurationError("The stripe package is not installed.")
    validate_stripe_config()
    stripe.api_key = str(getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    return stripe


def _site_base_url(request=None) -> str:
    if request is not None:
        return request.build_absolute_uri("/").rstrip("/")
    site_url = str(getattr(settings, "SITE_URL", "") or "").rstrip("/")
    return site_url or "https://culineire.ie"


def create_token_checkout_session(
    package, wallet, request=None,
    withdrawal_waived: bool = False,
    consent_text: str = "",
) -> CheckoutSessionInfo:
    from decimal import Decimal, ROUND_HALF_UP
    from django.utils import timezone
    from .models import TokenOrder

    stripe = _stripe()
    base_url = _site_base_url(request)

    price_cents = int(package.price_eur * 100)

    # VAT breakdown — Irish standard rate 23%
    vat_rate = Decimal("0.2300")
    amount_net_cents = int((Decimal(price_cents) / (1 + vat_rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    vat_amount_cents = price_cents - amount_net_cents

    order = TokenOrder.objects.create(
        wallet=wallet,
        package=package,
        tokens=package.tokens,
        amount_eur_cents=price_cents,
        amount_net_cents=amount_net_cents,
        vat_amount_cents=vat_amount_cents,
        vat_rate=vat_rate,
        right_of_withdrawal_waived=withdrawal_waived,
        withdrawal_consent_at=timezone.now() if withdrawal_waived else None,
        consent_text_snapshot=consent_text if withdrawal_waived else "",
    )

    metadata = {
        "token_order_id": str(order.pk),
        "wallet_id": str(wallet.pk),
        "package_id": str(package.pk),
        "tokens": str(package.tokens),
    }

    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=(
            f"{base_url}{reverse('chef_battle:token_checkout_success')}"
            f"?session_id={{CHECKOUT_SESSION_ID}}"
        ),
        cancel_url=f"{base_url}{reverse('chef_battle:token_checkout_cancel')}?order={order.pk}",
        customer_creation="always",
        metadata=metadata,
        payment_intent_data={"metadata": metadata},
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": price_cents,
                    "product_data": {
                        "name": f"CulinEire Arena Tokens — {package.name}",
                        "description": f"{package.tokens} tokens credited instantly to your arena wallet.",
                    },
                },
                "quantity": 1,
            }
        ],
    )

    session_id = _get(session, "id", "") or ""
    checkout_url = _get(session, "url", "") or ""

    order.stripe_checkout_session_id = session_id
    order.save(update_fields=["stripe_checkout_session_id", "updated_at"])

    return CheckoutSessionInfo(session_id=session_id, checkout_url=checkout_url)


def construct_stripe_event(payload: bytes, signature: str):
    stripe = _stripe()
    validate_stripe_config(require_webhook_secret=True)
    webhook_secret = str(getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "").strip()
    return stripe.Webhook.construct_event(payload, signature, webhook_secret)


def handle_stripe_event(event) -> dict[str, Any]:
    from .models import TokenOrder, ProcessedTokenStripeEvent

    event_id = _get(event, "id", "")
    event_type = _get(event, "type", "")
    if not event_id or not event_type:
        raise TokenPaymentVerificationError("Stripe event is missing id or type.")

    with transaction.atomic():
        _, created = ProcessedTokenStripeEvent.objects.get_or_create(
            event_id=event_id,
            defaults={"event_type": event_type},
        )
        if not created:
            return {"duplicate": True, "event_type": event_type}

        order = None
        if event_type == "checkout.session.completed":
            order = _handle_checkout_completed(_get(event, "data", {}).get("object", {}))
        elif event_type == "checkout.session.expired":
            order = _handle_checkout_expired(_get(event, "data", {}).get("object", {}))

        return {"duplicate": False, "event_type": event_type, "order_id": order.pk if order else None}


def _handle_checkout_completed(session) -> Any:
    from .models import TokenOrder, TokenWallet, TokenTransaction

    payment_status = (_get(session, "payment_status", "") or "").lower()
    if payment_status != "paid":
        return None

    metadata = _get(session, "metadata", {}) or {}
    order_id = metadata.get("token_order_id")
    if not order_id:
        logger.warning("Token webhook: no token_order_id in metadata for session %s", _get(session, "id"))
        return None

    try:
        order = TokenOrder.objects.select_for_update().select_related("wallet", "package").get(pk=order_id)
    except TokenOrder.DoesNotExist:
        logger.error("Token webhook: TokenOrder %s not found", order_id)
        return None

    if order.status == TokenOrder.Status.COMPLETED:
        return order

    if order.status != TokenOrder.Status.PENDING:
        logger.warning("Token webhook: order %s in unexpected state %s", order.pk, order.status)
        return order

    # Verify amount
    amount_total = _get(session, "amount_total")
    if amount_total is not None and int(amount_total) != order.amount_eur_cents:
        raise TokenPaymentVerificationError(
            f"Amount mismatch: expected {order.amount_eur_cents}, got {amount_total}"
        )

    wallet = TokenWallet.objects.select_for_update().get(pk=order.wallet_id)

    new_balance = wallet.balance + order.tokens
    wallet.balance = new_balance
    wallet.total_purchased = wallet.total_purchased + order.tokens
    wallet.save(update_fields=["balance", "total_purchased", "updated_at"])

    TokenTransaction.objects.create(
        wallet=wallet,
        tx_type=TokenTransaction.TxType.PURCHASE,
        amount=order.tokens,
        balance_after=new_balance,
        description=f"Purchased {order.package.name} ({order.tokens}T)",
    )

    order.status = TokenOrder.Status.COMPLETED
    order.stripe_payment_intent_id = _get(session, "payment_intent", "") or ""
    order.stripe_customer_id = _get(session, "customer", "") or ""
    order.currency = (_get(session, "currency", "") or "eur").lower()[:3]
    order.credited_at = timezone.now()
    order.save(update_fields=[
        "status", "stripe_payment_intent_id", "stripe_customer_id",
        "currency", "credited_at", "updated_at",
    ])

    logger.info("Token purchase completed: order %s, wallet %s, +%sT", order.pk, wallet.pk, order.tokens)
    return order


def _handle_checkout_expired(session) -> Any:
    from .models import TokenOrder

    metadata = _get(session, "metadata", {}) or {}
    order_id = metadata.get("token_order_id")
    if not order_id:
        return None

    try:
        order = TokenOrder.objects.select_for_update().get(pk=order_id)
    except TokenOrder.DoesNotExist:
        return None

    if order.status == TokenOrder.Status.PENDING:
        order.status = TokenOrder.Status.EXPIRED
        order.save(update_fields=["status", "updated_at"])

    return order
