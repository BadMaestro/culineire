"""LEDO-only catalog. Does not change the language of the host application."""
from django.utils.translation import get_language
from django.utils.functional import lazy

LANGUAGES = (("nb", "NO", "Norsk"), ("en", "EN", "English"), ("lt", "LT", "Lietuvių"), ("ru", "RU", "Русский"))

# Norwegian source | English | Lithuanian | Russian
ROWS = """Hopp til innhold|Skip to content|Pereiti prie turinio|Перейти к содержимому
LEDO Drive forside|LEDO Drive home|LEDO Drive pradžia|Главная LEDO Drive
Hovedmeny|Main navigation|Pagrindinis meniu|Главное меню
Slik fungerer det|How it works|Kaip tai veikia|Как это работает
Pris|Price|Kaina|Цена
FAQ|FAQ|DUK|Вопросы
Bestill tur|Book a ride|Užsakyti kelionę|Заказать поездку
LEDO Drive – forespør flyplasstransfer mellom Kongsberg og Gardermoen.|LEDO Drive – request an airport transfer between Kongsberg and Gardermoen.|LEDO Drive – užsisakykite pervežimą tarp Kongsbergo ir Gardermoeno oro uosto.|LEDO Drive — трансфер между Конгсбергом и аэропортом Гардермуэн.
Flyplasstransfer mellom Kongsberg og Gardermoen.|Airport transfers between Kongsberg and Gardermoen.|Pervežimai tarp Kongsbergo ir Gardermoeno oro uosto.|Трансфер между Конгсбергом и аэропортом Гардермуэн.
Kontaktinformasjon og organisasjonsnummer publiseres etter verifisering.|Contact details and company registration number will be published after verification.|Kontaktiniai duomenys ir įmonės kodas bus paskelbti juos patikrinus.|Контакты и регистрационный номер компании будут опубликованы после проверки.
Send forespørsel|Send request|Siųsti užklausą|Отправить заявку
Kongsberg · Oslo lufthavn|Kongsberg · Oslo Airport|Kongsbergas · Oslo oro uostas|Конгсберг · Аэропорт Осло
Flyplass<wbr>transfer|Airport transfer|Pervežimas į oro uostą|Трансфер в аэропорт
uten stress.|without the stress.|be rūpesčių.|без лишних забот.
Send en forespørsel om privat transport mellom Kongsberg og Gardermoen. Du ser prisen før du sender, og turen blir bekreftet av operatøren.|Request a private transfer between Kongsberg and Gardermoen. See the price before submitting; the operator confirms your ride.|Pateikite privataus pervežimo tarp Kongsbergo ir Gardermoeno užklausą. Kainą matysite prieš siųsdami, o kelionę patvirtins operatorius.|Оставьте заявку на индивидуальный трансфер между Конгсбергом и Гардермуэном. Цена видна до отправки, а поездку подтверждает оператор.
Se hvordan det virker|See how it works|Sužinoti daugiau|Как заказать
Dette er en forespørsel, ikke en automatisk bekreftet bestilling.|This is a request, not an automatically confirmed booking.|Tai užklausa, o ne automatiškai patvirtintas užsakymas.|Это заявка, а не автоматически подтверждённый заказ.
Direkte. Privat. Forutsigbart.|Direct. Private. Predictable.|Tiesiogiai. Privačiai. Aiškiai.|Напрямую. Индивидуально. Предсказуемо.
Viktige fordeler|Key benefits|Pagrindiniai privalumai|Преимущества
Direkte rute|Direct route|Tiesioginis maršrutas|Прямой маршрут
Fra dør til terminal|From your door to the terminal|Nuo durų iki terminalo|От двери до терминала
Pris på forhånd|Price upfront|Kaina iš anksto|Цена заранее
Ingen skjult beregning i skjemaet|Clear pricing in the form|Aiški kaina formoje|Прозрачный расчёт в форме
Personlig svar|Personal response|Asmeninis atsakymas|Личный ответ
Operatøren bekrefter tilgjengelighet|The operator confirms availability|Operatorius patvirtina užimtumą|Оператор проверяет доступность
En enkel reise|A simple journey|Paprasta kelionė|Всё просто
Tre steg.|Three steps.|Trys žingsniai.|Три шага.
Så er du på vei.|Then you are on your way.|Ir jūs jau kelyje.|И вы в пути.
Velg turen|Choose your journey|Pasirinkite kelionę|Выберите поездку
Velg retning, tidspunkt, passasjerer og eventuell retur.|Choose your direction, time, passengers and an optional return.|Pasirinkite kryptį, laiką, keleivių skaičių ir, jei reikia, kelionę atgal.|Укажите направление, время, пассажиров и при необходимости обратную поездку.
Se prisen|See the price|Peržiūrėkite kainą|Узнайте цену
Gjeldende pris og hva forespørselen gjelder vises før innsending.|Review the current price and journey details before submitting.|Prieš siųsdami peržiūrėkite galiojančią kainą ir kelionės informaciją.|Перед отправкой проверьте актуальную цену и детали поездки.
Få bekreftelse|Get confirmation|Gaukite patvirtinimą|Получите подтверждение
Du får et referansenummer. Operatøren kontrollerer kapasitet og bekrefter turen.|You receive a reference number. The operator checks capacity and confirms your ride.|Gausite užklausos numerį. Operatorius patikrins galimybes ir patvirtins kelionę.|Вы получите номер заявки. Оператор проверит наличие автомобиля и подтвердит поездку.
Forutsigbar pris|Clear pricing|Aiški kaina|Понятная цена
Avklart før du bestiller.|Know before you book.|Žinokite prieš užsakydami.|Всё ясно до заказа.
Prisen lagres når forespørselen sendes. LEDO Drive bekrefter tilgjengelighet og vilkår før turen blir endelig bestilt.|The price is recorded when you submit your request. LEDO Drive confirms availability and terms before the booking is final.|Kaina išsaugoma siunčiant užklausą. Prieš galutinį užsakymo patvirtinimą LEDO Drive patvirtina galimybes ir sąlygas.|Цена сохраняется при отправке заявки. LEDO Drive подтверждает доступность и условия до окончательного оформления заказа.
Prislisten verifiseres|Rates are being verified|Kainos tikrinamos|Тарифы проверяются
Bestilling åpnes når gjeldende tariffer er godkjent.|Booking opens once current rates are approved.|Užsakymai bus priimami patvirtinus galiojančias kainas.|Бронирование откроется после утверждения тарифов.
Hvor skal vi hente deg?|Where shall we pick you up?|Kur jus paimti?|Где вас забрать?
Fyll ut det vi trenger for å vurdere turen. Ingen betaling skjer på denne siden.|Provide the details we need to review your journey. No payment is taken on this page.|Pateikite kelionei įvertinti reikalingą informaciją. Šiame puslapyje mokėjimai nepriimami.|Укажите данные для рассмотрения поездки. Оплата на этой странице не принимается.
Kun nødvendige opplysninger|Only essential details|Tik būtini duomenys|Только необходимые данные
Kontakt- og reisedata brukes for å behandle forespørselen.|Contact and journey details are used to process your request.|Kontaktiniai ir kelionės duomenys naudojami užklausai apdoroti.|Контактные данные и сведения о поездке используются для обработки заявки.
Reisen|Journey|Kelionė|Поездка
Kontakt|Contact|Kontaktai|Контакты
Pris for forespørselen|Request price|Užklausos kaina|Стоимость поездки
Velg en rute|Choose a route|Pasirinkite maršrutą|Выберите маршрут
Forhåndsvisning|Preview|Peržiūra|Предпросмотр
Bestillingen er ikke åpnet ennå.|Booking is not open yet.|Užsakymai dar nepriimami.|Бронирование пока закрыто.
Aktuelle priser og vilkår må godkjennes før skjemaet kan ta imot forespørsler.|Current rates and terms must be approved before the form can accept requests.|Prieš priimant užklausas turi būti patvirtintos galiojančios kainos ir sąlygos.|До открытия формы необходимо утвердить актуальные тарифы и условия.
Greit å vite|Good to know|Verta žinoti|Полезно знать
Ofte stilte spørsmål.|Frequently asked questions.|Dažniausiai užduodami klausimai.|Частые вопросы.
Er turen bekreftet når jeg sender skjemaet?|Is my ride confirmed when I submit the form?|Ar kelionė patvirtinama išsiuntus formą?|Подтверждается ли поездка после отправки формы?
Nei. Du sender en forespørsel. Turen er først avtalt når LEDO Drive har bekreftet tilgjengeligheten.|No. You submit a request. Your ride is agreed only after LEDO Drive confirms availability.|Ne. Jūs siunčiate užklausą. Kelionė sutarta tik tada, kai LEDO Drive patvirtina galimybes.|Нет. Вы отправляете заявку. Поездка считается согласованной только после подтверждения от LEDO Drive.
Når ser jeg prisen?|When can I see the price?|Kada matysiu kainą?|Когда я увижу цену?
Gjeldende pris vises i skjemaet før du sender forespørselen og lagres med referansen din.|The current price is shown before you submit and is saved with your reference.|Galiojanti kaina rodoma prieš siunčiant užklausą ir išsaugoma kartu su jos numeriu.|Актуальная цена отображается до отправки и сохраняется вместе с номером заявки.
Kan jeg bestille tur-retur?|Can I book a return journey?|Ar galiu užsakyti kelionę pirmyn ir atgal?|Можно заказать поездку туда и обратно?
Ja, når en godkjent tur-retur-pris finnes for valgt rute. Velg retur og oppgi tidspunktet.|Yes, when an approved return fare is available for your route. Select return and enter the time.|Taip, jei pasirinktam maršrutui patvirtinta kelionės pirmyn ir atgal kaina. Pažymėkite grįžimą ir nurodykite laiką.|Да, если для маршрута утверждён обратный тариф. Выберите обратную поездку и укажите время.
Betaler jeg på nettsiden?|Do I pay on the website?|Ar mokama svetainėje?|Нужно платить на сайте?
Nei. Denne forhåndsvisningen tar ikke imot betaling. Betalingsmåte publiseres først etter at den er avtalt.|No. This preview does not accept payments. Payment methods will be published once agreed.|Ne. Šioje peržiūros versijoje mokėjimai nepriimami. Mokėjimo būdai bus paskelbti juos suderinus.|Нет. В этой версии оплата не принимается. Способы оплаты будут опубликованы после согласования.
Veien til flyet|Your journey to the airport|Kelionė į oro uostą|Ваша поездка в аэропорт
starter her.|starts here.|prasideda čia.|начинается здесь.
Forespørsel mottatt|Request received|Užklausa gauta|Заявка получена
Takk. Vi har registrert turen.|Thank you. Your request is recorded.|Ačiū. Jūsų užklausa užregistruota.|Спасибо. Ваша заявка зарегистрирована.
Dette er ikke en endelig bestillingsbekreftelse. Operatøren kontrollerer tilgjengeligheten før turen bekreftes.|This is not a final booking confirmation. The operator checks availability before confirming the ride.|Tai nėra galutinis užsakymo patvirtinimas. Prieš patvirtindamas kelionę operatorius patikrina galimybes.|Это не окончательное подтверждение заказа. Оператор проверит доступность перед подтверждением поездки.
Referanse|Reference|Užklausos numeris|Номер заявки
Rute|Route|Maršrutas|Маршрут
Henting|Pickup|Paėmimas|Подача автомобиля
Status|Status|Būsena|Статус
Til forsiden|Back to home|Į pradžią|На главную
Velg retning|Choose direction|Pasirinkite kryptį|Выберите направление
Hentedato og tid|Pickup date and time|Paėmimo data ir laikas|Дата и время подачи
Tur-retur|Return journey|Pirmyn ir atgal|Туда и обратно
Returdato og tid|Return date and time|Grįžimo data ir laikas|Дата и время обратной поездки
Voksne|Adults|Suaugusieji|Взрослые
Barn|Children|Vaikai|Дети
Bagasje|Luggage|Bagažas|Багаж
Flynummer|Flight number|Skrydžio numeris|Номер рейса
Spesielle behov|Special requirements|Specialūs poreikiai|Особые пожелания
Navn|Name|Vardas|Имя
E-post|Email|El. paštas|Электронная почта
Telefon|Phone|Telefonas|Телефон
Jeg godtar at dette er en forespørsel som må bekreftes av LEDO Drive.|I understand this is a request that must be confirmed by LEDO Drive.|Suprantu, kad tai užklausa, kurią turi patvirtinti LEDO Drive.|Я понимаю, что это заявка, которую должна подтвердить LEDO Drive.
Oppgi gyldig dato og tid.|Enter a valid date and time.|Įveskite teisingą datą ir laiką.|Укажите корректные дату и время.
Tidspunktet finnes ikke entydig på grunn av overgang til eller fra sommertid.|This time is ambiguous or does not exist because of a daylight saving time change.|Šis laikas neegzistuoja arba yra dviprasmis dėl vasaros laiko keitimo.|Это время не существует или неоднозначно из-за перевода часов.
Velg et tidspunkt i fremtiden.|Choose a future date and time.|Pasirinkite laiką ateityje.|Выберите дату и время в будущем.
Forespørselen kunne ikke sendes.|The request could not be sent.|Nepavyko išsiųsti užklausos.|Не удалось отправить заявку.
Oppgi tidspunkt for returen.|Enter a return date and time.|Nurodykite grįžimo datą ir laiką.|Укажите дату и время обратной поездки.
Returen må være etter hentetidspunktet.|The return must be after pickup.|Grįžimas turi būti vėliau nei paėmimas.|Обратная поездка должна быть позже подачи автомобиля.
For mange forsøk. Vent litt før du prøver igjen.|Too many attempts. Please wait before trying again.|Per daug bandymų. Palaukite ir bandykite dar kartą.|Слишком много попыток. Подождите и попробуйте снова.
Pris for denne ruten er ikke tilgjengelig ennå.|A fare for this route is not available yet.|Šio maršruto kaina dar nepaskelbta.|Тариф для этого маршрута пока недоступен.
Tur-retur-pris for denne ruten er ikke tilgjengelig ennå.|A return fare for this route is not available yet.|Šio maršruto kelionės pirmyn ir atgal kaina dar nepaskelbta.|Обратный тариф для этого маршрута пока недоступен.
Pris ikke tilgjengelig|Price unavailable|Kaina nepasiekiama|Цена недоступна
Mva. inkludert|VAT included|PVM įskaičiuotas|НДС включён
Ny forespørsel|New request|Nauja užklausa|Новая заявка
Bekreftet|Confirmed|Patvirtinta|Подтверждена
Fullført|Completed|Įvykdyta|Завершена
Kansellert av kunden|Cancelled by customer|Atšaukta kliento|Отменена клиентом
Kansellert av operatøren|Cancelled by operator|Atšaukta operatoriaus|Отменена оператором
Ikke møtt|No-show|Neatvyko|Неявка
Standard|Standard|Standartinė|Стандарт
Språk|Language|Kalba|Язык"""

CATALOG = {}
for row in ROWS.splitlines():
    source, en, lt, ru = row.split('|')
    CATALOG[source] = {'nb': source, 'en': en, 'lt': lt, 'ru': ru}
CATALOG['Flyplass<wbr>transfer']['nb'] = 'Flyplasstransfer'

def translate(source):
    language = (get_language() or 'nb').split('-')[0]
    return CATALOG.get(str(source), {}).get(language, str(source))

translate_lazy = lazy(translate, str)
