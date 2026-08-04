// トップ画面（一覧・編集・削除）の動作。
(async function () {
  const messageEl = document.getElementById("message");
  const postStatusEl = document.getElementById("post-status");
  const materialsListEl = document.getElementById("materials-list");
  const textsListEl = document.getElementById("texts-list");
  const decorationsListEl = document.getElementById("decorations-list");

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

  // ---------------- 自動投稿の実行状況 ----------------

  function formatDateTime(iso) {
    try {
      return new Date(iso).toLocaleString("ja-JP", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return iso;
    }
  }

  function renderPostStatus(status) {
    if (status.state === "success") {
      postStatusEl.className = "post-status post-status-success";
      postStatusEl.innerHTML = `✅ 自動投稿：直近の実行は正常に完了しました（${formatDateTime(status.created_at)}）`;
    } else if (status.state === "failure") {
      postStatusEl.className = "post-status post-status-error";
      postStatusEl.innerHTML =
        `⚠️ 自動投稿でエラーが発生しています（${formatDateTime(status.created_at)}）。` +
        `このままサポートへ、この画面のスクリーンショットか` +
        `<a href="${status.html_url}" target="_blank" rel="noopener">こちらの詳細画面のリンク</a>をお送りください。`;
    } else if (status.state === "running") {
      postStatusEl.className = "post-status post-status-info";
      postStatusEl.textContent = `⏳ 自動投稿を実行中です…（${formatDateTime(status.created_at)}）`;
    } else {
      postStatusEl.className = "post-status hidden";
      return;
    }
    postStatusEl.classList.remove("hidden");
  }

  async function loadPostStatus() {
    try {
      const status = await Api.getPostStatus();
      renderPostStatus(status);
    } catch (e) {
      // ここが失敗しても一覧画面自体は普段どおり使えるようにし、目立たせすぎない
      postStatusEl.className = "post-status hidden";
    }
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
            ${material.room_number ? `<span class="tag">${escapeHtml(material.room_number)}号室</span>` : ""}
            ${tagBadges(material.seasons)}
            ${material.ready_made ? '<span class="tag">完成写真</span>' : ""}
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
        <p class="edit-room-type-detail hint-text"></p>
      </div>
      <div class="field">
        <label class="field-label">部屋番号（任意）</label>
        <input type="text" class="edit-room-number" placeholder="例：601" />
      </div>
      <div class="field">
        <label class="field-label">季節</label>
        <div class="checkbox-grid edit-seasons"></div>
      </div>
      <div class="field">
        <label class="checkbox-pill">
          <input type="checkbox" class="edit-ready-made" />
          <span>この写真はすでに人物が入った完成写真です</span>
        </label>
      </div>
      <div class="button-row">
        <button type="button" class="save-btn">保存する</button>
      </div>
    `;

    const readyMadeCheckbox = panel.querySelector(".edit-ready-made");
    readyMadeCheckbox.checked = !!material.ready_made;
    readyMadeCheckbox.closest(".checkbox-pill").classList.toggle("checked", readyMadeCheckbox.checked);
    readyMadeCheckbox.addEventListener("change", () => {
      readyMadeCheckbox.closest(".checkbox-pill").classList.toggle("checked", readyMadeCheckbox.checked);
    });

    const roomTypeSelect = panel.querySelector(".edit-room-type");
    const roomTypeDetail = panel.querySelector(".edit-room-type-detail");
    renderRoomTypeSelect(roomTypeSelect, roomTypeDetail, config.room_types, material.room_type);

    panel.querySelector(".edit-room-number").value = material.room_number || "";

    const seasonsContainer = panel.querySelector(".edit-seasons");
    renderCheckboxGroup(seasonsContainer, `edit-season-${material.id}`, config.seasons, material.seasons || []);

    panel.querySelector(".save-btn").addEventListener("click", async () => {
      const btn = panel.querySelector(".save-btn");
      btn.disabled = true;
      btn.textContent = "保存しています…";
      try {
        await Api.updateMaterial(material.id, {
          room_type: roomTypeSelect.value,
          room_number: panel.querySelector(".edit-room-number").value,
          seasons: getCheckedValues(seasonsContainer),
          ready_made: readyMadeCheckbox.checked,
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
            ${
              text.material_ids && text.material_ids.length > 0
                ? `<span class="tag">写真指定あり（${text.material_ids.length}枚）</span>`
                : '<span class="tag">どの写真にも使用可</span>'
            }
            ${tagBadges(text.tags)}
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

  async function openTextEditor(panel, text) {
    panel.innerHTML = `
      <div class="field">
        <label class="field-label">文言</label>
        <textarea class="edit-text-body"></textarea>
        <div class="button-row edit-insert-placeholder-row">
          <button type="button" class="secondary" data-placeholder="room_type">部屋タイプを挿入</button>
          <button type="button" class="secondary" data-placeholder="room_number">部屋番号を挿入</button>
          <button type="button" class="secondary" data-placeholder="bed_size">ベッドサイズを挿入</button>
          <button type="button" class="secondary" data-placeholder="max_guests">最大宿泊人数を挿入</button>
        </div>
      </div>
      <div class="field">
        <label class="field-label">カテゴリ</label>
        <select class="edit-category"></select>
      </div>
      <div class="field">
        <label class="field-label">関連キーワード（任意）</label>
        <input type="text" class="edit-tags" placeholder="例：東京, 新宿, 予約訴求" />
      </div>
      <div class="field">
        <label class="field-label">この文言を使う写真（選ばなければどの写真にも使われます）</label>
        <div class="material-pick-grid edit-material-picker"></div>
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
    panel.querySelector(".edit-tags").value = (text.tags || []).join(", ");
    wirePlaceholderButtons(panel.querySelector(".edit-insert-placeholder-row"), panel.querySelector(".edit-text-body"));

    const categorySelect = panel.querySelector(".edit-category");
    categorySelect.innerHTML = config.text_categories
      .map((c) => `<option value="${c}" ${c === text.category ? "selected" : ""}>${c}</option>`)
      .join("");

    const materialPicker = panel.querySelector(".edit-material-picker");
    try {
      const { materials } = await Api.listMaterials();
      renderMaterialPicker(materialPicker, materials, text.material_ids || []);
    } catch (e) {
      materialPicker.innerHTML = `<p class="empty-state">${escapeHtml(e.message)}</p>`;
    }

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
      const tagsValue = panel.querySelector(".edit-tags").value;
      const materialIds = getCheckedValues(materialPicker);

      btn.disabled = true;
      btn.textContent = "保存しています…";
      try {
        await Api.updateText(text.id, {
          text: newText,
          category: categorySelect.value,
          tags: tagsValue,
          material_ids: materialIds,
          platforms,
        });
        showMessage("文言を更新しました。", "success");
        await loadTexts();
      } catch (e) {
        showMessage(e.message, "error");
        btn.disabled = false;
        btn.textContent = "保存する";
      }
    });
  }

  // ---------------- スタンプ・ハッシュタグ画像 ----------------

  async function loadDecorations() {
    decorationsListEl.innerHTML = '<div class="loading">読み込み中です…</div>';
    try {
      const { decorations } = await Api.listDecorations();
      renderDecorations(decorations);
    } catch (e) {
      decorationsListEl.innerHTML = "";
      showMessage(e.message, "error");
    }
  }

  function renderDecorations(items) {
    if (items.length === 0) {
      decorationsListEl.innerHTML =
        '<p class="empty-state">まだスタンプが登録されていません。「スタンプを登録する」から追加できます。</p>';
      return;
    }
    decorationsListEl.innerHTML = '<div class="grid" id="decorations-grid"></div>';
    const grid = document.getElementById("decorations-grid");

    items.forEach((decoration) => {
      const card = document.createElement("div");
      card.className = "material-card decoration-card";
      card.innerHTML = `
        <img class="thumb-transparent" src="${decoration.image_url}" alt="${escapeHtml(decoration.name || "スタンプ")}" loading="lazy" />
        <div class="body">
          <strong>${escapeHtml(decoration.name || "（名前未設定）")}</strong>
          <div class="tag-list">
            <span class="tag">${escapeHtml(PLACEMENT_LABELS[decoration.placement] || decoration.placement)}</span>
            ${tagBadges(decoration.tags)}
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
        openDecorationEditor(editPanel, decoration);
        editPanel.style.display = "block";
        editBtn.textContent = "編集をとじる";
      });

      deleteBtn.addEventListener("click", async () => {
        if (!window.confirm("このスタンプを削除します。よろしいですか？（元に戻せません）")) return;
        deleteBtn.disabled = true;
        try {
          await Api.deleteDecoration(decoration.id);
          showMessage("スタンプを削除しました。", "success");
          await loadDecorations();
        } catch (e) {
          showMessage(e.message, "error");
          deleteBtn.disabled = false;
        }
      });

      grid.appendChild(card);
    });
  }

  function openDecorationEditor(panel, decoration) {
    const placements = config.decoration_placements || Object.keys(PLACEMENT_LABELS);
    panel.innerHTML = `
      <div class="field">
        <label class="field-label">名前</label>
        <input type="text" class="edit-name" />
      </div>
      <div class="field">
        <label class="field-label">関連するキーワード（カンマ区切り）</label>
        <input type="text" class="edit-tags" />
      </div>
      <div class="field">
        <label class="field-label">表示位置</label>
        <select class="edit-placement"></select>
      </div>
      <div class="button-row">
        <button type="button" class="save-btn">保存する</button>
      </div>
    `;

    panel.querySelector(".edit-name").value = decoration.name || "";
    panel.querySelector(".edit-tags").value = (decoration.tags || []).join(", ");

    const placementSelect = panel.querySelector(".edit-placement");
    placementSelect.innerHTML = placements
      .map(
        (p) => `<option value="${p}" ${p === decoration.placement ? "selected" : ""}>${PLACEMENT_LABELS[p] || p}</option>`
      )
      .join("");

    panel.querySelector(".save-btn").addEventListener("click", async () => {
      const btn = panel.querySelector(".save-btn");
      btn.disabled = true;
      btn.textContent = "保存しています…";
      try {
        await Api.updateDecoration(decoration.id, {
          name: panel.querySelector(".edit-name").value,
          tags: panel.querySelector(".edit-tags").value,
          placement: placementSelect.value,
        });
        showMessage("スタンプの内容を更新しました。", "success");
        await loadDecorations();
      } catch (e) {
        showMessage(e.message, "error");
        btn.disabled = false;
        btn.textContent = "保存する";
      }
    });
  }

  // ---------------- 初期化 ----------------

  const currentUser = await requireLogin();
  if (!currentUser) return;

  try {
    config = await Api.getConfig();
  } catch (e) {
    showMessage(e.message, "error");
    return;
  }

  await Promise.all([loadMaterials(), loadTexts(), loadDecorations(), loadPostStatus()]);
})();
