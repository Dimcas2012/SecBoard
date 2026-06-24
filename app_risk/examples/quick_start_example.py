# SecBoard/app_risk/examples/quick_start_example.py

"""
Швидкий старт з кешуванням та асинхронною обробкою
==================================================

Цей файл демонструє основні можливості інтегрованої системи
кешування та асинхронної обробки для звітів SecBoard.
"""

import asyncio
import time
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.utils import timezone

# Імпорт оптимізованих сервісів
from app_risk.views_optimized import OptimizedReportController
from app_risk.tasks import submit_async_report_task, get_task_status
from app_risk.services import (
    get_cache_service,
    get_async_report_service,
    get_performance_monitor_service,
    ReportConfig
)


def demo_basic_caching():
    """Демонстрація базового кешування"""
    
    print("=== Демонстрація базового кешування ===")
    
    # Створення контролера
    controller = OptimizedReportController()
    
    # Отримання користувача (замініть на реального користувача)
    user = User.objects.first()
    if not user:
        print("Помилка: Користувач не знайдений")
        return
    
    # Параметри звіту
    params = {
        'reportType': 'summary',
        'format': 'pdf',
        'language': 'uk',
        'company_id': '',
        'startDate': '2023-01-01',
        'endDate': '2024-01-01'
    }
    
    # Перша генерація (без кешу)
    print("1. Перша генерація звіту (без кешу)...")
    start_time = time.time()
    
    report_data = controller.generate_optimized_report_data(user, params)
    
    first_generation_time = time.time() - start_time
    print(f"   Час генерації: {first_generation_time:.2f} сек")
    print(f"   Розмір даних: {len(str(report_data))} символів")
    
    # Друга генерація (з кешу)
    print("\n2. Друга генерація звіту (з кешу)...")
    start_time = time.time()
    
    cached_report_data = controller.generate_optimized_report_data(user, params)
    
    second_generation_time = time.time() - start_time
    print(f"   Час генерації: {second_generation_time:.2f} сек")
    print(f"   Прискорення: {first_generation_time/second_generation_time:.1f}x")
    
    # Статистика кешу
    cache_service = get_cache_service()
    stats = cache_service.get_cache_stats()
    
    print(f"\n3. Статистика кешу:")
    print(f"   Коефіцієнт попадання: {stats.get('hit_rate', 0):.1f}%")
    print(f"   Загальна кількість запитів: {stats.get('total_requests', 0)}")
    print(f"   Кількість кешованих елементів: {stats.get('cached_items', 0)}")


def demo_async_processing():
    """Демонстрація асинхронної обробки"""
    
    print("\n=== Демонстрація асинхронної обробки ===")
    
    # Отримання користувача
    user = User.objects.first()
    if not user:
        print("Помилка: Користувач не знайдений")
        return
    
    # Параметри для великого звіту
    params = {
        'reportType': 'full',
        'format': 'pdf',
        'language': 'uk',
        'company_id': '',
        'startDate': '2023-01-01',
        'endDate': '2024-01-01',
        'include_assets': True,
        'include_vulnerabilities': True,
        'include_treatments': True,
        'include_statistics': True
    }
    
    # Запуск асинхронного завдання
    print("1. Запуск асинхронного завдання...")
    
    job_id = submit_async_report_task(
        user_id=user.id,
        config_data=params,
        notify_email=False,
        priority='normal'
    )
    
    print(f"   Job ID: {job_id}")
    
    # Відстеження прогресу
    print("\n2. Відстеження прогресу:")
    
    max_wait_time = 60  # максимум 60 секунд
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        status = get_task_status(job_id)
        
        if status:
            print(f"   Статус: {status.get('status', 'unknown')}")
            print(f"   Прогрес: {status.get('progress', 0)}%")
            
            if status.get('status') in ['completed', 'failed']:
                break
        
        time.sleep(2)  # Перевірка кожні 2 секунди
    
    # Фінальний статус
    final_status = get_task_status(job_id)
    if final_status:
        print(f"\n3. Фінальний результат:")
        print(f"   Статус: {final_status.get('status', 'unknown')}")
        
        if final_status.get('status') == 'completed':
            result = final_status.get('result', {})
            print(f"   Файл: {result.get('file_path', 'не знайдено')}")
            print(f"   Розмір: {result.get('file_size', 0)} байт")
        elif final_status.get('status') == 'failed':
            print(f"   Помилка: {final_status.get('error', 'невідома помилка')}")


def demo_performance_monitoring():
    """Демонстрація моніторингу продуктивності"""
    
    print("\n=== Демонстрація моніторингу продуктивності ===")
    
    # Отримання сервісу моніторингу
    performance_service = get_performance_monitor_service()
    
    # Запуск моніторингу
    performance_service.start()
    
    # Симуляція деякої роботи
    print("1. Симуляція роботи системи...")
    
    for i in range(5):
        # Симуляція генерації звіту
        start_time = time.time()
        time.sleep(0.5)  # Імітація роботи
        duration = time.time() - start_time
        
        # Додавання метрик
        performance_service.add_metric(
            "report_generation_time",
            duration,
            "seconds",
            "report_generation"
        )
        
        print(f"   Звіт {i+1} згенеровано за {duration:.2f} сек")
    
    # Отримання звіту про продуктивність
    print("\n2. Звіт про продуктивність:")
    
    performance_report = performance_service.get_performance_report(
        time_window=timedelta(minutes=5)
    )
    
    print(f"   Загальна кількість метрик: {len(performance_report.get('metrics', []))}")
    print(f"   Середній час генерації: {performance_report.get('avg_generation_time', 0):.2f} сек")
    print(f"   Використання пам'яті: {performance_report.get('memory_usage', 0):.1f}%")
    print(f"   Використання CPU: {performance_report.get('cpu_usage', 0):.1f}%")


def demo_cache_strategies():
    """Демонстрація різних стратегій кешування"""
    
    print("\n=== Демонстрація стратегій кешування ===")
    
    cache_service = get_cache_service()
    
    # Тестові дані
    test_data = {
        'small_data': 'Це невеликі дані для тестування',
        'medium_data': 'Це середні дані для тестування ' * 100,
        'large_data': 'Це великі дані для тестування ' * 1000
    }
    
    strategies = ['lru', 'ttl', 'compressed']
    
    for strategy in strategies:
        print(f"\n{strategy.upper()} стратегія:")
        
        for data_type, data in test_data.items():
            key = f"test_{strategy}_{data_type}"
            
            # Збереження в кеш
            start_time = time.time()
            cache_service.set(key, data, timeout=300, strategy=strategy)
            save_time = time.time() - start_time
            
            # Отримання з кешу
            start_time = time.time()
            cached_data = cache_service.get(key)
            get_time = time.time() - start_time
            
            print(f"   {data_type}: збереження {save_time*1000:.2f}мс, отримання {get_time*1000:.2f}мс")
            
            # Перевірка цілісності
            if cached_data == data:
                print(f"   ✓ Дані збережено коректно")
            else:
                print(f"   ✗ Помилка збереження даних")


def demo_comprehensive_example():
    """Комплексний приклад використання всіх функцій"""
    
    print("\n=== Комплексний приклад ===")
    
    # Отримання користувача
    user = User.objects.first()
    if not user:
        print("Помилка: Користувач не знайдений")
        return
    
    # Створення конфігурації звіту
    config = ReportConfig(
        user=user,
        report_type='full',
        format='pdf',
        language='uk',
        company_id=None,
        notes='Тестовий звіт для демонстрації',
        date_range=(
            timezone.now().date() - timedelta(days=365),
            timezone.now().date()
        ),
        include_assets=True,
        include_vulnerabilities=True,
        include_treatments=True,
        include_statistics=True,
        enable_caching=True
    )
    
    print(f"1. Конфігурація звіту створена:")
    print(f"   Тип: {config.report_type}")
    print(f"   Формат: {config.format}")
    print(f"   Мова: {config.language}")
    print(f"   Період: {config.date_range[0]} - {config.date_range[1]}")
    print(f"   Кешування: {'увімкнено' if config.enable_caching else 'вимкнено'}")
    
    # Використання всіх сервісів разом
    controller = OptimizedReportController()
    
    # Генерація звіту з повним моніторингом
    print(f"\n2. Генерація звіту з повним моніторингом...")
    
    start_time = time.time()
    
    try:
        # Конвертація конфігурації в параметри
        params = {
            'reportType': config.report_type,
            'format': config.format,
            'language': config.language,
            'company_id': config.company_id,
            'notes': config.notes,
            'startDate': config.date_range[0].isoformat(),
            'endDate': config.date_range[1].isoformat(),
        }
        
        report_data = controller.generate_optimized_report_data(user, params)
        
        generation_time = time.time() - start_time
        
        print(f"   ✓ Звіт згенеровано успішно")
        print(f"   Час генерації: {generation_time:.2f} сек")
        print(f"   Розмір даних: {len(str(report_data))} символів")
        
        # Статистика
        cache_service = get_cache_service()
        cache_stats = cache_service.get_cache_stats()
        
        print(f"\n3. Підсумкова статистика:")
        print(f"   Коефіцієнт попадання в кеш: {cache_stats.get('hit_rate', 0):.1f}%")
        print(f"   Кешованих елементів: {cache_stats.get('cached_items', 0)}")
        print(f"   Загальна продуктивність: {'відмінна' if generation_time < 2 else 'добра' if generation_time < 5 else 'потребує оптимізації'}")
        
    except Exception as e:
        print(f"   ✗ Помилка генерації: {str(e)}")


def main():
    """Головна функція для запуску всіх демонстрацій"""
    
    print("Демонстрація можливостей кешування та асинхронної обробки SecBoard")
    print("=" * 70)
    
    try:
        # Перевірка наявності користувачів
        if not User.objects.exists():
            print("Помилка: У системі немає користувачів.")
            print("Створіть користувача через Django admin або команду createsuperuser")
            return
        
        # Запуск демонстрацій
        demo_basic_caching()
        demo_cache_strategies()
        demo_performance_monitoring()
        demo_comprehensive_example()
        
        # Асинхронна демонстрація (опційно)
        try_async = input("\nЗапустити демонстрацію асинхронної обробки? (y/N): ")
        if try_async.lower() == 'y':
            demo_async_processing()
        
        print("\n" + "=" * 70)
        print("Демонстрація завершена!")
        print("\nДля інтеграції в ваш проект:")
        print("1. Встановіть залежності: pip install celery redis django-redis")
        print("2. Налаштуйте Redis та Celery у settings.py")
        print("3. Запустіть Celery worker: celery -A SecBoard worker")
        print("4. Використовуйте оптимізовані view: /app_risk/reports/generate-optimized/")
        
    except Exception as e:
        print(f"Помилка під час демонстрації: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Для запуску з Django shell:
    # python manage.py shell
    # >>> exec(open('app_risk/examples/quick_start_example.py').read())
    
    main()