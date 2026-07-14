/** 高级筛选 + 检索结果多项下载 */
(function () {
  const el = id => document.getElementById(id);
  const panel = el("advancedPanel");
  const btnToggle = el("btnAdvancedToggle");
  const btnBulk = el("btnBulkDownload");
  const btnGeo = el("btnGeoDownload");
  const chkPage = el("chkSelectPage");
  const searchTools = el("searchTools");

  const fields = {
    exState: el("advExState"),
    stdType: el("advStdType"),
    province: el("advProvince"),
    city: el("advCity"),
    county: el("advCounty"),
    product: el("advProduct"),
    company: el("advCompany"),
    unitRank: el("advUnitRank"),
    yearFrom: el("advYearFrom"),
    yearTo: el("advYearTo"),
  };

  const selected = new Map();
  let lastPageIds = [];
  let filtersLoaded = false;
  const ADV_FILTER_HISTORY_KEY = "pdf_adv_filter_history_v1";
  const advFilterHistory = el("advFilterHistory");
  const advHistoryChips = el("advHistoryChips");
  const CURRENT_YEAR = new Date().getFullYear();
  const YEAR_MIN = 1980;

  function rankLabel(value) {
    if (value === "1") return "第1位";
    if (value === "2") return "第2位";
    if (value === "3") return "第3位";
    if (value === "gt3") return "大于三";
    return "";
  }

  function snapshotFilters() {
    return {
      exState: fields.exState?.value || "",
      stdType: fields.stdType?.value || "",
      province: fields.province?.value || "",
      city: fields.city?.value || "",
      county: fields.county?.value || "",
      product: fields.product?.value.trim() || "",
      company: fields.company?.value.trim() || "",
      unitRank: fields.unitRank?.value || "",
      yearFrom: fields.yearFrom?.value || "",
      yearTo: fields.yearTo?.value || "",
      q: el("query")?.value.trim() || "",
    };
  }

  function historyHasContent(snap) {
    return Boolean(
      snap.q ||
        snap.company ||
        snap.province ||
        snap.product ||
        snap.stdType ||
        snap.exState ||
        snap.yearFrom ||
        snap.yearTo
    );
  }

  function historyLabel(snap) {
    const parts = [];
    if (snap.q) parts.push(snap.q);
    if (snap.company) {
      let text = snap.company;
      if (snap.unitRank) text += ` · ${rankLabel(snap.unitRank)}`;
      parts.push(text);
    }
    const region = [snap.province, snap.city, snap.county].filter(Boolean).join("");
    if (region) parts.push(region);
    if (snap.product) parts.push(snap.product);
    if (snap.stdType) parts.push(snap.stdType);
    return parts.join(" / ") || "筛选条件";
  }

  function loadFilterHistory() {
    try {
      return JSON.parse(localStorage.getItem(ADV_FILTER_HISTORY_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveFilterHistory() {
    const snap = snapshotFilters();
    if (!historyHasContent(snap)) return;
    const key = JSON.stringify(snap);
    let list = loadFilterHistory().filter(item => JSON.stringify(item) !== key);
    list.unshift(snap);
    list = list.slice(0, 8);
    localStorage.setItem(ADV_FILTER_HISTORY_KEY, JSON.stringify(list));
    renderFilterHistory();
  }

  function renderFilterHistory() {
    if (!advFilterHistory || !advHistoryChips) return;
    const list = loadFilterHistory();
    if (!list.length) {
      advFilterHistory.hidden = true;
      advHistoryChips.innerHTML = "";
      return;
    }
    advFilterHistory.hidden = false;
    advHistoryChips.innerHTML = list
      .map(
        (snap, i) =>
          `<button type="button" class="chip adv-history-chip" data-idx="${i}" title="点击恢复此筛选">
            <span class="chip-text">${escapeHtml(historyLabel(snap))}</span>
            <span class="chip-del" data-del="${i}" aria-label="删除">×</span>
          </button>`
      )
      .join("");
    advHistoryChips.querySelectorAll(".adv-history-chip").forEach(btn => {
      btn.addEventListener("click", e => {
        if (e.target.closest(".chip-del")) return;
        const idx = Number(btn.dataset.idx);
        const snap = loadFilterHistory()[idx];
        if (snap) applyFilterHistory(snap);
      });
    });
    advHistoryChips.querySelectorAll(".chip-del").forEach(del => {
      del.addEventListener("click", e => {
        e.stopPropagation();
        const idx = Number(del.dataset.del);
        const list = loadFilterHistory();
        list.splice(idx, 1);
        localStorage.setItem(ADV_FILTER_HISTORY_KEY, JSON.stringify(list));
        renderFilterHistory();
      });
    });
  }

  async function applyFilterHistory(snap) {
    if (!snap) return;
    if (fields.exState) fields.exState.value = snap.exState || "";
    if (fields.stdType) fields.stdType.value = snap.stdType || "";
    if (fields.product) fields.product.value = snap.product || "";
    if (fields.company) fields.company.value = snap.company || "";
    if (fields.unitRank) fields.unitRank.value = snap.unitRank || "";
    if (fields.yearFrom) fields.yearFrom.value = snap.yearFrom || "";
    if (fields.yearTo) fields.yearTo.value = snap.yearTo || "";
    if (fields.province) fields.province.value = "";
    if (fields.city) fields.city.value = "";
    if (fields.county) fields.county.value = "";
    if (snap.province) {
      if (!filtersLoaded) await loadFilters();
      if (fields.province) fields.province.value = snap.province;
      await loadFilters({ province: snap.province });
      if (fields.city) fields.city.value = snap.city || "";
      if (snap.city) await loadFilters({ province: snap.province, city: snap.city });
      if (fields.county) fields.county.value = snap.county || "";
    }
    const qInput = el("query");
    if (qInput) qInput.value = snap.q || "";
    updateGeoBtn();
    if (!validateRankFilter()) return;
    saveFilterHistory();
    window.dispatchEvent(new CustomEvent("advanced-search"));
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function fillSelect(select, items, placeholder, valueKey, labelKey) {
    if (!select) return;
    const cur = select.value;
    select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>`;
    (items || []).forEach(it => {
      const opt = document.createElement("option");
      if (typeof it === "string") {
        opt.value = it;
        opt.textContent = it;
      } else {
        opt.value = String(it[valueKey] ?? "");
        opt.textContent = String(it[labelKey] ?? it[valueKey] ?? "");
      }
      select.appendChild(opt);
    });
    if (cur && [...select.options].some(o => o.value === cur)) {
      select.value = cur;
    }
  }

  function initYearSelects() {
    const years = [];
    for (let y = CURRENT_YEAR; y >= YEAR_MIN; y -= 1) {
      years.push(String(y));
    }
    fillSelect(fields.yearFrom, years, "不限");
    fillSelect(fields.yearTo, years, "不限");
  }

  function applyYearPreset(spanYears) {
    const span = Number(spanYears);
    if (!span || span < 1) return;
    const to = CURRENT_YEAR;
    const from = Math.max(YEAR_MIN, to - span + 1);
    if (fields.yearFrom) fields.yearFrom.value = String(from);
    if (fields.yearTo) fields.yearTo.value = String(to);
  }

  function syncYearRange() {
    const from = fields.yearFrom?.value;
    const to = fields.yearTo?.value;
    if (from && to && Number(from) > Number(to)) {
      fields.yearTo.value = from;
    }
  }

  let productSuggestItems = [];
  const productPanel = el("advProductPanel");
  let productComboOpen = false;
  let productActiveIdx = -1;

  function buildProductItems(products, suggestions) {
    const seen = new Set();
    const items = [];
    const add = (value, label) => {
      const v = String(value || "").trim();
      if (!v || seen.has(v)) return;
      seen.add(v);
      items.push({ value: v, label: label && label !== v ? label : "" });
    };
    (products || []).forEach(p => {
      add(p.name, p.name);
      (p.keywords || []).forEach(kw => add(kw, `${p.name} · ${kw}`));
    });
    (suggestions || []).forEach(s => add(s, s));
    return items;
  }

  function setProductSuggestions(products, suggestions) {
    productSuggestItems = buildProductItems(products, suggestions);
    if (productComboOpen) renderProductPanel(fields.product?.value || "");
  }

  function filterProductItems(query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return productSuggestItems.slice(0, 48);
    return productSuggestItems
      .filter(
        it =>
          it.value.toLowerCase().includes(q) ||
          (it.label && it.label.toLowerCase().includes(q))
      )
      .slice(0, 48);
  }

  function renderProductPanel(query) {
    if (!productPanel) return;
    const items = filterProductItems(query);
    if (!items.length) {
      hideProductPanel();
      return;
    }
    productPanel.innerHTML = items
      .map((it, i) => {
        const hint = it.label
          ? `<span class="adv-combo-hint">${escapeHtml(it.label)}</span>`
          : "";
        const active = i === productActiveIdx ? " active" : "";
        return `<button type="button" class="adv-combo-item${active}" role="option" data-value="${escapeHtml(it.value)}">${escapeHtml(it.value)}${hint}</button>`;
      })
      .join("");
    productPanel.hidden = false;
    productComboOpen = true;
  }

  function hideProductPanel() {
    if (!productPanel) return;
    productPanel.hidden = true;
    productComboOpen = false;
    productActiveIdx = -1;
  }

  function pickProduct(value) {
    if (fields.product) fields.product.value = value;
    hideProductPanel();
  }

  function initProductCombo() {
    const input = fields.product;
    if (!input || !productPanel) return;

    input.addEventListener("focus", () => {
      productActiveIdx = -1;
      if (!productSuggestItems.length && !filtersLoaded) loadFilters();
      renderProductPanel(input.value);
    });

    input.addEventListener("input", () => {
      productActiveIdx = -1;
      renderProductPanel(input.value);
    });

    input.addEventListener("keydown", e => {
      if (!productComboOpen) return;
      const buttons = [...productPanel.querySelectorAll(".adv-combo-item")];
      if (e.key === "ArrowDown") {
        e.preventDefault();
        productActiveIdx = Math.min(productActiveIdx + 1, buttons.length - 1);
        renderProductPanel(input.value);
        productPanel.querySelectorAll(".adv-combo-item")[productActiveIdx]?.scrollIntoView({
          block: "nearest",
        });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        productActiveIdx = Math.max(productActiveIdx - 1, 0);
        renderProductPanel(input.value);
        productPanel.querySelectorAll(".adv-combo-item")[productActiveIdx]?.scrollIntoView({
          block: "nearest",
        });
      } else if (e.key === "Enter" && productActiveIdx >= 0) {
        e.preventDefault();
        const btn = productPanel.querySelectorAll(".adv-combo-item")[productActiveIdx];
        if (btn) pickProduct(btn.dataset.value);
      } else if (e.key === "Escape") {
        hideProductPanel();
      }
    });

    productPanel.addEventListener("mousedown", e => {
      e.preventDefault();
      const btn = e.target.closest(".adv-combo-item");
      if (btn) pickProduct(btn.dataset.value);
    });

    input.addEventListener("blur", () => {
      setTimeout(hideProductPanel, 150);
    });
  }

  let companySuggestItems = [];
  const companyPanel = el("advCompanyPanel");
  let companyComboOpen = false;
  let companyActiveIdx = -1;
  let companySuggestTimer = null;
  let companySuggestLoading = false;
  let companySuggestSeq = 0;

  function companyInputActive() {
    return document.activeElement === fields.company;
  }

  function setCompanySuggestions(names) {
    companySuggestItems = (names || [])
      .map(n => String(n || "").trim())
      .filter(Boolean)
      .map(v => ({ value: v, label: "" }));
    companySuggestLoading = false;
    if (companyInputActive() || (fields.company?.value.trim().length >= 2)) {
      renderCompanyPanel(fields.company?.value || "");
    }
  }

  function rankCompanyItems(items, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return items;
    return [...items].sort((a, b) => {
      const av = a.value.toLowerCase();
      const bv = b.value.toLowerCase();
      const ap = av.startsWith(q) ? 0 : 1;
      const bp = bv.startsWith(q) ? 0 : 1;
      if (ap !== bp) return ap - bp;
      return av.length - bv.length || av.localeCompare(bv, "zh-CN");
    });
  }

  function filterCompanyItems(query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return companySuggestItems.slice(0, 48);
    return rankCompanyItems(
      companySuggestItems.filter(it => it.value.toLowerCase().includes(q)),
      q
    ).slice(0, 48);
  }

  function renderCompanyPanel(query) {
    if (!companyPanel) return;
    const q = String(query || "").trim();
    const items = filterCompanyItems(query);
    if (q.length >= 2 && companySuggestLoading && !items.length) {
      companyPanel.innerHTML = `<div class="adv-combo-empty">加载中…</div>`;
      companyPanel.hidden = false;
      companyComboOpen = true;
      return;
    }
    if (!items.length) {
      if (q.length >= 2 && !companySuggestLoading) {
        companyPanel.innerHTML = `<div class="adv-combo-empty">无匹配单位</div>`;
        companyPanel.hidden = false;
        companyComboOpen = true;
        return;
      }
      hideCompanyPanel();
      return;
    }
    companyPanel.innerHTML = items
      .map((it, i) => {
        const active = i === companyActiveIdx ? " active" : "";
        return `<button type="button" class="adv-combo-item${active}" role="option" data-value="${escapeHtml(it.value)}">${escapeHtml(it.value)}</button>`;
      })
      .join("");
    companyPanel.hidden = false;
    companyComboOpen = true;
  }

  function hideCompanyPanel() {
    if (!companyPanel) return;
    companyPanel.hidden = true;
    companyComboOpen = false;
    companyActiveIdx = -1;
  }

  function pickCompany(value) {
    if (fields.company) fields.company.value = value;
    hideCompanyPanel();
  }

  async function fetchCompanySuggestions(query) {
    const q = String(query || "").trim();
    clearTimeout(companySuggestTimer);
    if (q.length < 2) {
      companySuggestLoading = false;
      companySuggestItems = [];
      hideCompanyPanel();
      return;
    }
    companySuggestLoading = true;
    renderCompanyPanel(q);
    companySuggestTimer = setTimeout(async () => {
      const seq = ++companySuggestSeq;
      try {
        const res = await fetch(
          "/api/search/filters?company_q=" + encodeURIComponent(q)
        );
        const data = await res.json();
        if (seq !== companySuggestSeq) return;
        if (data.ok) setCompanySuggestions(data.companies);
        else companySuggestLoading = false;
      } catch (_) {
        if (seq === companySuggestSeq) {
          companySuggestLoading = false;
          renderCompanyPanel(fields.company?.value || q);
        }
      }
    }, 200);
  }

  function initCompanyCombo() {
    const input = fields.company;
    if (!input || !companyPanel) return;

    input.addEventListener("focus", () => {
      companyActiveIdx = -1;
      fetchCompanySuggestions(input.value);
    });

    input.addEventListener("input", () => {
      companyActiveIdx = -1;
      fetchCompanySuggestions(input.value);
    });

    input.addEventListener("keydown", e => {
      if (!companyComboOpen) return;
      const buttons = [...companyPanel.querySelectorAll(".adv-combo-item")];
      if (e.key === "ArrowDown") {
        e.preventDefault();
        companyActiveIdx = Math.min(companyActiveIdx + 1, buttons.length - 1);
        renderCompanyPanel(input.value);
        companyPanel.querySelectorAll(".adv-combo-item")[companyActiveIdx]?.scrollIntoView({
          block: "nearest",
        });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        companyActiveIdx = Math.max(companyActiveIdx - 1, 0);
        renderCompanyPanel(input.value);
        companyPanel.querySelectorAll(".adv-combo-item")[companyActiveIdx]?.scrollIntoView({
          block: "nearest",
        });
      } else if (e.key === "Enter" && companyActiveIdx >= 0) {
        e.preventDefault();
        const btn = companyPanel.querySelectorAll(".adv-combo-item")[companyActiveIdx];
        if (btn) pickCompany(btn.dataset.value);
      } else if (e.key === "Escape") {
        hideCompanyPanel();
      }
    });

    companyPanel.addEventListener("mousedown", e => {
      e.preventDefault();
      const btn = e.target.closest(".adv-combo-item");
      if (btn) pickCompany(btn.dataset.value);
    });

    input.addEventListener("blur", () => {
      setTimeout(hideCompanyPanel, 150);
    });
  }

  function appendFilterParams(p) {
    if (fields.exState?.value) p.set("ex_state", fields.exState.value);
    if (fields.stdType?.value) p.set("std_type", fields.stdType.value);
    if (fields.province?.value) p.set("province", fields.province.value);
    if (fields.city?.value) p.set("city", fields.city.value);
    if (fields.county?.value) p.set("county", fields.county.value);
    if (fields.product?.value.trim()) p.set("product", fields.product.value.trim());
    if (fields.company?.value.trim()) p.set("company", fields.company.value.trim());
    if (fields.unitRank?.value) p.set("unit_rank", fields.unitRank.value);
    if (fields.yearFrom?.value) p.set("year_from", fields.yearFrom.value);
    if (fields.yearTo?.value) p.set("year_to", fields.yearTo.value);
  }

  async function loadFilters(opts = {}) {
    const params = new URLSearchParams();
    if (opts.province) params.set("province", opts.province);
    if (opts.city) params.set("city", opts.city);
    if (opts.company_q) params.set("company_q", opts.company_q);
    if (opts.product_q) params.set("product_q", opts.product_q);
    try {
      const res = await fetch("/api/search/filters?" + params.toString());
      const data = await res.json();
      if (!data.ok) return;
      if (data.provinces && !opts.province && !opts.company_q && !opts.product_q) {
        fillSelect(fields.province, data.provinces, "省（全部）");
        fillSelect(fields.stdType, data.std_types, "标准类型（全部）");
        setProductSuggestions(data.products, null);
        if (fields.exState && fields.exState.options.length <= 1) {
          fillSelect(fields.exState, data.ex_states, "状态（全部）", "value", "label");
        }
        filtersLoaded = true;
      }
      if (opts.province) fillSelect(fields.city, data.cities, "市（全部）");
      if (opts.province && opts.city) fillSelect(fields.county, data.counties, "县/区（全部）");
      if (opts.product_q) {
        setProductSuggestions(data.products, data.product_suggestions);
      }
      if (opts.company_q) {
        setCompanySuggestions(data.companies);
        if (companyComboOpen) renderCompanyPanel(fields.company?.value || "");
      }
    } catch (_) {}
  }

  function hasActiveFilters() {
    return Object.entries(fields).some(([key, f]) => {
      if (!f) return false;
      if (key === "unitRank") {
        return Boolean(fields.company?.value.trim() && String(f.value || "").trim());
      }
      return Boolean(String(f.value || "").trim());
    });
  }

  function validateRankFilter() {
    if (fields.unitRank?.value && !fields.company?.value.trim()) {
      alert("「起草顺位」必须同时填写「公司/起草单位」，否则会按「任一顺位」匹配。");
      fields.unitRank.value = "";
      return false;
    }
    return true;
  }

  function filterSummary() {
    const parts = [];
    if (fields.province?.value) parts.push(fields.province.value);
    if (fields.city?.value) parts.push(fields.city.value);
    if (fields.county?.value) parts.push(fields.county.value);
    if (fields.company?.value.trim()) {
      parts.push(`起草单位含「${fields.company.value.trim()}」`);
    }
    if (fields.unitRank?.value && fields.company?.value.trim()) {
      parts.push(
        fields.unitRank.value === "gt3"
          ? "顺位大于三"
          : `仅第 ${fields.unitRank.value} 位`
      );
    }
    if (fields.product?.value.trim()) parts.push(`产品「${fields.product.value.trim()}」`);
    return parts.join(" · ");
  }

  function filterQuery() {
    const p = new URLSearchParams();
    p.set("advanced", "1");
    appendFilterParams(p);
    return p.toString();
  }

  function updateGeoBtn() {
    if (!btnGeo) return;
    const hasProvince = Boolean(fields.province?.value);
    btnGeo.disabled = !hasProvince;
    btnGeo.title = hasProvince
      ? "下载所选省/市条件下全部标准 PDF"
      : "需先选择省份";
  }

  function geoFilterParams() {
    const p = new URLSearchParams();
    appendFilterParams(p);
    p.set("pdf_only", "1");
    const q = el("query")?.value?.trim();
    if (q) p.set("q", q);
    return p;
  }

  function geoFilterBody() {
    const body = {};
    if (fields.exState?.value) body.ex_state = fields.exState.value;
    if (fields.stdType?.value) body.std_type = fields.stdType.value;
    if (fields.province?.value) body.province = fields.province.value;
    if (fields.city?.value) body.city = fields.city.value;
    if (fields.county?.value) body.county = fields.county.value;
    if (fields.product?.value.trim()) body.product = fields.product.value.trim();
    if (fields.company?.value.trim()) body.company = fields.company.value.trim();
    if (fields.unitRank?.value) body.unit_rank = fields.unitRank.value;
    if (fields.yearFrom?.value) body.year_from = fields.yearFrom.value;
    if (fields.yearTo?.value) body.year_to = fields.yearTo.value;
    body.pdf_only = true;
    body.scan_disk = false;
    const q = el("query")?.value?.trim();
    if (q) body.q = q;
    return body;
  }

  async function doGeoDownload() {
    if (!fields.province?.value) {
      alert("请先选择省份");
      return;
    }
    if (btnGeo) {
      btnGeo.disabled = true;
      btnGeo.textContent = "统计中…";
    }
    try {
      const previewRes = await fetch("/api/download/geo/preview?" + geoFilterParams().toString());
      const preview = await previewRes.json();
      if (!preview.ok) {
        alert(preview.error || "无法统计匹配数量");
        return;
      }
      const region = [fields.province?.value, fields.city?.value, fields.county?.value]
        .filter(Boolean)
        .join(" · ");
      let msg = `将下载「${region}」范围内共 ${preview.total} 条标准中的 PDF`;
      if (preview.capped) {
        msg += `\n（单次最多 ${preview.limit} 条，将下载前 ${preview.download_count} 条）`;
      }
      msg += "。\n打包可能需要较长时间，是否继续？";
      if (!window.confirm(msg)) return;

      if (btnGeo) btnGeo.textContent = "打包中…";
      const res = await fetch("/api/download/geo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(geoFilterBody()),
      });
      if (!res.ok) {
        let err = "下载失败";
        try {
          const j = await res.json();
          err = j.error || err;
        } catch (_) {}
        alert(err);
        return;
      }
      const blob = await res.blob();
      const disp = res.headers.get("content-disposition") || "";
      let name = "地区批量下载.zip";
      const m = /filename\*?=(?:UTF-8'')?["']?([^"';]+)/i.exec(disp);
      if (m) name = decodeURIComponent(m[1].trim());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message || "网络错误");
    } finally {
      updateGeoBtn();
      if (btnGeo) btnGeo.textContent = "地区批量下载";
    }
  }

  function updateBulkBtn() {
    const n = selected.size;
    const countEl = document.getElementById("bulkCount");
    if (countEl) countEl.textContent = String(n);
    if (btnBulk) btnBulk.disabled = n < 1;
  }

  function pageSelectableIds() {
    return lastPageIds.filter(id => {
      const row = document.querySelector(`.result-row[data-id="${id}"]`);
      const cb = row?.querySelector(".bulk-item-check");
      return cb && !cb.disabled;
    });
  }

  function syncPageCheckbox() {
    if (!chkPage) return;
    const ids = pageSelectableIds();
    if (!ids.length) {
      chkPage.checked = false;
      chkPage.indeterminate = false;
      return;
    }
    const checked = ids.filter(id => selected.has(Number(id))).length;
    chkPage.checked = checked === ids.length;
    chkPage.indeterminate = checked > 0 && checked < ids.length;
  }

  function toggleSelect(id, stdId, hasPdf, checked, syncMaster = true) {
    id = Number(id);
    if (checked) selected.set(id, { id, std_id: stdId, has_pdf: hasPdf });
    else selected.delete(id);
    updateBulkBtn();
    if (syncMaster) syncPageCheckbox();
  }

  function onResultsRendered(data, searchMode) {
    if (searchMode === "batch") return;
    if (
      searchMode !== "search" &&
      searchMode !== "product" &&
      searchMode !== "tuangbiao"
    ) {
      return;
    }

    lastPageIds = (data.items || []).map(item => item.id);
    document.querySelectorAll(".bulk-item-check").forEach(cb => {
      if (cb.dataset.bound === "1") return;
      cb.dataset.bound = "1";
      cb.addEventListener("change", () => {
        const id = Number(cb.dataset.id);
        toggleSelect(id, cb.dataset.stdId || "", !cb.disabled, cb.checked);
      });
    });
    syncPageCheckbox();
    updateBulkBtn();
  }

  function clearSelection() {
    selected.clear();
    updateBulkBtn();
    document.querySelectorAll(".bulk-item-check").forEach(cb => {
      cb.checked = false;
    });
    syncPageCheckbox();
  }

  async function doBulkDownload() {
    if (!selected.size) return;
    const mode = window.AppUI?.getMode?.() || "search";
    const isCatalog = mode === "tuangbiao";
    if (btnBulk) {
      btnBulk.disabled = true;
      btnBulk.textContent = "打包中…";
    }
    try {
      const body = { ids: [...selected.keys()] };
      if (isCatalog) body.source = mode;
      else body.scan_disk = false;
      const res = await fetch("/api/download/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        let err = "下载失败";
        try {
          const j = await res.json();
          err = j.error || err;
        } catch (_) {}
        alert(err);
        return;
      }
      const blob = await res.blob();
      const disp = res.headers.get("content-disposition") || "";
      let name = "标准PDF多项下载.zip";
      const m = /filename\*?=(?:UTF-8'')?["']?([^"';]+)/i.exec(disp);
      if (m) name = decodeURIComponent(m[1].trim());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message || "网络错误");
    } finally {
      if (btnBulk) {
        btnBulk.disabled = selected.size < 1;
        btnBulk.textContent = "";
        btnBulk.append("多项下载 (");
        const span = document.createElement("span");
        span.id = "bulkCount";
        span.textContent = String(selected.size);
        btnBulk.append(span, ")");
      }
    }
  }

  function resetFilters() {
    Object.values(fields).forEach(f => {
      if (f) f.value = "";
    });
    fillSelect(fields.city, [], "市（全部）");
    fillSelect(fields.county, [], "县/区（全部）");
    hideProductPanel();
    hideCompanyPanel();
    updateGeoBtn();
  }

  if (btnToggle && panel) {
    btnToggle.addEventListener("click", () => {
      const open = panel.hidden;
      panel.hidden = !open;
      btnToggle.classList.toggle("active", open);
      if (open && !filtersLoaded) loadFilters();
    });
  }

  fields.province?.addEventListener("change", () => {
    if (fields.city) fields.city.value = "";
    if (fields.county) fields.county.value = "";
    loadFilters({ province: fields.province.value });
    updateGeoBtn();
  });
  fields.city?.addEventListener("change", () => {
    if (fields.county) fields.county.value = "";
    loadFilters({ province: fields.province?.value, city: fields.city.value });
    updateGeoBtn();
  });
  fields.county?.addEventListener("change", updateGeoBtn);
  if (fields.product) {
    let pt = null;
    fields.product.addEventListener("input", () => {
      clearTimeout(pt);
      const v = fields.product.value.trim();
      if (v.length < 1) return;
      pt = setTimeout(() => loadFilters({ product_q: v }), 280);
    });
  }

  el("btnAdvancedApply")?.addEventListener("click", () => {
    if (!validateRankFilter()) return;
    const workflow = window.TerminologyUI?.getWorkflow?.() || "search_first";
    if (workflow === "search_first" && !el("query")?.value?.trim()) {
      alert("「先查询后筛选」：请先输入关键词并完成检索，再叠加筛选。");
      return;
    }
    saveFilterHistory();
    window.dispatchEvent(new CustomEvent("advanced-search"));
  });
  el("btnAdvancedReset")?.addEventListener("click", resetFilters);

  fields.unitRank?.addEventListener("change", () => {
    if (!fields.company?.value.trim()) return;
    if (!validateRankFilter()) return;
    window.dispatchEvent(new CustomEvent("advanced-search"));
  });

  initYearSelects();
  initProductCombo();
  initCompanyCombo();
  renderFilterHistory();
  fields.yearFrom?.addEventListener("change", syncYearRange);
  fields.yearTo?.addEventListener("change", syncYearRange);
  document.querySelectorAll(".year-preset").forEach(btn => {
    btn.addEventListener("click", () => applyYearPreset(btn.dataset.years));
  });

  chkPage?.addEventListener("change", e => {
    const want = e.target.checked;
    pageSelectableIds().forEach(id => {
      const row = document.querySelector(`.result-row[data-id="${id}"]`);
      const cb = row?.querySelector(".bulk-item-check");
      if (!cb) return;
      cb.checked = want;
      toggleSelect(id, cb.dataset.stdId || "", true, want, false);
    });
    updateBulkBtn();
    syncPageCheckbox();
  });

  btnBulk?.addEventListener("click", doBulkDownload);
  btnGeo?.addEventListener("click", doGeoDownload);

  updateGeoBtn();

  window.AdvancedUI = {
    filterQuery,
    filterSummary,
    hasActiveFilters,
    validateRankFilter,
    onResultsRendered,
    clearSelection,
    resetFilters,
    isSelected: id => selected.has(Number(id)),
  };
})();
