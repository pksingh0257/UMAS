function readJSON(id) {
  const el = document.getElementById(id);
  if (!el) return null;

  try {
    return JSON.parse(el.textContent);
  } catch (error) {
    console.error(`Unable to parse dashboard JSON: ${id}`, error);
    return null;
  }
}

function themeColor(varName) {
  return getComputedStyle(document.documentElement)
    .getPropertyValue(varName)
    .trim();
}

function palette() {
  return [
    themeColor('--primary-red'),
    themeColor('--accent-blue'),
    '#4caf50',
    '#e3a008',
    '#8e24aa',
    '#00897b',
  ];
}

/*
 * The backend may already return labels such as:
 *   "Fund: Regimental Fund"
 *   "Sub-Head: ATG"
 *
 * The dashboard should show only the real business name:
 *   "Regimental Fund"
 *   "ATG"
 */
function cleanIncomeLabel(label) {
  if (label === null || label === undefined) return '';

  return String(label)
    .replace(/^\s*Fund\s*:\s*/i, '')
    .replace(/^\s*Sub[- ]?Head\s*:\s*/i, '')
    .trim();
}

function formatCurrency(value) {
  return `₹${Number(value || 0).toLocaleString('en-IN')}`;
}

document.addEventListener('DOMContentLoaded', () => {
  Chart.defaults.color = themeColor('--text-secondary');
  Chart.defaults.borderColor = themeColor('--border');
  Chart.defaults.font.family = "'Segoe UI', Arial, sans-serif";

  /* =====================================================
     ADMIN — CASES BY STAGE
     ===================================================== */
  const stageLabels = readJSON('cases-by-stage-labels');
  const stageData = readJSON('cases-by-stage-data');
  const stageCanvas = document.getElementById('casesByStageChart');

  if (stageCanvas && stageLabels) {
    new Chart(stageCanvas, {
      type: 'bar',
      data: {
        labels: stageLabels,
        datasets: [{
          label: 'Cases',
          data: stageData,
          backgroundColor: themeColor('--primary-red'),
          borderColor: themeColor('--primary-red'),
          borderWidth: 1,
          borderRadius: 6,
          maxBarThickness: 38,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: { grid: { display: false } },
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
          },
        },
      },
    });
  }

  /* =====================================================
     ADMIN — USERS BY ROLE
     ===================================================== */
  const roleLabels = readJSON('users-by-role-labels');
  const roleData = readJSON('users-by-role-data');
  const roleCanvas = document.getElementById('usersByRoleChart');

  if (roleCanvas && roleLabels) {
    new Chart(roleCanvas, {
      type: 'doughnut',
      data: {
        labels: roleLabels,
        datasets: [{
          data: roleData,
          backgroundColor: palette(),
          borderWidth: 2,
          borderColor: themeColor('--surface'),
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '65%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              padding: 14,
            },
          },
        },
      },
    });
  }

  /* =====================================================
     ADMIN — FUND HEAD -> SUB HEAD INCOME

     Each Fund Head gets a separate bar chart containing only the
     Sub Heads belonging to that Fund Head.
     ===================================================== */
  const fundIncomeGroups = readJSON('fund-income-groups');

  if (Array.isArray(fundIncomeGroups)) {
    fundIncomeGroups.forEach((group, index) => {
      const canvas = document.getElementById(`fundSubHeadChart-${index + 1}`);

      if (!canvas || !Array.isArray(group.labels) || !Array.isArray(group.data)) {
        return;
      }

      const accent = group.accent || themeColor('--primary-red');

      new Chart(canvas, {
        type: 'bar',
        data: {
          labels: group.labels.map(cleanIncomeLabel),
          datasets: [{
            label: group.name || 'Income',
            data: group.data,
            backgroundColor: accent,
            borderColor: accent,
            borderWidth: 1,
            borderRadius: 6,
            maxBarThickness: 44,
            categoryPercentage: 0.68,
            barPercentage: 0.82,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: (items) => {
                  return items.length ? `Sub Head: ${items[0].label}` : '';
                },
                label: (context) => {
                  return `Income: ${formatCurrency(context.raw)}`;
                },
              },
            },
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: {
                autoSkip: false,
                maxRotation: 0,
                minRotation: 0,
                padding: 6,
              },
            },
            y: {
              beginAtZero: true,
              ticks: {
                callback: (value) => formatCurrency(value),
              },
            },
          },
        },
      });
    });
  }

  /* =====================================================
     ADMIN — INCOME SHARE BY FUND HEAD
     ===================================================== */
  const fundPieLabelsRaw = readJSON('fund-income-pie-labels');
  const fundPieData = readJSON('fund-income-pie-data');
  const fundPieCanvas = document.getElementById('fundIncomePieChart');

  if (fundPieCanvas && Array.isArray(fundPieLabelsRaw)) {
    const fundPieLabels = fundPieLabelsRaw.map(cleanIncomeLabel);

    new Chart(fundPieCanvas, {
      type: 'pie',
      data: {
        labels: fundPieLabels,
        datasets: [{
          data: fundPieData,
          backgroundColor: palette(),
          borderWidth: 2,
          borderColor: themeColor('--surface'),
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              padding: 14,
            },
          },
          tooltip: {
            callbacks: {
              label: (context) => {
                return `${context.label}: ${formatCurrency(context.raw)}`;
              },
            },
          },
        },
      },
    });
  }

  /* =====================================================
     HEAD CLERK — REQUEST STATUS
     ===================================================== */
  const reqLabels = readJSON('request-status-labels');
  const reqData = readJSON('request-status-data');
  const reqCanvas = document.getElementById('requestStatusChart');

  if (reqCanvas && reqLabels) {
    new Chart(reqCanvas, {
      type: 'pie',
      data: {
        labels: reqLabels,
        datasets: [{
          data: reqData,
          backgroundColor: palette(),
          borderWidth: 2,
          borderColor: themeColor('--surface'),
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              padding: 14,
            },
          },
        },
      },
    });
  }

  /* =====================================================
     ACCOUNTS CLERK / JCO / OFFICER / CFA — MY CASES
     ===================================================== */
  const myStageLabels = readJSON('my-cases-by-stage-labels');
  const myStageData = readJSON('my-cases-by-stage-data');
  const myStageCanvas = document.getElementById('myCasesByStageChart');

  if (myStageCanvas && myStageLabels) {
    new Chart(myStageCanvas, {
      type: 'bar',
      data: {
        labels: myStageLabels,
        datasets: [{
          label: 'Cases',
          data: myStageData,
          backgroundColor: themeColor('--accent-blue'),
          borderColor: themeColor('--accent-blue'),
          borderWidth: 1,
          borderRadius: 6,
          maxBarThickness: 38,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: { grid: { display: false } },
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
          },
        },
      },
    });
  }

  /* =====================================================
     ACCOUNTS OFFICER — FUND ENTRY STATUS
     ===================================================== */
  const fundStatusLabels = readJSON('fund-entry-status-labels');
  const fundStatusData = readJSON('fund-entry-status-data');
  const fundStatusCanvas = document.getElementById('fundEntryStatusChart');

  if (fundStatusCanvas && fundStatusLabels) {
    new Chart(fundStatusCanvas, {
      type: 'pie',
      data: {
        labels: fundStatusLabels,
        datasets: [{
          data: fundStatusData,
          backgroundColor: palette(),
          borderWidth: 2,
          borderColor: themeColor('--surface'),
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              padding: 14,
            },
          },
        },
      },
    });
  }
<<<<<<< HEAD
});
=======
});
>>>>>>> prince_dev
