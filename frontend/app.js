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
  zoom: "fizzylog.zoom",
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

function loadStoredZoom() {
  const raw = localStorage.getItem(STORAGE_KEYS.zoom);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    const start = parsed && typeof parsed.start === "number" ? parsed.start : null;
    const end = parsed && typeof parsed.end === "number" ? parsed.end : null;
    if (start === null || end === null) {
      return null;
    }
    if (start < 0 || end > 100 || start >= end) {
      return null;
    }
    return { start, end };
  } catch (error) {
    return null;
  }
}

let zoomSaveTimer = null;
function scheduleZoomSave(payload) {
  if (!payload) {
    return;
  }
  if (zoomSaveTimer) {
    clearTimeout(zoomSaveTimer);
  }
  zoomSaveTimer = setTimeout(() => {
    const start = typeof payload.start === "number" ? payload.start : null;
    const end = typeof payload.end === "number" ? payload.end : null;
    if (start === null || end === null) {
      return;
    }
    localStorage.setItem(STORAGE_KEYS.zoom, JSON.stringify({ start, end }));
  }, 120);
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
  const storedZoom = loadStoredZoom();
  chart.setOption({
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
      bottom: 56,
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
    dataZoom: [
      {
        type: "slider",
        height: 20,
        bottom: 16,
        borderColor: "#e2ded7",
        fillerColor: "rgba(42, 111, 105, 0.15)",
        handleStyle: { color: "#2a6f69" },
        textStyle: { color: "#6b6760" },
        start: storedZoom ? storedZoom.start : undefined,
        end: storedZoom ? storedZoom.end : undefined,
      },
    ],
    series: [],
  });
  chart.on("datazoom", (event) => {
    if (event && typeof event.start === "number" && typeof event.end === "number") {
      scheduleZoomSave({ start: event.start, end: event.end });
      return;
    }
    const option = chart.getOption();
    if (option && option.dataZoom && option.dataZoom[0]) {
      scheduleZoomSave(option.dataZoom[0]);
    }
  });
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

  chart.setOption(
    { series: chartSeries },
    { notMerge: false, replaceMerge: ["series"] }
  );
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
