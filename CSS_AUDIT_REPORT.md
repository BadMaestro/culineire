# Аудит CSS — CulinEire

**Дата:** 2026-04-29
**Стек:** Django 5.x, чистый CSS (без препроцессоров и сборки)
**Объём проекта:** 11 файлов в `static/css/`, ~6 411 строк, ~143 KB

---

## TL;DR

Базовая архитектура — хорошая для 2026: cascade layers, логические свойства, `clamp()`, container queries,
`text-wrap: pretty/balance`, `prefers-reduced-motion`, `forced-colors`, `focus-visible`. Заметной грязи и `!important`
нет.

Главные проблемы:

1. ~53 KB **мёртвого кода** — четыре файла полностью не подключены, плюс ~120 строк неиспользуемых классов внутри живого
   файла.
2. **Дублирование** социальных иконок между `header.css` и `footer.css` (~70 строк копипаста).
3. **`color-scheme: light`** жёстко зашита — нет ни заготовки под dark mode, ни `light-dark()`.
4. **Бесконечная анимация** в god_mode.css не уважает `prefers-reduced-motion` (WCAG 2.2 SC 2.2.2).
5. **`@import url(googleapis...)`** внутри `god_mode.css` — блокирующий, надо переносить в `<link>` шаблона.
6. Несколько мест с **inline-стилями** в шаблонах, что мешает CSP.

Ниже полный разбор по приоритетам.

---

## 0. Карта используемости

| Файл                | Размер    | Подключён                               | Статус                                                 |
|---------------------|-----------|-----------------------------------------|--------------------------------------------------------|
| `base.css`          | 15 KB     | base.html                               | живой                                                  |
| `header.css`        | 9 KB      | base.html                               | живой                                                  |
| `content_cards.css` | 16 KB     | импорт из base.css `@layer components`  | живой (но содержит мёртвый блок)                       |
| `god_mode.css`      | 3 KB      | импорт из base.css `@layer special`     | живой                                                  |
| `footer.css`        | 3 KB      | импорт из base.css `@layer footer`      | живой                                                  |
| `detail_page.css`   | 44 KB     | recipe_detail.html, article_detail.html | живой                                                  |
| `auth.css`          | 2 KB      | login.html, signup.html                 | живой                                                  |
| `recipe_detail.css` | **45 KB** | нигде                                   | **мёртвый**, заменён на detail_page.css                |
| `site.css`          | 2 KB      | нигде                                   | **мёртвый**, классы `site-header`, `primary-nav` нигде |
| `styles.css`        | 3 KB      | нигде                                   | **мёртвый**, дубликат site.css из старой версии        |
| `media.css`         | 0 B       | нигде                                   | **мёртвый**, пустой                                    |

---

## 1. Критично (предлагается удалить/переписать первым делом)

### 1.1. Удалить мёртвые файлы

- `static/css/recipe_detail.css` (1930 строк, 45 KB) — старая версия, полностью повторяет `detail_page.css` со слегка
  другим синтаксисом цветов (`rgb(22 102 69)` вместо `#166645`).
- `static/css/site.css` (91 строка) — использует другой набор токенов (`--slate`, `--limestone`) и устаревшие классы
  `.site-header`, `.primary-nav`, `.main-nav`, `img.site-logo`. В шаблонах не встречается ни один из них.
- `static/css/styles.css` (71 строка) — то же самое в ещё более старой версии.
- `static/css/media.css` — пустой 0 B.

**Эффект:** −53 KB, −2 088 строк, минус когнитивная нагрузка при поиске «откуда стиль».

### 1.2. Удалить блок `.article-card*` в `content_cards.css` (строки 626–715 + соответствующие правила в @media)

Класс `article-card` нигде не используется в шаблонах, заменён на `recipe-card--article` (см. строки 586–622 в этом же
файле). Мёртвый код ~120 строк.

### 1.3. Inline-стили в шаблонах

- `templates/about.html`: `style="padding-block:2rem;"`
- `templates/recipes/author_detail.html`: 2× `style="margin-top: 2rem;"`
- `templates/recipes/recipe_detail.html`: `style="width: {{ average_rating_percentage }}%;"`

Первые три — заменить на классы (`.section--lg`, `.page-header--gap`).
Прогресс-бар рейтинга — оставить inline только для **значения**, но через CSS-переменную:

```html
<span class="rating-overview__stars-fill" style="--p:{{ average_rating_percentage }}%;">★★★★★</span>
```

```css
.rating-overview__stars-fill { width: var(--p, 0%); }
```

Это совместимо с CSP `style-src 'self' 'unsafe-hashes'` без `unsafe-inline`.

### 1.4. Анимация `god-gold-flow` без уважения к `prefers-reduced-motion`

`static/css/god_mode.css` — `animation: god-gold-flow 5s linear infinite;` крутится бесконечно у всех. По WCAG 2.2 (SC
2.2.2) бесконечный движущийся контент длительнее 5 секунд должен поддаваться остановке.

Минимум:

```css
@media (prefers-reduced-motion: reduce) {
  .author-name--god,
  .author-name--greenbear { animation: none; }
}
```

### 1.5. Блокирующий `@import url("https://fonts.googleapis.com/...")` в god_mode.css

`@import` из CSS грузится **последовательно после парсинга CSS** — Google не рекомендует так с 2018-го. Перенести
`Dancing Script` в `<link rel="stylesheet">` в `templates/base.html` рядом с другими шрифтами, или подгружать только на
странице автора через `{% block extra_head %}`.

---

## 2. Важно (оставить в текущем спринте правок)

### 2.1. Дублирование социальных ссылок

`header.css` строки 31–108 и `footer.css` строки 54–130 — **почти идентичны** (~70 строк копипаста на каждую). Стоит:

- вынести в общий `static/css/socials.css` или `@layer components` в base.css;
- единый базовый класс `.social-link` с CSS-переменной `--social-accent`;
- варианты `.ce-header-socials__link` и `.footer-socials__link` сделать «темами» через `--social-color: rgb(...);`.

**Эффект:** −60–80 строк, синхронность бренд-цветов.

### 2.2. Зафиксированная `color-scheme: light` — заготовка под dark mode

`base.css:13` и `detail_page.css:2` заявляют `color-scheme: light`. В 2026 «дефолт» для нового кода:

```css
:root { color-scheme: light dark; }
:root {
  --bg: light-dark(#faf6f0, #14201a);
  --surface: light-dark(#fffdf9, #1c2a23);
  --ink: light-dark(#1f2c25, #ecefe9);
  /* ... */
}
```

Даже без полного редизайна добавление `light dark` сразу даст пользователю системно-тёмные скроллбары/инпуты.
`light-dark()` — Baseline 2024, поддержано всеми вечно-зелёными.

### 2.3. Унификация cascade layers

Сейчас:

- `base.css` объявляет `@layer base, components, special, footer;`
- `detail_page.css` создаёт собственные `@layer detail-tokens, detail-page;` параллельно, не входящие в общую
  очерёдность.

**Best practice 2026:** один общий порядок слоёв, объявленный в самом раннем файле (base.css):

```css
@layer reset, tokens, base, components, layout, page, utilities, overrides;
```

И каждый файл/блок объявляет свои стили через `@layer page { ... }` — тогда `detail_page.css` гарантированно проиграет
`utilities` и выиграет у `components`.

### 2.4. Дублирование `:root` и токенов

- `:root { color-scheme: light }` объявлено и в base.css, и в detail_page.css — конфликта нет, но избыточно. Оставить
  только в base.css.
- В detail_page.css токены висят на `.detail-page` (ок), но многие повторяют то, что уже есть глобально:
  `--detail-text-main: #24313a` ≈ `--ink: #1f2c25`, `--detail-green-2: #0f4f36` ≈ `--brand-dark: #123c2d`.
  Стоит ввести алиасы: `--detail-text-main: var(--ink);` и решать оттенки через `color-mix()`.

### 2.5. Жёсткие хексы в живых файлах

В `base.css` и `header.css` повторяются `#3a2c1e`, `#1f2c25`, `#f7f2ea`, `#fff8ee` десятки раз. Всё, что повторяется ≥ 3
раз, — кандидат в токен. Минимум:

```css
:root {
  --ink-warm: #3a2c1e;          /* кнопочный warm */
  --ink-warm-soft: rgb(58 44 30 / 0.18);
  --paper: #f7f2ea;             /* текст на тёмном hero */
  --paper-dim: rgb(247 242 234 / 0.96);
}
```

Поможет, когда придёт dark mode.

### 2.6. Шрифты: пробелы в семействе

В `base.css:72` и `header.css:237` строка

```
"Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
```

повторяется. Вынести в `--font-sans` и использовать `font-family: var(--font-sans);`.

То же для `"Playfair Display", Georgia, serif` (`--font-serif`).

---

## 3. Рекомендации (улучшения, можно отдельным PR)

### 3.1. CSS Nesting (Baseline 2024)

Длинные цепочки селекторов `.detail-page__breadcrumb-item a:hover, .detail-page__breadcrumb-item a:focus-visible`
упрощаются:

```css
.detail-page__breadcrumb-item {
  & a {
    color: var(--ink-soft);
    text-decoration: none;
    &:hover, &:focus-visible { color: var(--brand); }
  }
}
```

Сэкономит ~5–10% строк в крупных файлах. Поддержка Chrome 120, Firefox 117, Safari 16.5 — все живые браузеры в 2026.

### 3.2. `@scope` для изоляции страничных стилей

`detail-page` имеет ~1200 строк правил начинающихся с `.detail-page__*`. Это идеальный кандидат для `@scope`:

```css
@scope (.detail-page) {
  :scope { --detail-radius-sm: 14px; /* ... */ }
  .breadcrumb { /* без префикса */ }
}
```

Сократит длинные имена и физически невозможно станет «протечь» стилями. Baseline 2024.

### 3.3. `@property` для анимируемых custom properties

Сейчас в `detail_page.css` галерея анимирует переменные через `transition: transform/opacity/...`, а вот
`--gallery-side-shift` в `.recipe-gallery` (строки 502–506) анимировать нельзя — она не объявлена через `@property`.
Если в будущем понадобится плавное «расхождение» картинок при drag, стоит:

```css
@property --gallery-side-shift {
  syntax: "<percentage>";
  initial-value: 28%;
  inherits: false;
}
```

### 3.4. `text-rendering: optimizeLegibility` — убрать

`base.css:79`. Анти-паттерн на длинных страницах: дорогая операция кёрнинга, особенно на мобильных. С 2020-х
рекомендуется не задавать вовсе (по умолчанию `auto`, браузер сам решает).

### 3.5. `* { box-sizing: border-box }` модернизировать

```css
:root { box-sizing: border-box; }
*, *::before, *::after { box-sizing: inherit; }
```

Преимущество: компоненты могут локально вернуться к `content-box` если очень нужно. Мелочь, но 2026-стиль.

### 3.6. `will-change` на галерее — точечно

`detail_page.css:558–560`: `will-change: transform, opacity` повешено на `.is-current/.is-prev/.is-next`. Это уже
хорошо, что не на всех `.recipe-gallery__item`, но в идеале JS включает `will-change` непосредственно перед transition и
убирает в `transitionend`. Иначе всегда висит композиторский слой.

### 3.7. `oklch()` / `color-mix()` для палитры

В 2026 предпочтительнее задавать палитру в OKLCH (равномерное восприятие):

```css
:root {
  --brand: oklch(34% 0.05 158);          /* зелёный */
  --brand-dark: oklch(28% 0.05 158);
  --brand-soft: color-mix(in oklab, var(--brand) 8%, transparent);
}
```

Большая работа, но даст доступную палитру и автоматические соотношения яркостей при создании dark mode.

### 3.8. Упрощённая поддержка line-clamp

`content_cards.css:447–451` использует «классический» сэндвич:

```css
display: -webkit-box;
-webkit-line-clamp: 3;
-webkit-box-orient: vertical;
overflow: hidden;
```

В 2026 можно ужать через `@supports` до stand-alone `line-clamp: 3` (Chrome 121, Safari 18.2). Но без падения в
Firefox (старый паттерн всё ещё нужен) разумнее оставить как есть. Это **не критично**, просто к сведению.

### 3.9. Дубль брейкпойнтов

В файлах разные значения: 480, 520, 640, 768, 839/840, 960. Стоит свести к набору токенов и/или заменить большинство на
container queries (как уже сделано в detail_page.css). Брейкпойнты можно вынести в `:root` через CSS env-variables-like:

```css
:root {
  --bp-sm: 480px;
  --bp-md: 640px;
  --bp-lg: 960px;
}
```

К сожалению, `@media (max-width: var(--bp-md))` пока не работает напрямую (CSS Values 5 черновик), но container queries
уже могут принимать calc/var. На сейчас — просто привести значения к **одному** ряду: 480, 640, 960.

### 3.10. `min-height: 100vh` нет, но есть `flex: 1 0 auto` на main

Хорошо. Если когда-то введёте sticky-header в полный экран на мобильных — стоит знать о `100dvh` (dynamic viewport)
вместо `100vh`.

### 3.11. `prefers-reduced-motion` в `header.css`

В этом файле есть transitions (`.ce-nav__toggle:active { transform: scale(0.98); }`, hamburger crossfade) — но нет
media-блока для уменьшения движения. Стоит добавить.

### 3.12. `forced-colors` — продолжить покрытие

Сейчас `forced-colors: active` объявлен только в base.css и content_cards.css. В detail_page.css он есть для форм. В
header.css/footer.css — нет. Полезно добавить минимум для социальных иконок (контраст в Windows High Contrast).

### 3.13. `scrollbar-gutter: stable` → `stable both-edges`

`base.css:61` — добавить `both-edges` для одинакового зазора в RTL-контекстах (если когда-нибудь добавится `dir="rtl"`).

### 3.14. `@font-face local()` для системных fallback

Сейчас всё через Google Fonts. Если хочется убрать сетевую зависимость, можно объявить `@font-face` с `local("Inter")`
first и self-hosted `.woff2` fallback. Это улучшит LCP на ~150–300 ms.

### 3.15. Минификация на проде

Размер CSS после удаления мёртвого кода: ~90 KB (≈25 KB gzip). Минификация (например, через `django-compressor` или
`whitenoise.compressed`) даст ещё минус ~15%.

---

## 4. Что **уже сделано хорошо** (стоит сохранить при рефакторинге)

- Cascade layers в base.css.
- Логические свойства повсеместно (`margin-inline`, `padding-block`, `inset-inline-start`).
- Container queries в `detail_page.css` (`container-type: inline-size; container-name: detail-page`).
- `text-wrap: pretty` и `text-wrap: balance`.
- `clamp()` для типографики.
- Modern alpha syntax `rgb(... / 0.5)` без запятых.
- `prefers-reduced-motion` в base, content_cards, detail_page.
- `forced-colors: active` для важных интерактивных элементов.
- `:focus-visible` везде, никаких `outline: none` без замены.
- `appearance: none` на кнопках.
- `aspect-ratio` на медиа-обёртках вместо padding-hack.
- `:where()` для понижения специфичности там, где надо.
- Ноль `!important` во всём проекте.
- Touch-friendly `min-height: 44px` на кнопках/линках навигации.

---

## 5. Предлагаемый порядок правок

1. **Шаг 1 (механический, низкий риск):** удалить `recipe_detail.css`, `site.css`, `styles.css`, `media.css`. Удалить
   мёртвый блок `.article-card*` в `content_cards.css`. Перенести `Dancing Script` из `@import` в `<link>` шаблона.
   Добавить `prefers-reduced-motion` для god_mode.
2. **Шаг 2:** убрать inline-стили из шаблонов, кроме рейтинга. Рейтинг переписать через CSS-переменную `--p`.
3. **Шаг 3:** вынести социальные иконки в общий компонент.
4. **Шаг 4:** добавить `color-scheme: light dark`, начать перенос цветов на `light-dark()` (минимум — `--bg`,
   `--surface`, `--ink`).
5. **Шаг 5:** свести cascade layers к одной декларации в base.css.
6. **Шаг 6 (по желанию):** CSS Nesting, `@scope`, `oklch()`.

Шаги 1–3 безопасны и могут быть сделаны в один коммит. Шаги 4–6 — отдельные PR-ы, поскольку требуют визуальной проверки.

---

*Конец отчёта.*
