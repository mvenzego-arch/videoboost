# StaticSite

Статический сайт: семантический HTML5, чистый CSS3, vanilla JS. Без npm,
фреймворков и сборщиков. Деплой — GitHub Pages с корня ветки `master`.

## Быстрый старт (локально)

```
python -m http.server 8000
```

Открой `http://127.0.0.1:8000/` в браузере. Остановка сервера: Ctrl+C.

## Структура

| Путь | Что там |
|---|---|
| `index.html` | главная: hero, 8 возможностей, «старая RX 570», CTA |
| `kak-rabotaet.html` | как работает: 5 шагов + FAQ |
| `skachat.html` | скачивание: сборки, чейнджлог, требования |
| `css/style.css` | все стили + дизайн-токены в `:root` |
| `js/main.js` | поведение (страница работает и без него) |
| `content/` | финальные тексты страниц (исходник копирайтера) |
| `assets/favicon/` | favicon (SVG) |
| `tools/` | скрипты проверок (Python 3.10, только stdlib) |

## Проверки

```
python tools/check_html.py
python tools/check_links.py
python tools/check_weights.py
python tools/check_contrast.py
```

Каждый скрипт: отчёт «файл:строка → что не так», выход 0 = чисто, 1 = есть ошибки.
