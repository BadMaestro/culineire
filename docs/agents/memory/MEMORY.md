# Memory Index — ПОЛНЫЙ КОНТЕКСТ СИНХРОНИЗИРОВАН

## 🔴 ЧИТАТЬ ПЕРВЫМ ПОСЛЕ КАЖДОГО ЛИМИТА И КАЖДОГО СЖАТИЯ

- [⚡ ЗОЛОТЫЕ ПРАВИЛА](GOLDEN_RULES.md) — **до любой работы**. Анализ 3 недель: 727 коммитов, каждый третий переделывает предыдущий, 39 дублей версий. Пять закономерностей и 11 правил против них.

## 🤝 HANDOFF (2026-07-10)
- [HANDOFF_TO_GREENBEAR.md](HANDOFF_TO_GREENBEAR.md) — **READY FOR TRANSMISSION**: Полный контекст для передачи следующему разработчику через CoWorking. Быстрый старт, все журналы, критические правила, оставшаяся работа.

## ⭐ MASTER WORKFLOW — ПРОЧИТАЙ ПЕРВЫМ!

- [MASTER_WORKFLOW.md](MASTER_WORKFLOW.md) — **COMPLETE**: who we are, what we build, exact verified commands (SSH, deploy, commit, push), current state, remaining work

## Критически важное

- [⚠️ greenbear — создатель сайта, особый пользователь](project_greenbear.md) — СУПЕР-КРИТИЧНО: greenbear это владелец с уникальными привилегиями, код под него намеренный — не рефакторить, только улучшать
- [god_mode.css — намеренный файл для greenbear](feedback_god_mode_css.md) — не мёртвый код, не удалять, не помечать unused в аудитах
- [⛔⛔ АККАУНТ GreenBear и его появление на сайте — НЕ ТРОГАТЬ НИКОГДА](feedback_greenbear_account_untouchable.md) — оповещение о входе только на OWNER_SLUG; нарушение = владелец меняет агентов; служебный force_login под привилегированным аккаунтом дёргает боевые механизмы
- [⛔ Страница GreenBear и god_mode.css — НЕ ТРОГАТЬ](feedback_greenbear_page_untouchable.md) — даже ради багфикса; "по эталону GreenBear" = образец для ДРУГИХ страниц, не менять его и не клонировать
- [Intentional patterns — never flag in audits](feedback_audit_intentional.md) — session dedup, fail_silently, god_mode.css, admin URL cave19850324/, Http404 для модераторов — намеренные решения
- [⛔ Hero object-position — LOCKED center 60%](feedback_hero_locked.md) — НИКОГДА не менять без разрешения владельца; полная таблица в CLAUDE.md
- [⛔ Пол арены — СВЕТЛЫЙ пергамент, тёмной темы пола НЕТ](feedback_arena_floor_light.md) — тёмное только чаша/трибуны вокруг; bolt наступил на это в v2.5.322, откатил v2.5.324; арена-визуал = лейн GB
- [⛔ Арена смотрится на /chef-battle/arena/?proto=1 → уже дефолт](reference_arena_proto_link.md) — после слияния v2.5.321 гейт снят, арена одна

- [⛔ Арена скрыта от ВСЕХ кроме staff/superuser до релиза](project_arena_hidden_until_release.md) — 404 для остальных ЗАДУМАН; не баг; НЕ СПРАШИВАТЬ СНОВА (владелец: спрашиваю месяцами одно и то же)

- [⭐ Мобильная арена — ОТДЕЛЬНАЯ сцена, тап по кольцу = список шефов](project_arena_mobile_decision.md) — решение владельца 2026-07-20; плитка на 390px выходит 8px высотой, тап не работает; делать ПОСЛЕ приёмки десктопа

## Субординация

- [⚡ ЗОЛОТОЕ ПРАВИЛО: сначала загрузи подчинённого, потом работай сам](feedback_subordinate_first.md) — проверять GB ЗАПРОСОМ перед любым своим действием; ждёт — ответить немедленно; его простой = мой простой

- [⛔ Правило №1 для GB: факт = замер, догадка в отдельную графу](feedback_gb_facts_need_evidence.md) — «не нашёл» ≠ «нет»; сервер проверять на сервере; «НЕ ПРОВЕРИЛ» допустимо
- [⛔ Связь с GB — только пинг-понг, писем по таймеру НЕТ](feedback_pingpong_protocol.md) — отправил→принял→прочитал→выполнил→отчитался→новое задание; GB пишет 2 раза за круг; шаг «новое задание» мой, его простой = мой косяк
- [⭐ GreenBear = Junior Front End Dev, режим MANUAL, начальник Bolt](project_greenbear_manual_mode.md) — с 2026-07-19: без моего приказа код не трогает; приказы давать чёткие с границами; его простой = мой косяк

## Правила работы (поведение Claude)

- [⛔ ПРОВЕРИТЬ ТРИЖДЫ ДО ОТВЕТА — приказ владельца](feedback_verify_before_speaking.md) — исследование ДО ответа, не в ответе; запрещены «снимаю тревогу», «я недочитал»; не проверил — так и писать
- [⭐ Работай как GreenBear — 7 практик + мои провалы 2026-07-20](feedback_work_like_greenbear.md) — числа вместо прилагательных; сам отзывай свои цифры; называй что решил сам; не сдавай регресс; доказывай отрицание перебором; сначала бесплатный путь

- [⚡ ЗОЛОТОЕ ПРАВИЛО: бритва Оккама — никогда не усложнять](feedback_occams_razor.md) — перед каждым советом: есть ли путь проще? Если да — только он.

- [⛔ Всегда отвечать на русском языке](feedback_language.md) — никакого украинского или английского без явного запроса



- [⛔ Проверять ВСЁ перед выводами](feedback_check_before_acting.md) — локальный репо + сервер + CoWork журнал; никогда не говорить "не сделано" без проверки сервера
- [⛔ Делать точно то что сказано](feedback_do_exactly_as_asked.md) — конкретное задание = буквальное выполнение; не изобретать JS-инжекции вместо {% include %}
- [⛔ НИКОГДА не менять задание самостоятельно](feedback_no_unauthorized_changes.md) — если подход не работает — сказать и ждать; менять решение без спроса ЗАПРЕЩЕНО
- [⛔ Сохранять решения в память НЕМЕДЛЕННО](feedback_save_decisions_immediately.md) — не откладывать; потеря контекста сессии = потеря всего
- [⛔ Follow output format exactly on first attempt](feedback_follow_output_format.md) — "strictly YAML only" = ни слова до и после
- [Always ask before skipping a task](feedback_always_ask.md) — никогда не пропускать задачу самостоятельно — только спросить
- [Commit/push/deploy АВТОНОМНО — не спрашивать](feedback_commit_approval.md) — владелец подтвердил 2026-06-14 и 2026-07-04 ("сними все блоки"): коммитить, пушить, деплоить без запроса разрешения
- [⛔ Каждый шаг — в три журнала](feedback_log_every_step.md) — с 2026-07-02: Deployment Journal + Chef Battle Roadmap + CoWork для greenbear; при старте сессии проверять CoWork
- [⛔ Не выдумывать про лимиты и состояние агентов](feedback_no_speculation_about_agents.md) — владелец узнаёт о лимитах ПЕРВЫМ и скажет сам; status/last_seen в CoWork мертвы; молчание = отправить кусок работы или забрать его часть, а не гадать и не ждать
- [⛔ Постоянная связь — читать инбокс агентов каждый цикл](feedback_constant_communication.md) — координатор НЕ имеет права молчать; читать вывод поллера каждый ход, отвечать на каждое сообщение; не залипать в свою задачу

## Git и деплой

- [ОБНОВЛЕНО 2026-07-04: локальная разработка РАЗРЕШЕНА](feedback_no_local_testing.md) — dev-сервер, скриншоты, preview, локальная копия сайта — всё допустимо когда шаг этого требует; финальное тестирование делает владелец на проде; никогда не репортить "локальный сервер запрещён" как блокер
- [ALWAYS push to GitHub after every commit](feedback_always_push.md) — ⚠️ после каждого коммита сразу push, иначе сервер деплоит старый код
- [⛔ Деплой ВСЕГДА автономно](feedback_deploy_authorization.md) — постоянное разрешение владельца 2026-07-04; после push сразу деплоить, не ждать команды; блок классификатора = технический, сообщить и дать команду
- [⛔ Попутные баги исправлять сразу](feedback_fix_side_issues.md) — найдено попутно → лучшее полноценное решение (не костыль) → исправить немедленно, не откладывать как "follow-up"
- [⛔ НЕ запускать Django на сервере под root — sudo -u deploy](feedback_never_run_as_root_on_server.md) — root-owned файлы ломают прод: статика молча старая, кеш → 500 на логине; «500 там где не менял» = искать root-owned файлы
- [⛔ Среда истины одна — ПРОД; числа с локалки не доказательство](feedback_prod_is_the_only_truth.md) — локалка только для тестов и «не падает ли»; старый дев-сервер показывает протухшие шаблоны и CSS
- [NEVER break production](feedback_prod_safety.md) — обязательный чеклист перед каждым пушем
- [Always work in main branch](feedback_work_in_main.md) — изменения напрямую в main, не в worktree-ветки
- [Verify before confirming](feedback_verify_before_confirming.md) — всегда проверять git status перед "всё готово к деплою"
- [⚠️ Независимый аудит находит то, что пропускает самопроверка](feedback_independent_audit.md) — pass 2 читать критерии буквально (серверное состояние, не UI); каждое число = источник истины?; чужие коммиты проверять на push
- [No commits until local is clean](feedback_commit_only_after_local_test.md) — перед каждым коммитом: check, migrate, локальный тест, git status
- [⚠️ SQLite маскирует прод-баги](feedback_sqlite_masks_prod_bugs.md) — локальные тесты на SQLite ≠ Postgres; проверять отдельно select_for_update+nullable select_related и живые платёжные пути (2 бага за 2 сессии)
- [Always stage untracked files](feedback_git_untracked.md) — читать обе секции git status; все файлы задачи в один коммит
- [⚠️ SSH деплой — правильный метод](feedback_ssh_deploy_method.md) — ВСЕГДА Bash tool + wsl с ключом culineire_linode; НЕ Ubuntu terminal через computer-use
- [Bump version before every deploy](feedback_version_bump.md) — перед каждым деплоем инкрементировать патч-версию в футере base.html
- [⛔ «RESTARTED» НЕ значит «задеплоено»](reference_deploy_restarted_lies.md) — collectstatic падает тихо (статика была root-owned), сайт отдаёт СТАРЫЙ хешированный файл; проверять живой файл curl-ом, не факт рестарта
- [⚠️ collectstatic после CSS/JS правок](project_deploy_workflow.md) — git pull + restart НЕ обновляют статику; нужен явный collectstatic --no-input, иначе сайт молча отдаёт старый файл

## Окружение и инфраструктура

- [⚠️ Рабочая среда — Windows + WSL](project_workstation.md) — файлы в E:\CulinEire Project\...; деплой через wsl + ssh; не предлагать Linux VM terminal
- [Production deploy workflow](project_deploy_workflow.md) — команда деплоя, структура сервера, IP 80.85.84.156, группы
- [NGINX Unit body size fix](project_nginx_unit_config.md) — proxy_request_buffering off решает 502 на больших загрузках
- [Maintenance mode — как включить/выключить](reference_maintenance_mode.md) — .env на сервере + sudo systemctl restart unit
- [⚠️ Run full test suite on server](reference_run_tests_server.md) — ТОЛЬКО через Python heredoc; set -a source ЛОМАЕТСЯ; suite = 260+ тестов
- [⚠️ Регрессия/деплой подводные камни](reference_regression_gotchas.md) — регрессия ПЕРЕД деплоем; static-ассерты матчить стем (не полное имя, ManifestStorage хеширует); frozen key-set тесты обновлять при новых ключах payload; 127.0.0.1 нельзя в MONITORING_INTERNAL_IPS; unbuffered nohup + Monitor для долгих прогонов
- [Coworking app — координация AI-агентов](reference_coworking_app.md) — /coworking/, агенты Bolt и GreenBear, handoff через кнопку, БД как канал синхронизации
- [⛔ CoWork agent_id регистрозависим — 'GreenBear' != 'greenbear'](reference_cowork_agent_id_case.md) — опечатка в регистре молча СОЗДАЁТ второй ящик, письмо теряется, отправитель видит «SENT»; только строчные
- [⭐ CoWork направленные сообщения + живой 15с поллер](reference_cowork_message_inbox.md) — CoworkingMessage.send(to_agent="bolt",...); Monitor-поллер agent_inbox каждые 15с; стартовать в начале каждой сессии; работает только пока сессия жива

## Стандарты UI и кода

- [No hacks — only proper fixes](feedback_no_hacks.md) — никогда костыли; только настоящий фикс причины
- [⛔ Массовое удаление — только по ТОЧНОМУ признаку](feedback_exact_filters_on_delete.md) — фильтр по подстроке снёс 3 живых сообщения; перед delete() всегда count() + показать примеры
- [No dashes in UI text](feedback_no_dashes.md) — не использовать em dash и двойные тире в шаблонах
- [Hard refresh is standard practice](feedback_hard_refresh.md) — Ctrl+Shift+R делается всегда, никогда не предлагать как решение
- [Blue annotations = hints, not bugs](feedback_blue_annotations.md) — синие рисунки на скриншотах = подсказки (выровнять/убрать), не артефакты UI
- [Button design system — unified structure](feedback_button_design_system.md) — все кнопки через существующие CSS-классы сайта
- [⛔ На арене hero НЕ НУЖЕН — навсегда](project_arena_no_hero.md) — решение владельца 2026-07-20; исключение из правила канонического hero; не «восстанавливать» при аудите
- [⭐ Канонический hero сайта — hero hero--home](feedback_canonical_hero.md) — НЕ battle-room-hero; эталон company-information + авторский профиль; btn-primary/secondary/text-link, никаких one-off
- [⛔ ЦВЕТА — только из файла схемы, вопросов не задавать](feedback_colour_scheme_is_law.md) — CulinEire_colour_font_scheme.pdf + токены :root; сырой hex запрещён; нет оттенка — брать ближайший токен, не выдумывать и не спрашивать
- [Синхронизировать стили с первого раза](feedback_style_sync.md) — любой новый UI сразу на CSS-переменных и классах проекта
- [App architecture rule](feedback_app_architecture.md) — каждый апп содержит только своё, новая функциональность = новый апп
- [⚠️ Static images must be in git before referencing in templates](feedback_static_images.md) — проверить git ls-files перед {% static 'images/X' %}; иначе → 500
- [Использовать встроенную генерацию картинок](feedback_image_generation.md) — для визуальных ассетов использовать систему Automatic Recipe Generation
- [⛔ Never touch Django Admin](feedback_no_django_admin.md) — никогда не открывать /cave19850324/; проверять сайт только через /recipes/moderation/
- [Preload all tools at session start](feedback_preload_tools.md) — в начале сессии сразу загружать все deferred tools одним батчем

- [Enter Arena button — единственный правильный способ](feedback_enter_arena_button.md) — всегда `{% include '_enter_arena_btn.html' %}`, только `btn-primary`, только `chef_battle:arena`

## Chef's Battle — ПОЛНЫЕ СПЕЦИФИКАЦИИ (2026-07-10)

### 🔴 НОВОЕ: Глубокий анализ всех документов проекта
- [Chef Battle Complete Specification](chef_battle_complete_specification.md) — **ПОЛНЫЙ СПРОС**: 7 фаз, все модели, сервисы, селекторы, правила, версия истории, оставшаяся работа
- [Chef Battle Business Model](chef_battle_business_model.md) — Retention loops, 4-сторонний marketplace, инвестор-кейс, успех-метрики, монетизация
- [Chef Battle Arena & Real Mechanic](chef_battle_arena_real_mechanic.md) — **КРИТИЧНО**: "Combat is NOT violence"; ингредиентный боевой движок, визуализация, артефакты (EPIC/LEGENDARY переписать), текущие пробелы
- [Chef Battle Legal & Compliance](chef_battle_legal_compliance.md) — Stripe, VAT 23%, DAC7, 18+, спонсорские битвы, tax requirements, чек-лист

### Существующие документы Chef's Battle
- [⚠️ План «Арена как зал» — утверждён 2026-07-02](project_arena_hall_plan.md) — переезды аватаров, встроенный Battle Room popup, прихожая, серые поля анонимов; НЕ кодить без команды; 6 открытых вопросов
- [Chef's Battle — концепция и стратегия запуска](chef_battle_concept.md) — competitive culinary platform; AllFresh партнёр; 10 шагов запуска; Founding Chefs
- [Chef's Battle — текущее состояние кода](project_chefs_battle.md) — Phase 1+2 реализованы и в проде; все модели, views, templates перечислены
- [Chef's Battle — аудит 2026-07-02](project_chefs_battle_audit_2026_07_02.md) — Arena-промпт выполнен целиком; флаг на проде ВЫКЛЮЧЕН (dark launch), 0 завершённых битв; ⚠️ outreach и AllFresh-пилот ИСКЛЮЧЕНЫ владельцем; кланы/спонсорские битвы/TikTok-Instagram live — ДО запуска, кланы приоритет
- [Chef's Battle ТЗ — все документы в репозитории](reference_chef_battle_tz.md) — docs/chef_battle/ в репо; читать через Read tool
- [⚠️ Победитель = только аудитория](project_chefs_battle_core_principle.md) — боевая система это фан; корону определяет только голосование
- [Chef's Battle — полная фазовая карта](project_chefs_battle_phase_map.md) — 7 фаз: Foundation → MVP → Social → Energy → Combat → Artifacts → Seasons
- [⚠️ CORE DESIGN «бой про рецепт» — доки ВРУТ, рецепт УЖЕ вшит](project_core_design_recipe_flow_state.md) — declare/entry/attach формы готовы, не переписывать; не сделаны только CTA на чужом рецепте и создание рецепта в потоке; везде только APPROVED
- [Chef's Battle — только рецепты](project_chefs_battle_entries.md) — записи в боях только через рецепты, статьи не участвуют
- [Chef's Battle — правила биатлона](project_battle_biathlon_rules.md) — 2 лока, 3 выстрела, отскок = потеря выстрела
- [Chef's Battle — полная механика боя](project_battle_full_mechanics.md) — Move очки (+5 рецепт/статья, +2 Pinch), 3 фазы, локи, выстрелы, реальная кухня, 10 фото, голосование аудитории
- [Chef's Battle — подарки зрителей и токены](project_battle_gifts_tokens.md) — цветы/кофе/пиво=5-20T; артефакты 10-400T; 100T=€10...1400T=€80
- [Chef's Battle — уровни шефов и слоты](project_battle_levels_slots.md) — 5 уровней (3 победы/уровень) + CulinEire Hero; 1 слот/24ч
- [Chef's Battle — механика ингредиентного боя](project_battle_ingredient_combat.md) — равные меню, 2 лока, хиты по незалоченным

## GreenBear маскот

- [GreenBear — золотой формат позиций и анимации](project_greenbear_golden_state.md) — bottom -0.8%, roam 62-88%, 3 спрайта по 4 фрейма; НЕ менять при замене картинок

## Сессионные итоги

- [⭐ СОСТОЯНИЕ 2026-07-20: арену НЕ программируем — зал стал картинкой](project_session_2026_07_20_state.md) — прод v2.5.360; фон + пол кодом; наклона нет; кадров 4 из 12; в git лежит НЕзадеплоенный WIP full-bleed; оба агента ушли в лимит

- [⭐ СОСТОЯНИЕ 2026-07-19: прод v2.5.335, доска 7/11, у GB убита СЕССИЯ (не агент)](project_session_2026_07_19_state.md) — агент GreenBear жив, но контекст сессии умер: новая сессия стартует с нуля, переориентировать; связи налаживаем заново; открыт walkover A/B — что сдали Bolt (319/320/323/324/332) и GB (325-331 арена-визуал), 3 открытых хвоста, границы лейнов, связь без пульсов
- [⭐ Arena Build board — доска строительства с START](reference_arena_build_board.md) — /recipes/moderation/arena-build-plan/, backend|frontend колонки, START шлёт сигнал обоим; done-флаги в ARENA_BUILD_STAGES синхронить руками после релизов

- [⭐ СОСТОЯНИЕ 2026-07-17: прод v2.5.312, ритуал старта ждёт деплоя](project_session_2026_07_17_state.md) — что в проде, что в main, решения владельца (анон-голоса, оба no-show, тест-шефы CrestedTen/Jam-Oliver), правило проверки трафика перед регрессией

- [⭐ Сессия 2026-07-16: процедурная арена, bolt limit-out v2.5.303](project_session_2026_07_16_procedural_arena.md) — все read-model контракты live; Ember и.о. координатора, критический путь = ?proto=1 гейт; по возврату: ревью гейта + регрессия + план переключения дефолта

- [Phase 6 разделён: bolt=сезоны (done), GB=кланы](project_phase6_split.md) — движок сезонов в проде v2.5.189; GreenBear взял кланы (дизайн до схемы); граница координации — не трогать Season/season_service

- [Сессия 2026-07-10: Gap 2 + Gap 4 + stale тесты](project_session_2026_07_10_battle_gaps.md) — artifact в combat реализован, cooldown на accept-пути, 5 stale тестов исправлены, v2.5.175→176

## Справочники

- [⛔ Арена смотрится на /chef-battle/arena/?proto=1](reference_arena_proto_link.md) — прото-гейт на проде, НЕ голый /arena/, НЕ dev-сервер; владелец бил за это

- [⭐ ЖУРНАЛЫ И КОНСОЛИ — все пути в коде](reference_journal_locations.md) — Arena Master Console Plan, Deployment Journal, Battlefield Progress, CoWorking Dashboard — ЧИТАТЬ ЧЕРЕЗ КОД, НЕ БРАУЗЕР
- [Post newsfeed entry via terminal](reference_post_newsfeed.md) — SSH + Python-скрипт во /tmp/ (set -a source ломается)
