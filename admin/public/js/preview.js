// 「プレビュー」画面の動作。
(async function () {
  const messageEl = document.getElementById("message");
  const materialPicker = document.getElementById("material-picker");
  const textSelect = document.getElementById("text-select");
  const createBtn = document.getElementById("create-preview-btn");
  const resultCard = document.getElementById("result-card");
  const renderedTextPreview = document.getElementById("rendered-text-preview");
  const previewGrid = document.getElementById("preview-grid");

  let materials = [];
  let texts = [];
  let selectedMaterialId = null;

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

  function hideMessage() {
    messageEl.className = "message hidden";
  }

  function textLabel(text) {
    const body = text.text.replace(/\s+/g, " ").trim();
    return escapeHtml(body.length > 24 ? `${body.slice(0, 24)}…` : body || "（文言未入力）");
  }

  function textAppliesToMaterial(text, materialId) {
    const ids = text.material_ids || [];
    return ids.length === 0 || ids.includes(materialId);
  }

  function populateTextSelect() {
    const eligible = texts.filter((t) => textAppliesToMaterial(t, selectedMaterialId));
    if (eligible.length === 0) {
      textSelect.innerHTML = '<option value="">この写真に使える文言がありません</option>';
      return;
    }
    textSelect.innerHTML = eligible.map((t) => `<option value="${t.id}">${textLabel(t)}</option>`).join("");
  }

  createBtn.addEventListener("click", async () => {
    hideMessage();
    resultCard.style.display = "none";

    const textId = textSelect.value;
    if (!selectedMaterialId || !textId) {
      showMessage("写真と文言を選んでください。", "error");
      return;
    }

    createBtn.disabled = true;
    createBtn.textContent = "作成しています…（15〜30秒程度かかります）";

    try {
      const result = await Api.createPreview({ material_id: selectedMaterialId, text_id: textId });
      renderedTextPreview.textContent = `投稿される文言: ${result.rendered_text}`;
      previewGrid.innerHTML = "";
      Object.entries(result.images).forEach(([platform, dataUrl]) => {
        const item = document.createElement("div");
        item.className = "material-card";
        item.innerHTML = `
          <img src="${dataUrl}" alt="${PLATFORM_LABELS[platform] || platform}" />
          <div class="body">
            <strong>${PLATFORM_LABELS[platform] || platform}</strong>
          </div>
        `;
        previewGrid.appendChild(item);
      });
      resultCard.style.display = "block";
      window.scrollTo({ top: resultCard.offsetTop, behavior: "smooth" });
    } catch (err) {
      showMessage(err.message, "error");
    } finally {
      createBtn.disabled = false;
      createBtn.textContent = "プレビューを作成する";
    }
  });

  const currentUser = await requireLogin();
  if (!currentUser) return;

  try {
    const [materialsResult, textsResult] = await Promise.all([Api.listMaterials(), Api.listTexts()]);
    materials = materialsResult.materials;
    texts = textsResult.texts;

    if (materials.length === 0) {
      showMessage("まだ写真が登録されていません。「写真を登録する」から追加してください。", "error");
      return;
    }
    if (texts.length === 0) {
      showMessage("まだ文言が登録されていません。「文言を登録する」から追加してください。", "error");
      return;
    }

    selectedMaterialId = materials[0].id;
    renderMaterialPicker(materialPicker, materials, [selectedMaterialId], {
      mode: "single",
      name: "preview-material",
      onChange: (materialId) => {
        selectedMaterialId = materialId;
        populateTextSelect();
      },
    });
    populateTextSelect();
  } catch (e) {
    showMessage(e.message, "error");
  }
})();
