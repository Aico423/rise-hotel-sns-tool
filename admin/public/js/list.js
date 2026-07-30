// トップ画面（一覧・編集・削除）の動作。
(async function () {
  const messageEl = document.getElementById("message");
  const materialsListEl = document.getElementById("materials-list");
  const textsListEl = document.getElementById("texts-list");

  let config = null;

  function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function tagBadges(values) {
    return (values || []).map((v) => `<span class="tag">${escapeHtml(v)}</span>`).join("");
  }

  function platformBadges(platforms) {
    return Object.entries(platforms || {})
      .filter(([, enabled]) => enabled)
      .map(([key]) => `<span class="tag">${escapeHtml(PLATFORM_LABELS[key] || key)}</span>`)
      .join("");
  }

  // ---------------- 客室写真 ----------------

  async function loadMaterials() {
    materialsListEl.innerHTML = '<div class="loading">読み込み中です…</div>';
    try {
      const { materials } = await Api.listMaterials();
      renderMaterials(materials);
    } catch (e) {
      materialsListEl.innerHTML = "";
      showMessage(e.message, "error");
    }
  }

  function renderMaterials(materials) {
    if (materials.length === 0) {
      materialsListEl.innerHTML =
        '<p class="empty-state">まだ写真が登録されていません。「写真を登録する」から追加できます。</p>';
      return;
    }
    materialsListEl.innerHTML = '<div class="grid" id="materials-grid"></div>';
    const grid = document.getElementById("materials-grid");

    materials.forEach((material) => {
      const card = document.createElement("div");
      card.className = "material-card";
      card.innerHTML = `
        <img src="${material.image_url}" alt="客室写真" loading="lazy" />
        <div class="body">
          <div class="tag-list">
            ${material.room_type ? `<span class="tag">${escapeHtml(material.room_type)}</span>` : ""}
            ${tagBadges(material.seasons)}
            ${tagBadges(material.features)}
          </div>
          <div class="card-actions">
            <button type="button" class="secondary edit-btn">編集する</button>
            <button type="button" class="danger delete-btn">削除する</button>
          </div>
          <div class="edit-panel" style="display:none"></div>
        </div>
      `;

      const editBtn = card.querySelector(".edit-btn");
      const deleteBtn = card.querySelector(".delete-btn");
      const editPanel = card.querySelector(".edit-panel");

      editBtn.addEventListener("click", () => {
        const isOpen = editPanel.style.display !== "none";
        if (isOpen) {
          editPanel.style.display = "none";
          editPanel.innerHTML = "";
          editBtn.textContent = "編集する";
          return;
        }
        openMaterialEditor(editPanel, material);
        editPanel.style.display = "block";
        editBtn.textContent = "編集をとじる";
      });

      deleteBtn.addEventListener("click", async () => {
        if (!window.confirm("この写真を削除します。よろしいですか？（元に戻せません）")) return;
        deleteBtn.disabled = true;
        try {
          await Api.deleteMaterial(material.id);
          showMessage("写真を削除しました。", "success");
          await loadMaterials();
        } catch (e) {
          showMessage(e.message, "error");
          deleteBtn.disabled = false;
        }
      });

      grid.appendChild(card);
    });
  }

  function openMaterialEditor(panel, material) {
    panel.innerHTML = `
      <div class="field">
        <label class="field-label">部屋タイプ</label>
        <select class="edit-room-type"></select>
      </div>
      <div class="field">
        <label class="field-label">季節</label>
        <div class="checkbox-grid edit-seasons"></div>
      </div>
      <div class="field">
        <label class="field-label">特徴</label>
        <div class="checkbox-grid edit-features"></div>
      </div>
      <div class="button-row">
        <button type="button" class="save-btn">保存する</button>
      </div>
    `;

    const roomTypeSelect = panel.querySelector(".edit-room-type");
    roomTypeSelect.innerHTML = config.room_types
      .map((rt) => `<option value="${rt}" ${rt === material.room_type ? "selected" : ""}>${rt}</option>`)
      .join("");

    const seasonsContainer = panel.querySelector(".edit-seasons");
    const featuresContainer = panel.querySelector(".edit-features");
    renderCheckboxGroup(seasonsContainer, `edit-season-${material.id}`, config.seasons, material.seasons || []);
    renderCheckboxGroup(featuresContainer, `edit-feature-${material.id}`, config.features, material.features || []);

    panel.querySelector(".save-btn").addEventListener("click", async () => {
      const btn = panel.querySelector(".save-btn");
      btn.disabled = true;
      btn.textContent = "保存しています…";
      try {
        await Api.updateMaterial(material.id, {
          room_type: roomTypeSelect.value,
          seasons: getCheckedValues(seasonsContainer),
          features: getCheckedValues(featuresContainer),
        });
        showMessage("写真の内容を更新しました。", "success");
        await loadMaterials();
      } catch (e) {
        showMessage(e.message, "error");
        btn.disabled = false;
        btn.textContent = "保存する";
      }
    });
  }

  // ---------------- 投稿文言 ----------------

  async function loadTexts() {
    textsListEl.innerHTML = '<div class="loading">読み込み中です…</div>';
    try {
      const { texts } = await Api.listTexts();
      renderTexts(texts);
    } catch (e) {
      textsListEl.innerHTML = "";
      showMessage(e.message, "error");
    }
  }

  function renderTexts(texts) {
    if (texts.length === 0) {
      textsListEl.innerHTML =
        '<p class="empty-state">まだ文言が登録されていません。「文言を登録する」から追加できます。</p>';
      return;
    }
    textsListEl.innerHTML = "";

    texts.forEach((text) => {
      const item = document.createElement("div");
      item.className = "text-item";
      item.innerHTML = `
        <p class="text-body">${escapeHtml(text.text)}</p>
        <div class="meta">
          <div class="tag-list">
            ${text.category ? `<span class="tag">${escapeHtml(text.category)}</span>` : ""}
            ${platformBadges(text.platforms)}
          </div>
          <div class="card-actions">
            <button type="button" class="secondary edit-btn">編集する</button>
            <button type="button" class="danger delete-btn">削除する</button>
          </div>
        </div>
        <div class="edit-panel" style="display:none"></div>
      `;

      const editBtn = item.querySelector(".edit-btn");
      const deleteBtn = item.querySelector(".delete-btn");
      const editPanel = item.querySelector(".edit-panel");

      editBtn.addEventListener("click", () => {
        const isOpen = editPanel.style.display !== "none";
        if (isOpen) {
          editPanel.style.display = "none";
          editPanel.innerHTML = "";
          editBtn.textContent = "編集する";
          return;
        }
        openTextEditor(editPanel, text);
        editPanel.style.display = "block";
        editBtn.textContent = "編集をとじる";
      });

      deleteBtn.addEventListener("click", async () => {
        if (!window.confirm("この文言を削除します。よろしいですか？（元に戻せません）")) return;
        deleteBtn.disabled = true;
        try {
          await Api.deleteText(text.id);
          showMessage("文言を削除しました。", "success");
          await loadTexts();
        } catch (e) {
          showMessage(e.message, "error");
          deleteBtn.disabled = false;
        }
      });

      textsListEl.appendChild(item);
    });
  }

  function openTextEditor(panel, text) {
    panel.innerHTML = `
      <div class="field">
        <label class="field-label">文言</label>
        <textarea class="edit-text-body"></textarea>
      </div>
      <div class="field">
        <label class="field-label">カテゴリ</label>
        <select class="edit-category"></select>
      </div>
      <div class="field">
        <label class="field-label">どのSNSに使いますか？</label>
        <div class="checkbox-grid edit-platforms"></div>
      </div>
      <div class="button-row">
        <button type="button" class="save-btn">保存する</button>
      </div>
    `;

    panel.querySelector(".edit-text-body").value = text.text;

    const categorySelect = panel.querySelector(".edit-category");
    categorySelect.innerHTML = config.text_categories
      .map((c) => `<option value="${c}" ${c === text.category ? "selected" : ""}>${c}</option>`)
      .join("");

    const platformsContainer = panel.querySelector(".edit-platforms");
    const selectedPlatforms = Object.entries(text.platforms || {})
      .filter(([, enabled]) => enabled)
      .map(([key]) => key);
    renderCheckboxGroup(
      platformsContainer,
      `edit-platform-${text.id}`,
      config.platforms,
      selectedPlatforms,
      PLATFORM_LABELS
    );

    panel.querySelector(".save-btn").addEventListener("click", async () => {
      const btn = panel.querySelector(".save-btn");
      const newText = panel.querySelector(".edit-text-body").value.trim();
      if (!newText) {
        showMessage("文言を入力してください。", "error");
        return;
      }
      const selected = getCheckedValues(platformsContainer);
      if (selected.length === 0) {
        showMessage("どのSNSに使うか、1つ以上選んでください。", "error");
        return;
      }
      const platforms = {};
      selected.forEach((p) => (platforms[p] = true));

      btn.disabled = true;
      btn.textContent = "保存しています…";
      try {
        await Api.updateText(text.id, { text: newText, category: categorySelect.value, platforms });
        showMessage("文言を更新しました。", "success");
        await loadTexts();
      } catch (e) {
        showMessage(e.message, "error");
        btn.disabled = false;
        btn.textContent = "保存する";
      }
    });
  }

  // ---------------- 初期化 ----------------

  try {
    config = await Api.getConfig();
  } catch (e) {
    showMessage(e.message, "error");
    return;
  }

  await Promise.all([loadMaterials(), loadTexts()]);
})();
