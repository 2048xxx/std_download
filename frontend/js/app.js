/** 标准检索 / 同类产品 / 模块切换 */
(function () {
  const mainArea = document.getElementById("mainArea");
  const searchPanel = document.getElementById("searchPanel");
  const batchStage = document.getElementById("batchStage");
  const searchTools = document.getElementById("searchTools");
  const advancedPanel = document.getElementById("advancedPanel");
  const form = document.getElementById("searchForm");
  const input = document.getElementById("query");
  const results = document.getElementById("results");
  const btnSearch = document.getElementById("btnSearch");
  const historyWrap = document.getElementById("historyWrap");
  const historyChips = document.getElementById("historyChips");
  const productBanner = document.getElementById("productBanner");
  const productClusterList = document.getElementById("productClusterList");
  const pageTitle = document.getElementById("pageTitle");
  const pageSubtitle = document.getElementById("pageSubtitle");
  const headerDbStatus = document.getElementById("headerDbStatus");

  const PAGE_COPY = {
    search: {
      title: "企业级标准下载中心",
      subtitle: "构建专属合规资源库，支持先查询后筛选 / 先筛选后查询双模式。",
    },
    terminology: {
      title: "术语检索",
      subtitle: "输入术语即可查找定义所在的国标，支持 AI 语义扩展与 PDF 下载。",
    },
    product: {
      title: "同类产品标准检索",
      subtitle: "输入产品名称，自动扩展同类关键词并检索相关标准。",
    },
    tuangbiao: {
      title: "团标征求意见稿",
      subtitle: "按协会名、标准名称检索团标 PDF 文件。",
    },
    batch: {
      title: "Excel 批量下载",
      subtitle: "上传标准清单，自动匹配并打包 ZIP 下载。",
    },
  };

  const PER_PAGE = 10;
  const HISTORY_KEY = "pdf_search_history_v1";
  let currentMode = "search";
  let currentPage = 1;
  const modeQueries = { search: "", terminology: "", product: "", tuangbiao: "", batch: "" };

  function persistModeQuery() {
    if (input) modeQueries[currentMode] = input.value || "";
  }

  function restoreModeQuery(mode) {
    if (input) input.value = modeQueries[mode] || "";
  }

  function isCatalogMode(mode) {
    return mode === "tuangbiao";
  }

  function isSearchLikeMode(mode) {
    return mode === "search" || mode === "product" || mode === "terminology" || isCatalogMode(mode);
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function formatReleaseDate(raw) {
    if (!raw) return "—";
    const s = String(raw).trim();
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    const rfc = s.match(/(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})/);
    if (rfc) {
      const months = {
        Jan: "01", Feb: "02", Mar: "03", Apr: "04", May: "05", Jun: "06",
        Jul: "07", Aug: "08", Sep: "09", Oct: "10", Nov: "11", Dec: "12",
      };
      const mon = months[rfc[2]];
      if (mon) {
        return `${rfc[3]}-${mon}-${String(rfc[1]).padStart(2, "0")}`;
      }
    }
    const d = new Date(s);
    if (!Number.isNaN(d.getTime())) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${y}-${m}-${day}`;
    }
    return s.length > 10 ? s.slice(0, 10) : s;
  }

  function fmtSize(n) {
    if (!n) return "";
    const u = ["B", "KB", "MB", "GB"];
    let v = Number(n);
    let i = 0;
    while (v >= 1024 && i < u.length - 1) {
      v /= 1024;
      i++;
    }
    return `${v.toFixed(i ? 1 : 0)} ${u[i]}`;
  }

  function loadHistory() {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveHistory(q) {
    const text = (q || "").trim();
    if (!text) return;
    let list = loadHistory().filter(x => x !== text);
    list.unshift(text);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, 8)));
    renderHistory();
  }

  function renderHistory() {
    if (!historyWrap || !historyChips) return;
    if (currentMode !== "search") {
      historyWrap.classList.add("empty");
      historyWrap.hidden = true;
      return;
    }
    historyWrap.hidden = false;
    const list = loadHistory();
    if (!list.length) {
      historyWrap.classList.add("empty");
      historyChips.innerHTML = "";
      return;
    }
    historyWrap.classList.remove("empty");
    historyChips.innerHTML = list
      .map(
        q =>
          `<button type="button" class="chip" data-q="${escapeHtml(q)}"><span class="chip-text">${escapeHtml(q)}</span></button>`
      )
      .join("");
    historyChips.querySelectorAll(".chip").forEach(chip => {
      chip.addEventListener("click", () => {
        if (input) input.value = chip.dataset.q || "";
        doSearch(1);
      });
    });
  }

  function setMode(mode) {
    if (mode !== currentMode) {
      persistModeQuery();
    }
    currentMode = mode;
    if (!mainArea) return;
    mainArea.classList.remove("mode-search", "mode-batch", "mode-product", "mode-tuangbiao", "mode-terminology");
    if (mode === "batch") mainArea.classList.add("mode-batch");
    else if (mode === "product") mainArea.classList.add("mode-product");
    else if (mode === "tuangbiao") mainArea.classList.add("mode-tuangbiao");
    else if (mode === "terminology") mainArea.classList.add("mode-terminology");
    else mainArea.classList.add("mode-search");

    document.querySelectorAll(".nav-group[data-mode]").forEach(g => {
      const active = g.dataset.mode === mode;
      g.classList.toggle("active-mode", active);
      if (g.dataset.mode === "product") {
        g.classList.toggle("open", active);
      } else {
        g.classList.remove("open");
      }
    });

    applyModeUi(mode);
    restoreModeQuery(mode);
  }

  function updateCatalogBanner(mode) {
    if (!productBanner) return;
    if (mode !== "product") {
      productBanner.hidden = true;
    }
  }

  function applyModeUi(mode) {
    const searchLike = isSearchLikeMode(mode);
    const btnAdvanced = document.getElementById("btnAdvancedToggle");
    if (searchPanel) searchPanel.hidden = !searchLike && mode !== "batch";
    if (searchPanel && searchLike) searchPanel.hidden = false;
    if (historyWrap) historyWrap.hidden = mode !== "search";
    if (results) results.hidden = mode === "batch";
    if (batchStage) batchStage.hidden = mode !== "batch";
    if (searchTools) {
      const showTools = mode === "search" || mode === "terminology";
      searchTools.hidden = !showTools;
      if (showTools) searchTools.style.removeProperty("display");
    }
    const bulkBar = searchTools?.querySelector(".bulk-bar");
    if (bulkBar) bulkBar.hidden = mode !== "search";
    window.TerminologyUI?.updateWorkflowUi?.();
    const bulkScan = document.querySelector(".bulk-scan");
    if (bulkScan) {
      bulkScan.hidden = mode === "tuangbiao";
    }
    if (btnAdvanced) btnAdvanced.style.display = mode === "search" ? "" : "none";
    if (advancedPanel) {
      if (mode !== "search") {
        advancedPanel.hidden = true;
        btnAdvanced?.classList.remove("active");
      } else if (!btnAdvanced?.classList.contains("active")) {
        advancedPanel.hidden = true;
      }
    }
    const termBanner = document.getElementById("termSemanticBanner");
    if (termBanner && mode !== "terminology") termBanner.hidden = true;

    if (input) {
      const placeholders = {
        terminology: "输入术语，如：数据元、个人信息、网络安全",
        product: "输入产品名，如：牙膏、牛奶、化妆品",
        tuangbiao: "输入团标名称或协会名关键词",
      };
      input.placeholder = placeholders[mode] || "标准编号或名称关键词";
    }
    const btnLabels = { terminology: "术语检索", product: "同类检索", tuangbiao: "检索团标" };
    if (btnSearch) btnSearch.textContent = btnLabels[mode] || "检索";

    updateCatalogBanner(mode);
    updatePageHead(mode);

    if (mode === "batch" && batchStage) batchStage.style.display = "flex";
    window.AdvancedUI?.clearSelection?.();
    renderHistory();
  }

  document.querySelectorAll("[data-mode-switch]").forEach(btn => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.modeSwitch || "search";
      if (mode === "product" && currentMode === "product") {
        document
          .querySelector('.nav-group[data-mode="product"]')
          ?.classList.toggle("open");
        return;
      }
      setMode(mode);
      if (results && mode !== "batch") {
        results.innerHTML = "";
      }
    });
  });

  function updatePageHead(mode) {
    const copy = PAGE_COPY[mode] || PAGE_COPY.search;
    if (pageTitle) pageTitle.textContent = copy.title;
    if (pageSubtitle) pageSubtitle.textContent = copy.subtitle;
    const pageHead = document.getElementById("pageHead");
    if (pageHead) pageHead.hidden = mode === "batch";
  }

  function statusPillClass(label) {
    if (label === "现行") return "live";
    if (label === "即将实施") return "soon";
    return "old";
  }

  function firstDownloadHref(item) {
    if (currentMode === "tuangbiao") {
      return item.has_pdf || item.has_file ? `/api/tuangbiao/${item.id}/download` : null;
    }
    const files = (item.files || []).filter(f => f.exists);
    if (!files.length) return null;
    const f = files[0];
    if (f.source === "disk") return `/api/download-std/${item.id}/${f.disk_index ?? 0}`;
    if (f.id) return `/api/download/${f.id}`;
    return null;
  }

  function renderPager(data) {
    if (data.total_pages <= 1) return "";
    const pages = [];
    const maxShow = 7;
    let start = Math.max(1, data.page - 3);
    let end = Math.min(data.total_pages, start + maxShow - 1);
    start = Math.max(1, end - maxShow + 1);
    for (let p = start; p <= end; p += 1) {
      pages.push(
        `<button type="button" class="pager-num${p === data.page ? " active" : ""}" data-page="${p}">${p}</button>`
      );
    }
    const from = data.total ? (data.page - 1) * data.per_page + 1 : 0;
    const to = Math.min(data.page * data.per_page, data.total);
    return `<div class="pager">
      <span class="pager-info">显示 ${from} 至 ${to} 项，共 ${data.total} 项</span>
      <div class="pager-pages">
        <button type="button" id="pgPrev" ${data.page <= 1 ? "disabled" : ""} aria-label="上一页">‹</button>
        ${pages.join("")}
        <button type="button" id="pgNext" ${data.page >= data.total_pages ? "disabled" : ""} aria-label="下一页">›</button>
      </div>
    </div>`;
  }
  function fileExtIcon(ext) {
    const e = (ext || "").toLowerCase();
    if (e === ".pdf") return "PDF";
    if (e === ".doc" || e === ".docx") return "DOC";
    return "文件";
  }

  function renderDetailHtml(item) {
    const catalogHref =
      currentMode === "tuangbiao" ? `/api/tuangbiao/${item.id}/download` : null;
    const stdIdentity = name => {
      const stem = (name || "").replace(/\.pdf$/i, "");
      const token = stem
        .split(/_[FTZX]_/i)[0]
        .split(/[\u4e00-\u9fff]/)[0]
        .replace(/\s+/g, "")
        .replace(/\//g, "")
        .replace(/[—－]/g, "-")
        .toUpperCase();
      const m =
        token.match(/^([A-Z]{1,6})([TZX])([\d]+(?:\.\d+)*)(?:-(\d{2,4}))?$/i) ||
        token.match(/^([A-Z]{1,6})([\d]+(?:\.\d+)*)(?:-(\d{2,4}))?$/i);
      if (!m) return null;
      if (m[2] && /^\d/.test(m[2])) {
        const year = m[3] ? (m[3].length === 2 ? `20${m[3]}` : m[3]) : "";
        return year ? `${m[1]}${m[2]}-${year}` : `${m[1]}${m[2]}`;
      }
      const year = m[3] ? (m[3].length === 2 ? `20${m[3]}` : m[3]) : "";
      return year ? `${m[1]}${m[2]}-${year}` : `${m[1]}${m[2]}`;
    };
    const fileScore = f =>
      (f.exists ? 1 : 0) * 1e12 + (f.file_size || 0) + (f.id ? 1 : 0);
    const seen = new Map();
    const files = (item.files || [])
      .reduce((acc, f) => {
        const name = f.file_name || "";
        const key = stdIdentity(name) || `${(f.resolved_path || f.file_path || "").toLowerCase()}|${name.toLowerCase()}`;
        const prev = seen.get(key);
        if (prev === undefined) {
          seen.set(key, acc.length);
          acc.push(f);
        } else if (fileScore(f) > fileScore(acc[prev])) {
          acc[prev] = f;
        }
        return acc;
      }, [])
      .map(f => {
        const href =
          catalogHref ||
          (f.source === "disk"
            ? `/api/download-std/${item.id}/${f.disk_index ?? 0}`
            : f.id
              ? `/api/download/${f.id}`
              : "#");
        const icon = catalogHref ? fileExtIcon(f.file_ext) : "PDF";
        const meta = [
          f.file_size ? fmtSize(f.file_size) : "",
          f.source === "disk" ? "磁盘扫描" : f.source === "catalog" ? "目录索引" : "",
          !f.exists ? "磁盘未找到" : "",
        ]
          .filter(Boolean)
          .join(" · ");
        return `
          <div class="file-row">
            <div class="file-icon">${icon}</div>
            <div class="file-info ${f.exists ? "" : "missing"}">
              <div class="file-name">${escapeHtml(f.file_name || "—")}</div>
              <div class="file-meta">${escapeHtml(meta || "—")}</div>
            </div>
            ${
              f.exists
                ? `<a class="btn-dl" href="${href}" download>下载</a>`
                : `<span class="btn-dl disabled">无文件</span>`
            }
          </div>`;
      })
      .join("");
    const blockTitle = isCatalogMode(currentMode) ? "文件" : "PDF 文件";
    return `
      <div class="pdf-block">
        <h3>${blockTitle}</h3>
        ${files || '<div class="file-meta">暂无文件记录</div>'}
      </div>`;
  }

  async function loadRowDetail(id, detailRow) {
    if (!detailRow || detailRow.dataset.loaded === "1") return;
    const cell = detailRow.querySelector("td");
    if (!cell) return;
    if (isCatalogMode(currentMode)) {
      cell.innerHTML = `<div class="pdf-block"><p class="file-meta">团标文件请使用右侧下载按钮</p></div>`;
      detailRow.dataset.loaded = "1";
      return;
    }
    cell.innerHTML = '<div class="loading"><div class="spinner"></div>正在加载 PDF 详情…</div>';
    try {
      const res = await fetch(`/api/std/${id}?scan_disk=0`);
      const ct = res.headers.get("content-type") || "";
      if (!ct.includes("application/json")) {
        throw new Error(`详情加载失败（HTTP ${res.status}）`);
      }
      const data = await res.json();
      if (!data.ok || !data.item) {
        cell.innerHTML = `<div class="alert">${escapeHtml(data.error || "加载失败")}</div>`;
        return;
      }
      cell.innerHTML = renderDetailHtml(data.item);
      detailRow.dataset.loaded = "1";
      const row = results.querySelector(`tr.result-row[data-id="${id}"]`);
      const dl = row?.querySelector(".btn-row-dl");
      const href = firstDownloadHref(data.item);
      if (dl && href) {
        dl.classList.remove("disabled");
        dl.outerHTML = `<a class="btn-row-dl" href="${href}" download title="下载" onclick="event.stopPropagation()">↓</a>`;
      }
    } catch (e) {
      cell.innerHTML = `<div class="alert">${escapeHtml(e.message || "加载失败")}</div>`;
    }
  }

  function renderItems(data) {
    const items = data.items || [];

    if (data.resolved && productBanner && currentMode === "product") {
      const r = data.resolved;
      const kws = (r.keywords || []).slice(0, 12).join("、");
      const groups = (r.cluster_names || []).join("、") || "—";
      productBanner.innerHTML = `<strong>同类产品扩展检索</strong>
        <span class="resolve-sub">命中产品组：${escapeHtml(groups)}</span>
        <span class="resolve-sub">扩展词：${escapeHtml(kws)}${(r.keywords || []).length > 12 ? "…" : ""}</span>`;
      productBanner.hidden = false;
    } else if (productBanner) {
      productBanner.hidden = currentMode !== "product";
    }

    if (!items.length) {
      results.innerHTML =
        '<div class="empty">未找到匹配结果，可换关键词或调整高级筛选</div>';
      return;
    }

    const canBulk =
      currentMode === "search" ||
      currentMode === "product" ||
      isCatalogMode(currentMode);
    const from = data.total ? (data.page - 1) * data.per_page + 1 : 0;
    const to = Math.min(data.page * data.per_page, data.total);
    const advHint =
      currentMode === "search" && window.AdvancedUI?.filterSummary?.();
    let html = `<section class="results-card">`;
    if (advHint) {
      html += `<div class="adv-filter-banner">当前筛选：${escapeHtml(advHint)}</div>`;
    }
    html += `<div class="results-table-meta">显示 ${from} 至 ${to} 项，共 ${data.total} 项</div>`;
    html += `<div class="table-wrap"><table class="results-table"><thead><tr>`;
    if (canBulk) html += `<th class="col-check"><input type="checkbox" id="tblSelectPageHint" disabled aria-hidden="true" style="visibility:hidden" /></th>`;
    html += `<th class="col-code">标准编号</th><th class="col-name">标准名称</th><th class="col-date">发布日期</th><th class="col-status">状态</th><th class="col-action">操作</th></tr></thead><tbody>`;

    html += items
      .map(item => {
        const hasFile = item.has_pdf || item.has_file || isCatalogMode(currentMode);
        const bulkChecked = window.AdvancedUI?.isSelected?.(item.id) ? " checked" : "";
        const bulkDisabled = hasFile ? "" : " disabled";
        const statusLabel = item.ex_state_label || item.std_status || "—";
        const dlHref = firstDownloadHref(item);
        const checkCell = canBulk
          ? `<td class="col-check"><input type="checkbox" class="bulk-item-check" data-id="${item.id}" data-std-id="${escapeHtml(item.std_id || "")}"${bulkChecked}${bulkDisabled} onclick="event.stopPropagation()" /></td>`
          : "";
        return `
          <tr class="result-row" data-id="${item.id}">
            ${checkCell}
            <td class="col-code"><span class="cell-code">${escapeHtml(item.std_id || "—")}</span></td>
            <td class="col-name"><span class="cell-name">${escapeHtml(item.std_chinesename || "（无名称）")}</span></td>
            <td class="col-date">${escapeHtml(formatReleaseDate(item.release_date))}</td>
            <td class="col-status">
              <span class="status-pill ${statusPillClass(statusLabel)}">${escapeHtml(statusLabel)}</span>
              <span class="status-pill ${hasFile ? "pdf-yes" : "pdf-no"}" style="margin-left:0.25rem">${hasFile ? (isCatalogMode(currentMode) ? "有文件" : "PDF") : "无PDF"}</span>
            </td>
            <td class="col-action">
              ${
                dlHref
                  ? `<a class="btn-row-dl" href="${dlHref}" download title="下载" onclick="event.stopPropagation()">↓</a>`
                  : `<span class="btn-row-dl disabled">↓</span>`
              }
            </td>
          </tr>
          <tr class="result-detail-row" data-for="${item.id}" style="display:none">
            <td colspan="${canBulk ? 6 : 5}"><div class="detail-placeholder">展开此行加载 PDF 文件列表</div></td>
          </tr>`;
      })
      .join("");
    html += `</tbody></table></div>`;
    html += renderPager(data);
    html += `</section>`;
    results.innerHTML = html;

    results.querySelectorAll("tr.result-row").forEach(row => {
      row.addEventListener("click", e => {
        if (e.target.closest(".bulk-item-check, .btn-row-dl")) return;
        const id = row.dataset.id;
        const detail = results.querySelector(`.result-detail-row[data-for="${id}"]`);
        const open = !row.classList.contains("expanded");
        row.classList.toggle("expanded", open);
        if (detail) {
          detail.style.display = open ? "table-row" : "none";
          if (open) loadRowDetail(id, detail);
        }
      });
    });

    document.getElementById("pgPrev")?.addEventListener("click", () => doSearch(data.page - 1));
    document.getElementById("pgNext")?.addEventListener("click", () => doSearch(data.page + 1));
    results.querySelectorAll(".pager-num").forEach(btn => {
      btn.addEventListener("click", () => doSearch(Number(btn.dataset.page)));
    });

    window.AdvancedUI?.onResultsRendered?.(data, currentMode);
  }

  async function doSearch(page) {
    if (currentMode === "terminology") {
      window.TerminologyUI?.doSearch?.(page || 1);
      return;
    }
    const q = (input?.value || "").trim();
    const workflow = window.TerminologyUI?.getWorkflow?.() || "search_first";
    const advActive = currentMode === "search" && window.AdvancedUI?.hasActiveFilters?.();

    if (currentMode === "search" && workflow === "filter_first" && !advActive) {
      results.innerHTML = '<div class="alert">「先筛选后查询」：请先打开高级选项，设置条件并点击「应用筛选」</div>';
      return;
    }
    if (currentMode === "search" && workflow === "search_first" && !q) {
      results.innerHTML = '<div class="alert">「先查询后筛选」：请先输入标准编号或名称关键词</div>';
      return;
    }
    if (!q && !advActive) {
      const hints = {
        tuangbiao: "请输入团标名称或协会名关键词",
      };
      results.innerHTML = `<div class="alert">${escapeHtml(hints[currentMode] || "请输入关键词或设置高级筛选条件")}</div>`;
      return;
    }
    currentPage = page || 1;
    if (btnSearch) btnSearch.disabled = true;
    results.innerHTML =
      '<div class="loading"><div class="spinner"></div>正在检索…</div>';

    const params = new URLSearchParams();
    params.set("q", q);
    params.set("page", String(currentPage));
    params.set("per_page", String(PER_PAGE));
    params.set("enrich", "0");
    params.set("scan_disk", "0");
    if (currentMode === "product") {
      params.set("source", "product");
    } else if (isCatalogMode(currentMode)) {
      params.set("source", currentMode);
    } else if (advActive && window.AdvancedUI?.filterQuery) {
      if (window.AdvancedUI.validateRankFilter && !window.AdvancedUI.validateRankFilter()) {
        if (btnSearch) btnSearch.disabled = false;
        return;
      }
      const extra = new URLSearchParams(window.AdvancedUI.filterQuery());
      extra.forEach((v, k) => params.set(k, v));
    }
    if (currentMode === "search") params.set("workflow", workflow);

    try {
      const res = await fetch(`/api/search?${params.toString()}`);
      const ct = res.headers.get("content-type") || "";
      let data;
      if (ct.includes("application/json")) {
        data = await res.json();
      } else {
        const text = await res.text();
        throw new Error(
          res.status === 0
            ? "无法连接服务器，请确认已启动 启动.bat"
            : `服务器响应异常（HTTP ${res.status}），请重启服务后重试`
        );
      }
      if (!data.ok) {
        results.innerHTML = `<div class="alert">${escapeHtml(data.error || "检索失败")}</div>`;
        return;
      }
      if (currentMode === "search" && q) saveHistory(q);
      renderItems(data);
    } catch (e) {
      results.innerHTML = `<div class="alert">检索失败：${escapeHtml(e.message || "网络错误")}</div>`;
    } finally {
      if (btnSearch) btnSearch.disabled = false;
    }
  }

  async function loadProductClusters() {
    if (!productClusterList) return;
    try {
      const res = await fetch("/api/product/clusters");
      const data = await res.json();
      if (!data.ok) return;
      productClusterList.innerHTML = (data.clusters || [])
        .map(
          c => `<li><button type="button" class="cat-item" data-kw="${escapeHtml((c.keywords || [])[0] || c.name)}">${escapeHtml(c.name || c.id)}</button></li>`
        )
        .join("");
      productClusterList.querySelectorAll(".cat-item").forEach(btn => {
        btn.addEventListener("click", () => {
          setMode("product");
          if (input) {
            input.value = btn.dataset.kw || "";
            modeQueries.product = input.value;
          }
          doSearch(1);
        });
      });
    } catch (_) {}
  }

  if (form) {
    form.addEventListener("submit", e => {
      e.preventDefault();
      doSearch(1);
    });
  }

  window.addEventListener("advanced-search", () => doSearch(1));

  async function loadHealth() {
    if (!headerDbStatus) return;
    try {
      const res = await fetch("/api/meta/health");
      const data = await res.json();
      if (!data.ok) return;
      headerDbStatus.textContent = `数据库: ${data.db_backend || "—"} · ${data.db_ready ? "就绪" : "未就绪"}`;
    } catch (_) {
      headerDbStatus.textContent = "服务连接中…";
    }
  }

  renderHistory();
  loadProductClusters();
  loadHealth();
  setMode("search");

  window.AppUI = { setMode, doSearch, getMode: () => currentMode, renderPager };
})();
