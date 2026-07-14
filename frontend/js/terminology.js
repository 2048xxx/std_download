/** 术语检索 + 检索工作流 UI */
(function () {
  const WORKFLOW_KEY = "pdf_search_workflow_v2";

  function getWorkflow() {
    const active = document.querySelector(".workflow-tab.active");
    return active?.dataset.workflow || "search_first";
  }

  function setWorkflow(mode) {
    document.querySelectorAll(".workflow-tab").forEach(btn => {
      const on = btn.dataset.workflow === mode;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    localStorage.setItem(WORKFLOW_KEY, mode);
    updateWorkflowUi();
  }

  function loadWorkflow() {
    const saved = localStorage.getItem(WORKFLOW_KEY);
    if (saved === "filter_first" || saved === "search_first") setWorkflow(saved);
    else updateWorkflowUi();
  }

  function updateWorkflowUi() {
    const mode = getWorkflow();
    const appMode = window.AppUI?.getMode?.() || "search";
    const segment = document.getElementById("workflowSegment");
    const guide = document.getElementById("workflowGuide");
    const steps = document.getElementById("workflowSteps");
    const tip = document.getElementById("workflowGuideTip");
    const query = document.getElementById("query");
    const btnApply = document.getElementById("btnAdvancedApply");
    const advHint = document.getElementById("advancedPanelHint");
    const termToolbar = document.getElementById("termToolbar");

    const isSearch = appMode === "search";
    const isTerm = appMode === "terminology";

    if (segment) segment.hidden = !isSearch;
    if (guide) guide.hidden = !isSearch;
    if (termToolbar) termToolbar.hidden = !isTerm;

    if (!isSearch) return;

    if (mode === "filter_first") {
      if (steps) {
        steps.innerHTML = `
          <span class="wf-step active" data-step="1"><em>1</em><span class="wf-step-text">设置高级筛选</span></span>
          <span class="wf-arrow">→</span>
          <span class="wf-step" data-step="2"><em>2</em><span class="wf-step-text">范围内关键词检索</span></span>`;
      }
      if (tip) tip.textContent = "先打开「高级选项」设置省/市/单位等条件并应用，再在搜索框输入关键词缩小范围。";
      if (query) query.placeholder = "在已筛选范围内输入关键词（可选）";
      if (btnApply) btnApply.textContent = "应用筛选（第 1 步）";
      if (advHint) advHint.textContent = "先筛选后查询：设置条件后点击「应用筛选」建立范围";
    } else {
      if (steps) {
        steps.innerHTML = `
          <span class="wf-step active" data-step="1"><em>1</em><span class="wf-step-text">输入关键词检索</span></span>
          <span class="wf-arrow">→</span>
          <span class="wf-step" data-step="2"><em>2</em><span class="wf-step-text">叠加高级筛选</span></span>`;
      }
      if (tip) tip.textContent = "先在搜索框输入标准编号或名称检索，再打开「高级选项」叠加筛选条件。";
      if (query) query.placeholder = "标准编号或名称关键词，如 GB/T 1002-2024、煤矿";
      if (btnApply) btnApply.textContent = "在此基础上筛选（第 2 步）";
      if (advHint) advHint.textContent = "先查询后筛选：完成检索后可叠加省/市/单位等条件";
    }
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function renderSemanticBanner(data) {
    const banner = document.getElementById("termSemanticBanner");
    if (!banner) return;
    const sem = data.semantic || {};
    const kws = (sem.keywords || []).slice(0, 10);
    if (!kws.length) {
      banner.hidden = true;
      return;
    }
    const srcLabel = sem.source === "ai" ? "AI 语义" : sem.source === "local" ? "本地扩展" : "";
    banner.hidden = false;
    banner.innerHTML = `
      <div class="term-banner-inner">
        <span class="term-banner-tag">${escapeHtml(srcLabel || "扩展")}</span>
        <span class="term-banner-kws">${escapeHtml(kws.join(" · "))}</span>
        ${sem.semantic_note ? `<span class="term-banner-note">${escapeHtml(sem.semantic_note)}</span>` : ""}
      </div>`;
  }

  function renderTermResults(data, container) {
    renderSemanticBanner(data);
    const items = data.items || [];
    if (!items.length) {
      container.innerHTML = '<div class="empty-state"><p>未找到包含该术语的国标</p><p class="empty-hint">可换词、关闭「仅国标」或构建术语索引后重试</p></div>';
      return;
    }

    const from = data.total ? (data.page - 1) * data.per_page + 1 : 0;
    const to = Math.min(data.page * data.per_page, data.total);
    let html = `<section class="results-card term-results-card">`;
    if (data.fallback) {
      html += `<div class="adv-filter-banner">术语索引未构建，当前为标准名称模糊匹配</div>`;
    }
    html += `<div class="results-table-meta">共 ${data.total} 条 · 显示 ${from}–${to}</div>`;
    html += `<div class="table-wrap"><table class="results-table term-table"><thead><tr>
      <th>术语</th><th>定义</th><th>所在国标</th><th>标准名称</th><th class="col-action">操作</th>
    </tr></thead><tbody>`;

    html += items.map(item => {
      const baseId = item.base_id || item.id;
      const hasPdf = item.has_pdf;
      const dlBtn = hasPdf
        ? `<button type="button" class="btn-term-dl" data-base="${baseId}" title="下载 PDF">下载</button>`
        : `<span class="btn-term-dl disabled">无 PDF</span>`;
      return `<tr class="term-row" data-id="${baseId}">
        <td class="col-term"><strong>${escapeHtml(item.term)}</strong></td>
        <td class="col-def"><p class="term-def-text">${escapeHtml(item.definition)}</p></td>
        <td class="col-code"><code>${escapeHtml(item.std_id)}</code></td>
        <td class="col-name">${escapeHtml(item.std_chinesename || "—")}</td>
        <td class="col-action">${dlBtn}</td>
      </tr>`;
    }).join("");

    html += `</tbody></table></div>`;
    html += window.AppUI?.renderPager?.(data) || "";
    html += `</section>`;
    container.innerHTML = html;

    container.querySelectorAll(".btn-term-dl[data-base]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const baseId = btn.dataset.base;
        try {
          const res = await fetch(`/api/std/${baseId}?scan_disk=0`);
          const j = await res.json();
          if (!j.ok || !j.item) {
            alert(j.error || "未找到文件");
            return;
          }
          const files = (j.item.files || []).filter(f => f.exists);
          if (!files.length) {
            alert("未找到可下载的 PDF");
            return;
          }
          const f = files[0];
          window.location.href = f.source === "disk"
            ? `/api/download-std/${baseId}/${f.disk_index ?? 0}`
            : `/api/download/${f.id}`;
        } catch (e) {
          alert(e.message || "下载失败");
        }
      });
    });

    bindPager(container, data);
  }

  function bindPager(container, data) {
    container.querySelector("#pgPrev")?.addEventListener("click", () => doTermSearch(data.page - 1));
    container.querySelector("#pgNext")?.addEventListener("click", () => doTermSearch(data.page + 1));
    container.querySelectorAll(".pager-num").forEach(btn => {
      btn.addEventListener("click", () => doTermSearch(Number(btn.dataset.page)));
    });
  }

  async function doTermSearch(page) {
    const input = document.getElementById("query");
    const results = document.getElementById("results");
    const btnSearch = document.getElementById("btnSearch");
    const q = (input?.value || "").trim();
    if (!q) {
      if (results) results.innerHTML = '<div class="alert">请输入术语，如：数据元、个人信息、网络安全</div>';
      return;
    }
    if (btnSearch) btnSearch.disabled = true;
    if (results) results.innerHTML = '<div class="loading"><div class="spinner"></div>正在检索术语…</div>';

    const params = new URLSearchParams({
      q, page: String(page || 1), per_page: "10", enrich: "1",
      gb_only: document.getElementById("chkGbOnly")?.checked !== false ? "1" : "0",
      semantic: document.getElementById("chkTermSemantic")?.checked !== false ? "1" : "0",
      scan_disk: "0",
    });

    try {
      const res = await fetch(`/api/terminology/search?${params}`);
      const data = await res.json();
      if (!data.ok) {
        results.innerHTML = `<div class="alert">${escapeHtml(data.error || "检索失败")}</div>`;
        return;
      }
      renderTermResults(data, results);
    } catch (e) {
      results.innerHTML = `<div class="alert">检索失败：${escapeHtml(e.message)}</div>`;
    } finally {
      if (btnSearch) btnSearch.disabled = false;
    }
  }

  document.querySelectorAll(".workflow-tab").forEach(btn => {
    btn.addEventListener("click", () => setWorkflow(btn.dataset.workflow || "search_first"));
  });

  loadWorkflow();

  window.TerminologyUI = {
    doSearch: doTermSearch,
    updateWorkflowUi,
    getWorkflow,
    setWorkflow,
  };
})();
