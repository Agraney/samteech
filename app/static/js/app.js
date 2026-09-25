// Samtech Transformer Factory Intelligence - Business-First Operations Logic

let currentSnapshotId = null;
let currentSelectedMonth = 'ALL';
let currentSelectedRating = 'ALL';
let currentDashboardData = null;

let stockItemsAll = [];
let activeRatingFilter = 'ALL';
let stockSortOrder = 'name';

let readinessItemsAll = [];
let readinessRatingFilter = 'ALL';

let finishedGoodsAll = [];
let finishedRatingFilter = 'ALL';

let bomSpecsAll = [];
let bomRatingFilter = 'ALL';

let monthlyTargetsAll = [];
let qualityRatingsAll = [];
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
      badgeText.textContent = 'AI: Local SQL Engine (Click for Key)';
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

async function loadSnapshot(snapshotId, month = null, rating = null) {
  if (!snapshotId) return;
  currentSnapshotId = parseInt(snapshotId);
  if (month !== null) {
    currentSelectedMonth = month;
  }
  if (rating !== null) {
    currentSelectedRating = rating;
  }

  try {
    const monthQuery = currentSelectedMonth ? `&month=${encodeURIComponent(currentSelectedMonth)}` : '';
    const ratingQuery = currentSelectedRating ? `&rating=${encodeURIComponent(currentSelectedRating)}` : '';
    const res = await fetch(`/api/insights/dashboard?snapshot_id=${currentSnapshotId}${monthQuery}${ratingQuery}`);
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
    loadSnapshot(currentSnapshotId, currentSelectedMonth, currentSelectedRating);
  }
}

function changeSelectedRating(rating) {
  currentSelectedRating = rating;
  if (currentSnapshotId) {
    loadSnapshot(currentSnapshotId, currentSelectedMonth, currentSelectedRating);
  }
}

function refreshDashboard() {
  if (currentSnapshotId) {
    loadSnapshot(currentSnapshotId, currentSelectedMonth, currentSelectedRating);
  } else {
    loadSnapshotsList();
  }
}

// ---------------------------------------------------------------------------
// Render Dashboard Content
// ---------------------------------------------------------------------------
function renderDashboard(data) {
  const stock = data.stock || {};
  const prod = data.production || {};
  const cons = data.consumption || {};
  const exec = data.executive_summary || {};
  const mStats = data.monthly_stats || {};
  const fg = data.finished_goods || {};
  const wip = data.wip || {};
  const quality = data.quality || prod.quality || {};
  const readiness = data.material_readiness || {};
  const outsourcing = data.outsourcing || {};
  const flow = data.manufacturing_flow || [];
  const dailyBrief = data.daily_brief || {};
  const ratingsMatrix = data.ratings_matrix || [];

  // 0. Update Header Selectors
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

  const ratingSelect = document.getElementById('ratingSelect');
  if (ratingSelect && data.available_ratings) {
    ratingSelect.innerHTML = '';
    data.available_ratings.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r;
      opt.textContent = r === 'ALL' ? 'All Ratings (Global)' : `${r} Transformer`;
      if (r === data.selected_rating) {
        opt.selected = true;
      }
      ratingSelect.appendChild(opt);
    });
  }

  // 1. Executive KPI Strip (7 Factory Metrics)
  document.getElementById('valStockTotal').textContent = formatINR(stock.total_value);
  document.getElementById('subStockItems').textContent = `${stock.total_items || 0} materials tracked`;

  const totalAlerts = (stock.zero_stock_count || 0) + (stock.low_stock_count || 0);
  document.getElementById('valStockAlerts').textContent = totalAlerts;
  document.getElementById('subStockAlerts').textContent = `${stock.zero_stock_count || 0} out-of-stock, ${stock.low_stock_count || 0} low-stock`;

  const totalProd = Math.round(prod.total_produced_units || 0);
  document.getElementById('valProdTotal').textContent = `${totalProd.toLocaleString()} units`;
  document.getElementById('subProdStages').textContent = `Period: ${data.selected_month === 'ALL' ? 'Full FY' : data.selected_month}`;

  const totalDispatch = Math.round(prod.total_dispatched || 0);
  document.getElementById('valDispatchTotal').textContent = `${totalDispatch.toLocaleString()} units`;
  document.getElementById('subDispatchUnits').textContent = 'Final factory shipment';

  document.getElementById('valQualityRate').textContent = `${quality.pass_rate_pct || 100}%`;
  document.getElementById('subQualityCounts').textContent = `${Math.round(quality.passed || 0)} passed / ${Math.round(quality.failed || 0)} failed`;

  const totalBufferWip = (wip.physical_buffers || []).reduce((acc, b) => acc + (b.units || 0), 0);
  document.getElementById('valWipTotal').textContent = `${Math.round(totalBufferWip).toLocaleString()} units`;
  document.getElementById('subWipDetail').textContent = 'Physical sub-assembly buffer';

  const bneck = prod.bottleneck || wip.bottleneck || {};
  document.getElementById('valBottleneckSection').textContent = bneck.stage || bneck.section || 'None';
  document.getElementById('subBottleneckThroughput').textContent = bneck.accumulated_before 
    ? `${bneck.accumulated_before} units accumulated`
    : `Stage throughput: ${Math.round(bneck.throughput || 0)} units`;

  // 2. Executive Action Narrative Banner
  document.getElementById('narrativeHeadline').textContent = exec.headline || 'Analyzing operations...';
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

  // 3. Tab 1: Factory Control Room Components
  renderManufacturingFlow(flow, data.selected_month);
  renderDailyBrief(dailyBrief, stock, prod, quality);
  renderRatingsMatrix(ratingsMatrix);

  // 4. Tab 2: Production Flow Tab
  renderFlowStagesTable(flow);
  renderPipelineChart(flow, bneck.stage || bneck.section);
  renderDailyTrendChart(prod.daily_trends || []);

  // 5. Tab 3: WIP & Bottlenecks Tab
  renderWipAndBottlenecks(wip);

  // 6. Tab 4: Material Readiness Tab
  renderMaterialReadiness(readiness);

  // 7. Tab 5: Finished Goods & Sourcing Tab
  renderFinishedGoods(fg, outsourcing);

  // 8. Tab 6: Raw Materials Inventory Tab
  stockItemsAll = stock.all_items || [];
  filterStockTable();

  // 9. Tab 7: Targets & Performance Tab
  renderTargetsTab(mStats, data.selected_month, data.available_months);

  // 10. Tab 8: Quality Inspection Tab
  renderQualityTab(quality);

  // 11. Tab 9: Consumption & BOM Tab
  renderConsumptionTab(cons, data.bom_specs);
}

function renderEmptyState() {
  document.getElementById('narrativeHeadline').textContent = 'No workbook data loaded';
  document.getElementById('narrativeBullets').innerHTML = '<li>Please upload your factory .xlsm workbook to view insights.</li>';
}

// ---------------------------------------------------------------------------
// Tab 1: Manufacturing Process Flow & Daily Brief
// ---------------------------------------------------------------------------
function renderManufacturingFlow(flowStages, selectedMonth) {
  const container = document.getElementById('manufacturingFlowPipeline');
  if (!container) return;

  const monthBadge = document.getElementById('flowMonthBadge');
  if (monthBadge) {
    monthBadge.textContent = selectedMonth === 'ALL' ? 'Full Financial Year' : `Month: ${selectedMonth}`;
  }

  if (!flowStages || flowStages.length === 0) {
    container.innerHTML = '<div class="text-center text-muted p-4">No flow stages available.</div>';
    return;
  }

  let html = '';
  flowStages.forEach((stage, idx) => {
    const isBottleneck = stage.status === 'BOTTLENECK';
    const output = Math.round(stage.actual_output ?? stage.output ?? 0);
    const target = Math.round(stage.target_output ?? stage.monthly_target ?? 0);
    const actual = Math.round(stage.actual_output ?? stage.monthly_actual ?? 0);
    const variance = Math.round(stage.variance ?? 0);
    const fulfillment = Math.round(stage.achievement_pct ?? 0);
    const sec = (stage.section || stage.stage_id || stage.stage_name || '').toUpperCase();

    let stageIcon = '⚙️';
    if (sec.includes('WINDING')) stageIcon = '🌀';
    else if (sec.includes('CCA') || sec.includes('CORE')) stageIcon = '⚡';
    else if (sec.includes('TANKING')) stageIcon = '🛢️';
    else if (sec.includes('TESTING')) stageIcon = '🛡️';
    else if (sec.includes('PAINTING')) stageIcon = '🎨';
    else if (sec.includes('DISPATCH')) stageIcon = '🚚';

    html += `
      <div class="pipeline-stage-card ${isBottleneck ? 'bottleneck' : ''}">
        <div class="stage-card-top">
          <span class="stage-num-badge">${idx + 1}</span>
          <span class="status-pill ${isBottleneck ? 'insufficient' : 'healthy'}">${isBottleneck ? 'BOTTLENECK' : 'ACTIVE'}</span>
        </div>
        <div class="stage-name">${stageIcon} ${stage.stage_name}</div>
        <div class="stage-output-num">${output.toLocaleString()} <span style="font-size:11px; font-weight:500; color:var(--text-muted);">units</span></div>
        <div class="stage-target-meta">
          <span>Target: <strong>${target.toLocaleString()}</strong></span>
          <span>Actual: <strong>${actual.toLocaleString()}</strong></span>
        </div>
        <div class="progress-track" style="margin-top:6px; height:5px;">
          <div class="progress-fill ${fulfillment >= 100 ? 'ahead' : (fulfillment >= 70 ? 'on-track' : 'behind')}" style="width: ${Math.min(fulfillment, 100)}%"></div>
        </div>
        <div style="font-size:10px; color:var(--text-muted); display:flex; justify-content:space-between; margin-top:4px;">
          <span>Var: <strong style="color:${variance >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'}">${variance >= 0 ? '+' : ''}${variance}</strong></span>
          <span>${fulfillment}%</span>
        </div>
      </div>
    `;

    // Add connector arrow between stages
    if (idx < flowStages.length - 1) {
      const accum = stage.accumulation_to_next || 0;
      let accumClass = 'neutral';
      let accumText = 'Aligned';
      if (accum > 15) {
        accumClass = 'danger';
        accumText = `+${accum} units buffer`;
      } else if (accum > 0) {
        accumClass = 'warning';
        accumText = `+${accum} buffer`;
      } else if (accum < 0) {
        accumClass = 'neutral';
        accumText = `${accum} deficit`;
      }

      html += `
        <div class="pipeline-connector">
          <div style="font-size:18px;">➔</div>
          <span class="accumulation-pill ${accumClass}">${accumText}</span>
        </div>
      `;
    }
  });

  container.innerHTML = html;
}

function renderDailyBrief(brief, stock, prod, quality) {
  if (!brief) return;

  const dateEl = document.getElementById('briefAsOfDate');
  if (dateEl) dateEl.textContent = brief.as_of_date || 'Current Snapshot';

  // Production & Dispatch
  const elProdThroughput = document.getElementById('briefProdThroughput');
  if (elProdThroughput) elProdThroughput.textContent = `${Math.round(prod.total_produced_units || 0).toLocaleString()} units produced`;
  const elDispatchText = document.getElementById('briefDispatchText');
  if (elDispatchText) elDispatchText.textContent = `${Math.round(prod.total_dispatched || 0).toLocaleString()} units dispatched`;

  const stageList = document.getElementById('briefStageList');
  if (stageList && brief.production_summary) {
    stageList.innerHTML = `
      <span class="brief-pill">HV Winding: ${brief.production_summary.latest_hv_winding || 0}</span>
      <span class="brief-pill">LV Winding: ${brief.production_summary.latest_lv_winding || 0}</span>
      <span class="brief-pill">CCA: ${brief.production_summary.latest_cca || 0}</span>
      <span class="brief-pill">Tanking: ${brief.production_summary.latest_tanking || 0}</span>
    `;
  }

  // Inventory
  const elStockVal = document.getElementById('briefStockVal');
  if (elStockVal) elStockVal.textContent = formatINR(stock.total_value);
  const elStockAlerts = document.getElementById('briefStockAlertsText');
  if (elStockAlerts) elStockAlerts.textContent = `${stock.zero_stock_count || 0} out-of-stock, ${stock.low_stock_count || 0} low stock (&le;7d)`;

  const stockPills = document.getElementById('briefStockAlertPills');
  if (stockPills && brief.inventory_summary) {
    stockPills.innerHTML = `
      <span class="brief-pill" style="color:var(--accent-rose);">${brief.inventory_summary.out_of_stock_materials || 0} Critical Out-of-Stock</span>
      <span class="brief-pill" style="color:var(--accent-amber);">${brief.inventory_summary.low_stock_materials || 0} Low Stock Alert</span>
    `;
  }

  // WIP
  const elWipText = document.getElementById('briefWipText');
  if (elWipText && brief.wip_summary) {
    elWipText.textContent = `Stage Accumulations: ${brief.wip_summary.total_stage_accumulations || 0} units`;
  }
  const elBottleneck = document.getElementById('briefBottleneckText');
  if (elBottleneck && brief.wip_summary) {
    elBottleneck.textContent = brief.wip_summary.major_accumulation 
      ? `Highest buffer: ${brief.wip_summary.major_accumulation}`
      : 'No critical stage imbalance';
  }

  // Quality
  const elQualityRate = document.getElementById('briefQualityRate');
  if (elQualityRate) elQualityRate.textContent = `${quality.pass_rate_pct || 100}% Pass Rate`;
  const elQualityCounts = document.getElementById('briefQualityCounts');
  if (elQualityCounts) elQualityCounts.textContent = `${Math.round(quality.passed || 0)} passed / ${Math.round(quality.failed || 0)} failed`;

  // Attention Items List
  const attentionList = document.getElementById('attentionList');
  if (attentionList) {
    attentionList.innerHTML = '';
    const items = brief.attention_items || [];
    if (items.length === 0) {
      attentionList.innerHTML = '<li style="color:var(--accent-emerald);">✓ All operational metrics within normal manufacturing thresholds.</li>';
    } else {
      items.forEach(it => {
        const li = document.createElement('li');
        const text = typeof it === 'string' ? it : (it.text || JSON.stringify(it));
        li.textContent = text;
        attentionList.appendChild(li);
      });
    }
  }
}

function renderRatingsMatrix(matrix) {
  const tbody = document.getElementById('ratingsMatrixBody');
  if (!tbody) return;

  tbody.innerHTML = '';
  if (!matrix || matrix.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No rating matrix available.</td></tr>';
    return;
  }

  matrix.forEach(row => {
    const prodUnits = Math.round(row.production_units || 0);
    const target = Math.round(row.target_units || 0);
    const actual = Math.round(row.actual_units || 0);
    const variance = Math.round(row.variance_units || 0);
    const stock = Math.round(row.finished_stock || 0);
    const outsourced = Math.round(row.outsourced_stock || 0);

    tbody.innerHTML += `
      <tr>
        <td><strong>${row.rating}</strong></td>
        <td><strong>${prodUnits.toLocaleString()}</strong></td>
        <td>${target.toLocaleString()}</td>
        <td>${actual.toLocaleString()}</td>
        <td><strong style="color:${variance >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'}">${variance >= 0 ? '+' : ''}${variance}</strong></td>
        <td>${stock.toLocaleString()} units</td>
        <td>${outsourced.toLocaleString()} units</td>
        <td><span class="status-pill ${variance >= 0 ? 'healthy' : 'attention'}">${variance >= 0 ? 'On Target' : 'Behind Target'}</span></td>
      </tr>
    `;
  });
}

// ---------------------------------------------------------------------------
// Tab 2: Production Flow Tab
// ---------------------------------------------------------------------------
function renderFlowStagesTable(stages) {
  const tbody = document.getElementById('flowStagesTableBody');
  if (!tbody) return;

  tbody.innerHTML = '';
  if (!stages || stages.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No stages loaded.</td></tr>';
    return;
  }

  stages.forEach((st, idx) => {
    const variance = Math.round(st.variance || 0);
    const fulfillment = Math.round(st.achievement_pct || 0);
    const accum = st.accumulation_to_next || 0;

    tbody.innerHTML += `
      <tr>
        <td><span class="stage-num-badge">${idx + 1}</span></td>
        <td><strong>${st.stage_name}</strong></td>
        <td><strong>${Math.round(st.actual_output ?? st.output ?? 0).toLocaleString()}</strong></td>
        <td>${Math.round(st.target_output ?? st.monthly_target ?? 0).toLocaleString()}</td>
        <td>${Math.round(st.actual_output ?? st.monthly_actual ?? 0).toLocaleString()}</td>
        <td><strong style="color:${variance >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'}">${variance >= 0 ? '+' : ''}${variance}</strong></td>
        <td>
          <div class="progress-bar-cell">
            <div class="progress-track">
              <div class="progress-fill ${fulfillment >= 100 ? 'ahead' : (fulfillment >= 70 ? 'on-track' : 'behind')}" style="width: ${Math.min(fulfillment, 100)}%"></div>
            </div>
            <span class="text-xs text-muted">${fulfillment}%</span>
          </div>
        </td>
        <td><span class="accumulation-pill ${accum > 15 ? 'danger' : (accum > 0 ? 'warning' : 'neutral')}">${accum > 0 ? `+${accum} units` : (accum < 0 ? `${accum} units` : 'Balanced')}</span></td>
        <td><span class="status-pill ${st.status === 'BOTTLENECK' ? 'insufficient' : 'healthy'}">${st.status}</span></td>
      </tr>
    `;
  });
}

function renderPipelineChart(flowStages, bottleneckName) {
  const canvas = document.getElementById('pipelineChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (charts.pipeline) charts.pipeline.destroy();

  const labels = flowStages.map(s => s.stage_name || s[0]);
  const data = flowStages.map(s => Math.round(s.output !== undefined ? s.output : s[1]));
  const backgroundColors = flowStages.map(s => {
    const name = s.stage_name || s[0];
    return name === bottleneckName ? 'rgba(244, 63, 94, 0.85)' : 'rgba(0, 240, 255, 0.75)';
  });
  const borderColors = flowStages.map(s => {
    const name = s.stage_name || s[0];
    return name === bottleneckName ? '#f43f5e' : '#00f0ff';
  });

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

function renderDailyTrendChart(dailyTrends) {
  const canvas = document.getElementById('dailyTrendChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
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

// ---------------------------------------------------------------------------
// Tab 3: WIP & Bottlenecks Tab
// ---------------------------------------------------------------------------
function renderWipAndBottlenecks(wip) {
  if (!wip) return;

  const bneck = wip.bottleneck || {};
  const badge = document.getElementById('wipBottleneckBadge');
  if (badge) {
    if (bneck.stage) {
      badge.className = 'badge danger';
      badge.textContent = `Bottleneck Stage: ${bneck.stage}`;
    } else {
      badge.className = 'badge success';
      badge.textContent = 'Balanced Flow';
    }
  }

  const diagEl = document.getElementById('wipDiagnosisText');
  if (diagEl) {
    let diagHtml = '';
    if (bneck.stage && bneck.accumulated_before > 0) {
      diagHtml = `
        <p><strong>Primary Shop Floor Imbalance:</strong> The workbook data indicates that <strong>${bneck.accumulated_before} units</strong> have completed upstream processing before <strong>${bneck.stage}</strong>.</p>
        <p class="text-sm text-muted mt-2">Data indicates accumulation prior to ${bneck.stage}. Investigate department tank/filling capacity and material readiness rather than assuming unverified causes.</p>
      `;
    } else {
      diagHtml = `<p>No critical stage throughput accumulation detected across the manufacturing pipeline.</p>`;
    }

    if (wip.summary_notes && wip.summary_notes.length > 0) {
      diagHtml += `<ul class="attention-list mt-3">`;
      wip.summary_notes.forEach(note => {
        diagHtml += `<li>${note}</li>`;
      });
      diagHtml += `</ul>`;
    }
    diagEl.innerHTML = diagHtml;
  }

  // Physical Warehouse Buffer Stocks
  const bufferList = document.getElementById('bufferStockList');
  if (bufferList && wip.physical_buffers) {
    bufferList.innerHTML = '';
    wip.physical_buffers.forEach(b => {
      bufferList.innerHTML += `
        <div class="buffer-stock-item">
          <div>
            <div class="buffer-stock-name">${b.buffer_name}</div>
            <div class="text-xs text-muted">Source: <code>${b.sheet_pattern}</code></div>
          </div>
          <div class="buffer-stock-val">${Math.round(b.units || 0).toLocaleString()} units</div>
        </div>
      `;
    });
  }

  // Sequential Stage-to-Stage Accumulation Table
  const accumBody = document.getElementById('wipAccumulationBody');
  if (accumBody && wip.throughput_accumulation) {
    accumBody.innerHTML = '';
    if (wip.throughput_accumulation.length === 0) {
      accumBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No throughput accumulations detected.</td></tr>';
      return;
    }

    wip.throughput_accumulation.forEach(item => {
      const gap = Math.round(item.accumulation_units || 0);
      let condition = '<span class="status-pill healthy">Balanced</span>';
      if (gap > 15) {
        condition = `<span class="status-pill insufficient">+${gap} Bottleneck Buffer</span>`;
      } else if (gap > 0) {
        condition = `<span class="status-pill attention">+${gap} Modest Buffer</span>`;
      } else if (gap < 0) {
        condition = `<span class="status-pill below">${gap} Downstream Deficit</span>`;
      }

      accumBody.innerHTML += `
        <tr>
          <td><strong>${item.transition}</strong></td>
          <td>${Math.round(item.stage_a_output || 0).toLocaleString()}</td>
          <td>${Math.round(item.stage_b_output || 0).toLocaleString()}</td>
          <td><strong>${gap > 0 ? '+' : ''}${gap}</strong></td>
          <td>${condition}</td>
        </tr>
      `;
    });
  }
}

// ---------------------------------------------------------------------------
// Tab 4: Material Readiness Tab
// ---------------------------------------------------------------------------
function setReadinessRatingFilter(rating) {
  readinessRatingFilter = rating;
  document.querySelectorAll('#readinessRatingChips .chip').forEach(c => {
    c.classList.toggle('active', c.getAttribute('data-rating') === rating);
  });
  filterMaterialReadinessTable();
}

function renderMaterialReadiness(readiness) {
  readinessItemsAll = readiness.readiness_items || readiness.materials || [];

  // Update Summary Counts
  let healthy = 0;
  let attention = 0;
  let insufficient = 0;

  readinessItemsAll.forEach(m => {
    if (m.status === 'HEALTHY') healthy++;
    else if (m.status === 'ATTENTION') attention++;
    else if (m.status === 'INSUFFICIENT') insufficient++;
  });

  const elHealthy = document.getElementById('statHealthyCount');
  if (elHealthy) elHealthy.textContent = healthy;
  const elAttention = document.getElementById('statAttentionCount');
  if (elAttention) elAttention.textContent = attention;
  const elInsufficient = document.getElementById('statInsufficientCount');
  if (elInsufficient) elInsufficient.textContent = insufficient;

  filterMaterialReadinessTable();
}

function filterMaterialReadinessTable() {
  const tbody = document.getElementById('readinessTableBody');
  if (!tbody) return;

  const filtered = readinessItemsAll.filter(item => {
    if (readinessRatingFilter !== 'ALL' && item.rating !== readinessRatingFilter) {
      return false;
    }
    return true;
  });

  tbody.innerHTML = '';
  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No material readiness records for selected rating.</td></tr>';
    return;
  }

  filtered.forEach(m => {
    let statusPill = '<span class="status-pill healthy">Healthy</span>';
    if (m.status === 'INSUFFICIENT') {
      statusPill = '<span class="status-pill insufficient">Zero Stock</span>';
    } else if (m.status === 'ATTENTION') {
      statusPill = '<span class="status-pill attention">Attention</span>';
    }

    const gap = m.gap;
    const gapColor = gap > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)';
    const gapSign = gap > 0 ? '-' : '+'; // If gap > 0, required > available = shortage

    tbody.innerHTML += `
      <tr>
        <td><span class="badge info">${m.rating}</span></td>
        <td><strong>${m.material_name}</strong></td>
        <td>${m.norm_per_transformer} ${m.unit}</td>
        <td>${m.planned_units} TR</td>
        <td>${m.required_qty.toLocaleString()} ${m.unit}</td>
        <td><strong>${m.available_qty.toLocaleString()}</strong> ${m.unit}</td>
        <td><strong style="color:${gapColor}">${gapSign}${Math.abs(gap).toLocaleString()} ${m.unit}</strong></td>
        <td>${m.unit}</td>
        <td>${statusPill}</td>
      </tr>
    `;
  });
}

// ---------------------------------------------------------------------------
// Tab 5: Finished Goods & Sourcing Tab
// ---------------------------------------------------------------------------
function renderFinishedGoods(fg, outsourcing) {
  const elTrans = document.getElementById('valFinTransformers');
  if (elTrans) elTrans.textContent = `${Math.round(fg.total_finished_transformers || 0)} units`;
  const elCCA = document.getElementById('valFinCCA');
  if (elCCA) elCCA.textContent = `${Math.round(fg.total_cca_ready || 0)} units`;
  const elHV = document.getElementById('valFinHVCoils');
  if (elHV) elHV.textContent = `${Math.round(fg.total_hv_coils_ready || 0)} coils`;
  const elLV = document.getElementById('valFinLVCoils');
  if (elLV) elLV.textContent = `${Math.round(fg.total_lv_coils_ready || 0)} coils`;

  // Sourcing Split
  if (outsourcing.transformers) {
    const tr = outsourcing.transformers;
    document.getElementById('txtInhouseTR').textContent = Math.round(tr.in_house_units || 0);
    document.getElementById('pctInhouseTR').textContent = `${tr.in_house_pct || 100}%`;
    document.getElementById('txtOutsourcedTR').textContent = Math.round(tr.outsourced_units || 0);
    document.getElementById('pctOutsourcedTR').textContent = `${tr.outsourced_pct || 0}%`;

    document.getElementById('barInhouseTR').style.width = `${tr.in_house_pct || 100}%`;
    document.getElementById('barOutsourcedTR').style.width = `${tr.outsourced_pct || 0}%`;
  }

  if (outsourcing.cca) {
    const cca = outsourcing.cca;
    document.getElementById('txtInhouseCCA').textContent = Math.round(cca.in_house_units || 0);
    document.getElementById('pctInhouseCCA').textContent = `${cca.in_house_pct || 100}%`;
    document.getElementById('txtOutsourcedCCA').textContent = Math.round(cca.outsourced_units || 0);
    document.getElementById('pctOutsourcedCCA').textContent = `${cca.outsourced_pct || 0}%`;

    document.getElementById('barInhouseCCA').style.width = `${cca.in_house_pct || 100}%`;
    document.getElementById('barOutsourcedCCA').style.width = `${cca.outsourced_pct || 0}%`;
  }

  finishedGoodsAll = [
    ...(fg.finished_transformers || []),
    ...(fg.cca_fin || []),
    ...(fg.hv_coils || []),
    ...(fg.lv_coils || []),
    ...(fg.outsourced_units || [])
  ];
  filterFinishedGoodsTable();
}

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
      ? '<span class="status-pill healthy">Ready in Stock</span>' 
      : '<span class="status-pill insufficient">None Ready</span>';

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
// Tab 6: Raw Materials Inventory Tab
// ---------------------------------------------------------------------------
function setRatingFilter(rating) {
  activeRatingFilter = rating;
  document.querySelectorAll('#ratingChips .chip').forEach(c => {
    c.classList.toggle('active', c.getAttribute('data-rating') === rating);
  });
  filterStockTable();
}

function filterStockTable() {
  const query = document.getElementById('stockSearch')?.value.toLowerCase().trim() || '';
  const alertsOnly = document.getElementById('chkAlertsOnly')?.checked || false;
  const sortSelect = document.getElementById('stockSortSelect')?.value || 'name';

  let filtered = stockItemsAll.filter(item => {
    if (activeRatingFilter !== 'ALL' && item.rating !== activeRatingFilter) {
      return false;
    }
    if (query) {
      const matchText = `${item.material_name} ${item.material_type || ''} ${item.size || ''} ${item.sheet_name || ''}`.toLowerCase();
      if (!matchText.includes(query)) return false;
    }
    if (alertsOnly) {
      if (item.closing_balance > 0 && item.days_remaining > 7.0) return false;
    }
    return true;
  });

  // Sorting
  if (sortSelect === 'lowest_stock') {
    filtered.sort((a, b) => a.closing_balance - b.closing_balance);
  } else if (sortSelect === 'highest_value') {
    filtered.sort((a, b) => (b.value || 0) - (a.value || 0));
  } else if (sortSelect === 'highest_issued') {
    filtered.sort((a, b) => (b.issued_qty || 0) - (a.issued_qty || 0));
  } else {
    filtered.sort((a, b) => a.material_name.localeCompare(b.material_name));
  }

  const tbody = document.getElementById('stockTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="13" class="text-center text-muted">No materials match the selected filters.</td></tr>';
    return;
  }

  filtered.forEach(item => {
    let tag = '<span class="status-pill healthy">Healthy</span>';
    if (item.closing_balance <= 0.001) {
      tag = '<span class="status-pill insufficient">Out of Stock</span>';
    } else if (item.days_remaining <= 7.0 || item.closing_balance < 20.0) {
      tag = `<span class="status-pill attention">Low (${item.days_remaining}d)</span>`;
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

// ---------------------------------------------------------------------------
// Tab 7: Targets & Performance Tab (PRODUCTION MASTER)
// ---------------------------------------------------------------------------
function renderTargetsTab(mStats, selectedMonth, availableMonths) {
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
    const currMonthObj = availableMonths?.find(m => m.id === selectedMonth);
    elFocus.textContent = currMonthObj ? currMonthObj.label : selectedMonth;
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

function filterMonthlyTable() {
  const monthFilter = document.getElementById('monthlyTableMonthFilter')?.value || 'ALL';
  const secFilter = document.getElementById('monthlyTableSectionFilter')?.value || 'ALL';

  const filtered = monthlyTargetsAll.filter(row => {
    if (monthFilter !== 'ALL' && row.month !== monthFilter) return false;
    if (secFilter !== 'ALL' && row.section !== secFilter) return false;
    return (row.target_units > 0 || row.actual_units > 0 || row.variance_units !== 0);
  });

  const tbody = document.getElementById('monthlyTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No monthly target records match the filter.</td></tr>';
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
// Tab 8: Quality Inspection Tab
// ---------------------------------------------------------------------------
function renderQualityTab(quality) {
  renderQualityChart(quality.passed || 0, quality.failed || 0);

  const tbody = document.getElementById('qualityRatingsTableBody');
  if (!tbody) return;

  tbody.innerHTML = '';
  const breakdown = quality.ratings_breakdown || [];
  if (breakdown.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No quality inspection records.</td></tr>';
    return;
  }

  breakdown.forEach(item => {
    const passRate = item.pass_rate_pct || 100;
    const passed = Math.round(item.passed || 0);
    const failed = Math.round(item.failed || 0);
    const total = passed + failed;

    tbody.innerHTML += `
      <tr>
        <td><strong>${item.rating}</strong></td>
        <td><strong style="color:var(--accent-emerald)">${passed.toLocaleString()}</strong></td>
        <td><strong style="color:var(--accent-rose)">${failed.toLocaleString()}</strong></td>
        <td>${total.toLocaleString()}</td>
        <td><strong>${passRate}%</strong></td>
        <td><span class="status-pill ${passRate >= 95 ? 'healthy' : 'attention'}">${passRate >= 95 ? 'High Quality' : 'Needs Review'}</span></td>
      </tr>
    `;
  });
}

function renderQualityChart(passed, failed) {
  const canvas = document.getElementById('qualityDonutChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
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
  if (legend) {
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
}

// ---------------------------------------------------------------------------
// Tab 9: Consumption & BOM Tab
// ---------------------------------------------------------------------------
function renderConsumptionTab(cons, bomSpecs) {
  renderNormsTable(cons.variances || []);
  bomSpecsAll = bomSpecs || [];
  filterBomTable();
}

function renderNormsTable(variances) {
  const tbody = document.getElementById('normsTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const badge = document.getElementById('normsSummaryBadge');
  const overCount = variances.filter(v => v.status === 'OVER_CONSUMED').length;
  if (badge) {
    if (overCount > 0) {
      badge.className = 'badge danger';
      badge.textContent = `${overCount} Material(s) Over Standard Norms`;
    } else {
      badge.className = 'badge success';
      badge.textContent = 'Norms Adherence In Spec';
    }
  }

  if (variances.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No consumption norms found in current workbook.</td></tr>';
    return;
  }

  variances.forEach(v => {
    let statusPill = '<span class="status-pill within">Within Norm</span>';
    if (v.status === 'OVER_CONSUMED') {
      statusPill = `<span class="status-pill above">Above Norm (+${v.variance_pct}%)</span>`;
    } else if (v.status === 'UNDER_CONSUMED') {
      statusPill = `<span class="status-pill below">Below Norm (${v.variance_pct}%)</span>`;
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
        <td>${statusPill}</td>
      </tr>
    `;
  });
}

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
    const chk = document.getElementById('chkAlertsOnly');
    if (chk) {
      chk.checked = true;
      filterStockTable();
    }
  }
}

// ---------------------------------------------------------------------------
// Data Lineage Modal
// ---------------------------------------------------------------------------
function openLineageModal() {
  document.getElementById('lineageModal').classList.add('active');
}

function closeLineageModal() {
  document.getElementById('lineageModal').classList.remove('active');
}

function showMetricLineage(metricKey, event) {
  if (event) event.stopPropagation();
  const lineageMap = currentDashboardData?.lineage || {};
  const sourceText = lineageMap[metricKey] || "Calculated from workbook data";
  alert(`DATA LINEAGE:\n${sourceText}`);
}

// ---------------------------------------------------------------------------
// AI Q&A Assistant (Strictly Read-Only)
// ---------------------------------------------------------------------------
async function sendChatMessage() {
  const input = document.getElementById('chatInput');
  const question = input.value.trim();
  if (!question) return;

  input.value = '';
  appendChatMessage('user', question);

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
        <summary>View Executed Read-Only SQL Query</summary>
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
      <span>Querying shop floor SQLite database...</span>
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
  if (text.includes('|') && text.includes('---')) {
    const lines = text.split('\n');
    let inTable = false;
    let tableHtml = '<div class="table-container my-2"><table class="data-table">';
    let regularText = '';

    for (let line of lines) {
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        inTable = true;
        if (line.includes('---')) continue;
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

  let safe = escapeHtml(text);
  safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/\n/g, '<br>');
  return safe;
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ---------------------------------------------------------------------------
// File Upload & Modals (Single Ingestion Method)
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

// ---------------------------------------------------------------------------
// Gemini API Key Modal
// ---------------------------------------------------------------------------
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
