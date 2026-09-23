// Samtech Transformer Factory Insights - Frontend Application Logic

let currentSnapshotId = null;
let currentSelectedMonth = 'ALL';
let currentDashboardData = null;
let stockItemsAll = [];
let activeRatingFilter = 'ALL';
let finishedGoodsAll = [];
let finishedRatingFilter = 'ALL';
let bomSpecsAll = [];
let bomRatingFilter = 'ALL';
let monthlyTargetsAll = [];
let charts = {};
let selectedFileToUpload = null;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  checkConfig();
  loadSnapshotsList();
  setupDragAndDrop();
});

// Format Indian Currency / numbers
function formatINR(val) {
  if (val === null || val === undefined) return "₹0.00";
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2
  }).format(val);
}

// ---------------------------------------------------------------------------
// Config & Snapshot Selection
// ---------------------------------------------------------------------------
async function checkConfig() {
  try {
    const res = await fetch('/api/config');
    const data = await res.json();
    const badge = document.getElementById('aiStatusBadge');
    const badgeText = document.getElementById('aiStatusText');
    if (data.has_gemini_key) {
      badge.classList.remove('local');
      badgeText.textContent = 'AI: Gemini Connected';
    } else {
      badge.classList.add('local');
      badgeText.textContent = 'AI: Local SQL Engine (Click to set Key)';
    }
  } catch (err) {
    console.error('Error checking config:', err);
  }
}

async function loadSnapshotsList() {
  try {
    const res = await fetch('/api/snapshots');
    const data = await res.json();
    const select = document.getElementById('snapshotSelect');
    select.innerHTML = '';

    if (!data.snapshots || data.snapshots.length === 0) {
      select.innerHTML = '<option value="">No snapshots uploaded yet</option>';
      renderEmptyState();
      return;
    }

    data.snapshots.forEach((snap, idx) => {
      const opt = document.createElement('option');
      opt.value = snap.id;
      const dateStr = snap.uploaded_at ? snap.uploaded_at.substring(0, 16) : 'Unknown date';
      opt.textContent = `#${snap.id}: ${snap.filename} (${dateStr})`;
      if (idx === 0 && !currentSnapshotId) {
        opt.selected = true;
        currentSnapshotId = snap.id;
      } else if (snap.id === currentSnapshotId) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });

    if (currentSnapshotId) {
      loadSnapshot(currentSnapshotId);
    }
  } catch (err) {
    console.error('Error loading snapshots:', err);
  }
}

async function loadSnapshot(snapshotId, month = null) {
  if (!snapshotId) return;
  currentSnapshotId = parseInt(snapshotId);
  if (month !== null) {
    currentSelectedMonth = month;
  }
  try {
    const monthQuery = currentSelectedMonth ? `&month=${encodeURIComponent(currentSelectedMonth)}` : '';
    const res = await fetch(`/api/insights/dashboard?snapshot_id=${currentSnapshotId}${monthQuery}`);
    const data = await res.json();
    if (data.has_data) {
      currentDashboardData = data;
      renderDashboard(data);
    } else {
      renderEmptyState();
    }
  } catch (err) {
    console.error('Error loading dashboard data:', err);
  }
}

function changeSelectedMonth(month) {
  currentSelectedMonth = month;
  if (currentSnapshotId) {
    loadSnapshot(currentSnapshotId, currentSelectedMonth);
  }
}

function refreshDashboard() {
  if (currentSnapshotId) {
    loadSnapshot(currentSnapshotId, currentSelectedMonth);
  } else {
    loadSnapshotsList();
  }
}

// ---------------------------------------------------------------------------
// Render Dashboard Content
// ---------------------------------------------------------------------------
function renderDashboard(data) {
  const stock = data.stock;
  const prod = data.production;
  const cons = data.consumption;
  const exec = data.executive_summary;
  const mStats = data.monthly_stats || {};
  const fg = data.finished_goods || {};

  // 0. Update Month Selector in Header
  const monthSelect = document.getElementById('monthSelect');
  if (monthSelect && data.available_months) {
    monthSelect.innerHTML = '';
    data.available_months.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.label;
      if (m.id === data.selected_month) {
        opt.selected = true;
      }
      monthSelect.appendChild(opt);
    });
  }

  // 1. KPI Cards
  document.getElementById('valStockTotal').textContent = formatINR(stock.total_value);
  document.getElementById('subStockItems').textContent = `${stock.total_items} materials tracked`;

  const totalAlerts = (stock.zero_stock_count || 0) + (stock.low_stock_count || 0);
  document.getElementById('valStockAlerts').textContent = totalAlerts;
  document.getElementById('subStockAlerts').textContent = `${stock.zero_stock_count} out-of-stock, ${stock.low_stock_count} low-stock`;

  document.getElementById('valProdTotal').textContent = `${Math.round(prod.total_produced_units || 0)} units`;
  document.getElementById('subProdDispatched').textContent = `${Math.round(prod.total_dispatched || 0)} units dispatched`;

  const quality = prod.quality || {};
  document.getElementById('valQualityRate').textContent = `${quality.pass_rate_pct || 100}%`;
  document.getElementById('subQualityCounts').textContent = `${Math.round(quality.passed || 0)} passed / ${Math.round(quality.failed || 0)} failed`;

  const bneck = prod.bottleneck || {};
  document.getElementById('valBottleneckSection').textContent = bneck.section || 'None';
  document.getElementById('subBottleneckThroughput').textContent = `Stage throughput: ${Math.round(bneck.throughput || 0)} units`;

  // 2. Narrative Banner
  document.getElementById('narrativeHeadline').textContent = exec.headline;
  const badge = document.getElementById('narrativeBadge');
  if (exec.action_required) {
    badge.className = 'narrative-badge badge danger';
    badge.textContent = 'ATTENTION REQUIRED';
  } else {
    badge.className = 'narrative-badge badge success';
    badge.textContent = 'HEALTHY OPERATIONS';
  }

  const bulletsList = document.getElementById('narrativeBullets');
  bulletsList.innerHTML = '';
  (exec.bullets || []).forEach(b => {
    const li = document.createElement('li');
    li.textContent = b;
    bulletsList.appendChild(li);
  });

  // 3. Render Charts
  renderPipelineChart(prod.flow_stages || [], bneck.section);
  renderQualityChart(quality.passed || 0, quality.failed || 0);
  renderDailyTrendChart(prod.daily_trends || []);
  renderRatingChart(prod.ratings || []);

  // 4. Render Tables
  renderTopMovers(stock.top_issued || [], stock.top_received || []);
  
  stockItemsAll = stock.all_items || [];
  filterStockTable();

  renderNormsTable(cons.variances || []);

  // 5. Monthly Master & Targets
  const targets = mStats.targets || [];
  monthlyTargetsAll = targets;

  const totalTarget = targets.filter(t => t.month !== 'YEARLY').reduce((acc, t) => acc + (t.target_units || 0), 0);
  const totalActual = targets.filter(t => t.month !== 'YEARLY').reduce((acc, t) => acc + (t.actual_units || 0), 0);
  const totalVariance = targets.filter(t => t.month !== 'YEARLY').reduce((acc, t) => acc + (t.variance_units || 0), 0);

  const elTarget = document.getElementById('valMonthlyTargetTotal');
  if (elTarget) elTarget.textContent = `${Math.round(totalTarget).toLocaleString()} units`;
  const elActual = document.getElementById('valMonthlyActualTotal');
  if (elActual) elActual.textContent = `${Math.round(totalActual).toLocaleString()} units`;
  const elVar = document.getElementById('valMonthlyVarianceTotal');
  if (elVar) {
    elVar.textContent = `${totalVariance >= 0 ? '+' : ''}${Math.round(totalVariance).toLocaleString()} units`;
    elVar.style.color = totalVariance >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)';
  }
  const elFocus = document.getElementById('valMonthlyFocusMonth');
  if (elFocus) {
    const currMonthObj = data.available_months?.find(m => m.id === data.selected_month);
    elFocus.textContent = currMonthObj ? currMonthObj.label : data.selected_month;
  }

  // Populate monthly table month filter dropdown
  const mTableFilter = document.getElementById('monthlyTableMonthFilter');
  if (mTableFilter && mStats.fy_months) {
    const currentVal = mTableFilter.value;
    mTableFilter.innerHTML = '<option value="ALL">All Months & Yearly</option>';
    mStats.fy_months.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      mTableFilter.appendChild(opt);
    });
    if (currentVal && Array.from(mTableFilter.options).some(o => o.value === currentVal)) {
      mTableFilter.value = currentVal;
    }
  }

  renderMonthlySectionChart(mStats);
  filterMonthlyTable();

  // 6. Finished Goods & Sub-Assemblies
  const elTrans = document.getElementById('valFinTransformers');
  if (elTrans) elTrans.textContent = `${Math.round(fg.total_finished_transformers || 0)} units`;
  const elCCA = document.getElementById('valFinCCA');
  if (elCCA) elCCA.textContent = `${Math.round(fg.total_cca_ready || 0)} units`;
  const elHV = document.getElementById('valFinHVCoils');
  if (elHV) elHV.textContent = `${Math.round(fg.total_hv_coils_ready || 0)} coils`;
  const elLV = document.getElementById('valFinLVCoils');
  if (elLV) elLV.textContent = `${Math.round(fg.total_lv_coils_ready || 0)} coils`;

  finishedGoodsAll = [
    ...(fg.finished_transformers || []),
    ...(fg.cca_fin || []),
    ...(fg.hv_coils || []),
    ...(fg.lv_coils || []),
    ...(fg.outsourced_units || [])
  ];
  filterFinishedGoodsTable();

  // 7. BOM Specifications
  bomSpecsAll = data.bom_specs || [];
  filterBomTable();
}

function renderEmptyState() {
  document.getElementById('narrativeHeadline').textContent = 'No workbook data loaded';
  document.getElementById('narrativeBullets').innerHTML = '<li>Please upload your factory .xlsm workbook to view insights.</li>';
}

// ---------------------------------------------------------------------------
// Chart Rendering (Chart.js)
// ---------------------------------------------------------------------------
function renderPipelineChart(flowStages, bottleneckName) {
  const ctx = document.getElementById('pipelineChart').getContext('2d');
  if (charts.pipeline) charts.pipeline.destroy();

  const labels = flowStages.map(s => s[0]);
  const data = flowStages.map(s => s[1]);
  const backgroundColors = flowStages.map(s => 
    s[0] === bottleneckName ? 'rgba(239, 68, 68, 0.85)' : 'rgba(0, 240, 255, 0.7)'
  );
  const borderColors = flowStages.map(s => 
    s[0] === bottleneckName ? '#ef4444' : '#00f0ff'
  );

  charts.pipeline = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Units Completed',
        data: data,
        backgroundColor: backgroundColors,
        borderColor: borderColors,
        borderWidth: 1.5,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.raw} units completed ${ctx.label === bottleneckName ? '(BOTTLENECK)' : ''}`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#9ca3af', font: { size: 10 } }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#9ca3af', font: { size: 10 } }
        }
      }
    }
  });
}

function renderQualityChart(passed, failed) {
  const ctx = document.getElementById('qualityDonutChart').getContext('2d');
  if (charts.quality) charts.quality.destroy();

  const total = passed + failed;
  const passPct = total > 0 ? Math.round((passed / total) * 100) : 100;

  charts.quality = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Passed Inspection', 'Failed Inspection'],
      datasets: [{
        data: [passed, failed],
        backgroundColor: ['rgba(16, 185, 129, 0.85)', 'rgba(239, 68, 68, 0.85)'],
        borderColor: ['#10b981', '#ef4444'],
        borderWidth: 2,
        cutout: '72%'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      }
    }
  });

  const legend = document.getElementById('qualityStatsLegend');
  legend.innerHTML = `
    <div style="display:flex; justify-content:space-around; text-align:center; padding-top:12px;">
      <div>
        <div style="color:#10b981; font-weight:700; font-size:16px;">${Math.round(passed)}</div>
        <div style="color:#9ca3af; font-size:11px;">Passed (${passPct}%)</div>
      </div>
      <div>
        <div style="color:#ef4444; font-weight:700; font-size:16px;">${Math.round(failed)}</div>
        <div style="color:#9ca3af; font-size:11px;">Failed (${100 - passPct}%)</div>
      </div>
    </div>
  `;
}

function renderDailyTrendChart(dailyTrends) {
  const ctx = document.getElementById('dailyTrendChart').getContext('2d');
  if (charts.dailyTrend) charts.dailyTrend.destroy();

  const labels = dailyTrends.map(d => d.date);
  const data = dailyTrends.map(d => d.total_daily_units);

  charts.dailyTrend = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Daily Output Units',
        data: data,
        borderColor: '#00f0ff',
        backgroundColor: 'rgba(0, 240, 255, 0.1)',
        borderWidth: 2.5,
        fill: true,
        tension: 0.3,
        pointBackgroundColor: '#00f0ff',
        pointRadius: 3
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#9ca3af', font: { size: 10 }, maxRotation: 45 }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#9ca3af', font: { size: 10 } }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

function renderRatingChart(ratings) {
  const ctx = document.getElementById('ratingBarChart').getContext('2d');
  if (charts.ratingBar) charts.ratingBar.destroy();

  const labels = ratings.map(r => r.rating);
  const data = ratings.map(r => r.total_units);

  charts.ratingBar = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Units Produced',
        data: data,
        backgroundColor: 'rgba(59, 130, 246, 0.75)',
        borderColor: '#3b82f6',
        borderWidth: 1.5,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#9ca3af', font: { size: 11 } } },
        y: { ticks: { color: '#9ca3af', font: { size: 10 } }, grid: { color: 'rgba(255, 255, 255, 0.05)' } }
      }
    }
  });
}

function renderMonthlySectionChart(monthlyStats) {
  const canvas = document.getElementById('monthlySectionChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  if (charts.monthlySection) charts.monthlySection.destroy();

  const fyMonths = (monthlyStats.fy_months || []).filter(m => m !== 'YEARLY');
  const sectionSummary = monthlyStats.section_summary || {};

  const stages = [
    { name: 'HV WINDING', color: 'rgba(0, 240, 255, 0.85)' },
    { name: 'LV WINDING', color: 'rgba(59, 130, 246, 0.85)' },
    { name: 'CORE COIL ASSEMBLY', color: 'rgba(139, 92, 246, 0.85)' },
    { name: 'TANKING', color: 'rgba(245, 158, 11, 0.85)' },
    { name: 'TESTING PASSED', color: 'rgba(16, 185, 129, 0.85)' }
  ];

  const datasets = stages.map(st => {
    const dataPoints = fyMonths.map(m => {
      const monthData = sectionSummary[st.name]?.[m];
      return monthData ? Math.round(monthData.actual || 0) : 0;
    });
    return {
      label: st.name,
      data: dataPoints,
      backgroundColor: st.color,
      borderRadius: 4
    };
  });

  charts.monthlySection = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: fyMonths,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: { color: '#9ca3af', font: { size: 10 } }
        },
        tooltip: {
          mode: 'index',
          intersect: false
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#9ca3af', font: { size: 10 } }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#9ca3af', font: { size: 10 } }
        }
      }
    }
  });
}

// ---------------------------------------------------------------------------
// Table Renderers
// ---------------------------------------------------------------------------
function renderTopMovers(topIssued, topReceived) {
  const tbodyIssued = document.querySelector('#tableTopIssued tbody');
  tbodyIssued.innerHTML = '';
  if (topIssued.length === 0) {
    tbodyIssued.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No issuance records</td></tr>';
  } else {
    topIssued.forEach(item => {
      const days = item.days_remaining > 900 ? '90+ d' : `${item.days_remaining} d`;
      const badgeClass = item.days_remaining <= 7 ? 'stock-tag low' : 'stock-tag healthy';
      tbodyIssued.innerHTML += `
        <tr>
          <td><span class="badge info">${item.rating}</span></td>
          <td><strong>${item.material_name}</strong></td>
          <td>${item.issued_qty.toLocaleString()} ${item.unit}</td>
          <td>${item.closing_balance.toLocaleString()} ${item.unit}</td>
          <td><span class="${badgeClass}">${days}</span></td>
        </tr>
      `;
    });
  }

  const tbodyReceived = document.querySelector('#tableTopReceived tbody');
  tbodyReceived.innerHTML = '';
  if (topReceived.length === 0) {
    tbodyReceived.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No restock records</td></tr>';
  } else {
    topReceived.forEach(item => {
      tbodyReceived.innerHTML += `
        <tr>
          <td><span class="badge info">${item.rating}</span></td>
          <td><strong>${item.material_name}</strong></td>
          <td>${item.received_qty.toLocaleString()} ${item.unit}</td>
          <td>${item.closing_balance.toLocaleString()} ${item.unit}</td>
          <td>₹${item.rate.toLocaleString()}</td>
        </tr>
      `;
    });
  }
}

function filterStockTable() {
  const query = document.getElementById('stockSearch').value.toLowerCase().trim();
  const alertsOnly = document.getElementById('chkAlertsOnly').checked;

  const filtered = stockItemsAll.filter(item => {
    // Rating filter
    if (activeRatingFilter !== 'ALL' && item.rating !== activeRatingFilter) {
      return false;
    }
    // Search query
    if (query) {
      const matchText = `${item.material_name} ${item.material_type || ''} ${item.size || ''} ${item.sheet_name || ''}`.toLowerCase();
      if (!matchText.includes(query)) return false;
    }
    // Alerts only
    if (alertsOnly) {
      if (item.closing_balance > 0 && item.days_remaining > 7.0) return false;
    }
    return true;
  });

  const tbody = document.getElementById('stockTableBody');
  tbody.innerHTML = '';

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="13" class="text-center text-muted">No materials match the selected filters.</td></tr>';
    return;
  }

  filtered.forEach(item => {
    let tag = '<span class="stock-tag healthy">Healthy</span>';
    if (item.closing_balance <= 0.001) {
      tag = '<span class="stock-tag zero">Out of Stock</span>';
    } else if (item.days_remaining <= 7.0 || item.closing_balance < 20.0) {
      tag = `<span class="stock-tag low">Low (${item.days_remaining}d)</span>`;
    }

    const runOut = item.days_remaining > 900 ? '90+ days' : `${item.days_remaining} days`;

    tbody.innerHTML += `
      <tr>
        <td><span class="badge info">${item.rating}</span></td>
        <td><code class="text-xs text-muted">${item.sheet_name}</code></td>
        <td><strong>${item.material_name}</strong></td>
        <td>${item.material_type || '-'} ${item.size ? `(${item.size})` : ''}</td>
        <td>${item.unit}</td>
        <td>${item.opening_balance.toLocaleString()}</td>
        <td>${item.received_qty.toLocaleString()}</td>
        <td>${item.issued_qty.toLocaleString()}</td>
        <td><strong>${item.closing_balance.toLocaleString()}</strong></td>
        <td>${runOut}</td>
        <td>₹${item.rate.toLocaleString()}</td>
        <td>${formatINR(item.value)}</td>
        <td>${tag}</td>
      </tr>
    `;
  });
}

function setRatingFilter(rating) {
  activeRatingFilter = rating;
  document.querySelectorAll('#ratingChips .chip').forEach(c => {
    if (c.getAttribute('data-rating') === rating) {
      c.classList.add('active');
    } else {
      c.classList.remove('active');
    }
  });
  filterStockTable();
}

function renderNormsTable(variances) {
  const tbody = document.getElementById('normsTableBody');
  tbody.innerHTML = '';

  const badge = document.getElementById('normsSummaryBadge');
  const overCount = variances.filter(v => v.status === 'OVER_CONSUMED').length;
  if (overCount > 0) {
    badge.className = 'badge danger';
    badge.textContent = `${overCount} Material(s) Over Standard Norms`;
  } else {
    badge.className = 'badge success';
    badge.textContent = 'Norms Adherence In Spec';
  }

  if (variances.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No consumption norms found in current workbook.</td></tr>';
    return;
  }

  variances.forEach(v => {
    let statusBadge = '<span class="badge success">Normal</span>';
    if (v.status === 'OVER_CONSUMED') {
      statusBadge = `<span class="badge danger">Over (+${v.variance_pct}%)</span>`;
    } else if (v.status === 'UNDER_CONSUMED') {
      statusBadge = `<span class="badge info">Under (${v.variance_pct}%)</span>`;
    }

    tbody.innerHTML += `
      <tr>
        <td><span class="badge info">${v.rating}</span></td>
        <td><strong>${v.material_name}</strong></td>
        <td>${v.norm_per_transformer} ${v.unit}</td>
        <td>${v.units_produced}</td>
        <td>${v.expected_qty.toLocaleString()} ${v.unit}</td>
        <td>${v.actual_qty.toLocaleString()} ${v.unit}</td>
        <td><strong>${v.variance_pct > 0 ? '+' : ''}${v.variance_pct}%</strong></td>
        <td>${statusBadge}</td>
      </tr>
    `;
  });
}

// ---------------------------------------------------------------------------
// Monthly Master & Targets Table
// ---------------------------------------------------------------------------
function filterMonthlyTable() {
  const monthFilter = document.getElementById('monthlyTableMonthFilter')?.value || 'ALL';
  const secFilter = document.getElementById('monthlyTableSectionFilter')?.value || 'ALL';

  const filtered = monthlyTargetsAll.filter(row => {
    if (monthFilter !== 'ALL' && row.month !== monthFilter) return false;
    if (secFilter !== 'ALL' && row.section !== secFilter) return false;
    // Show records that have target, actual, or variance
    return (row.target_units > 0 || row.actual_units > 0 || row.variance_units !== 0);
  });

  const tbody = document.getElementById('monthlyTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No monthly target records match the selected filter.</td></tr>';
    return;
  }

  filtered.forEach(r => {
    const target = Math.round(r.target_units || 0);
    const actual = Math.round(r.actual_units || 0);
    const variance = Math.round(r.variance_units || 0);

    let varBadge = '<span class="badge info">0</span>';
    if (variance > 0) {
      varBadge = `<span class="badge success">+${variance}</span>`;
    } else if (variance < 0) {
      varBadge = `<span class="badge danger">${variance}</span>`;
    }

    let pct = target > 0 ? Math.round((actual / target) * 100) : (actual > 0 ? 100 : 0);
    let fillClass = pct >= 100 ? 'ahead' : (pct >= 70 ? 'on-track' : 'behind');

    tbody.innerHTML += `
      <tr>
        <td><strong>${r.month}</strong></td>
        <td><span class="badge info">${r.section}</span></td>
        <td><strong>${r.rating}</strong></td>
        <td>${target.toLocaleString()}</td>
        <td><strong>${actual.toLocaleString()}</strong></td>
        <td>${varBadge}</td>
        <td>
          <div class="progress-bar-cell">
            <div class="progress-track">
              <div class="progress-fill ${fillClass}" style="width: ${Math.min(pct, 100)}%"></div>
            </div>
            <span class="text-xs text-muted">${pct}%</span>
          </div>
        </td>
      </tr>
    `;
  });
}

// ---------------------------------------------------------------------------
// Finished Goods Table
// ---------------------------------------------------------------------------
function setFinishedRatingFilter(rating) {
  finishedRatingFilter = rating;
  document.querySelectorAll('#finishedRatingChips .chip').forEach(c => {
    c.classList.toggle('active', c.getAttribute('data-rating') === rating);
  });
  filterFinishedGoodsTable();
}

function filterFinishedGoodsTable() {
  const query = (document.getElementById('finishedSearch')?.value || '').toLowerCase().trim();
  const tbody = document.getElementById('finishedGoodsTableBody');
  if (!tbody) return;

  const filtered = finishedGoodsAll.filter(item => {
    if (finishedRatingFilter !== 'ALL' && item.rating !== finishedRatingFilter) return false;
    if (query) {
      const matchText = `${item.material_name} ${item.material_type || ''} ${item.sheet_name || ''} ${item.rating}`.toLowerCase();
      if (!matchText.includes(query)) return false;
    }
    return true;
  });

  tbody.innerHTML = '';
  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No finished goods match the selected criteria.</td></tr>';
    return;
  }

  filtered.forEach(item => {
    let cat = 'Sub-Assembly';
    if (item.sheet_name.includes('FINISHED TR') || item.material_name.includes('TRANSFORMER')) {
      cat = 'Finished Transformer';
    } else if (item.sheet_name.includes('OUTSOURCED')) {
      cat = 'Outsourced Unit';
    } else if (item.sheet_name.includes('CCA')) {
      cat = 'Core-Coil Assembly';
    } else if (item.sheet_name.includes('HV COIL')) {
      cat = 'HV Winding Coil';
    } else if (item.sheet_name.includes('LV COIL')) {
      cat = 'LV Winding Coil';
    }

    const readyBalance = Math.round(item.closing_balance || 0);
    const tag = readyBalance > 0 
      ? '<span class="stock-tag healthy">Ready in Stock</span>' 
      : '<span class="stock-tag zero">None Ready</span>';

    tbody.innerHTML += `
      <tr>
        <td><span class="badge info">${item.rating}</span></td>
        <td><strong>${cat}</strong></td>
        <td>${item.material_name}</td>
        <td><code class="text-xs text-muted">${item.sheet_name}</code></td>
        <td>${Math.round(item.opening_balance || 0).toLocaleString()}</td>
        <td>${Math.round(item.received_qty || 0).toLocaleString()}</td>
        <td>${Math.round(item.issued_qty || 0).toLocaleString()}</td>
        <td><strong>${readyBalance.toLocaleString()} units</strong></td>
        <td>${tag}</td>
      </tr>
    `;
  });
}

// ---------------------------------------------------------------------------
// BOM Specifications Table
// ---------------------------------------------------------------------------
function setBomRatingFilter(rating) {
  bomRatingFilter = rating;
  document.querySelectorAll('#bomRatingChips .chip').forEach(c => {
    c.classList.toggle('active', c.getAttribute('data-rating') === rating);
  });
  filterBomTable();
}

function filterBomTable() {
  const query = (document.getElementById('bomSearch')?.value || '').toLowerCase().trim();
  const tbody = document.getElementById('bomSpecsTableBody');
  if (!tbody) return;

  const filtered = bomSpecsAll.filter(b => {
    if (bomRatingFilter !== 'ALL' && b.rating !== bomRatingFilter) return false;
    if (query) {
      const matchText = `${b.rating} ${b.material_name} ${b.material_type || ''} ${b.size || ''}`.toLowerCase();
      if (!matchText.includes(query)) return false;
    }
    return true;
  });

  tbody.innerHTML = '';
  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No BOM design specifications found.</td></tr>';
    return;
  }

  filtered.forEach(b => {
    tbody.innerHTML += `
      <tr>
        <td><span class="badge info">${b.rating}</span></td>
        <td><strong>${b.material_name}</strong></td>
        <td>${b.material_type || '-'}</td>
        <td><code>${b.size || '-'}</code></td>
        <td>${b.pieces_count ? b.pieces_count.toLocaleString() : '-'}</td>
        <td>${b.qty_per_coil ? b.qty_per_coil.toLocaleString() : '-'}</td>
        <td><strong>${b.qty_per_transformer ? b.qty_per_transformer.toLocaleString() : '-'}</strong></td>
        <td><span class="text-xs text-muted">${b.unit || ''}</span></td>
      </tr>
    `;
  });
}

// ---------------------------------------------------------------------------
// Tabs Switching
// ---------------------------------------------------------------------------
function switchTab(tabId, subAction) {
  document.querySelectorAll('.content-tabs .tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
  });
  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === `tab-${tabId}`);
  });

  if (tabId === 'inventory' && subAction === 'alerts') {
    document.getElementById('chkAlertsOnly').checked = true;
    filterStockTable();
  }
}

// ---------------------------------------------------------------------------
// AI Q&A Assistant Logic
// ---------------------------------------------------------------------------
async function sendChatMessage() {
  const input = document.getElementById('chatInput');
  const question = input.value.trim();
  if (!question) return;

  input.value = '';
  appendChatMessage('user', question);

  // Loading bubble
  const loadingId = 'loading-' + Date.now();
  appendLoadingBubble(loadingId);

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: question, session_id: 'browser_session' })
    });
    const data = await res.json();
    removeLoadingBubble(loadingId);
    appendChatMessage('assistant', data.answer, data.sql_query, data.data);
  } catch (err) {
    removeLoadingBubble(loadingId);
    appendChatMessage('assistant', `Error connecting to AI service: ${err.message}`);
  }
}

function askPreset(question) {
  switchTab('assistant');
  document.getElementById('chatInput').value = question;
  sendChatMessage();
}

function appendChatMessage(role, content, sqlQuery = null, tabularData = null) {
  const container = document.getElementById('chatMessages');
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${role}-message`;

  const avatar = role === 'user' ? '👤' : '🤖';
  
  let formattedHtml = `<p>${formatMarkdownText(content)}</p>`;

  if (sqlQuery) {
    formattedHtml += `
      <details class="sql-toggle">
        <summary>View Executed SQL Query</summary>
        <pre><code>${escapeHtml(sqlQuery)}</code></pre>
      </details>
    `;
  }

  msgDiv.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-content">${formattedHtml}</div>
  `;

  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
}

function appendLoadingBubble(id) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.id = id;
  div.className = 'message assistant-message';
  div.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-content text-muted">
      <span>Querying shop floor database...</span>
    </div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function removeLoadingBubble(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function clearChat() {
  document.getElementById('chatMessages').innerHTML = `
    <div class="message system-message">
      <div class="msg-avatar">🤖</div>
      <div class="msg-content">
        <p>Chat cleared. Ask me any question about your shop floor inventory, production output, or bottlenecks.</p>
      </div>
    </div>
  `;
}

function formatMarkdownText(text) {
  if (!text) return '';
  // Convert markdown tables if present
  if (text.includes('|') && text.includes('---')) {
    const lines = text.split('\n');
    let inTable = false;
    let tableHtml = '<div class="table-container my-2"><table class="data-table">';
    let regularText = '';

    for (let line of lines) {
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        inTable = true;
        if (line.includes('---')) continue; // separator
        const cells = line.split('|').map(c => c.trim()).filter((c, idx, arr) => idx > 0 && idx < arr.length - 1);
        tableHtml += '<tr>' + cells.map(c => `<td>${escapeHtml(c)}</td>`).join('') + '</tr>';
      } else {
        if (inTable) {
          tableHtml += '</table></div>';
          regularText += tableHtml;
          inTable = false;
          tableHtml = '<div class="table-container my-2"><table class="data-table">';
        }
        regularText += escapeHtml(line) + '<br>';
      }
    }
    if (inTable) tableHtml += '</table></div>';
    return inTable ? regularText + tableHtml : regularText;
  }

  // Basic bold format
  let safe = escapeHtml(text);
  safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/\n/g, '<br>');
  return safe;
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ---------------------------------------------------------------------------
// File Upload & Modals
// ---------------------------------------------------------------------------
function openUploadModal() {
  document.getElementById('uploadModal').classList.add('active');
  document.getElementById('uploadProgressWrap').style.display = 'none';
  document.getElementById('uploadProgressBar').style.width = '0%';
}

function closeUploadModal() {
  document.getElementById('uploadModal').classList.remove('active');
}

function setupDragAndDrop() {
  const dropZone = document.getElementById('dropZone');
  if (!dropZone) return;

  ['dragenter', 'dragover'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files.length) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  });
}

function handleFileSelect(e) {
  if (e.target.files.length) {
    setSelectedFile(e.target.files[0]);
  }
}

function setSelectedFile(file) {
  if (!file.name.endsWith('.xlsm') && !file.name.endsWith('.xlsx')) {
    alert('Please select a valid Excel workbook (.xlsm or .xlsx)');
    return;
  }
  selectedFileToUpload = file;
  document.getElementById('selectedFileInfo').style.display = 'flex';
  document.getElementById('selectedFileName').textContent = file.name;
  document.getElementById('selectedFileSize').textContent = `${(file.size / 1024).toFixed(1)} KB`;
  document.getElementById('btnSubmitUpload').disabled = false;
}

async function submitUpload() {
  if (!selectedFileToUpload) return;

  const btn = document.getElementById('btnSubmitUpload');
  btn.disabled = true;

  const progressWrap = document.getElementById('uploadProgressWrap');
  const progressBar = document.getElementById('uploadProgressBar');
  const statusText = document.getElementById('uploadStatusText');

  progressWrap.style.display = 'block';
  progressBar.style.width = '40%';
  statusText.textContent = 'Uploading workbook to local factory server...';

  const formData = new FormData();
  formData.append('file', selectedFileToUpload);
  formData.append('notes', document.getElementById('uploadNotes').value);

  try {
    progressBar.style.width = '70%';
    statusText.textContent = 'Parsing 87 sheets & calculating operational metrics...';

    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (res.ok) {
      progressBar.style.width = '100%';
      statusText.textContent = 'Ingestion complete! Loading new snapshot...';
      setTimeout(() => {
        closeUploadModal();
        currentSnapshotId = data.summary.snapshot_id;
        loadSnapshotsList();
      }, 700);
    } else {
      alert(`Upload failed: ${data.detail || 'Unknown error'}`);
      btn.disabled = false;
    }
  } catch (err) {
    alert(`Upload failed: ${err.message}`);
    btn.disabled = false;
  }
}

// Gemini Key Modal
function openApiKeyModal() {
  document.getElementById('apiKeyModal').classList.add('active');
}

function closeApiKeyModal() {
  document.getElementById('apiKeyModal').classList.remove('active');
}

async function saveGeminiKey() {
  const key = document.getElementById('inputGeminiKey').value.trim();
  if (!key) {
    alert('Please enter a valid API key.');
    return;
  }
  try {
    const res = await fetch('/api/config/gemini-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key })
    });
    if (res.ok) {
      alert('Gemini API Key saved successfully!');
      closeApiKeyModal();
      checkConfig();
    } else {
      alert('Failed to save key.');
    }
  } catch (err) {
    alert('Error saving key: ' + err.message);
  }
}
