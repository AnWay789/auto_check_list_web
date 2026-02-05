import logging
import re
import html

logger = logging.getLogger(__name__)

def remove_shielding(modeladmin, request, queryset):
    """
    Удаляет экранирование из текстовых полей в queryset.
    """
    for obj in queryset:
        obj.dashboard.name = re.sub(r"\\([_*[\]()~`>#+\-=|{}.!])", r"\1", obj.dashboard.name)
        obj.dashboard.save(update_fields=['name'])
        if obj.description is not None:
            obj.description = re.sub(r"\\([_*[\]()~`>#+\-=|{}.!])", r"\1", obj.description)
        obj.save(update_fields=['description'])
    return queryset

remove_shielding.short_description = "Удалить экранирование из текстовых полей"

def markdownv2_to_html(text: str) -> str:
    # Сохраняем фрагменты %...% — их не форматируем
    placeholders = []
    def save_noformat(match):
        placeholders.append(match.group(1))
        return f"\x00NOFORMAT_{len(placeholders) - 1}\x00"

    text = re.sub(r"%([^%]+)%", save_noformat, text)

    # HTML escape
    text = html.escape(text)
    # Code blocks
    text = re.sub(
        r"```([\s\S]*?)```",
        r"<pre><code>\1</code></pre>",
        text
    )

    # Inline code
    text = re.sub(
        r"`([^`]+)`",
        r"<code>\1</code>",
        text
    )

    # Links [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^\)]+)\)",
        r'<a href="\2">\1</a>',
        text
    )

    # Bold / Italic / Underline / Strike
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^_]+)__", r"<u>\1</u>", text)
    text = re.sub(r"_([^_]+)_", r"<i>\1</i>", text)
    text = re.sub(r"~([^~]+)~", r"<s>\1</s>", text)

    # Remove markdown escaping
    text = re.sub(r"\\([_*[\]()~`>#+\-=|{}.!])", r"\1", text)

    # Восстанавливаем фрагменты %...% как обычный текст (без форматирования)
    for i, raw in enumerate(placeholders):
        text = text.replace(f"\x00NOFORMAT_{i}\x00", html.escape(raw))

    return text
