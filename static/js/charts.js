
document.addEventListener("DOMContentLoaded", function () {
const expenseCtx = document
    .getElementById("expensePieChart");

if (expenseCtx) {

    new Chart(expenseCtx, {

        type: "doughnut",

        data: {

            

            datasets: [{

                data: [650, 420, 310, 180, 250, 140],

                backgroundColor: [
                    "#2563EB",
                    "#22C55E",
                    "#F59E0B",
                    "#EF4444",
                    "#8B5CF6",
                    "#06B6D4"
                ],

                borderWidth: 0,

                hoverOffset: 12

            }],
            labels: [
                "Food",
                "Shopping",
                "Bills",
                "Transport",
                "Entertainment",
                "Others"
            ],
        },

        options: {

            responsive: true,

            maintainAspectRatio: false,

            cutout: "72%",

            plugins: {

                legend: {

                    position: "bottom",
                    display:"false",

                    labels: {

                        usePointStyle: true,
                        pointStyle: "circle",
                        padding: 20,
                        boxWidth: 10

                    }

                },

                tooltip: {

                    backgroundColor: "#1E293B",
                    cornerRadius: 8

                }

            }

        }

    });

}
});



// income vs expense line graph
document.addEventListener("DOMContentLoaded", function () {

    const incomeChart = document.getElementById("incomeExpenseChart");

    if (incomeChart) {

        const ctx = incomeChart.getContext("2d");

        // Gradient for Income
        const incomeGradient = ctx.createLinearGradient(0, 0, 0, 300);
        incomeGradient.addColorStop(0, "rgba(34,197,94,0.35)");
        incomeGradient.addColorStop(1, "rgba(34,197,94,0)");

        // Gradient for Expenses
        const expenseGradient = ctx.createLinearGradient(0, 0, 0, 300);
        expenseGradient.addColorStop(0, "rgba(239,68,68,0.35)");
        expenseGradient.addColorStop(1, "rgba(239,68,68,0)");

        new Chart(incomeChart, {

            type: "line",

            data:{
                labels:["Jan","Feb","Mar","Apr","May","Jun"],

                datasets:[
                {
                    label:"Income",
                    data:[5000,6200,7000,6800,7600,8200],
                    borderColor:"#22C55E",
                    backgroundColor: incomeGradient,
                    fill:true,
                    tension:.4,
                    pointRadius:5,
                    pointHoverRadius:7
                },
                {
                    label:"Expenses",
                    data:[3200,4000,4500,4200,5000,5400],
                    borderColor:"#EF4444",
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
                        position:"bottom"
                    }
                },

                scales:{

                    x:{
                        grid:{
                            display:false
                        },
                        border:{
                            display:false
                        }
                    },

                    y:{
                        grid:{
                            display:false
                        },
                        border:{
                            display:false
                        },
                        ticks:{
                            callback:(value)=>"₹"+(value/1000)+"K"
                        }
                    }

                }
            }

        });

    }

});


// Expense Pie Chart
document.addEventListener("DOMContentLoaded", function () {
    const expenseCtx = document
    .getElementById("expensePie");

if (expenseCtx) {

    new Chart(expenseCtx, {



    type:"doughnut",

    data:{
        labels:["Food","Bills","Travel","Shopping","Others"],

        datasets:[{

            data:[25,20,15,30,10],

            backgroundColor:[
                "#2563EB",
                "#22C55E",
                "#F59E0B",
                "#EF4444",
                "#8B5CF6"
            ]

        }]
    },  options: {
             responsive: true,
             maintainAspectRatio: false
    }

})
}
});


// Monthly Cash Flow

document.addEventListener("DOMContentLoaded", function () {
    const monthlycashflow = document.getElementById("cashFlowChart");

    if (monthlycashflow) {

        const cashFlowChart = new Chart(monthlycashflow, {
            type: "bar",
            data: {
                labels: ["Income", "Expenses", "Savings"],
                datasets: [{
                    label: "July 2026",
                    data: [50000, 35000, 15000],
                    backgroundColor: [
                        "#22C55E",
                        "#EF4444",
                        "#2563EB"
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
                    title: {
                        display: true,
                        text: "Monthly Cash Flow - July 2026",
                        font: {
                            size: 18,
                            weight: "bold"
                        }
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
                            color: "#64748b",
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
                            color: "#64748b",
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


const spent = 12500;
const budget = 15000;

const percentage = (spent / budget) * 100;

const foodProgress = document.getElementById("food-progress");
if (foodProgress) {
    foodProgress.style.width = percentage + "%";
}
