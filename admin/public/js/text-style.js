// 「文字の装飾の設定」画面の動作。
(async function () {
  const messageEl = document.getElementById("message");
  const listEl = document.getElementById("text-styles-list");
  const form = document.getElementById("text-style-form");
  const nameInput = document.getElementById("name-input");
  const badgeBgColor = document.getElementById("badge-bg-color");
  const badgeTextColor = document.getElementById("badge-text-color");
  const badgeWeight = document.getElementById("badge-weight");
  const accentColor = document.getElementById("accent-color");
  const accentWeight = document.getElementById("accent-weight");
  const bodyTextColor = document.getElementById("body-text-color");
  const bodyWeight = document.getElementById("body-weight");
  const submitBtn = document.getElementById("submit-btn");

  const WEIGHT_LABELS = {
    regular: "標準",
    medium: "やや太め",
    semibold: "太め",
    bold: "かなり太め",
    extrabold: "最も太い",
  };

  let fontWeights = ["regular", "medium", "semibold", "bold", "extrabold"];

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function fillWeightSelect(selectEl, selected) {
    selectEl.innerHTML = fontWeights
      .map((w) => `<option value="${w}" ${w === selected ? "selected" : ""}>${WEIGHT_LABELS[w] || w}</option>`)
      .join("");
  }

  async function loadTextStyles() {
    listEl.innerHTML = '<div class="loading">読み込み中です…</div>';
    try {
      const { text_styles: textStyles, font_weights: weights } = await Api.listTextStyles();
      if (weights && weights.length) fontWeights = weights;
      renderTextStyles(textStyles);
    } catch (e) {
      listEl.innerHTML = "";
      showMessage(e.message, "error");
    }
  }

  function renderTextStyles(textStyles) {
    if (!textStyles || textStyles.length === 0) {
      listEl.innerHTML = '<p class="empty-state">まだパターンが登録されていません。下のフォームから追加してください。</p>';
      return;
    }

    listEl.innerHTML = "";
    textStyles.forEach((style) => {
      const item = document.createElement("div");
      item.className = "text-item";
      item.innerHTML = `
        <div class="meta">
          <div>
            <strong>${escapeHtml(style.name)}</strong>
            ${style.is_default ? '<span class="tag">既定</span>' : ""}
            <div class="style-swatch-row">
              <span class="style-swatch" style="background:${style.badge_bg_color}" title="バッジ背景色"></span>
              <span class="style-swatch" style="background:${style.accent_color}" title="強調ワードの色"></span>
              <span class="style-swatch" style="background:${style.body_text_color}" title="本文の色"></span>
            </div>
          </div>
          <div class="card-actions">
            ${style.is_default ? "" : '<button type="button" class="secondary set-default-btn">既定にする</button>'}
            <button type="button" class="secondary edit-btn">編集する</button>
            <button type="button" class="danger delete-btn">削除する</button>
          </div>
        </div>
        <div class="edit-panel" style="display:none"></div>
      `;

      const editBtn = item.querySelector(".edit-btn");
      const deleteBtn = item.querySelector(".delete-btn");
      const setDefaultBtn = item.querySelector(".set-default-btn");
      const editPanel = item.querySelector(".edit-panel");

      editBtn.addEventListener("click", () => {
        const isOpen = editPanel.style.display !== "none";
        if (isOpen) {
          editPanel.style.display = "none";
          editPanel.innerHTML = "";
          editBtn.textContent = "編集する";
          return;
        }
        openEditor(editPanel, style);
        editPanel.style.display = "block";
        editBtn.textContent = "編集をとじる";
      });

      if (setDefaultBtn) {
        setDefaultBtn.addEventListener("click", async () => {
          setDefaultBtn.disabled = true;
          try {
            await Api.updateTextStyle(style.id, { set_default: true });
            showMessage(`「${style.name}」を既定のパターンにしました。`, "success");
            await loadTextStyles();
          } catch (e) {
            showMessage(e.message, "error");
            setDefaultBtn.disabled = false;
          }
        });
      }

      deleteBtn.addEventListener("click", async () => {
        if (!window.confirm(`「${style.name}」を削除します。よろしいですか？（元に戻せません）`)) return;
        deleteBtn.disabled = true;
        try {
          await Api.deleteTextStyle(style.id);
          showMessage("パターンを削除しました。", "success");
          await loadTextStyles();
        } catch (e) {
          showMessage(e.message, "error");
          deleteBtn.disabled = false;
        }
      });

      listEl.appendChild(item);
    });
  }

  function openEditor(panel, style) {
    panel.innerHTML = `
      <div class="field">
        <label class="field-label">パターンの名前</label>
        <input type="text" class="edit-name" />
      </div>
      <div class="field">
        <label class="field-label">部屋番号バッジ</label>
        <div class="style-row">
          <label class="style-subfield">背景色 <input type="color" class="edit-badge-bg-color" /></label>
          <label class="style-subfield">文字色 <input type="color" class="edit-badge-text-color" /></label>
          <label class="style-subfield">太さ <select class="edit-badge-weight"></select></label>
        </div>
      </div>
      <div class="field">
        <label class="field-label">強調ワード（最大宿泊人数など）</label>
        <div class="style-row">
          <label class="style-subfield">文字色 <input type="color" class="edit-accent-color" /></label>
          <label class="style-subfield">太さ <select class="edit-accent-weight"></select></label>
        </div>
      </div>
      <div class="field">
        <label class="field-label">本文</label>
        <div class="style-row">
          <label class="style-subfield">文字色 <input type="color" class="edit-body-text-color" /></label>
          <label class="style-subfield">太さ <select class="edit-body-weight"></select></label>
        </div>
      </div>
      <div class="button-row">
        <button type="button" class="save-btn">保存する</button>
      </div>
    `;

    panel.querySelector(".edit-name").value = style.name || "";
    panel.querySelector(".edit-badge-bg-color").value = style.badge_bg_color || "#c45a3c";
    panel.querySelector(".edit-badge-text-color").value = style.badge_text_color || "#ffffff";
    fillWeightSelect(panel.querySelector(".edit-badge-weight"), style.badge_weight || "extrabold");
    panel.querySelector(".edit-accent-color").value = style.accent_color || "#c45a3c";
    fillWeightSelect(panel.querySelector(".edit-accent-weight"), style.accent_weight || "bold");
    panel.querySelector(".edit-body-text-color").value = style.body_text_color || "#2d1e16";
    fillWeightSelect(panel.querySelector(".edit-body-weight"), style.body_weight || "medium");

    panel.querySelector(".save-btn").addEventListener("click", async () => {
      const btn = panel.querySelector(".save-btn");
      const newName = panel.querySelector(".edit-name").value.trim();
      if (!newName) {
        showMessage("パターンの名前を入力してください。", "error");
        return;
      }
      btn.disabled = true;
      btn.textContent = "保存しています…";
      try {
        await Api.updateTextStyle(style.id, {
          name: newName,
          badge_bg_color: panel.querySelector(".edit-badge-bg-color").value,
          badge_text_color: panel.querySelector(".edit-badge-text-color").value,
          badge_weight: panel.querySelector(".edit-badge-weight").value,
          accent_color: panel.querySelector(".edit-accent-color").value,
          accent_weight: panel.querySelector(".edit-accent-weight").value,
          body_text_color: panel.querySelector(".edit-body-text-color").value,
          body_weight: panel.querySelector(".edit-body-weight").value,
        });
        showMessage("パターンの内容を更新しました。", "success");
        await loadTextStyles();
      } catch (e) {
        showMessage(e.message, "error");
        btn.disabled = false;
        btn.textContent = "保存する";
      }
    });
  }

  const currentUser = await requireLogin();
  if (!currentUser) return;

  try {
    const { font_weights: weights } = await Api.listTextStyles();
    if (weights && weights.length) fontWeights = weights;
  } catch (e) {
    // 一覧取得時にまとめてエラー表示するため、ここでは無視する
  }
  fillWeightSelect(badgeWeight, "extrabold");
  fillWeightSelect(accentWeight, "bold");
  fillWeightSelect(bodyWeight, "medium");

  await loadTextStyles();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = nameInput.value.trim();
    if (!name) {
      showMessage("パターンの名前を入力してください。", "error");
      return;
    }
    submitBtn.disabled = true;
    submitBtn.textContent = "追加しています…";
    try {
      await Api.createTextStyle({
        name,
        badge_bg_color: badgeBgColor.value,
        badge_text_color: badgeTextColor.value,
        badge_weight: badgeWeight.value,
        accent_color: accentColor.value,
        accent_weight: accentWeight.value,
        body_text_color: bodyTextColor.value,
        body_weight: bodyWeight.value,
      });
      showMessage("パターンを追加しました。", "success");
      form.reset();
      badgeBgColor.value = "#c45a3c";
      badgeTextColor.value = "#ffffff";
      accentColor.value = "#c45a3c";
      bodyTextColor.value = "#2d1e16";
      await loadTextStyles();
    } catch (e) {
      showMessage(e.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "追加する";
    }
  });
})();
