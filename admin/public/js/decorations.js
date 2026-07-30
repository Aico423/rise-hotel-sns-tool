// 「スタンプを登録する」画面の動作。
(async function () {
  const messageEl = document.getElementById("message");
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const pickFileBtn = document.getElementById("pick-file-btn");
  const preview = document.getElementById("preview");
  const nameInput = document.getElementById("name-input");
  const tagsInput = document.getElementById("tags-input");
  const placementSelect = document.getElementById("placement-select");
  const form = document.getElementById("decoration-form");
  const submitBtn = document.getElementById("submit-btn");

  let compressedDataUrl = null;

  function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
  }

  function hideMessage() {
    messageEl.className = "message hidden";
  }

  async function handleFile(file) {
    if (!file || !file.type.startsWith("image/")) {
      showMessage("画像ファイルを選んでください。", "error");
      return;
    }
    hideMessage();
    try {
      // スタンプは透明部分を保つ必要があるため、JPEG圧縮ではなくPNGのまま軽く縮小する。
      compressedDataUrl = await compressImageToDataUrl(file, 800, 1.0, "image/png");
      preview.src = compressedDataUrl;
      preview.style.display = "block";
    } catch (e) {
      showMessage(e.message, "error");
    }
  }

  pickFileBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => handleFile(e.target.files[0]));

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  });

  try {
    const config = await Api.getConfig();
    const placements = config.decoration_placements || Object.keys(PLACEMENT_LABELS);
    placementSelect.innerHTML = placements
      .map((p) => `<option value="${p}">${PLACEMENT_LABELS[p] || p}</option>`)
      .join("");
  } catch (e) {
    showMessage(e.message, "error");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideMessage();

    if (!compressedDataUrl) {
      showMessage("画像を選んでください。", "error");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "保存しています…";

    try {
      await Api.createDecoration({
        image_base64: compressedDataUrl,
        name: nameInput.value,
        tags: tagsInput.value,
        placement: placementSelect.value,
      });
      showMessage("スタンプを登録しました。一覧画面に戻ります…", "success");
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
