// 「写真を登録する」画面の動作。
(async function () {
  const messageEl = document.getElementById("message");
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const pickFileBtn = document.getElementById("pick-file-btn");
  const preview = document.getElementById("preview");
  const roomTypeSelect = document.getElementById("room-type");
  const roomTypeDetail = document.getElementById("room-type-detail");
  const roomNumberInput = document.getElementById("room-number");
  const seasonsContainer = document.getElementById("seasons-checkboxes");
  const readyMadeCheckbox = document.getElementById("ready-made-checkbox");
  const form = document.getElementById("material-form");
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
      compressedDataUrl = await compressImageToDataUrl(file);
      preview.src = compressedDataUrl;
      preview.style.display = "block";
    } catch (e) {
      showMessage(e.message, "error");
    }
  }

  readyMadeCheckbox.addEventListener("change", () => {
    readyMadeCheckbox.closest(".checkbox-pill").classList.toggle("checked", readyMadeCheckbox.checked);
  });

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
    renderRoomTypeSelect(roomTypeSelect, roomTypeDetail, config.room_types);
    renderCheckboxGroup(seasonsContainer, "season", config.seasons);
  } catch (e) {
    showMessage(e.message, "error");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideMessage();

    if (!compressedDataUrl) {
      showMessage("写真を選んでください。", "error");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "保存しています…";

    try {
      await Api.createMaterial({
        image_base64: compressedDataUrl,
        room_type: roomTypeSelect.value,
        room_number: roomNumberInput.value,
        seasons: getCheckedValues(seasonsContainer),
        ready_made: readyMadeCheckbox.checked,
      });
      showMessage("写真を登録しました。一覧画面に戻ります…", "success");
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
