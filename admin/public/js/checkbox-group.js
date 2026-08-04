// パスワード入力欄に「表示/非表示」切り替えボタン（目のアイコン）を追加する。
// 同じinput要素に対して二重に呼び出しても安全（既にボタンが付いていれば何もしない）。
const _EYE_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z"/><circle cx="12" cy="12" r="3"/></svg>';
const _EYE_OFF_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a21.6 21.6 0 0 1 5.06-6.06M9.9 4.24A10.4 10.4 0 0 1 12 4c7 0 11 8 11 8a21.6 21.6 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

function wirePasswordToggle(inputEl) {
  if (!inputEl || inputEl.dataset.toggleWired) return;
  inputEl.dataset.toggleWired = "true";

  const wrapper = document.createElement("div");
  wrapper.className = "password-field-wrapper";
  inputEl.parentNode.insertBefore(wrapper, inputEl);
  wrapper.appendChild(inputEl);

  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.className = "password-toggle-btn";
  toggleBtn.setAttribute("aria-label", "パスワードを表示する");
  toggleBtn.innerHTML = _EYE_ICON;
  wrapper.appendChild(toggleBtn);

  toggleBtn.addEventListener("click", () => {
    const willShow = inputEl.type === "password";
    inputEl.type = willShow ? "text" : "password";
    toggleBtn.innerHTML = willShow ? _EYE_OFF_ICON : _EYE_ICON;
    toggleBtn.setAttribute("aria-label", willShow ? "パスワードを非表示にする" : "パスワードを表示する");
  });
}

// ログイン状態を確認し、未ログインならlogin.htmlへ、管理者専用ページで管理者でなければ
// index.htmlへ移動する。管理者のときだけ「ユーザー管理」リンクを表示する。
// 戻り値: ログイン済みユーザー情報（{email, role}）。ページ遷移が発生した場合はnullを返す。
async function requireLogin({ adminOnly = false } = {}) {
  let sessionInfo;
  try {
    sessionInfo = await Api.getSession();
  } catch (e) {
    window.location.href = "login.html";
    return null;
  }

  if (!sessionInfo.logged_in) {
    window.location.href = "login.html";
    return null;
  }

  if (adminOnly && sessionInfo.role !== "admin") {
    window.location.href = "index.html";
    return null;
  }

  const usersNavLink = document.querySelector('a[href="users.html"]');
  if (usersNavLink && sessionInfo.role !== "admin") {
    usersNavLink.remove();
  }

  const logoutLink = document.getElementById("logout-link");
  if (logoutLink) {
    logoutLink.addEventListener("click", async (e) => {
      e.preventDefault();
      try {
        await Api.logout();
      } catch (err) {
        // ログアウト自体が失敗しても、ログイン画面には戻す
      }
      window.location.href = "login.html";
    });
  }

  return { email: sessionInfo.email, role: sessionInfo.role };
}

// 「部屋タイプを挿入」等のボタンを押したときに、textareaのカーソル位置に
// {room_type} のようなプレースホルダーを挿入する（専門用語を見せずに差し込みができるようにする）。
function wirePlaceholderButtons(container, textarea) {
  container.querySelectorAll("button[data-placeholder]").forEach((button) => {
    button.addEventListener("click", () => {
      const token = `{${button.dataset.placeholder}}`;
      const start = textarea.selectionStart ?? textarea.value.length;
      const end = textarea.selectionEnd ?? textarea.value.length;
      textarea.value = textarea.value.slice(0, start) + token + textarea.value.slice(end);
      const cursor = start + token.length;
      textarea.focus();
      textarea.setSelectionRange(cursor, cursor);
    });
  });
}

// 部屋タイプの選択肢(<select>)を描画し、選んだ内容(ベッドサイズ・最大宿泊人数)を
// hintEl に表示する。roomTypes は [{name, bed_size, max_guests}, ...] の形。
function renderRoomTypeSelect(selectEl, hintEl, roomTypes, selectedName) {
  selectEl.innerHTML = roomTypes
    .map((rt) => `<option value="${rt.name}" ${rt.name === selectedName ? "selected" : ""}>${rt.name}</option>`)
    .join("");

  function updateHint() {
    const current = roomTypes.find((rt) => rt.name === selectEl.value);
    if (!current) {
      hintEl.textContent = "";
      return;
    }
    hintEl.textContent = `ベッド: ${current.bed_size || "-"} ／ 最大宿泊人数: ${current.max_guests || "-"}`;
  }

  selectEl.addEventListener("change", updateHint);
  updateHint();
}

// 投稿先コード -> 画面表示名（専門用語を出さないため、ここで日本語に変換する）。
const PLATFORM_LABELS = {
  x: "X",
  instagram: "Instagram",
  facebook: "Facebook",
  google: "Googleビジネスプロフィール",
};

// スタンプ・ハッシュタグ画像の表示位置コード -> 画面表示名。
const PLACEMENT_LABELS = {
  top_left: "左上",
  top_right: "右上",
  top_center: "上中央",
  bottom_left: "左下",
  bottom_right: "右下",
  bottom_center: "下中央",
};

// タグ選択用のチェックボックス群（丸いピル表示）を描画する共通処理。
function renderCheckboxGroup(container, groupName, options, selectedValues, labels) {
  selectedValues = selectedValues || [];
  labels = labels || {};
  container.innerHTML = "";
  options.forEach((value) => {
    const id = `${groupName}-${value}`;
    const label = document.createElement("label");
    label.className = "checkbox-pill";
    label.setAttribute("for", id);

    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = id;
    input.value = value;
    input.checked = selectedValues.includes(value);
    if (input.checked) label.classList.add("checked");

    input.addEventListener("change", () => {
      label.classList.toggle("checked", input.checked);
    });

    const span = document.createElement("span");
    span.textContent = labels[value] || value;

    label.appendChild(input);
    label.appendChild(span);
    container.appendChild(label);
  });
}

function getCheckedValues(container) {
  return Array.from(container.querySelectorAll("input[type=checkbox]:checked")).map((el) => el.value);
}

// ラジオボタン用：チェックされている1件の値を返す（無ければnull）。
function getCheckedValue(container) {
  const el = container.querySelector("input:checked");
  return el ? el.value : null;
}

// 「この文言を使う写真」等を選ぶための、サムネイル付き選択肢一覧を描画する。
// options.mode: "multi"（既定・チェックボックスで複数選択） または "single"（ラジオボタンで1件選択）
// options.name: singleモードのとき、ラジオボタンをグループ化するためのname属性
// options.onChange: 選択が変わるたびに呼ばれる (materialId) => void
function renderMaterialPicker(container, materials, selectedIds, options) {
  selectedIds = selectedIds || [];
  options = options || {};
  const mode = options.mode || "multi";
  const inputType = mode === "single" ? "radio" : "checkbox";
  const inputName = options.name || `material-picker-${Math.random().toString(36).slice(2)}`;
  container.innerHTML = "";

  if (!materials || materials.length === 0) {
    container.innerHTML = '<p class="empty-state">まだ写真が登録されていません。</p>';
    return;
  }

  materials.forEach((material) => {
    const item = document.createElement("label");
    item.className = "material-pick-item";
    const isChecked = selectedIds.includes(material.id);
    if (isChecked) item.classList.add("checked");

    const labelText = [
      material.room_type,
      material.room_number ? `${material.room_number}号室` : "",
      ...(material.seasons || []),
    ]
      .filter(Boolean)
      .join("・");

    item.innerHTML = `
      <img src="${material.image_url}" alt="客室写真" loading="lazy" />
      <div class="label-row">
        <input type="${inputType}" name="${inputName}" value="${material.id}" ${isChecked ? "checked" : ""} />
        <span>${labelText || "（タグ未設定）"}</span>
      </div>
    `;

    const input = item.querySelector("input");
    input.addEventListener("change", () => {
      if (mode === "single") {
        container.querySelectorAll(".material-pick-item").forEach((el) => el.classList.remove("checked"));
      }
      item.classList.toggle("checked", input.checked);
      if (options.onChange) options.onChange(material.id);
    });

    container.appendChild(item);
  });
}
