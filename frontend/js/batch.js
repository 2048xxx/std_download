/** 批量 Excel → 后端检索 PDF → ZIP 下载（含 Excel 备注回写） */
(function () {
  const el = id => document.getElementById(id);
  const batchFile = el("batchFile");
  const btnBatchParse = el("btnBatchParse");
  const btnBatchPreview = el("btnBatchPreview");
  const btnBatchDownload = el("btnBatchDownload");
  const batchScanDisk = el("batchScanDisk");
  const batchMeta = el("batchMeta");
  const batchTableWrap = el("batchTableWrap");
  const batchTableSection = el("batchTableSection");
  const batchFileName = el("batchFileName");
  const batchDropzone = el("batchDropzone");
  const btnBatchTemplate = el("btnBatchTemplate");
  const batchFeedback = el("batchFeedback");
  const batchStage = el("batchStage");
  const batchSteps = el("batchSteps");
  const btnBatchBack = el("btnBatchBack");

  let parsedItems = [];
  let parsedMeta = null;
  let previewMap = new Map();

  const FETCH_TIMEOUT_MS = 30 * 60 * 1000;

  function fetchWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUT_MS) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const { signal: outerSignal, ...rest } = options;
    if (outerSignal) {
      if (outerSignal.aborted) controller.abort();
      else outerSignal.addEventListener("abort", () => controller.abort(), { once: true });
    }
    return fetch(url, { ...rest, signal: controller.signal }).finally(() => clearTimeout(timer));
  }

  function fetchErrorMessage(e, fallback) {
    if (e?.name === "AbortError") {
      return "请求超时。请减少批量条数、关闭「扫描磁盘」，或稍后重试。";
    }
    return e?.message || fallback || "未知错误";
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function statusLabel(status) {
    const map = {
      ok: "可下载",
      not_found: "未找到",
      no_pdf: "无 PDF",
      empty: "空行",
      error: "错误",
    };
    return map[status] || status || "—";
  }

  function statusClass(status) {
    if (status === "ok") return "batch-ok";
    if (status === "not_found" || status === "no_pdf") return "batch-warn";
    return "batch-fail";
  }

  function setStep(step) {
    if (!batchSteps) return;
    batchSteps.querySelectorAll("li[data-step]").forEach(li => {
      const n = Number(li.dataset.step);
      li.classList.toggle("is-active", n === step);
      li.classList.toggle("is-done", n < step);
    });
  }

  function setFileName(name) {
    if (!batchFileName) return;
    batchFileName.textContent = name || "未选择文件";
    batchFileName.classList.toggle("has-file", !!name);
  }

  function showTableSection(show) {
    if (batchTableSection) batchTableSection.hidden = !show;
    if (show) batchStage?.classList.add("has-table");
    else batchStage?.classList.remove("has-table");
  }

  function setFeedback(html) {
    if (!batchFeedback) return;
    if (html) {
      batchFeedback.innerHTML = html;
      batchFeedback.hidden = false;
      batchStage?.classList.add("has-feedback");
    } else {
      batchFeedback.innerHTML = "";
      batchFeedback.hidden = true;
      batchStage?.classList.remove("has-feedback");
    }
  }

  function setMeta(text) {
    if (batchMeta) batchMeta.textContent = text || "";
  }

  function setBusy(busy) {
    if (btnBatchParse) btnBatchParse.disabled = busy;
    if (btnBatchPreview) btnBatchPreview.disabled = busy || !parsedItems.length;
    if (btnBatchDownload) btnBatchDownload.disabled = busy || !parsedItems.length;
  }

  function renderTable() {
    if (!batchTableWrap) return;
    if (!parsedItems.length) {
      batchTableWrap.innerHTML = "";
      showTableSection(false);
      return;
    }
    showTableSection(true);
    let html = `<table class="batch-table"><thead><tr>
      <th>行</th><th>标准号</th><th>标准名</th><th>PDF</th><th>状态</th>
    </tr></thead><tbody>`;
    parsedItems.forEach(it => {
      const prev = previewMap.get(it.row);
      const st = prev?.status || "—";
      html += `<tr>
        <td>${it.row}</td>
        <td>${escapeHtml(it.query)}</td>
        <td class="batch-name">${escapeHtml(prev?.std_chinesename || it.name_hint || "—")}</td>
        <td>${escapeHtml(prev?.file_name || prev?.pdf_name || "—")}</td>
        <td><span class="batch-status ${statusClass(st)}">${escapeHtml(statusLabel(st))}</span></td>
      </tr>`;
    });
    html += "</tbody></table>";
    batchTableWrap.innerHTML = html;
  }

  async function doParse() {
    const file = batchFile?.files?.[0];
    if (!file) {
      setFeedback('<div class="alert">请先选择 Excel 或 CSV 文件</div>');
      return;
    }
    setFileName(file.name);
    setBusy(true);
    previewMap = new Map();
    setFeedback('<div class="loading"><div class="spinner"></div>正在解析 Excel…</div>');
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetchWithTimeout("/api/batch/parse", { method: "POST", body: fd }, 120000);
      const data = await res.json();
      if (!data.ok) {
        setFeedback(`<div class="alert">${escapeHtml(data.error || "解析失败")}</div>`);
        parsedItems = [];
        parsedMeta = null;
        renderTable();
        return;
      }
      parsedItems = data.items || [];
      parsedMeta = data.meta || null;
      const trunc = parsedMeta?.truncated ? `（已达上限 ${parsedMeta.max_rows} 条）` : "";
      setMeta(`已识别 ${parsedItems.length} 条标准号${trunc}`);
      renderTable();
      setStep(2);
      setFeedback(
        '<div class="batch-hint">解析完成。可先「预览匹配」，再「下载 ZIP」。后端将自动从 E 盘标准库查找 PDF，未找到项在 Excel 备注中填「否」。</div>'
      );
      if (btnBatchPreview) btnBatchPreview.disabled = false;
      if (btnBatchDownload) btnBatchDownload.disabled = false;
    } catch (e) {
      setFeedback(`<div class="alert">解析失败：${escapeHtml(fetchErrorMessage(e, "未知错误"))}</div>`);
    } finally {
      setBusy(false);
    }
  }

  async function doPreview() {
    if (!parsedItems.length) {
      setFeedback('<div class="alert">请先解析 Excel</div>');
      return;
    }
    setBusy(true);
    setFeedback('<div class="loading"><div class="spinner"></div>正在匹配标准（预览）…</div>');
    try {
      const res = await fetchWithTimeout(
        "/api/batch/preview",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            items: parsedItems,
            scan_disk: batchScanDisk?.checked === true,
          }),
        },
        10 * 60 * 1000
      );
      const data = await res.json();
      if (!data.ok) {
        setFeedback(`<div class="alert">${escapeHtml(data.error || "预览失败")}</div>`);
        return;
      }
      previewMap = new Map();
      (data.items || []).forEach((r, i) => {
        const row = parsedItems[i]?.row ?? r.row ?? i + 1;
        previewMap.set(row, r);
      });
      renderTable();
      setStep(3);
      const s = data.summary || {};
      setFeedback(
        `<div class="batch-hint">预览完成：共 ${s.total} 条，预计可下载 <strong>${s.success}</strong> 个 PDF，失败 ${s.failed} 条。</div>`
      );
    } catch (e) {
      setFeedback(`<div class="alert">预览失败：${escapeHtml(fetchErrorMessage(e, "未知错误"))}</div>`);
    } finally {
      setBusy(false);
    }
  }

  async function doDownload() {
    if (!parsedItems.length) {
      setFeedback('<div class="alert">请先解析 Excel</div>');
      return;
    }
    const file = batchFile?.files?.[0];
    if (!file) {
      setFeedback('<div class="alert">请重新选择 Excel 文件后再下载</div>');
      return;
    }
    setBusy(true);
    setFeedback('<div class="loading"><div class="spinner"></div>正在匹配标准并打包 ZIP，请稍候…</div>');
    try {
      const scan = batchScanDisk?.checked === true;
      const fd = new FormData();
      fd.append("file", file);
      fd.append("items", JSON.stringify(parsedItems));
      const res = await fetchWithTimeout(
        `/api/batch/download?scan_disk=${scan ? "1" : "0"}`,
        { method: "POST", body: fd }
      );
      const ctype = res.headers.get("content-type") || "";
      if (!res.ok) {
        let err = "下载失败";
        if (ctype.includes("json")) {
          const data = await res.json();
          err = data.error || err;
          if (data.summary) {
            previewMap = new Map();
            (data.summary.results || []).forEach(r => previewMap.set(r.row, r));
            renderTable();
          }
        }
        setFeedback(`<div class="alert">${escapeHtml(err)}</div>`);
        return;
      }
      const blob = await res.blob();
      const disp = res.headers.get("content-disposition") || "";
      let name = "标准PDF批量下载.zip";
      const m = /filename\*?=(?:UTF-8'')?["']?([^"';]+)/i.exec(disp);
      if (m) name = decodeURIComponent(m[1].trim());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
      setFeedback(
        '<div class="batch-hint">ZIP 已开始下载。内含 PDF、带「否」备注的 Excel 及下载清单。<br/>⚠️ <strong>重要提示：</strong>若下载被浏览器拦截，请在浏览器右上角下载列表或地址栏右侧选择<strong>「保留」</strong>或<strong>「允许下载」</strong>。</div>'
      );
      setStep(3);
    } catch (e) {
      setFeedback(`<div class="alert">下载失败：${escapeHtml(fetchErrorMessage(e, "未知错误"))}</div>`);
    } finally {
      setBusy(false);
    }
  }

  function bindDropzone(zone, input, onFiles) {
    if (!zone || !input) return;
    ["dragenter", "dragover"].forEach(ev => {
      zone.addEventListener(ev, e => {
        e.preventDefault();
        zone.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach(ev => {
      zone.addEventListener(ev, e => {
        e.preventDefault();
        zone.classList.remove("is-dragover");
      });
    });
    zone.addEventListener("drop", e => {
      const files = e.dataTransfer?.files;
      if (!files?.length) return;
      onFiles(files);
    });
  }

  if (batchFile) {
    batchFile.addEventListener("change", () => {
      const f = batchFile.files?.[0];
      setFileName(f ? f.name : "");
      parsedItems = [];
      parsedMeta = null;
      previewMap = new Map();
      renderTable();
      setStep(1);
      if (btnBatchPreview) btnBatchPreview.disabled = true;
      if (btnBatchDownload) btnBatchDownload.disabled = true;
    });
  }

  if (btnBatchBack) {
    btnBatchBack.addEventListener("click", () => {
      showTableSection(false);
      setStep(parsedItems.length ? 2 : 1);
    });
  }

  bindDropzone(batchDropzone, batchFile, files => {
    const file = files[0];
    if (!file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    batchFile.files = dt.files;
    batchFile.dispatchEvent(new Event("change"));
  });

  if (btnBatchTemplate) {
    btnBatchTemplate.addEventListener("click", e => {
      e.preventDefault();
      setStep(1);
      window.location.href = "/api/batch/template";
    });
  }
  if (btnBatchParse) btnBatchParse.addEventListener("click", doParse);
  if (btnBatchPreview) btnBatchPreview.addEventListener("click", doPreview);
  if (btnBatchDownload) btnBatchDownload.addEventListener("click", doDownload);

  setMeta("后端模式 · 自动读 E 盘 · 支持 .xlsx / .csv · 单次最多 400 条");
  setStep(1);

  fetch("/api/meta/health")
    .then(r => r.json())
    .then(info => {
      if (!info.db_ready) {
        setFeedback(
          '<div class="alert">标准库未就绪。请先运行 <code>python scripts/build_index.py</code> 构建索引；或勾选「扫描磁盘」仅按文件名查找 PDF。</div>'
        );
      } else if (!info.pdf_root_exists) {
        setFeedback(
          `<div class="alert">PDF 根目录不存在（${escapeHtml(info.pdf_root)}）。请检查 paths.py 或 .env 中的 PDF_ROOT。</div>`
        );
      }
    })
    .catch(() => {});
})();
