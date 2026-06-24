# Risk Report Services - Архітектурні покращення

## Огляд

Цей пакет містить рефакторизовані сервіси для генерації звітів з ризиків, які забезпечують:

- **Розділення відповідальностей** - кожен сервіс має чітко визначену роль
- **Модульність** - компоненти можна легко замінювати та тестувати
- **Масштабованість** - легко додавати нові формати та типи звітів
- **Кешування** - оптимізація продуктивності через кешування даних
- **Валідацію** - комплексна перевірка конфігурації та даних

## Структура сервісів

### 1. ReportConfig (`report_config.py`)
**Призначення**: Конфігурація звітів з валідацією та серіалізацією

**Ключові можливості**:
- Dataclass для типобезпечної конфігурації
- Автоматична валідація параметрів
- Серіалізація в/з JSON та Django request
- Генерація хешів для кешування
- Підтримка багатомовності

**Приклад використання**:
```python
config = ReportConfig(
    report_type='full',
    format='pdf',
    language='uk',
    start_date=datetime.now().date() - timedelta(days=30),
    end_date=datetime.now().date()
)

# Створення з request
config = ReportConfig.from_request(request)

# Валідація
errors = config.validate()
```

### 2. ReportDataService (`report_data_service.py`)
**Призначення**: Оптимізоване отримання та обробка даних для звітів

**Ключові можливості**:
- Оптимізовані запити з prefetch_related
- Кешування результатів
- Агрегація статистики
- Розрахунок compliance метрик
- Фільтрація по компаніях та датах

**Приклад використання**:
```python
data_service = ReportDataService(user, config)

# Швидкі статистики
quick_stats = data_service.get_quick_statistics()

# Повні дані для звіту
comprehensive_data = data_service.get_comprehensive_report_data()
```

### 3. ReportGeneratorFactory (`report_generator_factory.py`)
**Призначення**: Фабрика для створення генераторів різних форматів

**Підтримувані формати**:
- **PDF** - ReportLab або WeasyPrint
- **Word** - python-docx
- **Excel** - xlsxwriter

**Ключові можливості**:
- Автоматичний вибір доступного генератора
- Перевірка залежностей
- Розширюваність для нових форматів
- Уніфікований інтерфейс

**Приклад використання**:
```python
# Створення генератора
generator = ReportGeneratorFactory.create_generator(config, data_service)

# Генерація звіту
result = generator.generate()

# Перевірка доступності формату
is_available = ReportGeneratorFactory.is_format_available('pdf')
```

### 4. ReportValidators (`report_validators.py`)
**Призначення**: Комплексна валідація конфігурації та даних

**Типи валідації**:
- Базова валідація параметрів
- Перевірка прав доступу
- Валідація доступності форматів
- Бізнес-правила
- Перевірка цілісності даних

**Приклад використання**:
```python
validator = ReportConfigValidator(config, user)
result = validator.validate()

if not result['is_valid']:
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")
```

### 5. ReportService (`report_service.py`)
**Призначення**: Головний сервіс для управління генерацією звітів

**Ключові можливості**:
- Координація всіх інших сервісів
- Обробка помилок та логування
- Генерація HTTP відповідей
- Попередній перегляд звітів
- Управління шаблонами

**Приклад використання**:
```python
report_service = ReportService(user)

# Генерація звіту
result = report_service.generate_report(config)

# Попередній перегляд
preview = report_service.get_report_preview(config)

# HTTP відповідь
response = report_service.generate_report_response(config)
```

## Переваги нової архітектури

### 1. **Продуктивність**
- Оптимізовані SQL запити з prefetch_related
- Кешування даних та результатів
- Ліниве завантаження великих наборів даних
- Паралельна обробка де можливо

### 2. **Надійність**
- Комплексна валідація на всіх рівнях
- Обробка помилок з детальним логуванням
- Перевірка залежностей перед генерацією
- Graceful degradation при недоступності форматів

### 3. **Розширюваність**
- Легко додавати нові формати через фабрику
- Модульна структура дозволяє заміну компонентів
- Підтримка кастомних валідаторів
- Розширювані шаблони звітів

### 4. **Тестованість**
- Кожен сервіс можна тестувати незалежно
- Мокування залежностей
- Чіткі інтерфейси між компонентами
- Тестування різних сценаріїв

### 5. **Підтримуваність**
- Чіткий розподіл відповідальностей
- Документований код
- Типізація для кращого IDE підтримки
- Консистентні патерни

## Міграція з старого коду

### Крок 1: Поступове впровадження
```python
# Старий код
from .report_views import generate_risk_report_old

# Новий код
from .services.report_service import ReportService
from .services.report_config import ReportConfig
```

### Крок 2: Використання нових views
```python
# В urls.py
from .views.report_views_refactored import ReportGenerationView

urlpatterns = [
    path('reports/generate/', ReportGenerationView.as_view(), name='generate_report'),
    # Або для зворотної сумісності
    path('reports/legacy/', generate_risk_report, name='generate_report_legacy'),
]
```

### Крок 3: Оновлення шаблонів
```html
<!-- Нові AJAX endpoints -->
<script>
fetch('/api/reports/preview/', {
    method: 'POST',
    body: JSON.stringify(config),
    headers: {'Content-Type': 'application/json'}
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        showPreview(data.preview);
    }
});
</script>
```

## Конфігурація та налаштування

### Налаштування кешування
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'TIMEOUT': 300,  # 5 хвилин для звітних даних
    }
}
```

### Налаштування логування
```python
LOGGING = {
    'loggers': {
        'app_risk.services': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### Встановлення залежностей
```bash
# PDF генерація
pip install reportlab
# або
pip install weasyprint

# Word документи
pip install python-docx

# Excel файли
pip install xlsxwriter
# або
pip install openpyxl
```

## Приклади використання

Дивіться файл `examples/service_usage_example.py` для детальних прикладів використання всіх сервісів.

## Тестування

```python
# Тестування конфігурації
def test_report_config():
    config = ReportConfig(report_type='full', format='pdf')
    assert config.is_valid()

# Тестування генерації
def test_report_generation():
    service = ReportService(user)
    result = service.generate_report(config)
    assert result['success']
```

## Моніторинг та метрики

Сервіси автоматично логують:
- Час генерації звітів
- Помилки та попередження
- Статистики використання
- Продуктивність запитів

## Підтримка

Для питань та пропозицій щодо покращення архітектури звертайтесь до команди розробки. 