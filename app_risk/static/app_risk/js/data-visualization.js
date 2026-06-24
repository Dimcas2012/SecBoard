/**
 * SecBoard Risk Reports - Data Visualization
 * Enhanced charts, graphs, and interactive data displays
 */

class DataVisualization {
    constructor() {
        this.charts = new Map();
        this.themes = {
            light: {
                backgroundColor: '#ffffff',
                textColor: '#334155',
                gridColor: '#e2e8f0',
                primaryColor: '#2563eb',
                secondaryColor: '#64748b',
                successColor: '#16a34a',
                warningColor: '#d97706',
                errorColor: '#dc2626'
            },
            dark: {
                backgroundColor: '#1e293b',
                textColor: '#f1f5f9',
                gridColor: '#475569',
                primaryColor: '#60a5fa',
                secondaryColor: '#94a3b8',
                successColor: '#4ade80',
                warningColor: '#fbbf24',
                errorColor: '#f87171'
            }
        };
        this.init();
    }

    init() {
        this.loadChartLibraries();
        this.setupChartDefaults();
        this.initializeCharts();
        this.setupEventListeners();
    }

    loadChartLibraries() {
        // Load Chart.js if not already loaded
        if (typeof Chart === 'undefined') {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
            script.onload = () => this.setupChartDefaults();
            document.head.appendChild(script);
        }
    }

    setupChartDefaults() {
        if (typeof Chart === 'undefined') return;

        const currentTheme = this.getCurrentTheme();
        
        Chart.defaults.font.family = 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif';
        Chart.defaults.font.size = 12;
        Chart.defaults.color = currentTheme.textColor;
        Chart.defaults.backgroundColor = currentTheme.backgroundColor;
        Chart.defaults.borderColor = currentTheme.gridColor;
        Chart.defaults.plugins.legend.labels.usePointStyle = true;
        Chart.defaults.plugins.legend.labels.padding = 20;
        Chart.defaults.elements.point.radius = 4;
        Chart.defaults.elements.point.hoverRadius = 6;
        Chart.defaults.elements.line.tension = 0.4;
        Chart.defaults.elements.bar.borderRadius = 4;
        Chart.defaults.scales.linear.grid.color = currentTheme.gridColor;
        Chart.defaults.scales.category.grid.color = currentTheme.gridColor;
    }

    getCurrentTheme() {
        const theme = document.documentElement.getAttribute('data-theme') || 'light';
        return this.themes[theme];
    }

    initializeCharts() {
        // Initialize all charts on page load
        this.initRiskOverviewChart();
        this.initComplianceChart();
        this.initTrendChart();
        this.initHeatmapChart();
        this.initGaugeChart();
        this.initRadarChart();
        this.initTreemapChart();
        this.initTimelineChart();
    }

    // ===== RISK OVERVIEW DOUGHNUT CHART =====
    initRiskOverviewChart() {
        const canvas = document.getElementById('riskOverviewChart');
        if (!canvas) return;

        const theme = this.getCurrentTheme();
        const data = {
            labels: ['Критичні', 'Високі', 'Середні', 'Низькі'],
            datasets: [{
                data: [12, 28, 45, 89],
                backgroundColor: [
                    theme.errorColor,
                    theme.warningColor,
                    theme.primaryColor,
                    theme.successColor
                ],
                borderWidth: 0,
                hoverOffset: 8
            }]
        };

        const config = {
            type: 'doughnut',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            generateLabels: (chart) => {
                                const data = chart.data;
                                return data.labels.map((label, index) => ({
                                    text: `${label}: ${data.datasets[0].data[index]}`,
                                    fillStyle: data.datasets[0].backgroundColor[index],
                                    strokeStyle: data.datasets[0].backgroundColor[index],
                                    lineWidth: 0,
                                    pointStyle: 'circle'
                                }));
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed * 100) / total).toFixed(1);
                                return `${context.label}: ${context.parsed} (${percentage}%)`;
                            }
                        }
                    }
                },
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 1000,
                    easing: 'easeInOutQuart'
                }
            }
        };

        this.charts.set('riskOverview', new Chart(canvas, config));
    }

    // ===== COMPLIANCE PROGRESS CHART =====
    initComplianceChart() {
        const canvas = document.getElementById('complianceChart');
        if (!canvas) return;

        const theme = this.getCurrentTheme();
        const data = {
            labels: ['ISO 27001', 'PCI DSS', 'GDPR', 'SOX', 'HIPAA'],
            datasets: [{
                label: 'Виконано',
                data: [85, 92, 78, 95, 88],
                backgroundColor: theme.successColor,
                borderColor: theme.successColor,
                borderWidth: 2,
                borderRadius: 6,
                borderSkipped: false
            }, {
                label: 'Залишилось',
                data: [15, 8, 22, 5, 12],
                backgroundColor: theme.gridColor,
                borderColor: theme.gridColor,
                borderWidth: 2,
                borderRadius: 6,
                borderSkipped: false
            }]
        };

        const config = {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        stacked: true,
                        grid: {
                            display: false
                        },
                        ticks: {
                            callback: (value) => `${value}%`
                        }
                    },
                    y: {
                        stacked: true,
                        grid: {
                            display: false
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${context.parsed.x}%`
                        }
                    }
                },
                animation: {
                    duration: 1200,
                    easing: 'easeInOutQuart'
                }
            }
        };

        this.charts.set('compliance', new Chart(canvas, config));
    }

    // ===== TREND LINE CHART =====
    initTrendChart() {
        const canvas = document.getElementById('trendChart');
        if (!canvas) return;

        const theme = this.getCurrentTheme();
        const months = ['Січ', 'Лют', 'Бер', 'Кві', 'Тра', 'Чер', 'Лип', 'Сер', 'Вер', 'Жов', 'Лис', 'Гру'];
        
        const data = {
            labels: months,
            datasets: [{
                label: 'Нові ризики',
                data: [12, 19, 8, 15, 22, 18, 25, 20, 16, 14, 18, 12],
                borderColor: theme.errorColor,
                backgroundColor: theme.errorColor + '20',
                fill: true,
                tension: 0.4,
                pointBackgroundColor: theme.errorColor,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 8
            }, {
                label: 'Закриті ризики',
                data: [8, 15, 12, 18, 20, 22, 28, 25, 24, 22, 20, 18],
                borderColor: theme.successColor,
                backgroundColor: theme.successColor + '20',
                fill: true,
                tension: 0.4,
                pointBackgroundColor: theme.successColor,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 8
            }]
        };

        const config = {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    x: {
                        display: true,
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        display: true,
                        beginAtZero: true,
                        grid: {
                            color: theme.gridColor
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        align: 'end'
                    },
                    tooltip: {
                        backgroundColor: theme.backgroundColor,
                        titleColor: theme.textColor,
                        bodyColor: theme.textColor,
                        borderColor: theme.gridColor,
                        borderWidth: 1
                    }
                },
                animation: {
                    duration: 1500,
                    easing: 'easeInOutQuart'
                }
            }
        };

        this.charts.set('trend', new Chart(canvas, config));
    }

    // ===== RISK HEATMAP =====
    initHeatmapChart() {
        const canvas = document.getElementById('heatmapChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const theme = this.getCurrentTheme();
        
        // Generate heatmap data
        const heatmapData = this.generateHeatmapData();
        
        // Custom heatmap drawing
        this.drawHeatmap(ctx, heatmapData, theme);
    }

    generateHeatmapData() {
        const data = [];
        const categories = ['Фінанси', 'IT', 'Операції', 'Комплаєнс', 'HR'];
        const impacts = ['Низький', 'Середній', 'Високий', 'Критичний'];
        
        for (let i = 0; i < categories.length; i++) {
            for (let j = 0; j < impacts.length; j++) {
                data.push({
                    category: categories[i],
                    impact: impacts[j],
                    value: Math.floor(Math.random() * 20) + 1,
                    x: i,
                    y: j
                });
            }
        }
        
        return data;
    }

    drawHeatmap(ctx, data, theme) {
        const canvas = ctx.canvas;
        const padding = 60;
        const cellWidth = (canvas.width - padding * 2) / 5;
        const cellHeight = (canvas.height - padding * 2) / 4;
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw cells
        data.forEach(item => {
            const x = padding + item.x * cellWidth;
            const y = padding + item.y * cellHeight;
            
            // Calculate color intensity
            const intensity = item.value / 20;
            const color = this.interpolateColor(theme.primaryColor, theme.errorColor, intensity);
            
            // Draw cell
            ctx.fillStyle = color;
            ctx.fillRect(x, y, cellWidth - 2, cellHeight - 2);
            
            // Draw value
            ctx.fillStyle = intensity > 0.5 ? '#ffffff' : theme.textColor;
            ctx.font = '12px Inter';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(item.value, x + cellWidth / 2, y + cellHeight / 2);
        });
        
        // Draw labels
        ctx.fillStyle = theme.textColor;
        ctx.font = '11px Inter';
        ctx.textAlign = 'center';
        
        // Category labels
        ['Фінанси', 'IT', 'Операції', 'Комплаєнс', 'HR'].forEach((label, i) => {
            ctx.fillText(label, padding + i * cellWidth + cellWidth / 2, padding - 20);
        });
        
        // Impact labels
        ctx.textAlign = 'right';
        ['Низький', 'Середній', 'Високий', 'Критичний'].forEach((label, i) => {
            ctx.fillText(label, padding - 10, padding + i * cellHeight + cellHeight / 2);
        });
    }

    interpolateColor(color1, color2, factor) {
        const c1 = this.hexToRgb(color1);
        const c2 = this.hexToRgb(color2);
        
        const r = Math.round(c1.r + (c2.r - c1.r) * factor);
        const g = Math.round(c1.g + (c2.g - c1.g) * factor);
        const b = Math.round(c1.b + (c2.b - c1.b) * factor);
        
        return `rgb(${r}, ${g}, ${b})`;
    }

    hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    }

    // ===== GAUGE CHART =====
    initGaugeChart() {
        const canvas = document.getElementById('gaugeChart');
        if (!canvas) return;

        const theme = this.getCurrentTheme();
        const value = 75; // Risk score
        
        const data = {
            datasets: [{
                data: [value, 100 - value],
                backgroundColor: [
                    this.getGaugeColor(value, theme),
                    theme.gridColor
                ],
                borderWidth: 0,
                circumference: 180,
                rotation: 270,
                cutout: '75%'
            }]
        };

        const config = {
            type: 'doughnut',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: false
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeInOutQuart'
                }
            },
            plugins: [{
                id: 'gaugeText',
                beforeDraw: (chart) => {
                    const ctx = chart.ctx;
                    const centerX = chart.chartArea.left + (chart.chartArea.right - chart.chartArea.left) / 2;
                    const centerY = chart.chartArea.top + (chart.chartArea.bottom - chart.chartArea.top) / 2;
                    
                    ctx.save();
                    ctx.font = 'bold 24px Inter';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = theme.textColor;
                    ctx.fillText(`${value}%`, centerX, centerY - 10);
                    
                    ctx.font = '12px Inter';
                    ctx.fillText('Рівень ризику', centerX, centerY + 15);
                    ctx.restore();
                }
            }]
        };

        this.charts.set('gauge', new Chart(canvas, config));
    }

    getGaugeColor(value, theme) {
        if (value <= 25) return theme.successColor;
        if (value <= 50) return theme.warningColor;
        if (value <= 75) return theme.primaryColor;
        return theme.errorColor;
    }

    // ===== RADAR CHART =====
    initRadarChart() {
        const canvas = document.getElementById('radarChart');
        if (!canvas) return;

        const theme = this.getCurrentTheme();
        const data = {
            labels: ['Технічні', 'Операційні', 'Фінансові', 'Стратегічні', 'Комплаєнс', 'Репутаційні'],
            datasets: [{
                label: 'Поточний стан',
                data: [85, 70, 90, 65, 80, 75],
                backgroundColor: theme.primaryColor + '20',
                borderColor: theme.primaryColor,
                borderWidth: 2,
                pointBackgroundColor: theme.primaryColor,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6
            }, {
                label: 'Цільовий стан',
                data: [95, 85, 95, 80, 90, 85],
                backgroundColor: theme.successColor + '20',
                borderColor: theme.successColor,
                borderWidth: 2,
                borderDash: [5, 5],
                pointBackgroundColor: theme.successColor,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        };

        const config = {
            type: 'radar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        grid: {
                            color: theme.gridColor
                        },
                        angleLines: {
                            color: theme.gridColor
                        },
                        pointLabels: {
                            color: theme.textColor,
                            font: {
                                size: 11
                            }
                        },
                        ticks: {
                            display: false
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                animation: {
                    duration: 1500,
                    easing: 'easeInOutQuart'
                }
            }
        };

        this.charts.set('radar', new Chart(canvas, config));
    }

    // ===== TREEMAP CHART =====
    initTreemapChart() {
        const canvas = document.getElementById('treemapChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const theme = this.getCurrentTheme();
        
        const data = [
            { name: 'Кіберзагрози', value: 35, color: theme.errorColor },
            { name: 'Операційні ризики', value: 25, color: theme.warningColor },
            { name: 'Фінансові ризики', value: 20, color: theme.primaryColor },
            { name: 'Комплаєнс', value: 15, color: theme.successColor },
            { name: 'Інші', value: 5, color: theme.secondaryColor }
        ];

        this.drawTreemap(ctx, data, theme);
    }

    drawTreemap(ctx, data, theme) {
        const canvas = ctx.canvas;
        const total = data.reduce((sum, item) => sum + item.value, 0);
        
        let x = 0;
        let y = 0;
        const padding = 2;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = '12px Inter';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        data.forEach(item => {
            const width = (item.value / total) * canvas.width;
            const height = canvas.height;
            
            // Draw rectangle
            ctx.fillStyle = item.color;
            ctx.fillRect(x + padding, y + padding, width - padding * 2, height - padding * 2);
            
            // Draw text
            ctx.fillStyle = '#ffffff';
            ctx.fillText(item.name, x + width / 2, y + height / 2 - 10);
            ctx.fillText(`${item.value}%`, x + width / 2, y + height / 2 + 10);
            
            x += width;
        });
    }

    // ===== TIMELINE CHART =====
    initTimelineChart() {
        const canvas = document.getElementById('timelineChart');
        if (!canvas) return;

        const theme = this.getCurrentTheme();
        const events = [
            { date: '2024-01-15', title: 'Виявлено критичну вразливість', type: 'critical' },
            { date: '2024-02-03', title: 'Впроваджено нові контролі', type: 'success' },
            { date: '2024-02-20', title: 'Проведено аудит безпеки', type: 'info' },
            { date: '2024-03-10', title: 'Оновлено політики безпеки', type: 'warning' },
            { date: '2024-03-25', title: 'Завершено навчання персоналу', type: 'success' }
        ];

        const data = {
            labels: events.map(e => e.date),
            datasets: [{
                label: 'Події',
                data: events.map((e, i) => ({ x: e.date, y: i + 1 })),
                backgroundColor: events.map(e => this.getEventColor(e.type, theme)),
                borderColor: events.map(e => this.getEventColor(e.type, theme)),
                borderWidth: 2,
                pointRadius: 8,
                pointHoverRadius: 10,
                showLine: true,
                fill: false
            }]
        };

        const config = {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'day',
                            displayFormats: {
                                day: 'MMM DD'
                            }
                        },
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        display: false,
                        min: 0,
                        max: events.length + 1
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            title: (context) => {
                                const index = context[0].dataIndex;
                                return events[index].title;
                            },
                            label: (context) => {
                                const index = context.dataIndex;
                                return events[index].date;
                            }
                        }
                    }
                },
                animation: {
                    duration: 1800,
                    easing: 'easeInOutQuart'
                }
            }
        };

        this.charts.set('timeline', new Chart(canvas, config));
    }

    getEventColor(type, theme) {
        const colors = {
            critical: theme.errorColor,
            success: theme.successColor,
            warning: theme.warningColor,
            info: theme.primaryColor
        };
        return colors[type] || theme.secondaryColor;
    }

    // ===== INTERACTIVE FEATURES =====
    setupEventListeners() {
        // Theme change listener
        document.addEventListener('ui:themeChanged', () => {
            this.updateChartsTheme();
        });

        // Window resize listener
        window.addEventListener('resize', this.debounce(() => {
            this.resizeCharts();
        }, 250));

        // Chart interaction listeners
        this.setupChartInteractions();
    }

    setupChartInteractions() {
        // Add click handlers for charts
        this.charts.forEach((chart, key) => {
            chart.options.onClick = (event, elements) => {
                if (elements.length > 0) {
                    this.handleChartClick(key, elements[0], chart);
                }
            };
        });
    }

    handleChartClick(chartKey, element, chart) {
        const data = chart.data;
        const datasetIndex = element.datasetIndex;
        const dataIndex = element.index;
        
        // Get clicked data
        const clickedData = {
            chart: chartKey,
            dataset: data.datasets[datasetIndex],
            label: data.labels[dataIndex],
            value: data.datasets[datasetIndex].data[dataIndex]
        };
        
        // Dispatch custom event
        const event = new CustomEvent('chartClicked', { detail: clickedData });
        document.dispatchEvent(event);
        
        // Show details modal or update other charts
        this.showChartDetails(clickedData);
    }

    showChartDetails(data) {
        // Create or update details modal
        const modal = document.getElementById('chartDetailsModal') || this.createDetailsModal();
        const content = modal.querySelector('.modal-body');
        
        content.innerHTML = `
            <h5>Деталі: ${data.label}</h5>
            <p><strong>Значення:</strong> ${data.value}</p>
            <p><strong>Діаграма:</strong> ${data.chart}</p>
            <p><strong>Набір даних:</strong> ${data.dataset.label}</p>
        `;
        
        // Show modal
        if (window.UI) {
            window.UI.openModal(modal);
        }
    }

    createDetailsModal() {
        const modal = document.createElement('div');
        modal.id = 'chartDetailsModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h4>Деталі діаграми</h4>
                    <button class="modal-close" data-modal-close>&times;</button>
                </div>
                <div class="modal-body"></div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" data-modal-close>Закрити</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        return modal;
    }

    updateChartsTheme() {
        this.setupChartDefaults();
        
        this.charts.forEach((chart, key) => {
            const theme = this.getCurrentTheme();
            
            // Update chart colors based on theme
            if (chart.config.type === 'doughnut' || chart.config.type === 'pie') {
                this.updateDoughnutTheme(chart, theme);
            } else if (chart.config.type === 'line') {
                this.updateLineTheme(chart, theme);
            } else if (chart.config.type === 'bar') {
                this.updateBarTheme(chart, theme);
            } else if (chart.config.type === 'radar') {
                this.updateRadarTheme(chart, theme);
            }
            
            chart.update('none');
        });
        
        // Redraw custom charts
        this.initHeatmapChart();
        this.initTreemapChart();
    }

    updateDoughnutTheme(chart, theme) {
        chart.options.plugins.legend.labels.color = theme.textColor;
        chart.options.plugins.tooltip.backgroundColor = theme.backgroundColor;
        chart.options.plugins.tooltip.titleColor = theme.textColor;
        chart.options.plugins.tooltip.bodyColor = theme.textColor;
        chart.options.plugins.tooltip.borderColor = theme.gridColor;
    }

    updateLineTheme(chart, theme) {
        chart.options.scales.x.grid.color = theme.gridColor;
        chart.options.scales.y.grid.color = theme.gridColor;
        chart.options.scales.x.ticks.color = theme.textColor;
        chart.options.scales.y.ticks.color = theme.textColor;
        chart.options.plugins.legend.labels.color = theme.textColor;
    }

    updateBarTheme(chart, theme) {
        chart.options.scales.x.grid.color = theme.gridColor;
        chart.options.scales.y.grid.color = theme.gridColor;
        chart.options.scales.x.ticks.color = theme.textColor;
        chart.options.scales.y.ticks.color = theme.textColor;
        chart.options.plugins.legend.labels.color = theme.textColor;
    }

    updateRadarTheme(chart, theme) {
        chart.options.scales.r.grid.color = theme.gridColor;
        chart.options.scales.r.angleLines.color = theme.gridColor;
        chart.options.scales.r.pointLabels.color = theme.textColor;
        chart.options.plugins.legend.labels.color = theme.textColor;
    }

    resizeCharts() {
        this.charts.forEach(chart => {
            chart.resize();
        });
    }

    // ===== UTILITY METHODS =====
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // ===== PUBLIC API =====
    getChart(key) {
        return this.charts.get(key);
    }

    updateChartData(key, newData) {
        const chart = this.charts.get(key);
        if (chart) {
            chart.data = newData;
            chart.update();
        }
    }

    exportChart(key, format = 'png') {
        const chart = this.charts.get(key);
        if (chart) {
            const url = chart.toBase64Image();
            const link = document.createElement('a');
            link.download = `${key}-chart.${format}`;
            link.href = url;
            link.click();
        }
    }

    destroyChart(key) {
        const chart = this.charts.get(key);
        if (chart) {
            chart.destroy();
            this.charts.delete(key);
        }
    }

    destroyAllCharts() {
        this.charts.forEach(chart => chart.destroy());
        this.charts.clear();
    }

    // Static method for creating instance
    static getInstance() {
        if (!DataVisualization.instance) {
            DataVisualization.instance = new DataVisualization();
        }
        return DataVisualization.instance;
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.Charts = DataVisualization.getInstance();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DataVisualization;
}
</rewritten_file>