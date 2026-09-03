function reportThemeColor(name, fallback) {
    const value = getComputedStyle(document.documentElement)
        .getPropertyValue(name)
        .trim();
    return value || fallback;
}

function reportChartTheme() {
    return {
        axis: reportThemeColor("--chart-axis", "#64748B"),
        grid: reportThemeColor("--chart-grid", "rgba(18, 35, 51, 0.12)"),
        tooltipBackground: reportThemeColor("--chart-tooltip-bg", "#1E293B"),
        tooltipText: reportThemeColor("--chart-tooltip-text", "#F8FAFC"),
        primary: reportThemeColor("--chart-primary", "#2563EB"),
        accent: reportThemeColor("--accent-primary", "#138A70"),
        accentFill: reportThemeColor("--chart-accent-fill", "rgba(19, 138, 112, 0.14)"),
        series: [
            reportThemeColor("--chart-report-series-1", "#138A70"),
            reportThemeColor("--chart-report-series-2", "#65D0B2"),
            reportThemeColor("--chart-report-series-3", "#A8864B"),
            reportThemeColor("--chart-report-series-4", "#B91C1C"),
            reportThemeColor("--chart-report-series-5", "#7C3AED"),
        ],
    };
}

document.addEventListener("DOMContentLoaded", function () {
    const categoryCanvas = document.getElementById("reportsExpenseCategoryChart");
    const categoryData = window.reportsExpenseCategories || [];
    const monthlyCanvas = document.getElementById("reportsMonthlyExpenseChart");
    const monthlyData = window.reportsMonthlyExpenses || [];
    const theme = reportChartTheme();

    if (categoryCanvas && categoryData.length && typeof Chart !== "undefined") {
        new Chart(categoryCanvas, {
            type: "doughnut",
            data: {
                labels: categoryData.map((item) => item.category),
                datasets: [{
                    data: categoryData.map((item) => item.amount),
                    backgroundColor: theme.series.concat([theme.primary]),
                    borderWidth: 0,
                    hoverOffset: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: theme.axis },
                    },
                    tooltip: {
                        backgroundColor: theme.tooltipBackground,
                        titleColor: theme.tooltipText,
                        bodyColor: theme.tooltipText,
                        callbacks: {
                            label: (context) => ` ₹${context.parsed.toLocaleString()}`,
                        },
                    },
                },
            },
        });
    }

    if (monthlyCanvas && monthlyData.length && typeof Chart !== "undefined") {
        new Chart(monthlyCanvas, {
            type: "line",
            data: {
                labels: monthlyData.map((item) => item.month),
                datasets: [{
                    label: "Recorded Expenses",
                    data: monthlyData.map((item) => item.amount),
                    borderColor: theme.accent,
                    backgroundColor: theme.accentFill,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: theme.axis },
                    },
                    tooltip: {
                        backgroundColor: theme.tooltipBackground,
                        titleColor: theme.tooltipText,
                        bodyColor: theme.tooltipText,
                    },
                },
                scales: {
                    x: {
                        grid: { display: false, color: theme.grid },
                        ticks: { color: theme.axis },
                    },
                    y: {
                        beginAtZero: true,
                        grid: { display: false, color: theme.grid },
                        ticks: {
                            color: theme.axis,
                            callback: (value) => `₹${value.toLocaleString()}`,
                        },
                    },
                },
            },
        });
    }
});
