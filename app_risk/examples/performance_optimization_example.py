# SecBoard/app_risk/examples/performance_optimization_example.py

"""
Приклад використання всіх оптимізацій продуктивності
"""

import asyncio
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.utils import timezone

# Імпорт оптимізованих сервісів
from ..services import (
    # Основні сервіси
    ReportConfig,
    
    # Оптимізовані сервіси
    OptimizedReportDataService,
    get_cache_service,
    get_async_report_service,
    get_pagination_service,
    get_serialization_service,
    get_performance_monitor_service,
    
    # Моніторинг
    performance_monitor,
    start_monitoring,
    add_metric,
    monitor_operation
)


class OptimizedReportController:
    """Контролер для демонстрації оптимізованої генерації звітів"""
    
    def __init__(self):
        # Ініціалізація сервісів
        self.cache_service = get_cache_service()
        self.async_service = get_async_report_service()
        self.pagination_service = get_pagination_service()
        self.serialization_service = get_serialization_service()
        self.performance_service = get_performance_monitor_service()
        
        # Запуск моніторингу
        start_monitoring()
        self.performance_service.start()
    
    @performance_monitor(category="report_generation")
    def generate_optimized_report(self, user: User, report_type: str = "comprehensive") -> dict:
        """
        Генерація оптимізованого звіту з використанням всіх оптимізацій
        """
        
        # 1. Створення конфігурації звіту
        config = ReportConfig(
            user=user,
            report_type=report_type,
            date_range=(
                timezone.now() - timedelta(days=30),
                timezone.now()
            ),
            include_assets=True,
            include_vulnerabilities=True,
            include_treatments=True,
            include_statistics=True,
            format="pdf",
            page_size=100,
            enable_caching=True,
            language="uk"
        )
        
        # 2. Перевірка кешу
        cache_key = f"optimized_report_{config.hash}"
        cached_report = self.cache_service.get(cache_key)
        
        if cached_report:
            add_metric("cache_hit", 1, "count", "report_generation")
            return cached_report
        
        add_metric("cache_miss", 1, "count", "report_generation")
        
        # 3. Використання оптимізованого сервісу даних
        with monitor_operation("data_collection", "report_generation"):
            data_service = OptimizedReportDataService(config)
            
            # Отримання даних з оптимізованими запитами
            report_data = data_service.get_optimized_report_data()
        
        # 4. Пагінація для великих наборів даних
        if len(report_data.get('assets', [])) > 1000:
            with monitor_operation("pagination_setup", "report_generation"):
                paginated_assets = self.pagination_service.paginate_list(
                    report_data['assets'],
                    page_number=1,
                    page_size=config.page_size,
                    cache_prefix=f"report_assets_{config.hash}"
                )
                report_data['assets'] = paginated_assets.items
                report_data['pagination_info'] = paginated_assets.to_dict()['pagination']
        
        # 5. Серіалізація та стиснення
        with monitor_operation("serialization", "report_generation"):
            # Автоматичний вибір оптимального формату
            optimal_config = self.serialization_service.optimize_config_for_data(report_data)
            
            # Серіалізація з оптимальними параметрами
            serialized_data = self.serialization_service.serialize(report_data, optimal_config)
            
            # Збереження в кеші
            self.cache_service.set(
                cache_key, 
                report_data, 
                timeout=1800,  # 30 хвилин
                strategy='compressed'
            )
        
        # 6. Додавання метрик
        add_metric("report_size", len(serialized_data), "bytes", "report_generation")
        add_metric("assets_count", len(report_data.get('assets', [])), "count", "report_generation")
        
        return report_data
    
    async def generate_async_report(self, user: User, report_type: str = "comprehensive") -> str:
        """
        Асинхронна генерація звіту для великих обсягів даних
        """
        
        config = ReportConfig(
            user=user,
            report_type=report_type,
            date_range=(
                timezone.now() - timedelta(days=90),  # Більший період
                timezone.now()
            ),
            include_assets=True,
            include_vulnerabilities=True,
            include_treatments=True,
            include_statistics=True,
            format="excel",
            page_size=1000,
            enable_caching=True,
            language="uk"
        )
        
        # Запуск асинхронного завдання
        job_id = await self.async_service.submit_report_job(
            config=config,
            priority="high",
            notification_methods=["email", "cache"]
        )
        
        return job_id
    
    def get_report_with_streaming(self, user: User, chunk_size: int = 100):
        """
        Генерація звіту з потоковою обробкою (streaming)
        """
        
        config = ReportConfig(
            user=user,
            report_type="streaming",
            date_range=(
                timezone.now() - timedelta(days=365),  # Рік даних
                timezone.now()
            ),
            include_assets=True,
            page_size=chunk_size,
            enable_caching=True
        )
        
        # Створення потокового завантажувача
        data_service = OptimizedReportDataService(config)
        
        def data_loader(page_number: int, page_size: int):
            """Завантаження даних по частинах"""
            return data_service.get_assets_page(page_number, page_size)
        
        def count_loader():
            """Підрахунок загальної кількості"""
            return data_service.get_total_assets_count()
        
        # Використання пагінації для streaming
        pagination_service = self.pagination_service
        
        # Отримання даних частинами
        for chunk in pagination_service.stream_data(data_loader, count_loader(), chunk_size):
            yield chunk
    
    def benchmark_performance(self, user: User) -> dict:
        """
        Бенчмаркінг продуктивності різних підходів
        """
        
        results = {}
        
        # 1. Тест без оптимізацій (симуляція)
        with monitor_operation("benchmark_unoptimized", "benchmarking"):
            # Симуляція повільного запиту
            import time
            time.sleep(2)  # Імітація повільної обробки
            
        # 2. Тест з оптимізаціями
        with monitor_operation("benchmark_optimized", "benchmarking"):
            optimized_report = self.generate_optimized_report(user, "benchmark")
        
        # 3. Тест кешування
        with monitor_operation("benchmark_cached", "benchmarking"):
            cached_report = self.generate_optimized_report(user, "benchmark")  # Має бути закешований
        
        # 4. Отримання метрик
        performance_report = self.performance_service.get_performance_report(
            time_window=timedelta(minutes=5)
        )
        
        results = {
            'timestamp': timezone.now().isoformat(),
            'performance_report': performance_report,
            'cache_stats': self.cache_service.get_cache_stats(),
            'serialization_benchmarks': self.serialization_service.benchmark_formats(
                {'test': 'data'}, iterations=50
            )
        }
        
        return results
    
    def get_system_health(self) -> dict:
        """
        Отримання стану системи та метрик продуктивності
        """
        
        return {
            'timestamp': timezone.now().isoformat(),
            'system_stats': self.performance_service.get_real_time_stats(),
            'cache_health': {
                'strategies': self.cache_service.get_active_strategies(),
                'stats': self.cache_service.get_cache_stats(),
                'memory_usage': self.cache_service.get_memory_usage()
            },
            'async_jobs': {
                'active_jobs': len(self.async_service.get_active_jobs()),
                'queue_size': self.async_service.get_queue_size(),
                'completed_jobs': self.async_service.get_completed_jobs_count()
            },
            'pagination_stats': self.pagination_service.get_pagination_stats()
        }
    
    def cleanup_resources(self):
        """
        Очищення ресурсів та зупинка сервісів
        """
        
        # Очищення кешу
        self.cache_service.clear_expired()
        
        # Зупинка моніторингу
        self.performance_service.stop()
        
        # Очищення метрик
        self.performance_service.clear_metrics()
        
        # Зупинка асинхронних завдань
        self.async_service.shutdown()


# Приклади використання

def example_basic_optimized_report():
    """Базовий приклад оптимізованого звіту"""
    
    # Створення контролера
    controller = OptimizedReportController()
    
    # Отримання користувача (в реальному коді)
    user = User.objects.first()  # Замінити на реального користувача
    
    try:
        # Генерація звіту
        report_data = controller.generate_optimized_report(user, "comprehensive")
        
        print(f"Звіт згенеровано успішно!")
        print(f"Кількість активів: {len(report_data.get('assets', []))}")
        print(f"Статистика: {report_data.get('statistics', {})}")
        
        # Отримання стану системи
        health = controller.get_system_health()
        print(f"Стан системи: {health}")
        
    finally:
        # Очищення ресурсів
        controller.cleanup_resources()


async def example_async_report():
    """Приклад асинхронного звіту"""
    
    controller = OptimizedReportController()
    user = User.objects.first()
    
    try:
        # Запуск асинхронного завдання
        job_id = await controller.generate_async_report(user, "comprehensive")
        print(f"Асинхронне завдання запущено: {job_id}")
        
        # Відстеження прогресу
        while True:
            job_status = await controller.async_service.get_job_status(job_id)
            print(f"Прогрес: {job_status.progress}%")
            
            if job_status.status.value in ['completed', 'failed']:
                break
            
            await asyncio.sleep(1)
        
        if job_status.status.value == 'completed':
            result = await controller.async_service.get_job_result(job_id)
            print(f"Звіт завершено: {result}")
        
    finally:
        controller.cleanup_resources()


def example_streaming_report():
    """Приклад потокового звіту"""
    
    controller = OptimizedReportController()
    user = User.objects.first()
    
    try:
        print("Початок потокової обробки...")
        
        chunk_count = 0
        total_items = 0
        
        # Обробка даних частинами
        for chunk in controller.get_report_with_streaming(user, chunk_size=50):
            chunk_count += 1
            total_items += len(chunk)
            
            print(f"Оброблено частину {chunk_count}, елементів: {len(chunk)}")
            
            # Тут можна обробляти кожну частину окремо
            # Наприклад, записувати в файл, відправляти по мережі тощо
        
        print(f"Потокова обробка завершена. Всього частин: {chunk_count}, елементів: {total_items}")
        
    finally:
        controller.cleanup_resources()


def example_performance_benchmark():
    """Приклад бенчмаркінгу продуктивності"""
    
    controller = OptimizedReportController()
    user = User.objects.first()
    
    try:
        print("Запуск бенчмаркінгу...")
        
        # Виконання бенчмарку
        results = controller.benchmark_performance(user)
        
        print("Результати бенчмаркінгу:")
        print(f"Аналіз запитів: {results['performance_report']['query_analysis']}")
        print(f"Аналіз функцій: {results['performance_report']['function_analysis']}")
        print(f"Системні ресурси: {results['performance_report']['system_analysis']}")
        
        # Статистика кешування
        cache_stats = results['cache_stats']
        print(f"Кеш - попадання: {cache_stats['hit_count']}, промахи: {cache_stats['miss_count']}")
        
        # Бенчмарк серіалізації
        serialization_benchmarks = results['serialization_benchmarks']
        for format_name, stats in serialization_benchmarks.items():
            print(f"{format_name}: {stats['total_time']:.4f}s, розмір: {stats['serialized_size']} bytes")
        
    finally:
        controller.cleanup_resources()


if __name__ == "__main__":
    # Запуск прикладів
    print("=== Базовий оптимізований звіт ===")
    example_basic_optimized_report()
    
    print("\n=== Потоковий звіт ===")
    example_streaming_report()
    
    print("\n=== Бенчмаркінг продуктивності ===")
    example_performance_benchmark()
    
    # Для асинхронного прикладу потрібно запустити в async контексті
    print("\n=== Асинхронний звіт ===")
    print("Для запуску: asyncio.run(example_async_report())")