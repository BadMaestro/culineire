# Static Images — всегда проверять git ls-files перед использованием

## Правило

Перед тем как менять ссылку на любой статик-файл (изображение, иконка, шрифт) —
ОБЯЗАТЕЛЬНО проверить что файл уже в git:

```bash
git ls-files static/images/hero.png
```

Если вывод пустой — файл НЕ в git. Добавить в тот же коммит что и шаблон:

```bash
git add static/images/hero.png templates/home.html
git commit -m "..."
```

## Почему это критично

CulinEire использует ManifestStaticFilesStorage. При деплое Django компилирует
статик в staticfiles.json. Если файл есть локально но отсутствует в git:
- на сервере файла нет
- {% static 'images/hero.png' %} падает с ValueError
- сайт отдаёт 500 на всех страницах где есть этот тег

## Нельзя

- Менять `{% static 'images/X' %}` в шаблоне не проверив что X в git
- Коммитить шаблон отдельно от нового статик-файла
- Говорить "готово" если `git ls-files` вернул пустую строку

## Всегда

1. `git ls-files static/images/имя_файла` — проверить что файл отслеживается
2. Если нет — `git add` файл В ТОМ ЖЕ коммите что и шаблон
3. Это касается hero images, favicon, og-images, любых новых static-файлов
