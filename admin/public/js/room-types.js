// 「部屋タイプの設定」画面の動作。
(async function () {
  const messageEl = document.getElementById("message");
  const listEl = document.getElementById("room-types-list");
  const form = document.getElementById("room-type-form");
  const nameInput = document.getElementById("name-input");
  const bedSizeInput = document.getElementById("bed-size-input");
  const maxGuestsInput = document.getElementById("max-guests-input");
  const submitBtn = document.getElementById("submit-btn");

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

  async function loadRoomTypes() {
    listEl.innerHTML = '<div class="loading">読み込み中です…</div>';
    try {
      const { room_types: roomTypes } = await Api.listRoomTypes();
      renderRoomTypes(roomTypes);
    } catch (e) {
      listEl.innerHTML = "";
      showMessage(e.message, "error");
    }
  }

  function renderRoomTypes(roomTypes) {
    if (!roomTypes || roomTypes.length === 0) {
      listEl.innerHTML = '<p class="empty-state">まだ部屋タイプが登録されていません。下のフォームから追加してください。</p>';
      return;
    }

    listEl.innerHTML = "";
    roomTypes.forEach((roomType) => {
      const item = document.createElement("div");
      item.className = "text-item";
      item.innerHTML = `
        <div class="meta">
          <div>
            <strong>${escapeHtml(roomType.name)}</strong>
            <p class="hint-text" style="margin:6px 0 0">
              ベッド: ${escapeHtml(roomType.bed_size || "-")} ／ 最大宿泊人数: ${escapeHtml(String(roomType.max_guests ?? "-"))}
            </p>
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
        openEditor(editPanel, roomType);
        editPanel.style.display = "block";
        editBtn.textContent = "編集をとじる";
      });

      deleteBtn.addEventListener("click", async () => {
        if (!window.confirm(`「${roomType.name}」を削除します。よろしいですか？（元に戻せません）`)) return;
        deleteBtn.disabled = true;
        try {
          await Api.deleteRoomType(roomType.name);
          showMessage("部屋タイプを削除しました。", "success");
          await loadRoomTypes();
        } catch (e) {
          showMessage(e.message, "error");
          deleteBtn.disabled = false;
        }
      });

      listEl.appendChild(item);
    });
  }

  function openEditor(panel, roomType) {
    panel.innerHTML = `
      <div class="field">
        <label class="field-label">部屋タイプ名</label>
        <input type="text" class="edit-name" />
      </div>
      <div class="field">
        <label class="field-label">ベッドの説明</label>
        <textarea class="edit-bed-size" placeholder="2段ベッドなど上下がある場合は、Enterで改行して分けて入力すると見やすく表示されます。"></textarea>
      </div>
      <div class="field">
        <label class="field-label">最大宿泊人数の表記</label>
        <input type="text" class="edit-max-guests" />
      </div>
      <p class="hint-text">
        部屋タイプ名を変更すると、この部屋タイプを使っているすべての写真の登録内容にも自動で反映されます。
      </p>
      <div class="button-row">
        <button type="button" class="save-btn">保存する</button>
      </div>
    `;

    panel.querySelector(".edit-name").value = roomType.name || "";
    panel.querySelector(".edit-bed-size").value = roomType.bed_size || "";
    panel.querySelector(".edit-max-guests").value = roomType.max_guests ?? "";

    panel.querySelector(".save-btn").addEventListener("click", async () => {
      const btn = panel.querySelector(".save-btn");
      const newName = panel.querySelector(".edit-name").value.trim();
      if (!newName) {
        showMessage("部屋タイプの名前を入力してください。", "error");
        return;
      }
      btn.disabled = true;
      btn.textContent = "保存しています…";
      try {
        await Api.updateRoomType(roomType.name, {
          name: newName,
          bed_size: panel.querySelector(".edit-bed-size").value,
          max_guests: panel.querySelector(".edit-max-guests").value,
        });
        showMessage("部屋タイプの内容を更新しました。", "success");
        await loadRoomTypes();
      } catch (e) {
        showMessage(e.message, "error");
        btn.disabled = false;
        btn.textContent = "保存する";
      }
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = nameInput.value.trim();
    if (!name) {
      showMessage("部屋タイプの名前を入力してください。", "error");
      return;
    }
    submitBtn.disabled = true;
    submitBtn.textContent = "追加しています…";
    try {
      await Api.createRoomType({
        name,
        bed_size: bedSizeInput.value,
        max_guests: maxGuestsInput.value,
      });
      showMessage("部屋タイプを追加しました。", "success");
      form.reset();
      await loadRoomTypes();
    } catch (e) {
      showMessage(e.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "追加する";
    }
  });

  const currentUser = await requireLogin();
  if (!currentUser) return;

  await loadRoomTypes();
})();
