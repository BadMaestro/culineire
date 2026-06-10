Ниже — рабочее ТЗ / roadmap / implementation blueprint для CHEF Battle / CHEF Combats под ваш текущий стек и с упором на максимально бесплатные технологии 2026 года.

Я специально делаю это не как абстрактную идею, а как исполняемое ТЗ по фазам, чтобы по нему можно было:

планировать разработку,
ставить задачи AI developer,
оценивать сроки и риски,
поэтапно прийти к тому интерфейсу и ощущению, которые у нас в мокапах.
1. Название проекта
Рекомендуемое публичное название

Chef’s Battle

Почему:

звучит понятно;
хорошо подходит для сайта CulinEire;
легко читается новой аудиторией;
подходит под UI, маркетинг, видео и SEO.
Внутреннее / кодовое название системы

CHEF Combats

Почему:

отражает механику, вдохновлённую old-school browser PvP;
удобно как внутренний термин для product/game logic.
Рекомендация
В интерфейсе и маркетинге: Chef’s Battle
В технической документации / внутренних обсуждениях: CHEF Combats Engine
2. Главная цель проекта

Создать для CulinEire не просто раздел с конкурсами рецептов, а живую кулинарную PvP-систему, которая будет:

удерживать авторов и шефов на сайте;
мотивировать публиковать больше рецептов и статей;
создавать rivalry, статус и публичную репутацию;
превращать контент в игровую экономику;
делать сайт “живым” через новости, события, crown-status и battle activity;
создавать основу для будущей монетизации, sponsorship и media-format expansion.
3. Стратегическая суть продукта
Что мы строим

Chef’s Battle — это culinary PvP / creator competition / social status engine поверх существующей платформы CulinEire.

Ключевая идея

Автор вызывает другого автора на кулинарную дуэль.
Есть:

тема,
таймер,
battle room,
скрытые submission,
публичное раскрытие,
голосование аудитории,
расчёт результата,
рейтинг,
титулы,
crown holder,
news / activity signal по всему сайту.
Почему это будет работать

Потому что система опирается сразу на 4 сильных слоя:

Контент — рецепты и статьи.
PvP — вызов, принятие, победа, поражение.
Социальный статус — ранги, титулы, crown, streaks.
Публичность — battle news, live events, feed, pop-up, profile history.
4. Основа механики (из Combats → в CulinEire)

Мы переносим не внешний вид старой игры, а её ядро:

Из old browser PvP берём:
вызов одного игрока другому;
accept / refuse / ignore;
публичность исхода;
важность репутации;
рейтинг и ранги;
карьерный рост;
социальное давление;
сезоны;
редкие предметы / artifacts;
ощущение “живого мира”.
В culinary-формат переводим так:
вместо оружия — recipe skill / creativity / execution;
вместо PvP-удара — battle action / move / tactical choice;
вместо кланов — kitchens / clans / houses;
вместо опыта за мобов — progression за рецепты, статьи, лайки и победы;
вместо fantasy combat — culinary duel system.
5. На каком оборудовании и стеке строим

Это важно, потому что ТЗ должно соответствовать вашей реальной инфраструктуре.

Текущий рабочий контур

Из известного контекста:

Backend: Django + Python 3.12
Database: PostgreSQL
Server: Ubuntu / Linux
App server: NGINX Unit
Version control: GitHub
Dev environment: Linux Mint VM + PyCharm на Windows host
Current architecture: Django monolith
Already existing modules: authors, recipes, articles, newsfeed, legal, sponsors, presence, messaging, collection и т.д.
Вывод

Не строим новый отдельный сервис.
Не уходим в microservices.
Не ломаем monolith.

Правильное направление:

Развивать Chef Battle как новый Django app, встроенный в текущий проект.

6. Максимально бесплатные технологии 2026 года

Ниже — рекомендуемый бесплатный стек.

Backend
Django — основной framework
PostgreSQL — база данных
Django ORM — модели и связи
Django Admin — модерация / управление
Django management commands — перерасчёты, сезоны, cleanups
Celery или Dramatiq — фоновые задачи
(если хочется проще — можно начать без них и добавить позже)
Redis или Valkey — кэш / очереди / live state
Django Channels или SSE — live notifications
(для MVP можно начать с polling, потом перейти к push/live)
Frontend
Django templates
HTMX — динамика без тяжёлого SPA
Alpine.js — лёгкая интерактивность
Vanilla JS — где проще без фреймворка
CSS existing system + точечное улучшение battle-UI
Chart.js — если нужны рейтинговые графики
Sortable / lightweight libs — только если реально нужно
Real-time / UX
SSE first или polling first
WebSocket — только где оправдано
Live popups, activity feed, timer refresh, vote states
Media / video / promo

Максимально бесплатный набор:

Remotion — для программной сборки promo-video из мокапа
FFmpeg — рендер / кодирование / композитинг
Blender — если нужен subtle parallax / depth
GIMP / Krita / Photopea — подготовка ассетов
DaVinci Resolve Free — финальный монтаж, если нужен
OBS Studio — демонстрационные capture-видео
Monitoring / QA
pytest / Django tests
Playwright — e2e / smoke UI
Lighthouse
Sentry free tier (если захотите)
server logs / nginx unit logs
7. Product principles — жёсткие правила
Обязательные принципы
MVP не должен быть перегружен.
Battle должен быть понятен даже новому пользователю.
Контент — топливо игры.
Сайт должен “звучать” событиями.
Статус должен быть видимым.
Публичность должна создавать напряжение.
Нельзя превращать систему в pay-to-win.
Все ключевые игровые очки должны зарабатываться реальной активностью.
Анти-абуз — не дополнение, а часть архитектуры.
Каждая фаза должна быть production-safe.
8. Что именно должен уметь продукт
8.1. Battle challenge flow
Пользовательский сценарий

Автор / chef нажимает Challenge Chef.

Он выбирает:

opponent;
battle theme;
optional message;
battle type;
optional start time;
wager / rating stake (необязательно в MVP).
Возможные статусы challenge
pending
accepted
refused
expired
cancelled
Правила
Нельзя спамить вызовами.
Нельзя бросать 50 вызовов подряд.
Нужен cooldown.
Нужны eligibility rules.
8.2. Accept / Refuse / Ignore
Если принято
создаётся battle room;
battle получает start/end time;
запускается timer;
оба участника получают instructions и CTA.
Если отказ
отказ фиксируется публично;
challenger может получить минимальный prestige;
opponent теряет немного reputation;
в профиле увеличивается счётчик refused battles.
Если проигнорировано
challenge expires;
возможно трактуется мягче, чем direct refusal;
это решение можно задать параметром.
8.3. Battle room

Публичная battle-страница показывает:

title / theme;
challenger;
opponent;
battle status;
timer;
battle log;
submissions state;
reveal state;
voting panel;
final result;
comments / live chat layer;
support indicators;
stats;
site-wide relevance.
8.4. Submission system

Каждый chef должен подать:

recipe или
article или
special battle entry format (на будущее).
Минимум для MVP

Лучше начать с:

recipe submission,
optional article support later.
Submission fields
related recipe/article;
hero image;
optional short battle statement;
submitted_at;
visibility state;
late status;
moderation flags.
Правило

До дедлайна submissions скрыты.
После дедлайна — раскрываются одновременно.

8.5. Voting
MVP voting

Простой vote:

vote for Chef A
vote for Chef B
Later version

Можно добавить criteria:

presentation
creativity
authenticity
technical execution

Но не в первом MVP.

Anti-abuse voting rules
one authenticated vote per user;
optional protected anonymous voting later;
no self-voting;
rate limiting;
IP / device / session controls;
suspicious activity flags;
anomaly detection.
8.6. Result calculation

После окончания битвы:

winner determined;
loser determined;
result reason stored;
wins/losses updated;
ratings recalculated;
streaks updated;
crown transferred if applicable;
site-wide event generated;
chef profiles updated.
8.7. “Battle should sound across the site”

Это ключевой продуктовый принцип.

Когда происходит что-то важное, событие должно появляться в:

homepage battle news;
activity feed;
chef profile activity;
battle history;
battle room log;
live notification popup;
optional messaging/inbox;
optional email digest later.
Важные event types
challenge_created
challenge_accepted
challenge_refused
battle_started
battle_submission_received
battle_revealed
battle_finished
chef_defeated_other_chef
new_crown_holder
rank_promoted
streak_achieved
9. Ranking system

Нужно разделить два слоя прогрессии.

9.1. Battle Rating

Чистый PvP-показатель.

Влияет:

wins/losses
opponent strength
streak
refusal penalties
battle difficulty modifier (later)
9.2. Culinary Reputation

Общий статус автора на платформе.

Влияет:

published recipes
published articles
likes
engagement
battle participation
quality
consistency
season performance
Почему это важно

Чтобы не получилось:

один человек просто спамит битвами;
или наоборот, автор публикует сильный контент, но никак не отражается в статусе.
10. Rank ladder

Предлагаемая линейка:

Kitchen Porter
Prep Cook
Commis Chef
Chef de Partie
Sous Chef
Head Chef
Executive Chef
Culinary Master
Возможный future layer
Grandmaster Chef
Legendary Chef
Hall of Flame / Hall of Fame
11. Crown system

Очень сильная механика.

Концепция

Победитель важной битвы или топ-chef сезона получает:

Crown Holder
Reigning Chef
special profile treatment
visual badge
highlighted listing
time-limited prestige
MVP вариант
crown на 24 часа;
crown marker на профиле;
crown marker в feed / battle news.
12. Battle economy

Контент должен быть топливом PvP.

Chef earns battle energy / moves by:
approved recipe published;
approved article published;
likes received;
battle participation;
battle win;
special seasonal events.
Chef spends moves on:
attack;
defence;
special actions;
boosted action strength.
Важно

Эта система не нужна в самом первом релизе.
Её вводим фазой позже.

13. Combat layer (future)

Это будущее развитие поверх базового battle voting.

Возможные механики
attack
block
partial defence
full defence
missed hit
move investment
tactical power
artifacts
Пример логики
Chef A invests 3 moves into attack
Chef B invests 2 moves into defence
system calculates:
full hit
partial hit
blocked hit
Победа определяется:
по 3 успешным попаданиям / missed hits
по раундам
по таймеру
по audience vote if unresolved
14. Artifacts
Основной принцип

Artifacts нельзя просто покупать напрямую.

Они зарабатываются через:

battles
seasons
achievements
milestones
tournaments
Примеры
Golden Knife
Iron Pan
Master’s Apron
Ancient Recipe Scroll
Butcher’s Cleaver
Fireproof Shield
Эффекты artifacts
cosmetic prestige
battle modifiers
profile flair
event-based bonuses
visual uniqueness
15. Cosmetics & monetisation

Это важно, но после MVP.

Разрешённая монетизация
Premium profile frames
Crowns / banners / animated badges
Featured chef promotion
Sponsored battles
Sponsored tournaments
Creator subscriptions
Premium analytics
Optional extra battle energy with strict limits
Что запрещено
жёсткое pay-to-win;
покупка ultimate power;
прямая продажа сильнейших artifacts;
возможность за деньги полностью убивать organic competition.
16. Anti-abuse system

Это критично.

Нужно защититься от:
battle farming;
repeated weak-target abuse;
vote brigading;
fake accounts;
self-voting;
fake likes;
artificial energy farming;
spam content;
repeated challenge harassment.
Обязательные защиты
cooldown between same pair;
daily/weekly battle limits;
diminishing returns vs repeated opponent;
only approved content grants moves;
moderation flags;
anomaly detection on votes;
admin review tools;
suspicious vote logs;
rate limits;
IP/device/session checks;
anti-bot measures.
17. Data model (Django)

Ниже — рекомендуемая базовая модельная структура.

17.1. ChefBattleProfile

Профиль battle-уровня.

Поля:

user
public_title
battle_rank
battle_rating
culinary_reputation
wins
losses
refused_battles
ignored_battles
win_streak
best_win_streak
crown_until
crown_count
battle_moves
seasonal_score
featured_badge_state
current_clan / kitchen (later)
created_at
updated_at
17.2. BattleChallenge

Поля:

challenger
opponent
theme
message
battle_type
proposed_start_time
status
expires_at
accepted_at
refused_at
cancelled_at
created_at
updated_at
17.3. Battle

Поля:

challenge
challenger
opponent
theme
battle_type
status
start_time
submission_deadline
reveal_time
end_time
winner
loser
result_reason
rating_delta_challenger
rating_delta_opponent
crown_awarded
season
created_at
updated_at
17.4. BattleEntry

Поля:

battle
author
recipe
article
cover_image
battle_statement
submitted_at
is_revealed
is_late
moderation_status
score_snapshot (later)
created_at
updated_at
17.5. BattleVote

Поля:

battle
voter_user
voted_for
ip_hash
user_agent_hash
session_key_hash
created_at
is_suspicious
moderation_note
17.6. BattleEvent

Поля:

battle
event_type
actor
target
message
payload_json
is_public
created_at
17.7. BattleMoveTransaction

Поля:

chef_profile
amount
direction (earn/spend)
reason
source_content_type
source_object_id
balance_after
created_at
17.8. Artifact

Поля:

name
slug
description
rarity
effect_type
effect_value
image
is_active
created_at
17.9. ChefArtifact

Поля:

chef_profile
artifact
earned_at
equipped
source_reason
17.10. CosmeticItem

Поля:

name
slug
type
price
rarity
image
is_active
17.11. ChefCosmetic

Поля:

chef_profile
item
purchased_at
equipped
17.12. Season

Поля:

name
starts_at
ends_at
status
crown_rule
reward_rules_json
17.13. SeasonStanding

Поля:

season
chef_profile
score
rank_position
wins
losses
streak
updated_at
18. URL / pages map
Базовые страницы
/battle/
/battle/challenges/
/battle/challenge/new/
/battle/challenge/<id>/
/battle/<battle_id>/
/battle/leaderboard/
/battle/history/
/battle/season/<slug>/
/chef/<slug>/battle/
/battle/crown-holder/
Admin / moderation
/admin/...
/battle/moderation/
/battle/votes/review/
/battle/events/
19. UX / UI requirements
Главная UI-цель

Battle должен ощущаться:

premium,
modern,
readable,
tense,
alive,
but not cluttered.
Визуальный характер
dark premium culinary UI;
Irish green accents for left/hero side;
red or amber competitive accents for opponent side;
strong typography;
esports-style energy;
no cartoon;
no fantasy nonsense;
no overloaded neon chaos;
readable text first.
Обязательные battle UI components
hero battle title
chef vs chef layout
rank / clan / country
timer
live status
battle theme
submission area
audience support / votes
activity/chat block
badges / crown markers
result banner
history / stats
20. Поэтапный план реализации
PHASE 0 — Architecture & foundation
Цель

Подготовить систему, чтобы дальше не переделывать всё заново.

Что делаем
Финализируем название:
public: Chef’s Battle
internal: CHEF Combats
Создаём новый Django app:
chef_battle
Проектируем модели
Определяем permissions
Проектируем event model
Проектируем ranking rules v1
Определяем UI map
Пишем technical design doc
Готовим migrations
Определяем battle eligibility rules
Результат
согласованная архитектура;
схема моделей;
battle terminology;
roadmap;
zero ambiguity.
Success criteria
все сущности описаны;
нет противоречий;
есть ясный MVP scope.
PHASE 1 — MVP core battle system
Цель

Сделать работающую первую версию, которая уже создаёт retention.

Scope
Chef battle profile
Challenge creation
Accept / refuse / expire
Battle room
Submission flow
24h timer
Hidden until reveal
Public voting
Winner calculation
Win/loss/refusal stats
Rating points
Crown holder for 24h
Homepage battle news
Backend
модели;
service layer;
validation;
battle lifecycle handlers;
rating calc v1;
scheduled expiry / reveal / finish jobs.
Frontend
battle listing page;
challenge form;
challenge response page;
battle room page;
leaderboard;
profile battle stats block.
Admin
review battles;
review votes;
review refusals;
force resolve if needed.
Testing
model tests;
flow tests;
permissions;
vote safety;
timer rules;
challenge lifecycle.
Phase 1 result

Уже можно:

вызывать;
принимать;
публиковать;
голосовать;
побеждать;
видеть рейтинг и crown.
Success metrics
≥ 1 completed battle end-to-end;
no broken lifecycle states;
no duplicate votes;
correct stat updates;
visible homepage battle event.
PHASE 2 — Social layer & site-wide visibility
Цель

Сделать battle “слышимым” по всему сайту.

Scope
Activity feed integration
Battle history
Profile battle activity
Live pop-up notifications
Better event cards
Crown announcements
Rank promotion announcements
In-site notification inbox integration
Tech recommendation
Start with polling or SSE
Use HTMX updates for feed / notifications
Avoid overengineering WebSocket on day one
Result

Battle перестаёт жить только на одной странице.
Он становится публичным событием сайта.

Success metrics
user sees battle events outside battle page;
homepage reflects live world state;
return value increases.
PHASE 3 — Progression & energy economy
Цель

Превратить публикацию контента в топливо PvP.

Scope
Battle moves / energy
Move earning rules
Move transaction ledger
Battle action costs
Simple “boost” mechanics
Contribution-to-power logic
Example rules
approved recipe = +X moves
approved article = +Y moves
like milestone = +small bonus
battle participation = +bonus
battle win = +bonus
Important
daily caps;
weekly caps;
anti-farming;
only approved content counts.
Result

Inactive chef = weak chef
Active chef = dangerous chef

PHASE 4 — Basic combat mechanics
Цель

Добавить настоящую old-school PvP-логику поверх battle system.

Scope
Attack / defence actions
Move investment
Partial / full block
Missed hits
Tactical logs
Battle rounds
Combat result engine
UX
readable round log
visual but clean action indicators
no heavy animation required
Result

Battle превращается из voting-only system в real tactical culinary duel.

PHASE 5 — Artifacts, cosmetics, prestige
Цель

Добавить долгосрочную мотивацию и monetisation-friendly layer.

Scope
Artifacts
Artifact inventory
Equip system
Premium cosmetics
Frames, crowns, banners
Featured chef options
Prestige visuals
Rule

Artifacts earn-only.
Cosmetics can be premium.

PHASE 6 — Seasons, tournaments, clan/kitchen system
Цель

Сделать long-term game loop.

Scope
Seasons
Seasonal standings
Rewards
Hall of Fame
Tournaments
Kitchens / clans
Regional leagues
Team identity layer
Result

Это уже не просто feature.
Это мета-игра и социальная экосистема.

PHASE 7 — Sponsorship, media engine, growth loops
Цель

Коммерциализировать и масштабировать.

Scope
Sponsored battles
Brand-themed events
Weekly battle recap
Social snippet generation
Media cards
Newsletter integration
Video highlight automation
Examples
Irish Butter Challenge
Farmhouse Breakfast Cup
Lamb Masters Week
Artisan Bread Duel
21. Что НЕ делаем в начале

Чтобы не утонуть, не делаем в первом релизе:

сложный real-time WebSocket arena engine;
многоуровневую боёвку с 20 типами урона;
сложные классы chefs;
marketplace;
direct paid artifacts;
excessive animations;
clan wars;
advanced tournaments;
multi-mode spectator overlays;
AI judging as core scoring layer.
22. Технический принцип реализации
Архитектурный подход

Monolith-first, service-layer inside Django.

Почему
соответствует текущему проекту;
быстрее внедряется;
дешевле поддерживается;
меньше рисков;
проще тестировать;
проще деплоить.
Рекомендуемая структура app
models.py
services/
challenge_service.py
battle_service.py
rating_service.py
event_service.py
vote_service.py
energy_service.py
selectors/
tasks/
admin.py
views/
templates/chef_battle/...
tests/
23. Тестовая стратегия
Обязательные виды тестов
Unit tests
rating calc
refusal rules
crown transfer
move calculations
Model tests
statuses
constraints
unique vote rules
lifecycle safety
Integration tests
full challenge flow
submission flow
reveal flow
battle finish flow
Permission tests
who can challenge
who can vote
who can edit
who can view hidden content
Anti-abuse tests
duplicate voting
self-voting
repeated farm pair
suspicious limits
UI / E2E
Playwright smoke flows
timer presence
public battle page
leaderboard update
24. Метрики успеха

Нужны продуктовые KPI.

Авторские
% authors who issue at least 1 challenge
% accepted battles
avg battles per active chef
content output uplift after Chef Battle launch
battle completion rate
Контентные
recipe publication increase
article publication increase
time between publications
% authors returning weekly
Engagement
votes per battle
views per battle
comments per battle
support clicks
battle page dwell time
Retention
D7 / D30 for authors participating in battle
repeat challenger rate
repeat opponent rate
seasonal return rate
Abuse / safety
suspicious vote rate
refusal abuse rate
farm detection rate
moderation interventions per 100 battles
25. Promo / video workstream

Ты отдельно уточнил задачу по промо-видео по мокапу.
Это можно выделить как parallel marketing workstream, чтобы подготовить анонс.

25.1. Цель видео

Создать premium cinematic 16:9 promo video на 8–10 секунд, основанное на загруженном мокапе Chef’s Battle.

25.2. Важное правило

Видео не должно редизайнить интерфейс.
Оно должно оживить уже существующий mockup.

25.3. Что нужно сохранить
layout
typography
battle title
VS symbol
timer
chef cards
names
live chat area
badges
buttons
visible UI text
CulinEire brand
25.4. Что должно анимироваться
slow cinematic push-in
subtle parallax
soft glow on green/red accents
LIVE badge pulse
timer glow
viewer count flicker
tiny icon activity
light chat motion
badge shimmer
gentle kitchen movement inside video windows:
steam
fire flicker
small chef motion
warm light movement
25.5. Атмосфера
premium dark culinary esports feel
serious
elegant
modern
competitive
realistic
25.6. Что запрещено
random text
text distortion
fake logos
redesign
cartoon style
fantasy style
messy layout
extra characters
new brand names
26. Бесплатный pipeline для promo video
Рекомендуемый production path
Option A — best free engineering path
prepare UI layers from source mockup
animate in Remotion
use FFmpeg for final encode
optionally use Blender for subtle depth/parallax
final polish in DaVinci Resolve Free
Option B — lighter path
animate in After Effects alternative not required
use CapCut free / DaVinci free
but Remotion is better if you want reproducible motion spec
Recommendation

Если цель — контролируемое премиальное promo video, то:

Remotion + FFmpeg + optional Blender
это лучший “почти бесплатный” и воспроизводимый стек.
27. Готовое ТЗ для promo video production

Ниже — уже в нормальной форме.

VIDEO PRODUCTION BRIEF — CHEF’S BATTLE PROMO

Project: CulinEire — Chef’s Battle feature promo
Format: short feature announcement video
Aspect ratio: 16:9
Duration: 8–10 seconds
Style: realistic cinematic website promo, premium, sharp, polished, modern

Source material

Use the uploaded CulinEire Chef’s Battle website mockup as the exact visual reference.

Core instruction

Animate the uploaded Chef’s Battle mockup into a premium cinematic promo video while preserving the exact page composition and visible interface structure as closely as possible.

Preserve
CulinEire brand name
headline “CHEF’S BATTLE”
VS symbol
chef identities
names
timer
live chat
badges
buttons
UI labels
layout hierarchy
Camera motion
slow cinematic push-in toward the centre
subtle parallax depth
smooth premium motion
no fast movement
no aggressive zooms
UI animation
soft green/red accent glow
pulsing LIVE badges
small viewer count flicker
gentle icon micro-motion
timer glow
soft appearing chat messages
subtle badge shimmer
Chef window motion

Each chef video panel should feel like a real live stream:

gentle steam
slight pan heat
warm light flicker
subtle hand/cooking movement
small flame movement
Visual tone
premium dark culinary platform
left side with Irish green accents
right side with competitive red accents
modern professional food website
clean esports-style duel energy
Restrictions
no fake text
no random brand changes
no fake logos
no redesign
no cartoon
no fantasy
no messy UI
no extra characters
Final output

A polished short premium announcement video that feels like a live, high-end feature reveal for the CulinEire Chef’s Battle platform.

28. Финальная практическая рекомендация

Если говорить по-взрослому и без воды, то правильный путь такой:

Сначала делаем:
MVP ядро
challenge
accept/refuse
battle room
hidden submissions
24h timer
public voting
winner
rating
crown
homepage battle news
Потом усиливаем:
live notifications
battle history
profile stats
feed integration
Потом включаем “game engine”:
earned moves
attack/block logic
artifacts
seasons
29. Самое важное управленческое решение

Если хотите довести идею до реально работающего продукта, то нельзя строить всё сразу.

Правильная логика

Phase 1 = social culinary duel
а не full fantasy combat simulator.

Потому что именно social layer уже даст:

return visits,
public drama,
more content,
status,
competition,
identity.

А уже потом можно надстраивать глубокую PvP-механику.

30. Короткий executive summary

Chef’s Battle / CHEF Combats — это retention engine для CulinEire, превращающий публикацию рецептов и статей в живую соревновательную систему с вызовами, рейтингами, crown-status, публичными победами, site-wide event visibility, progression, future battle economy and social prestige.

Рекомендуемый путь реализации:
Django monolith → MVP battle core → social visibility → energy economy → combat mechanics → artifacts/cosmetics → seasons/clans/sponsorship.