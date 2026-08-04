// 「ユーザー管理」画面の動作（管理者のみアクセス可能）。
(async function () {
  const messageEl = document.getElementById("message");
  const usersListEl = document.getElementById("users-list");
  const form = document.getElementById("user-form");
  const emailInput = document.getElementById("new-email");
  const passwordInput = document.getElementById("new-password");
  const roleSelect = document.getElementById("new-role");
  const submitBtn = document.getElementById("submit-btn");

  wirePasswordToggle(passwordInput);

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

  let currentUserEmail = null;

  async function loadUsers() {
    usersListEl.innerHTML = '<div class="loading">読み込み中です…</div>';
    try {
      const { users } = await Api.listUsers();
      renderUsers(users);
    } catch (e) {
      usersListEl.innerHTML = "";
      showMessage(e.message, "error");
    }
  }

  function renderUsers(users) {
    if (users.length === 0) {
      usersListEl.innerHTML = '<p class="empty-state">まだユーザーが登録されていません。</p>';
      return;
    }
    usersListEl.innerHTML = "";

    users.forEach((user) => {
      const item = document.createElement("div");
      item.className = "text-item";
      const roleLabel = user.role === "admin" ? "管理者" : "スタッフ";
      const isSelf = user.email === currentUserEmail;
      item.innerHTML = `
        <div class="meta">
          <div class="tag-list">
            <span class="tag">${escapeHtml(user.email)}</span>
            <span class="tag">${roleLabel}</span>
          </div>
          <div class="card-actions">
            <button type="button" class="secondary edit-btn">編集する</button>
            <button type="button" class="danger delete-btn" ${isSelf ? "disabled" : ""}>削除する</button>
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
        openEditor(editPanel, user, isSelf);
        editPanel.style.display = "block";
        editBtn.textContent = "編集をとじる";
      });

      if (!isSelf) {
        deleteBtn.addEventListener("click", async () => {
          if (!window.confirm(`${user.email} を削除します。よろしいですか？（元に戻せません）`)) return;
          deleteBtn.disabled = true;
          try {
            await Api.deleteUser(user.email);
            showMessage("ユーザーを削除しました。", "success");
            await loadUsers();
          } catch (e) {
            showMessage(e.message, "error");
            deleteBtn.disabled = false;
          }
        });
      }

      usersListEl.appendChild(item);
    });
  }

  function openEditor(panel, user, isSelf) {
    panel.innerHTML = `
      <div class="field">
        <label class="field-label">権限</label>
        <select class="edit-role" ${isSelf ? "disabled" : ""}>
          <option value="user">スタッフ（写真・文言の登録のみ）</option>
          <option value="admin">管理者（ユーザー管理も可能）</option>
        </select>
        ${isSelf ? '<p class="hint-text">自分自身の権限は変更できません。別の管理者に依頼してください。</p>' : ""}
      </div>
      <div class="field">
        <label class="field-label">新しいパスワード（変更する場合のみ入力・8文字以上）</label>
        <input type="password" class="edit-password" autocomplete="new-password" placeholder="変更しない場合は空欄のまま" />
      </div>
      <div class="button-row">
        <button type="button" class="save-btn">保存する</button>
      </div>
    `;

    panel.querySelector(".edit-role").value = user.role;
    wirePasswordToggle(panel.querySelector(".edit-password"));

    panel.querySelector(".save-btn").addEventListener("click", async () => {
      const btn = panel.querySelector(".save-btn");
      const newPassword = panel.querySelector(".edit-password").value;
      if (newPassword && newPassword.length < 8) {
        showMessage("パスワードは8文字以上にしてください。", "error");
        return;
      }
      const payload = {};
      if (!isSelf) payload.role = panel.querySelector(".edit-role").value;
      if (newPassword) payload.password = newPassword;
      if (Object.keys(payload).length === 0) {
        showMessage("変更する内容がありません。", "error");
        return;
      }

      btn.disabled = true;
      btn.textContent = "保存しています…";
      try {
        await Api.updateUser(user.email, payload);
        showMessage(`${user.email} の内容を更新しました。`, "success");
        await loadUsers();
      } catch (e) {
        showMessage(e.message, "error");
        btn.disabled = false;
        btn.textContent = "保存する";
      }
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideMessageIfAny();

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
      showMessage("メールアドレスとパスワードを入力してください。", "error");
      return;
    }
    if (password.length < 8) {
      showMessage("パスワードは8文字以上にしてください。", "error");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "追加しています…";

    try {
      await Api.createUser({ email, password, role: roleSelect.value });
      showMessage("ユーザーを追加しました。", "success");
      form.reset();
      await loadUsers();
    } catch (err) {
      showMessage(err.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "追加する";
    }
  });

  function hideMessageIfAny() {
    messageEl.className = "message hidden";
  }

  const currentUser = await requireLogin({ adminOnly: true });
  if (!currentUser) return;
  currentUserEmail = currentUser.email;

  await loadUsers();
})();
