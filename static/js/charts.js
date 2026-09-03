
function themeColor(name, fallback) {
    const value = getComputedStyle(document.documentElement)
        .getPropertyValue(name)
        .trim();
    return value || fallback;
}

function chartTheme() {
    return {
        axis: themeColor("--chart-axis", "#64748B"),
        grid: themeColor("--chart-grid", "rgba(18, 35, 51, 0.12)"),
        tooltipBackground: themeColor("--chart-tooltip-bg", "#1E293B"),
        tooltipText: themeColor("--chart-tooltip-text", "#F8FAFC"),
        income: themeColor("--chart-income", "#22C55E"),
        incomeFillStart: themeColor("--chart-income-fill-start", "rgba(34,197,94,0.35)"),
        incomeFillEnd: themeColor("--chart-income-fill-end", "rgba(34,197,94,0)"),
        expense: themeColor("--chart-expense", "#EF4444"),
        expenseFill: themeColor("--chart-expense-fill", "rgba(239, 68, 68, 0.15)"),
        expenseFillStart: themeColor("--chart-expense-fill-start", "rgba(239, 68, 68, 0.35)"),
        expenseFillEnd: themeColor("--chart-expense-fill-end", "rgba(239, 68, 68, 0)"),
        primary: themeColor("--chart-primary", "#2563EB"),
        series: [
            themeColor("--chart-series-1", "#2563EB"),
            themeColor("--chart-series-2", "#22C55E"),
            themeColor("--chart-series-3", "#F59E0B"),
            themeColor("--chart-series-4", "#EF4444"),
            themeColor("--chart-series-5", "#8B5CF6"),
            themeColor("--chart-series-6", "#06B6D4"),
        ],
    };
}

document.addEventListener("DOMContentLoaded", function () {
const expenseCtx = document
    .getElementById("expensePieChart");

const expenseBreakdown = window.dashboardExpenseBreakdown || [];

if (expenseCtx && typeof Chart !== "undefined") {
    const theme = chartTheme();

    new Chart(expenseCtx, {

        type: "doughnut",

        data: {

            

            datasets: [{

                data: expenseBreakdown.map((item) => item.amount),

                backgroundColor: theme.series,

                borderWidth: 0,

                hoverOffset: 12

            }],
            labels: expenseBreakdown.map((item) => item.category),
        },

        options: {

            responsive: true,

            maintainAspectRatio: false,

            cutout: "72%",

            plugins: {

                legend: {

                    position: "bottom",
                    display: false,

                    labels: {

                        usePointStyle: true,
                        pointStyle: "circle",
                        padding: 20,
                        boxWidth: 10,
                        color: theme.axis,

                    }

                },

                tooltip: {

                    backgroundColor: theme.tooltipBackground,
                    titleColor: theme.tooltipText,
                    bodyColor: theme.tooltipText,
                    cornerRadius: 8

                }

            }

        }

    });

}
});


document.addEventListener("DOMContentLoaded", function () {
    const monthlySpendingChart = document.getElementById("monthlySpendingChart");
    const monthlyExpenses = window.dashboardMonthlyExpenses || [];

    if (monthlySpendingChart && monthlyExpenses.length && typeof Chart !== "undefined") {
        const theme = chartTheme();
        new Chart(monthlySpendingChart, {
            type: "line",
            data: {
                labels: monthlyExpenses.map((item) => item.month),
                datasets: [{
                    label: "Expenses",
                    data: monthlyExpenses.map((item) => item.amount),
                    borderColor: theme.expense,
                    backgroundColor: theme.expenseFill,
                    fill: true,
                    tension: 0.35,
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
                        callbacks: {
                            label: (context) => `₹${context.parsed.y.toLocaleString()}`,
                        },
                    },
                },
                scales: {
                    x: {
                        grid: {
                            display: false,
                            color: theme.grid,
                        },
                        ticks: { color: theme.axis },
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            display: false,
                            color: theme.grid,
                        },
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



// income vs expense line graph
document.addEventListener("DOMContentLoaded", function () {

    const incomeChart = document.getElementById("incomeExpenseChart");

    if (incomeChart && typeof Chart !== "undefined") {
        const theme = chartTheme();

        const ctx = incomeChart.getContext("2d");

        // Gradient for Income
        const incomeGradient = ctx.createLinearGradient(0, 0, 0, 300);
        incomeGradient.addColorStop(0, theme.incomeFillStart);
        incomeGradient.addColorStop(1, theme.incomeFillEnd);

        // Gradient for Expenses
        const expenseGradient = ctx.createLinearGradient(0, 0, 0, 300);
        expenseGradient.addColorStop(0, theme.expenseFillStart);
        expenseGradient.addColorStop(1, theme.expenseFillEnd);

        new Chart(incomeChart, {

            type: "line",

            data:{
                labels:["Jan","Feb","Mar","Apr","May","Jun"],

                datasets:[
                {
                    label:"Income",
                    data:[5000,6200,7000,6800,7600,8200],
                    borderColor: theme.income,
                    backgroundColor: incomeGradient,
                    fill:true,
                    tension:.4,
                    pointRadius:5,
                    pointHoverRadius:7
                },
                {
                    label:"Expenses",
                    data:[3200,4000,4500,4200,5000,5400],
                    borderColor: theme.expense,
                    backgroundColor: expenseGradient,
                    fill:true,
                    tension:.4,
                    pointRadius:5,
                    pointHoverRadius:7
                }]
            },

            options: {

                responsive:true,
                maintainAspectRatio:false,

                plugins:{
                    legend:{
                        position:"bottom",
                        labels: { color: theme.axis }
                    },
                    tooltip:{
                        backgroundColor: theme.tooltipBackground,
                        titleColor: theme.tooltipText,
                        bodyColor: theme.tooltipText
                    }
                },

                scales:{

                    x:{
                        grid:{
                            display:false,
                            color: theme.grid
                        },
                        border:{
                            display:false,
                            color: theme.grid
                        },
                        ticks:{ color: theme.axis }
                    },

                    y:{
                        grid:{
                            display:false,
                            color: theme.grid
                        },
                        border:{
                            display:false,
                            color: theme.grid
                        },
                        ticks:{
                            color: theme.axis,
                            callback:(value)=>"₹"+(value/1000)+"K"
                        }
                    }

                }
            }

        });

    }

});


// Monthly Cash Flow

document.addEventListener("DOMContentLoaded", function () {
    const monthlycashflow = document.getElementById("cashFlowChart");

    if (monthlycashflow && typeof Chart !== "undefined") {
        const theme = chartTheme();

        const cashFlowChart = new Chart(monthlycashflow, {
            type: "bar",
            data: {
                labels: ["Income", "Expenses", "Savings"],
                datasets: [{
                    label: "July 2026",
                    data: [50000, 35000, 15000],
                    backgroundColor: [
                        theme.income,
                        theme.expense,
                        theme.primary
                    ],
                    borderRadius: 8,
                    barThickness: 60
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,

                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: theme.tooltipBackground,
                        titleColor: theme.tooltipText,
                        bodyColor: theme.tooltipText
                    },
                    title: {
                        display: true,
                        text: "Monthly Cash Flow - July 2026",
                        font: {
                            size: 18,
                            weight: "bold"
                        },
                        color: theme.axis
                    }
                },

                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        border: {
                            display: false
                        },
                        ticks: {
                            color: theme.axis,
                            font: {
                                size: 13,
                                weight: "600"
                            }
                        }
                    },

                    y: {
                        beginAtZero: true,
                        grid: {
                            display: false
                        },
                        border: {
                            display: false
                        },
                        ticks: {
                            color: theme.axis,
                            callback: (value) => "₹" + (value / 1000) + "K"
                        }
                    }
                }
            }
        });

        const monthFilter = document.getElementById("monthFilter");
        if (monthFilter) {
            monthFilter.addEventListener("change", () => {
                cashFlowChart.data.datasets[0].data = [58000, 42000, 16000];
                cashFlowChart.options.plugins.title.text =
                    `Monthly Cash Flow - ${monthFilter.value}`;

                cashFlowChart.update();
            });
        }

    }
});
