/* ===== 3.4 公司通用分析：板块A 产品规模画像 ===== */
function renderProductBar(elId, data) {
  const el = document.getElementById(elId);
  if (!el || !data || !data.top_products) return;
  const chart = echarts.init(el, null, { renderer: "canvas" });
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 130, right: 50, top: 10, bottom: 30 },
    tooltip: {
      trigger: "axis", backgroundColor: ADLS.bg, borderColor: ADLS.slate300,
      textStyle: { color: ADLS.slate700, fontSize: 11 },
      extraCssText: "box-shadow:none;border-radius:0;",
      formatter: (p) => `${p[0].name}<br/>规模: ${p[0].value} 亿 (占比 ${data.top_products[p[0].dataIndex].pct}%)`,
    },
    xAxis: { type: "value", ...axisStyle(), axisLabel: { formatter: (v) => v + "亿" } },
    yAxis: {
      type: "category", data: data.top_products.map(p => p.name).reverse(),
      ...axisStyle({ axisLabel: { color: ADLS.slate500, fontSize: 10 } }),
    },
    series: [{
      type: "bar",
      data: data.top_products.map(p => p.scale).reverse(),
      itemStyle: { color: ADLS.primary },
      barWidth: "55%",
      label: { show: true, position: "right", formatter: (p) => p.value + "亿", fontSize: 10, color: ADLS.slate500 },
    }],
  });
  window.addEventListener("resize", () => chart.resize());
}

function renderTypeDonut(elId, data) {
  const el = document.getElementById(elId);
  if (!el || !data || !data.type_composition) return;
  const usComp = data.us_type_composition || [];
  const chart = echarts.init(el, null, { renderer: "canvas" });
  const series = [{
    name: "选中公司",
    type: "pie", radius: ["35%", "60%"],
    center: ["50%", "55%"],
    data: data.type_composition.map((t, i) => ({
      name: t.type, value: t.scale,
      itemStyle: { color: PALETTE[i % PALETTE.length] },
    })),
    label: { fontSize: 10, color: ADLS.slate500, formatter: "{b}\n{d}%" },
    itemStyle: { borderColor: ADLS.bg, borderWidth: 2 },
  }];
  // 外圈：工银瑞信对比
  if (usComp.length) {
    series.push({
      name: "工银瑞信",
      type: "pie", radius: ["66%", "80%"],
      center: ["50%", "55%"],
      data: usComp.map((t, i) => ({
        name: t.type, value: t.scale,
        itemStyle: { color: PALETTE[i % PALETTE.length], opacity: 0.45 },
      })),
      label: { show: false },
      itemStyle: { borderColor: ADLS.bg, borderWidth: 2 },
      tooltip: { formatter: (p) => `工银瑞信<br/>${p.name}: ${p.value}亿 (${p.percent}%)` },
    });
  }
  chart.setOption({
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item", backgroundColor: ADLS.bg, borderColor: ADLS.slate300,
      textStyle: { color: ADLS.slate700, fontSize: 11 },
      extraCssText: "box-shadow:none;border-radius:0;",
    },
    legend: { type: "scroll", textStyle: { color: ADLS.slate500, fontSize: 10 }, top: 0, itemWidth: 10, itemHeight: 8 },
    series: series,
  });
  window.addEventListener("resize", () => chart.resize());
}

function renderProfile(htmlId, data) {
  const el = document.getElementById(htmlId);
  if (!el || !data) return;
  const c = data.concentration || {};
  const ql = data.latest_q_label || '';
  const cr1Cls = c.cr1 && c.cr1 > 50 ? "up" : "flat";
  const cr5Cls = c.cr5 && c.cr5 > 50 ? "up" : "flat";

  // 板块B 表格HTML
  let growthHtml = (data.growth_products||[]).map(r =>
    `<tr class="${r.corp == US ? 'us' : ''}">
      <td class="l">${r.name}</td><td class="num">${r.q4}</td><td class="num">${r.scale}</td>
      <td class="num up">+${r.delta}</td>
      <td class="num ${r.ret>0?'up':'down'}">${r.ret!=null?r.ret+'%':'—'}</td></tr>`).join('');
  let typeChangeHtml = (data.type_change||[]).map(r =>
    `<tr><td class="l">${r.type}</td><td class="num">${r.q4}</td><td class="num">${r.q1}</td>
      <td class="num ${r.delta>0?'up':'down'}">${r.delta>0?'+':''}${r.delta}</td>
      <td class="num ${r.pct>0?'up':'down'}">${r.pct!=null?r.pct+'%':'—'}</td></tr>`).join('');

  el.innerHTML = `
    <div style="margin-bottom:16px;padding:8px 12px;background:var(--slate-100);border:1px solid var(--slate-300);">
      <span style="font-size:14px;font-weight:700;color:var(--able-primary);">板块 A · 产品规模画像</span>
      <span style="font-size:11px;color:var(--slate-400);margin-left:8px;">${ql} 季末 · 单位：亿元</span>
    </div>
    <div class="kpi-row" style="margin-bottom:12px;">
      <div class="kpi"><div class="k">公司总规模</div><div class="v">${data.total}</div><div class="d">亿元 · ${data.product_count} 只产品</div></div>
      <div class="kpi"><div class="k">CR1（最大产品）</div><div class="v ${cr1Cls}">${c.cr1||'—'}%</div><div class="d">单产品集中度</div></div>
      <div class="kpi"><div class="k">CR5（前5产品）</div><div class="v ${cr5Cls}">${c.cr5||'—'}%</div><div class="d">头部集中度</div></div>
      <div class="kpi"><div class="k">CR10（前10产品）</div><div class="v">${c.cr10||'—'}%</div><div class="d">产品分散度</div></div>
    </div>
    <div class="grid grid-2" style="margin-bottom:16px;">
      <div class="box">
        <div class="box-head"><span class="title">Top15 产品规模</span><span class="badge">A · BAR</span></div>
        <div class="box-body padded"><div id="cp-bar" class="chart chart-lg"></div></div>
      </div>
      <div class="box">
        <div class="box-head"><span class="title">产品类型构成（事后分类）</span><span class="badge">A · DONUT</span></div>
        <div class="box-body padded"><div id="cp-donut" class="chart chart-lg"></div></div>
      </div>
    </div>
    ${data.ai_pa ? `<div style="background:#F5E9D3; border:1px solid var(--bg-light); padding:16px 20px; margin-bottom:16px;">
      <div style="font-size:12px;font-weight:700;color:var(--bg-dark);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">AI 分析 · 板块A 产品规模画像</div>
      <div style="font-size:13px;color:var(--slate-700);line-height:1.8;white-space:pre-wrap;">${data.ai_pa}</div>
    </div>` : ''}

    <div style="margin-bottom:16px;padding:8px 12px;background:var(--slate-100);border:1px solid var(--slate-300);">
      <span style="font-size:14px;font-weight:700;color:var(--able-primary);">板块 B · 产品增长来源</span>
      <span style="font-size:11px;color:var(--slate-400);margin-left:8px;">${ql} 规模变动 · 单位：亿元</span>
    </div>
    <div class="box" style="margin-bottom:12px;">
      <div class="box-head"><span class="title">规模增长 TOP10</span><span class="badge">B · GROWTH</span></div>
      <div class="box-body">
        <table class="data"><thead><tr><th class="l">基金名称</th><th>上季规模</th><th>本季规模</th><th>变动</th><th>收益率</th></tr></thead>
        <tbody>${growthHtml}</tbody></table>
      </div>
    </div>
    <div class="box" style="margin-bottom:16px;">
      <div class="box-head"><span class="title">收益率 vs 最大回撤散点</span><span class="badge">B · SCATTER</span><span class="right">x=最大回撤 · y=收益率</span></div>
      <div class="box-body padded"><div id="cp-growth-scatter" class="chart chart-lg"></div></div>
    </div>
    ${data.ai_pb ? `<div style="background:#F5E9D3; border:1px solid var(--bg-light); padding:16px 20px; margin-bottom:16px;">
      <div style="font-size:12px;font-weight:700;color:var(--bg-dark);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">AI 分析 · 板块B 产品增长来源</div>
      <div style="font-size:13px;color:var(--slate-700);line-height:1.8;white-space:pre-wrap;">${data.ai_pb}</div>
    </div>` : ''}

    <div style="margin-bottom:16px;padding:8px 12px;background:var(--slate-100);border:1px solid var(--slate-300);">
      <span style="font-size:14px;font-weight:700;color:var(--able-primary);">板块 C · 产品布局分析</span>
      <span style="font-size:11px;color:var(--slate-400);margin-left:8px;">按事后分类 · ${ql} 变动</span>
    </div>
    <div class="grid grid-2" style="margin-bottom:12px;">
      <div class="box">
        <div class="box-head"><span class="title">${data.corp} 产品布局规模变化</span><span class="badge">C · STACK</span></div>
        <div class="box-body padded"><div id="cp-layout" class="chart chart-lg"></div></div>
      </div>
      <div class="box">
        <div class="box-head"><span class="title">工银瑞信 产品布局规模变化</span><span class="badge">C · 对比</span></div>
        <div class="box-body padded"><div id="cp-layout-us" class="chart chart-lg"></div></div>
      </div>
    </div>
    <div class="box" style="margin-bottom:16px;">
      <div class="box-head"><span class="title">各类型产品规模变动明细</span><span class="badge">C · TABLE</span></div>
      <div class="box-body">
        <table class="data"><thead><tr><th class="l">类型</th><th>上季规模</th><th>本季规模</th><th>变动</th><th>变动占比</th></tr></thead>
        <tbody>${typeChangeHtml}</tbody></table>
      </div>
    </div>
    ${data.ai_pc ? `<div style="background:#F5E9D3; border:1px solid var(--bg-light); padding:16px 20px; margin-bottom:16px;">
      <div style="font-size:12px;font-weight:700;color:var(--bg-dark);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">AI 分析 · 板块C 产品布局分析</div>
      <div style="font-size:13px;color:var(--slate-700);line-height:1.8;white-space:pre-wrap;">${data.ai_pc}</div>
    </div>` : ''}

    <div style="margin-bottom:16px;padding:8px 12px;background:var(--slate-100);border:1px solid var(--slate-300);">
      <span style="font-size:14px;font-weight:700;color:var(--able-primary);">板块 D · 产品特征分析</span>
      <span style="font-size:11px;color:var(--slate-400);margin-left:8px;">产品生命周期画像 · ${ql}</span>
    </div>
    <div class="grid grid-2" style="margin-bottom:16px;">
      <div class="box">
        <div class="box-head"><span class="title">成立年限 vs 规模散点</span><span class="badge">D · SCATTER</span><span class="right">x=年限 · y=规模</span></div>
        <div class="box-body padded"><div id="cp-age-scatter" class="chart chart-lg"></div></div>
      </div>
      <div class="box">
        <div class="box-head"><span class="title">产品规模分布</span><span class="badge">D · HIST</span></div>
        <div class="box-body padded"><div id="cp-hist" class="chart chart-lg"></div></div>
      </div>
    </div>
    ${data.ai_pd ? `<div style="background:#F5E9D3; border:1px solid var(--bg-light); padding:16px 20px; margin-bottom:16px;">
      <div style="font-size:12px;font-weight:700;color:var(--bg-dark);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">AI 分析 · 板块D 产品特征分析</div>
      <div style="font-size:13px;color:var(--slate-700);line-height:1.8;white-space:pre-wrap;">${data.ai_pd}</div>
    </div>` : ''}

    <div style="margin-bottom:12px;padding:8px 12px;background:var(--slate-100);border:1px solid var(--slate-300);">
      <span style="font-size:14px;font-weight:700;color:var(--able-primary);">板块 E · 核心结论</span>
      <span style="font-size:11px;color:var(--slate-400);margin-left:8px;">自动生成</span>
    </div>
    <div class="box" style="margin-bottom:16px;">
      <div class="box-body" style="padding:12px;">
        ${(data.insights||[]).map((t,i) =>
          `<div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:8px;">
            <span style="font-size:11px;font-weight:700;color:var(--able-primary);min-width:20px;">${i+1}.</span>
            <span style="font-size:12px;color:var(--slate-700);">${t}</span>
          </div>`
        ).join('')}
      </div>
    </div>
  `;
  // 渲染图表
  renderProductBar("cp-bar", data);
  renderTypeDonut("cp-donut", data);
  renderGrowthScatter("cp-growth-scatter", data);
  renderStackedArea("cp-layout", data.layout, US);
  if (data.us_layout) renderStackedArea("cp-layout-us", data.us_layout, US);
  renderAgeScatter("cp-age-scatter", data);
  renderHistogram("cp-hist", data);
}

function renderBoardAllocation(elId, data) {
  const el = document.getElementById(elId);
  if (!el || !data || !data.scatter_points) return;
  const usPts = data.us_scatter_points || [];
  const chart = echarts.init(el, null, { renderer: "canvas" });
  const series = [{
    name: data.corp + " 产品",
    type: "scatter", symbolSize: 8,
    data: data.scatter_points.map(p => ({ value: [p.dd, p.ret], name: p.name })),
    itemStyle: { color: ADLS.primary },
  }];
  if (usPts.length) {
    series.push({
      name: "工银瑞信 产品",
      type: "scatter", symbolSize: 8,
      data: usPts.map(p => ({ value: [p.dd, p.ret], name: p.name })),
      itemStyle: { color: ADLS.up },
    });
  }
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 56, right: 30, top: 30, bottom: 40 },
    tooltip: {
      trigger: "item", backgroundColor: ADLS.bg, borderColor: ADLS.slate300,
      textStyle: { color: ADLS.slate700, fontSize: 11 },
      extraCssText: "box-shadow:none;border-radius:0;",
      formatter: (p) => `${p.seriesName}<br/>${p.data.name}<br/>最大回撤: ${p.value[0]}%<br/>收益率: ${p.value[1]}%`,
    },
    legend: { textStyle: { color: ADLS.slate500, fontSize: 10 }, top: 0, itemWidth: 10, itemHeight: 8 },
    xAxis: { type: "value", name: "最大回撤(%)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
    yAxis: { type: "value", name: "收益率(%)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
    series: series,
  });
  window.addEventListener("resize", () => chart.resize());
}

function renderGrowthScatter(elId, data) {
  const el = document.getElementById(elId);
  if (!el || !data || !data.scatter_points) return;
  const usPts = data.us_scatter_points || [];
  const chart = echarts.init(el, null, { renderer: "canvas" });
  const series = [{
    name: data.corp + " 产品",
    type: "scatter", symbolSize: 8,
    data: data.scatter_points.map(p => ({ value: [p.dd, p.ret], name: p.name })),
    itemStyle: { color: ADLS.primary },
  }];
  // 工银瑞信对比点（红色，始终显示）
  if (usPts.length) {
    series.push({
      name: "工银瑞信产品",
      type: "scatter", symbolSize: 8,
      data: usPts.map(p => ({ value: [p.dd, p.ret], name: p.name })),
      itemStyle: { color: ADLS.up },
    });
  }
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 56, right: 30, top: 30, bottom: 40 },
    tooltip: {
      trigger: "item", backgroundColor: ADLS.bg, borderColor: ADLS.slate300,
      textStyle: { color: ADLS.slate700, fontSize: 11 },
      extraCssText: "box-shadow:none;border-radius:0;",
      formatter: (p) => `${p.seriesName}<br/>${p.data.name}<br/>最大回撤: ${p.value[0]}%<br/>收益率: ${p.value[1]}%`,
    },
    legend: { textStyle: { color: ADLS.slate500, fontSize: 10 }, top: 0, itemWidth: 10, itemHeight: 8 },
    xAxis: { type: "value", name: "最大回撤(%)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
    yAxis: { type: "value", name: "收益率(%)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
    series: series,
  });
  window.addEventListener("resize", () => chart.resize());
}

function renderAgeScatter(elId, data) {
  const el = document.getElementById(elId);
  if (!el || !data || !data.scatter_age_points) return;
  const chart = echarts.init(el, null, { renderer: "canvas" });
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 56, right: 30, top: 16, bottom: 40 },
    tooltip: {
      trigger: "item", backgroundColor: ADLS.bg, borderColor: ADLS.slate300,
      textStyle: { color: ADLS.slate700, fontSize: 11 },
      extraCssText: "box-shadow:none;border-radius:0;",
      formatter: (p) => `${p.data.name}<br/>成立年限: ${p.value[0]} 年<br/>规模: ${p.value[1]} 亿<br/>类型: ${p.data.type}`,
    },
    xAxis: { type: "value", name: "成立年限", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
    yAxis: { type: "value", name: "规模(亿)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
    series: [{ type: "scatter", symbolSize: (v) => Math.max(6, Math.sqrt(v[1]) * 2),
      data: data.scatter_age_points.map(p => ({ value: [p.years, p.scale], name: p.name, type: p.type })),
      itemStyle: { color: ADLS.mint },
    }],
  });
  window.addEventListener("resize", () => chart.resize());
}

function renderHistogram(elId, data) {
  const el = document.getElementById(elId);
  if (!el || !data || !data.histogram) return;
  const usHist = data.us_histogram || [];
  const chart = echarts.init(el, null, { renderer: "canvas" });
  const series = [{
    name: data.corp + " 产品",
    type: "bar", data: data.histogram.map(h => h.count),
    itemStyle: { color: ADLS.primary }, barWidth: "35%",
    label: { show: true, position: "top", fontSize: 10, color: ADLS.slate500 },
  }];
  if (usHist.length) {
    series.push({
      name: "工银瑞信 产品",
      type: "bar", data: usHist.map(h => h.count),
      itemStyle: { color: ADLS.up }, barWidth: "35%",
      label: { show: true, position: "top", fontSize: 10, color: ADLS.slate500 },
    });
  }
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 48, right: 20, top: 30, bottom: 40 },
    tooltip: {
      trigger: "axis", backgroundColor: ADLS.bg, borderColor: ADLS.slate300,
      textStyle: { color: ADLS.slate700, fontSize: 11 },
      extraCssText: "box-shadow:none;border-radius:0;",
    },
    legend: { textStyle: { color: ADLS.slate500, fontSize: 10 }, top: 0, itemWidth: 10, itemHeight: 8 },
    xAxis: { type: "category", data: data.histogram.map(h => h.label), ...axisStyle() },
    yAxis: { type: "value", name: "产品数量", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
    series: series,
  });
  window.addEventListener("resize", () => chart.resize());
}

/* ECharts 渲染层 —— 遵循 ADLS 深海色板 / 去背 / 等宽数字 */
const ADLS = {
  primary: "#205781",
  mint: "#4F959D",
  up: "#ef4444",
  down: "#10b981",
  slate300: "#CBD5E1",
  slate400: "#94A3B8",
  slate500: "#64748B",
  slate700: "#334155",
  bg: "#F8FAFC",
};

const PALETTE = [
  "#205781", "#4F959D", "#0F766E", "#7c3aed", "#db2777",
  "#ea580c", "#ca8a04", "#16a34a", "#0891b2", "#9333ea",
  "#b45309", "#1e40af", "#0d9488", "#be185d", "#475569",
];

const HIGHLIGHT_US = {
  itemStyle: { color: ADLS.up },
  lineStyle: { width: 2.5, color: ADLS.up },
  z: 10,
};

function baseGrid() {
  return {
    left: 48, right: 16, top: 30, bottom: 32,
  };
}

function axisStyle(opts = {}) {
  return Object.assign({
    axisLine: { lineStyle: { color: ADLS.slate300 } },
    axisTick: { lineStyle: { color: ADLS.slate300 } },
    axisLabel: { color: ADLS.slate500, fontSize: 10, fontFamily: "ui-monospace, monospace" },
    splitLine: { lineStyle: { color: ADLS.slate300, type: "dashed", opacity: .4 } },
  }, opts);
}

function tooltip() {
  return {
    trigger: "axis",
    backgroundColor: ADLS.bg,
    borderColor: ADLS.slate300,
    textStyle: { color: ADLS.slate700, fontSize: 11 },
    extraCssText: "box-shadow: none; border-radius: 0;",
  };
}

function legend() {
  return {
    type: "scroll",
    textStyle: { color: ADLS.slate500, fontSize: 10 },
    itemWidth: 10, itemHeight: 8,
    top: 0,
  };
}

/* 集中度 / 仓位 时间序列：我司高亮，其余灰阶 */
function renderTimeSeries(elId, data, field, valueSuffix, usName, opts = {}) {
  const el = document.getElementById(elId);
  if (!el || !data) return;
  const corps = Object.keys(data);
  if (!corps.length) return;
  const dates = data[corps[0]].dates;
  const series = corps.map((corp, i) => ({
    name: corp,
    type: "line",
    symbol: "none",
    smooth: false,
    data: data[corp][field],
    z: corp === usName ? 20 : 1,
    lineStyle: { width: corp === usName ? 2.8 : 1.4, color: corp === usName ? ADLS.up : PALETTE[i % PALETTE.length] },
    itemStyle: { color: corp === usName ? ADLS.up : PALETTE[i % PALETTE.length] },
    emphasis: { focus: "series" },
  }));
  // y 轴区间：opts.yMin/yMax 为固定区间（多图共用便于对比）；opts.zoomY 则按数据收紧
  let yExtra = {};
  if (opts.yMin != null || opts.yMax != null) {
    yExtra = { min: opts.yMin, max: opts.yMax, scale: true };
  } else if (opts.zoomY) {
    const all = corps.flatMap(c => (data[c][field] || [])).filter(v => typeof v === "number" && isFinite(v));
    if (all.length) {
      const lo = Math.min(...all), hi = Math.max(...all);
      const pad = Math.max((hi - lo) * 0.08, 1);
      yExtra = { min: Math.floor(lo - pad), max: Math.ceil(hi + pad), scale: true };
    }
  }
  const chart = echarts.init(el, null, { renderer: "canvas" });
  chart.setOption({
    backgroundColor: "transparent",
    grid: baseGrid(),
    tooltip: tooltip(),
    legend: legend(),
    xAxis: { type: "category", data: dates, ...axisStyle({ axisLabel: { color: ADLS.slate500, fontSize: 10, rotate: 0 } }) },
    yAxis: { type: "value", ...axisStyle(), ...yExtra, axisLabel: { formatter: (v) => v + (valueSuffix || "") } },
    series,
  });
  window.addEventListener("resize", () => chart.resize());
}

/* 各公司 加权最大回撤(x) vs 加权收益率(y) 散点：每公司异色、点旁标名、悬浮显示数据 */
function renderScatter(elId, points, usName) {
  const el = document.getElementById(elId);
  if (!el || !points) return;
  // x/y 轴区间按数据自适应，下限 floor、上限 ceil 到 5 的倍数
  const range5 = (vals) => {
    const f = vals.filter(v => typeof v === "number" && isFinite(v));
    if (!f.length) return null;
    let lo = Math.min(...f), hi = Math.max(...f);
    let mn = Math.floor(lo / 5) * 5, mx = Math.ceil(hi / 5) * 5;
    if (mn === mx) { mn -= 5; mx += 5; }
    return { min: mn, max: mx };
  };
  const xR = range5(points.map(p => p.dd));
  const yR = range5(points.map(p => p.ret));
  // 每个公司一个 series，便于异色 + 图例；我司红色加粗置顶
  const series = points.map((p, i) => ({
    name: p.corp,
    type: "scatter",
    symbolSize: p.is_us ? 16 : 11,
    z: p.is_us ? 20 : 1,
    data: [{ value: [p.dd, p.ret], name: p.corp }],
    itemStyle: { color: p.is_us ? ADLS.up : PALETTE[i % PALETTE.length] },
    label: {
      show: true,
      formatter: p.corp,
      position: "right",
      fontSize: 9,
      color: p.is_us ? ADLS.up : ADLS.slate700,
    },
    labelLayout: { hideOverlap: true },
  }));
  const chart = echarts.init(el, null, { renderer: "canvas" });
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 56, right: 24, top: 16, bottom: 40 },
    tooltip: {
      trigger: "item",
      backgroundColor: ADLS.bg, borderColor: ADLS.slate300,
      textStyle: { color: ADLS.slate700, fontSize: 11 },
      extraCssText: "box-shadow:none;border-radius:0;",
      formatter: (p) => `${p.data.name}<br/>加权收益率: ${p.value[1]}%<br/>加权最大回撤: ${p.value[0]}%`,
    },
    legend: { type: "scroll", textStyle: { color: ADLS.slate500, fontSize: 10 }, top: 0, itemWidth: 10, itemHeight: 8 },
    xAxis: { type: "value", name: "加权最大回撤(%)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle(), ...(xR || {}) },
    yAxis: { type: "value", name: "加权收益率(%)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle(), ...(yR || {}) },
    series,
  });
  window.addEventListener("resize", () => chart.resize());
}

/* 产品布局规模变化（堆叠面积） */
function renderStackedArea(elId, data, usName) {
  const el = document.getElementById(elId);
  if (!el || !data) return;
  const quarters = data.quarters;
  const types = data.types;
  const series = types.map((t, i) => ({
    name: t,
    type: "line",
    stack: "total",
    areaStyle: { opacity: 0.18 },
    symbol: "none",
    smooth: false,
    data: data.series[t],
    lineStyle: { width: 1, color: PALETTE[i % PALETTE.length] },
    itemStyle: { color: PALETTE[i % PALETTE.length] },
  }));
  const chart = echarts.init(el, null, { renderer: "canvas" });
  chart.setOption({
    backgroundColor: "transparent",
    grid: baseGrid(),
    tooltip: tooltip(),
    legend: { type: "scroll", textStyle: { color: ADLS.slate500, fontSize: 10 }, top: 0, itemWidth: 10, itemHeight: 8 },
    xAxis: { type: "category", data: quarters, ...axisStyle() },
    yAxis: { type: "value", ...axisStyle(), axisLabel: { formatter: (v) => v } },
    series,
  });
  window.addEventListener("resize", () => chart.resize());
}

/* 图3.1：规模变化区间 基金数量(柱) + 平均收益率(折线,右轴) */
function renderBinBarLine(elId, data) {
  const el = document.getElementById(elId);
  if (!el || !data || !data.labels) return;
  const chart = echarts.init(el, null, { renderer: "canvas" });
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 48, right: 56, top: 30, bottom: 60 },
    tooltip: {
      trigger: "axis", backgroundColor: ADLS.bg, borderColor: ADLS.slate300,
      textStyle: { color: ADLS.slate700, fontSize: 11 },
      extraCssText: "box-shadow:none;border-radius:0;",
    },
    legend: { textStyle: { color: ADLS.slate500, fontSize: 10 }, top: 0, itemWidth: 10, itemHeight: 8 },
    xAxis: { type: "category", data: data.labels, ...axisStyle({ axisLabel: { color: ADLS.slate500, fontSize: 10, rotate: 30 } }) },
    yAxis: [
      { type: "value", name: "基金数量", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
      { type: "value", name: "平均收益率%", nameTextStyle: { color: ADLS.slate400, fontSize: 10 },
        ...axisStyle({ splitLine: { show: false } }), axisLabel: { formatter: (v) => v + "%" } },
    ],
    series: [
      { name: "基金数量", type: "bar", data: data.counts, itemStyle: { color: ADLS.primary }, barWidth: "60%" },
      { name: "平均收益率", type: "line", yAxisIndex: 1, data: data.returns, symbol: "circle", symbolSize: 6,
        lineStyle: { width: 2, color: ADLS.up }, itemStyle: { color: ADLS.up },
        connectNulls: true },
    ],
  });
  window.addEventListener("resize", () => chart.resize());
}

/* 图3.2：各类型产品规模变动（柱，正绿负红） */
function renderTypeBar(elId, data) {
  const el = document.getElementById(elId);
  if (!el || !data || !data.types) return;
  const series = data.deltas.map((v) => ({ value: v, itemStyle: { color: v >= 0 ? ADLS.up : ADLS.down } }));
  const chart = echarts.init(el, null, { renderer: "canvas" });
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 48, right: 16, top: 24, bottom: 100 },
    tooltip: {
      trigger: "axis", backgroundColor: ADLS.bg, borderColor: ADLS.slate300,
      textStyle: { color: ADLS.slate700, fontSize: 11 },
      extraCssText: "box-shadow:none;border-radius:0;",
      formatter: (p) => `${p[0].name}<br/>规模变动: ${p[0].value} 亿`,
    },
    xAxis: { type: "category", data: data.types, ...axisStyle({ axisLabel: { color: ADLS.slate500, fontSize: 9, rotate: 45, interval: 0 } }) },
    yAxis: { type: "value", name: "亿元", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
    series: [{ type: "bar", data: series, barWidth: "55%" }],
  });
  window.addEventListener("resize", () => chart.resize());
}
