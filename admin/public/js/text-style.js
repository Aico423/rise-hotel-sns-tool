// 「文字の装飾の設定」画面の動作。
(async function () {
  const messageEl = document.getElementById("message");
  const form = document.getElementById("text-style-form");
  const submitBtn = document.getElementById("submit-btn");

  const badgeBgColor = document.getElementById("badge-bg-color");
  const badgeTextColor = document.getElementById("badge-text-color");
  const badgeWeight = document.getElementById("badge-weight");
  const accentColor = document.getElementById("accent-color");
  const accentWeight = document.getElementById("accent-weight");
  const bodyTextColor = document.getElementById("body-text-color");
  const bodyWeight = document.getElementById("body-weight");

  const WEIGHT_LABELS = {
    regular: "標準",
    medium: "やや太め",
    semibold: "太め",
    bold: "かなり太め",
    extrabold: "最も太い",
  };

  function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function fillWeightSelect(selectEl, weights, selected) {
    selectEl.innerHTML = weights
      .map((w) => `<option value="${w}" ${w === selected ? "selected" : ""}>${WEIGHT_LABELS[w] || w}</option>`)
      .join("");
  }

  const currentUser = await requireLogin();
  if (!currentUser) return;

  try {
    const config = await Api.getConfig();
    const weights = config.font_weights || ["regular", "medium", "semibold", "bold", "extrabold"];
    const style = config.text_style || {};

    badgeBgColor.value = style.badge_bg_color || "#c45a3c";
    badgeTextColor.value = style.badge_text_color || "#ffffff";
    fillWeightSelect(badgeWeight, weights, style.badge_weight || "extrabold");

    accentColor.value = style.accent_color || "#c45a3c";
    fillWeightSelect(accentWeight, weights, style.accent_weight || "bold");

    bodyTextColor.value = style.body_text_color || "#2d1e16";
    fillWeightSelect(bodyWeight, weights, style.body_weight || "medium");
  } catch (e) {
    showMessage(e.message, "error");
    return;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    submitBtn.disabled = true;
    submitBtn.textContent = "保存しています…";
    try {
      await Api.updateTextStyle({
        badge_bg_color: badgeBgColor.value,
        badge_text_color: badgeTextColor.value,
        badge_weight: badgeWeight.value,
        accent_color: accentColor.value,
        accent_weight: accentWeight.value,
        body_text_color: bodyTextColor.value,
        body_weight: bodyWeight.value,
      });
      showMessage("文字の装飾を更新しました。次回のプレビュー・投稿から反映されます。", "success");
    } catch (e) {
      showMessage(e.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "保存する";
    }
  });
})();
