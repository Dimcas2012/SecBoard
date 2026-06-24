# GDPR Guide Resources - Administrator Guide

## Огляд

Модуль **GDPR Guide Resources** дозволяє адміністраторам завантажувати та управляти ресурсами (checklists, templates, forms тощо), які відображаються в розділі **Downloads** GDPR Implementation Guide.

## Модель `GDPRGuide`

### Поля моделі

| Поле | Тип | Опис |
|------|-----|------|
| `title` | CharField | Назва ресурсу (відображається користувачам) |
| `description` | TextField | Опис ресурсу (опціонально) |
| `category` | CharField | Категорія: Checklist, Template, Email Template, Form, Guide, Other |
| `file` | FileField | Завантажений файл (зберігається в `media/gdpr_resources/YYYY/MM/`) |
| `file_type` | CharField | Тип файлу: PDF, DOCX, XLSX, TXT, ZIP, Other |
| `resource_id` | SlugField | Унікальний ідентифікатор (наприклад: `gdpr-implementation-checklist`) |
| `is_active` | BooleanField | Чи показувати ресурс користувачам |
| `order` | IntegerField | Порядок відображення (менше число = вище в списку) |
| `created_at` | DateTimeField | Дата створення |
| `updated_at` | DateTimeField | Дата останнього оновлення |
| `created_by` | ForeignKey | Користувач, який створив ресурс |

### Категорії ресурсів

1. **Checklist** (`checklist`) - Контрольні списки для впровадження GDPR
2. **Template** (`template`) - Шаблони документів (Privacy Policy, ROPA, DPIA тощо)
3. **Email Template** (`email`) - Шаблони листів (DSR responses, breach notifications)
4. **Form** (`form`) - Форми для збору даних (consent forms, DSR submission)
5. **Guide Document** (`guide`) - Посібники та керівництва
6. **Other** (`other`) - Інші типи ресурсів

### Типи файлів

- **PDF** - Найкраще для контрольних списків, форм, готових документів
- **DOCX** - Для редагованих шаблонів документів
- **XLSX** - Для таблиць (ROPA, data mapping worksheets)
- **TXT** - Для простих текстових шаблонів
- **ZIP** - Для пакетів файлів
- **Other** - Інші типи файлів

## Адміністрування через Django Admin

### Доступ до адмінки

1. Увійдіть в Django Admin: `http://your-domain/admin/`
2. Перейдіть до розділу **GDPR** → **GDPR Guide Resources**

### Створення нового ресурсу

1. Натисніть **Add GDPR Guide Resource**
2. Заповніть обов'язкові поля:
   - **Title**: Назва ресурсу (наприклад: "GDPR Implementation Checklist")
   - **Resource ID**: Унікальний slug (наприклад: `gdpr-implementation-checklist`)
   - **Category**: Виберіть категорію зі списку
   - **File**: Завантажте файл
   - **File Type**: Виберіть тип файлу
3. Опціонально:
   - **Description**: Додайте опис ресурсу
   - **Order**: Встановіть порядок відображення (за замовчуванням 0)
   - **Is Active**: Увімкніть для показу користувачам (за замовчуванням увімкнено)
4. Натисніть **Save**

### Редагування списку ресурсів

У списку ресурсів ви можете:
- **Змінювати порядок** прямо в таблиці (колонка Order)
- **Фільтрувати** за категорією, типом файлу, статусом активності, датою створення
- **Шукати** за назвою, описом або resource_id
- **Переглядати файл** - клік на іконку файлу

### Управління існуючими ресурсами

1. **Редагувати**: Клік на назву ресурсу
2. **Деактивувати**: Зніміть галочку "Is Active" (ресурс зникне з Downloads, але залишиться в базі)
3. **Видалити**: Клік на checkbox → Actions → Delete selected

### Приклад File Preview

При редагуванні ресурсу ви побачите:
- Велику іконку файлу
- Посилання для завантаження
- Розмір файлу (KB або MB)
- Тип файлу

## Рекомендовані ресурси для завантаження

### Checklists (PDF)
- GDPR Implementation Checklist
- Consent Audit Checklist
- DSR Workflow Checklist
- Breach Response Checklist
- Data Retention Audit Checklist

### Templates (DOCX/XLSX)
- Privacy Policy Template (DOCX)
- Cookie Policy Template (DOCX)
- DPIA Template (XLSX)
- ROPA (Art. 30) Template (XLSX)
- Data Processor Agreement (DOCX)
- Data Subject Rights Request Form (DOCX)

### Email Templates (TXT)
- DSR Access Request Response
- DSR Erasure Request Response
- DSR Rectification Response
- Breach Notification to DPA
- Breach Notification to Individuals
- Consent Confirmation Email
- Consent Withdrawal Confirmation

### Forms (PDF)
- Consent Form Examples
- DSR Submission Form
- Employee Consent Form
- Third-Party Data Transfer Form
- Data Mapping Worksheet (XLSX)

## Відображення ресурсів для користувачів

Ресурси відображаються в **GDPR Implementation Guide** → вкладка **Downloads** → **Learning Materials & Resources**.

Користувачі бачать:
- Назву ресурсу
- Іконку файлу (залежно від типу)
- Badge з типом файлу (PDF, DOCX, XLSX тощо)
- Посилання для завантаження

Ресурси групуються по категоріях:
1. **Checklists** (сині картки)
2. **Templates** (зелені картки)
3. **Email Templates** (блакитні картки)
4. **Forms** (жовті картки)

Якщо в категорії немає жодного активного ресурсу, користувачі побачать повідомлення: "No [category] available yet"

## URL для завантаження

Користувачі завантажують файли через захищений URL:
```
/app_gdpr/guide/download/<resource_id>/
```

Доступ контролюється через:
- `@login_required` - тільки авторизовані користувачі
- `@gdpr_access_required()` - користувачі з доступом до GDPR модуля

## Технічні деталі

### Зберігання файлів
- Файли зберігаються в `media/gdpr_resources/YYYY/MM/`
- Автоматична організація по роках та місяцях
- Зберігається оригінальна назва файлу

### Безпека
- Тільки користувачі з `has_access_compliance_dashboard` можуть переглядати Guide
- Файли завантажуються через захищений view (не прямі посилання)
- Перевірка `is_active` перед завантаженням

### Оптимізація
- Ресурси групуються по категоріях одним запитом
- Тільки активні ресурси (`is_active=True`) передаються в контекст
- Сортування за `category`, `order`, `title`

## Підтримка та troubleshooting

### Ресурс не відображається
1. Перевірте, що `is_active = True`
2. Перевірте, що файл завантажений
3. Перевірте, що `resource_id` унікальний
4. Перегляньте логи (`logger.error`)

### Помилка завантаження файлу
1. Перевірте, що файл існує в `media/`
2. Перевірте права доступу до `media/` директорії
3. Перевірте налаштування `MEDIA_ROOT` та `MEDIA_URL` в `settings.py`

### Badge або іконка відображається неправильно
1. Перевірте, що `file_type` відповідає реальному типу файлу
2. Перевірте методи `get_file_icon()` та `get_badge_class()` в моделі

## Розширення функціоналу

### Додавання нових типів файлів

У `models.py` → `GDPRGuide`:
```python
FILE_TYPE_CHOICES = [
    ('pdf', 'PDF'),
    ('docx', 'DOCX'),
    # ... додайте новий тип
    ('pptx', 'PPTX'),
]
```

Також оновіть `get_file_icon()`:
```python
icons = {
    # ...
    'pptx': 'fas fa-file-powerpoint text-danger',
}
```

### Додавання нових категорій

У `models.py` → `GDPRGuide`:
```python
CATEGORY_CHOICES = [
    # ... існуючі категорії
    ('video', _('Video Tutorial')),
]
```

У `views.py` → `GDPRGuideView`:
```python
context['resources_by_category'] = {
    # ...
    'video': resources.filter(category='video'),
}
```

У `gdpr_guide.html` додайте нову картку для категорії.

## Контакти

Для питань та підтримки зверніться до адміністратора системи або команди розробки.

