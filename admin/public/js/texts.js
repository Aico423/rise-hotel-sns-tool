// 「文言を登録する」画面の動作。
(async function () {
  const messageEl = document.getElementById("message");
  const textBody = document.getElementById("text-body");
  const categorySelect = document.getElementById("category");
  const tagsInput = document.getElementById("tags-input");
  const materialPicker = document.getElementById("material-picker");
  const platformsContainer = document.getElementById("platforms-checkboxes");
  const form = document.getElementById("text-form");
  const submitBtn = document.getElementById("submit-btn");

  wirePlaceholderButtons(document.querySelector(".insert-placeholder-row"), textBody);

  function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
  }

  function hideMessage() {
    messageEl.className = "message hidden";
  }

  const currentUser = await requireLogin();
  if (!currentUser) return;

  try {
    const config = await Api.getConfig();
    categorySelect.innerHTML = config.text_categories.map((c) => `<option value="${c}">${c}</option>`).join("");
    renderCheckboxGroup(platformsContainer, "platform", config.platforms, [], PLATFORM_LABELS);

    const { materials } = await Api.listMaterials();
    renderMaterialPicker(materialPicker, materials, []);
  } catch (e) {
    showMessage(e.message, "error");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideMessage();

    const text = textBody.value.trim();
    if (!text) {
      showMessage("文言を入力してください。", "error");
      return;
    }

    const selectedPlatforms = getCheckedValues(platformsContainer);
    if (selectedPlatforms.length === 0) {
      showMessage("どのSNSに使うか、1つ以上選んでください。", "error");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "保存しています…";

    const platforms = {};
    selectedPlatforms.forEach((p) => (platforms[p] = true));

    try {
      await Api.createText({
        text,
        category: categorySelect.value,
        tags: tagsInput.value,
        material_ids: getCheckedValues(materialPicker),
        platforms,
      });
      showMessage("文言を登録しました。一覧画面に戻ります…", "success");
      setTimeout(() => {
        window.location.href = "index.html";
      }, 1200);
    } catch (err) {
      showMessage(err.message, "error");
      submitBtn.disabled = false;
      submitBtn.textContent = "保存する";
    }
  });
})();
