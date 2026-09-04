// ============================================
// GET ANALYTICS DATA FROM DJANGO
// ============================================

const analyticsElement = document.getElementById("analytics-data");

if (!analyticsElement) {
  console.error("Analytics data element not found.");
} else {
  const analytics = JSON.parse(analyticsElement.textContent);

  console.log("Analytics loaded:", analytics);

  // ========================================
  // MONTHLY SPENDING
  // ========================================

  const monthlyCanvas = document.getElementById("monthlySpendingChart");

  if (monthlyCanvas) {
    const monthlyLabels = analytics.monthly_spending.map((item) => item.month);

    const monthlyAmounts = analytics.monthly_spending.map((item) =>
      Number(item.amount),
    );

    new Chart(monthlyCanvas, {
      type: "line",

      data: {
        labels: monthlyLabels,

        datasets: [
          {
            label: "Monthly spending",

            data: monthlyAmounts,

            borderWidth: 3,

            tension: 0.35,

            fill: true,

            pointRadius: 4,

            pointHoverRadius: 6,
          },
        ],
      },

      options: {
        responsive: true,

        maintainAspectRatio: false,

        interaction: {
          intersect: false,
          mode: "index",
        },

        plugins: {
          legend: {
            display: false,
          },

          tooltip: {
            callbacks: {
              label: function (context) {
                return "$" + Number(context.raw).toFixed(2);
              },
            },
          },
        },

        scales: {
          y: {
            beginAtZero: true,

            ticks: {
              callback: function (value) {
                return "$" + value;
              },
            },
          },
        },
      },
    });
  }

  // ========================================
  // SPENDING BY CATEGORY
  // ========================================

  const categoryCanvas = document.getElementById("categoryChart");

  if (categoryCanvas) {
    const categoryLabels = analytics.category_spending.map(
      (item) => item.category,
    );

    const categoryAmounts = analytics.category_spending.map((item) =>
      Number(item.amount),
    );

    new Chart(categoryCanvas, {
      type: "doughnut",

      data: {
        labels: categoryLabels,

        datasets: [
          {
            label: "Spending",

            data: categoryAmounts,

            borderWidth: 2,
          },
        ],
      },

      options: {
        responsive: true,

        maintainAspectRatio: false,

        plugins: {
          legend: {
            position: "right",
          },

          tooltip: {
            callbacks: {
              label: function (context) {
                const value = Number(context.raw).toFixed(2);

                return context.label + ": $" + value;
              },
            },
          },
        },
      },
    });
  }

  // ========================================
  // SUBSCRIPTION COSTS
  // ========================================

  const subscriptionCanvas = document.getElementById("subscriptionChart");

  if (subscriptionCanvas) {
    const subscriptionLabels = analytics.subscription_costs.map(
      (item) => item.merchant,
    );

    const subscriptionAmounts = analytics.subscription_costs.map((item) =>
      Number(item.amount),
    );

    new Chart(subscriptionCanvas, {
      type: "bar",

      data: {
        labels: subscriptionLabels,

        datasets: [
          {
            label: "Monthly cost",

            data: subscriptionAmounts,

            borderWidth: 1,
          },
        ],
      },

      options: {
        responsive: true,

        maintainAspectRatio: false,

        plugins: {
          legend: {
            display: false,
          },

          tooltip: {
            callbacks: {
              label: function (context) {
                return "$" + Number(context.raw).toFixed(2);
              },
            },
          },
        },

        scales: {
          y: {
            beginAtZero: true,

            ticks: {
              callback: function (value) {
                return "$" + value;
              },
            },
          },
        },
      },
    });
  }
}
