/* ECharts 渲染层 —— 遵循 ADLS 深海色板 / 去背 / 等宽数字 */
const ADLS = {
  primary: "#205781",
  mint: "#4F959D",
  up: "#10b981",
  down: "#ef4444",
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
  itemStyle: { color: ADLS.down },
  lineStyle: { width: 2.5, color: ADLS.down },
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
    lineStyle: { width: corp === usName ? 2.8 : 1.4, color: corp === usName ? ADLS.down : PALETTE[i % PALETTE.length] },
    itemStyle: { color: corp === usName ? ADLS.down : PALETTE[i % PALETTE.length] },
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
  // 每个公司一个 series，便于异色 + 图例；我司红色加粗置顶
  const series = points.map((p, i) => ({
    name: p.corp,
    type: "scatter",
    symbolSize: p.is_us ? 16 : 11,
    z: p.is_us ? 20 : 1,
    data: [{ value: [p.dd, p.ret], name: p.corp }],
    itemStyle: { color: p.is_us ? ADLS.down : PALETTE[i % PALETTE.length] },
    label: {
      show: true,
      formatter: p.corp,
      position: "right",
      fontSize: 9,
      color: p.is_us ? ADLS.down : ADLS.slate700,
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
    xAxis: { type: "value", name: "加权最大回撤(%)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
    yAxis: { type: "value", name: "加权收益率(%)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
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
        lineStyle: { width: 2, color: ADLS.down }, itemStyle: { color: ADLS.down },
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
