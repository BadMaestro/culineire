(() => {
    const form = document.querySelector("[data-booking-form]");
    if (!form) return;

    const priceData = document.getElementById("ledo-price-map");
    const prices = priceData ? JSON.parse(priceData.textContent) : {};
    const messages = JSON.parse(document.getElementById("ledo-messages").textContent);
    const route = form.querySelector("[name='route']");
    const returnTrip = form.querySelector("[name='return_trip']");
    const returnField = form.querySelector(".return-field");
    const returnAt = form.querySelector("[name='return_at']");
    const quote = form.querySelector("[data-quote]");
    const vat = form.querySelector("[data-vat]");

    const paint = () => {
        returnField.hidden = !returnTrip.checked;
        returnAt.required = returnTrip.checked;
        const selected = prices[route.value];
        if (!selected) {
            quote.textContent = messages["Velg en rute"];
            vat.textContent = "";
            return;
        }
        const amount = returnTrip.checked ? selected.return : selected.oneWay;
        quote.textContent = amount ? `${Number(amount).toLocaleString(document.documentElement.lang)} ${selected.currency}` : messages["Pris ikke tilgjengelig"];
        vat.textContent = amount && selected.vatIncluded ? messages["Mva. inkludert"] : "";
    };

    route.addEventListener("change", paint);
    returnTrip.addEventListener("change", paint);
    paint();
})();
