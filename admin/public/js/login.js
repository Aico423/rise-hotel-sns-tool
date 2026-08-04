// ログイン画面（初回のみ、管理者アカウント作成の初期設定画面にもなる）。
(async function () {
  const formTitle = document.getElementById("form-title");
  const formHint = document.getElementById("form-hint");
  const messageEl = document.getElementById("message");
  const form = document.getElementById("login-form");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const submitBtn = document.getElementById("submit-btn");

  let isSetupMode = false;
  let confirmPasswordInput = null;

  wirePasswordToggle(passwordInput);

  function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
  }

  function hideMessage() {
    messageEl.className = "message hidden";
  }

  try {
    const status = await Api.getBootstrapStatus();
    isSetupMode = status.needs_setup;
  } catch (e) {
    showMessage(e.message, "error");
  }

  if (isSetupMode) {
    formTitle.textContent = "初期設定：管理者アカウントを作成";
    formHint.textContent = "はじめてこの画面を開いたときだけ表示されます。管理者アカウントを1つ作成してください。";
    submitBtn.textContent = "作成してはじめる";

    const confirmField = document.createElement("div");
    confirmField.className = "field";
    confirmField.innerHTML = `
      <label class="field-label" for="password-confirm">パスワード（確認用）</label>
      <input type="password" id="password-confirm" autocomplete="new-password" />
    `;
    passwordInput.closest(".field").after(confirmField);
    confirmPasswordInput = document.getElementById("password-confirm");
    passwordInput.autocomplete = "new-password";
    wirePasswordToggle(confirmPasswordInput);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideMessage();

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
      showMessage("メールアドレスとパスワードを入力してください。", "error");
      return;
    }

    if (isSetupMode) {
      if (password.length < 8) {
        showMessage("パスワードは8文字以上にしてください。", "error");
        return;
      }
      if (password !== confirmPasswordInput.value) {
        showMessage("パスワード（確認用）が一致しません。", "error");
        return;
      }
    }

    submitBtn.disabled = true;
    submitBtn.textContent = isSetupMode ? "作成しています…" : "ログインしています…";

    try {
      if (isSetupMode) {
        await Api.bootstrap({ email, password });
      } else {
        await Api.login({ email, password });
      }
      window.location.href = "index.html";
    } catch (err) {
      showMessage(err.message, "error");
      submitBtn.disabled = false;
      submitBtn.textContent = isSetupMode ? "作成してはじめる" : "ログイン";
    }
  });
})();
