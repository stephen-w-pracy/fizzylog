/* global echarts */

const statusEl = document.getElementById("status");
const rangeChipsEl = document.getElementById("range-chips");
const exactInputEl = document.getElementById("exact-input");

let meta = null;
let chart = null;
let refreshTimer = null;

const RANGE_OPTIONS = ["2xx", "3xx", "4xx", "5xx"];
let selectedRanges = new Set();
const STORAGE_KEYS = {
  ranges: "fizzylog.statusRanges",
  exact: "fizzylog.statusExact",
};

function setStatus(message) {
  statusEl.textContent = message;
}

function buildChip(label) {
  const button = document.createElement("button");
  button.className = "chip";
  button.textContent = label;
  button.addEventListener("click", () => {
    if (selectedRanges.has(label)) {
      selectedRanges.delete(label);
    } else {
      selectedRanges.add(label);
    }
    persistRanges();
    syncChipState();
    fetchAndRender();
  });
  return button;
}

function syncChipState() {
  const buttons = rangeChipsEl.querySelectorAll(".chip");
  buttons.forEach((button) => {
    const label = button.textContent;
    if (selectedRanges.has(label)) {
      button.classList.add("active");
    } else {
      button.classList.remove("active");
    }
  });
}

function buildQuery() {
  const exactValue = exactInputEl.value.trim();
  if (exactValue.length > 0) {
    return `status_exact=${encodeURIComponent(exactValue)}`;
  }
  const ranges = Array.from(selectedRanges);
  if (ranges.length === 0 && meta) {
    ranges.push(...meta.status_filter.default_ranges);
  }
  return `status_ranges=${encodeURIComponent(ranges.join(","))}`;
}

function persistRanges() {
  const values = Array.from(selectedRanges);
  localStorage.setItem(STORAGE_KEYS.ranges, JSON.stringify(values));
}

function persistExact() {
  const value = exactInputEl.value.trim();
  if (value.length === 0) {
    localStorage.removeItem(STORAGE_KEYS.exact);
    return;
  }
  localStorage.setItem(STORAGE_KEYS.exact, value);
}

function loadStoredRanges() {
  const raw = localStorage.getItem(STORAGE_KEYS.ranges);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return null;
    }
    const filtered = parsed.filter((item) => RANGE_OPTIONS.includes(item));
    return filtered.length > 0 ? filtered : null;
  } catch (error) {
    return null;
  }
}

function loadStoredExact() {
  const raw = localStorage.getItem(STORAGE_KEYS.exact);
  if (!raw) {
    return "";
  }
  return raw;
}

async function fetchMeta() {
  const response = await fetch("/api/v1/meta");
  if (!response.ok) {
    throw new Error("Failed to load meta");
  }
  return response.json();
}

async function fetchSeries() {
  const query = buildQuery();
  const response = await fetch(`/api/v1/series?${query}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to load series");
  }
  return response.json();
}

function initChart() {
  const el = document.getElementById("chart");
  chart = echarts.init(el, null, { renderer: "canvas" });
  window.addEventListener("resize", () => chart.resize());
}

function renderSeries(seriesResponse) {
  const bucketStarts = seriesResponse.bucket_start_utc || [];
  const timestamps = bucketStarts.map((value) => value * 1000);

  const chartSeries = (seriesResponse.series || []).map((item) => {
    const data = timestamps.map((ts, idx) => [ts, item.counts[idx] || 0]);
    return {
      name: item.path,
      type: "line",
      showSymbol: false,
      smooth: false,
      data,
    };
  });

  const option = {
    animation: false,
    tooltip: {
      trigger: "axis",
    },
    legend: {
      top: 0,
    },
    grid: {
      left: 40,
      right: 24,
      top: 40,
      bottom: 32,
    },
    xAxis: {
      type: "time",
      axisLine: { lineStyle: { color: "#c8c2b9" } },
    },
    yAxis: {
      type: "value",
      min: 0,
      splitLine: { lineStyle: { color: "#eee8e0" } },
    },
    series: chartSeries,
  };

  chart.setOption(option, true);
}

async function fetchAndRender() {
  try {
    const series = await fetchSeries();
    renderSeries(series);
    setStatus(`Updated ${new Date().toLocaleTimeString()}`);
  } catch (error) {
    setStatus("Error loading data");
    console.error(error);
  }
}

function setupControls() {
  rangeChipsEl.innerHTML = "";
  RANGE_OPTIONS.forEach((range) => {
    rangeChipsEl.appendChild(buildChip(range));
  });
  syncChipState();

  exactInputEl.addEventListener("input", () => {
    persistExact();
    fetchAndRender();
  });
}

async function init() {
  try {
    meta = await fetchMeta();
    const storedRanges = loadStoredRanges();
    const storedExact = loadStoredExact();
    selectedRanges = new Set(storedRanges || meta.status_filter.default_ranges || []);
    if (storedExact) {
      exactInputEl.value = storedExact;
    }
    setupControls();
    initChart();
    await fetchAndRender();

    const refreshSeconds = meta.ui.refresh_seconds || 2;
    if (refreshTimer) {
      clearInterval(refreshTimer);
    }
    refreshTimer = setInterval(fetchAndRender, refreshSeconds * 1000);
  } catch (error) {
    setStatus("Failed to initialize");
    console.error(error);
  }
}

init();
