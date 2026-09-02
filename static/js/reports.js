document.addEventListener("DOMContentLoaded", function () {
    const categoryCanvas = document.getElementById("reportsExpenseCategoryChart");
    const categoryData = window.reportsExpenseCategories || [];
    const monthlyCanvas = document.getElementById("reportsMonthlyExpenseChart");
    const monthlyData = window.reportsMonthlyExpenses || [];

    if (categoryCanvas && categoryData.length && typeof Chart !== "undefined") {
        new Chart(categoryCanvas, {
            type: "doughnut",
            data: {
                labels: categoryData.map((item) => item.category),
                datasets: [{
                    data: categoryData.map((item) => item.amount),
                    backgroundColor: ["#138A70", "#65D0B2", "#A8864B", "#2563EB", "#B91C1C", "#7C3AED"],
                    borderWidth: 0,
                    hoverOffset: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: {
                    legend: { position: "bottom" },
                    tooltip: {
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
                    borderColor: "#138A70",
                    backgroundColor: "rgba(19, 138, 112, 0.14)",
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
                scales: {
                    x: { grid: { display: false } },
                    y: {
                        beginAtZero: true,
                        grid: { display: false },
                        ticks: { callback: (value) => `₹${value.toLocaleString()}` },
                    },
                },
            },
        });
    }
});
