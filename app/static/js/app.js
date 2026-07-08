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
  "#205781", "#4F959D", "#0F172A", "#64748B", "#94A3B8",
  "#7c8a9b", "#3b6e8f", "#5f8b94", "#2c5f7c", "#8aa3ad",
  "#1a4a6e", "#5d7a8c", "#3e6c7d", "#6990a0", "#456f82",
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
function renderTimeSeries(elId, data, field, valueSuffix, usName) {
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
    lineStyle: { width: corp === usName ? 2.6 : 1, color: corp === usName ? ADLS.down : PALETTE[i % PALETTE.length] },
    itemStyle: { color: corp === usName ? ADLS.down : PALETTE[i % PALETTE.length] },
    emphasis: { focus: "series" },
  }));
  const chart = echarts.init(el, null, { renderer: "canvas" });
  chart.setOption({
    backgroundColor: "transparent",
    grid: baseGrid(),
    tooltip: tooltip(),
    legend: legend(),
    xAxis: { type: "category", data: dates, ...axisStyle({ axisLabel: { color: ADLS.slate500, fontSize: 10, rotate: 0 } }) },
    yAxis: { type: "value", ...axisStyle(), axisLabel: { formatter: (v) => v + (valueSuffix || "") } },
    series,
  });
  window.addEventListener("resize", () => chart.resize());
}

/* 收益率 vs 最大回撤 散点 */
function renderScatter(elId, points, usName) {
  const el = document.getElementById(elId);
  if (!el || !points) return;
  const series = [
    {
      name: "同业",
      type: "scatter",
      symbolSize: 9,
      data: points.filter(p => !p.is_us).map(p => ({ value: [p.ret, p.dd], name: p.corp })),
      itemStyle: { color: ADLS.slate400 },
    },
    {
      name: usName,
      type: "scatter",
      symbolSize: 13,
      data: points.filter(p => p.is_us).map(p => ({ value: [p.ret, p.dd], name: p.corp })),
      itemStyle: { color: ADLS.down },
    },
  ];
  const chart = echarts.init(el, null, { renderer: "canvas" });
  chart.setOption({
    backgroundColor: "transparent",
    grid: baseGrid(),
    tooltip: {
      trigger: "item",
      backgroundColor: ADLS.bg, borderColor: ADLS.slate300,
      textStyle: { color: ADLS.slate700, fontSize: 11 },
      formatter: (p) => `${p.data.name}<br/>收益率: ${p.value[0]}%<br/>最大回撤: ${p.value[1]}%`,
    },
    legend: { textStyle: { color: ADLS.slate500, fontSize: 10 }, top: 0, itemWidth: 10, itemHeight: 8 },
    xAxis: { type: "value", name: "收益率(%)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
    yAxis: { type: "value", name: "最大回撤(%)", nameTextStyle: { color: ADLS.slate400, fontSize: 10 }, ...axisStyle() },
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
