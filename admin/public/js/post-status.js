// 「投稿状況」画面の動作。
(async function () {
  const messageEl = document.getElementById("message");
  const statusEl = document.getElementById("post-status");
  const historyEl = document.getElementById("post-status-history");
  const refreshBtn = document.getElementById("refresh-btn");

  function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
  }

  function hideMessage() {
    messageEl.className = "message hidden";
  }

  function formatDateTime(iso) {
    try {
      return new Date(iso).toLocaleString("ja-JP", {
        year: "numeric",
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return iso;
    }
  }

  const STATE_ICON = { success: "✅", failure: "⚠️", running: "⏳" };
  const STATE_LABEL = { success: "成功", failure: "失敗", running: "実行中" };

  function xLinkHtml(status) {
    if (!status.latest_x_post_url) return "";
    return ` <a href="${status.latest_x_post_url}" target="_blank" rel="noopener">Xで実際の投稿を確認する</a>`;
  }

  function renderStatus(status) {
    if (status.state === "no_history") {
      statusEl.className = "post-status post-status-info";
      statusEl.textContent = "まだ自動投稿の実行記録がありません。";
      statusEl.classList.remove("hidden");
      return;
    }

    if (status.state === "success") {
      statusEl.className = "post-status post-status-success";
      statusEl.innerHTML = `✅ 直近の自動投稿は正常に完了しました（${formatDateTime(status.created_at)}）${xLinkHtml(status)}`;
    } else if (status.state === "failure") {
      statusEl.className = "post-status post-status-error";
      statusEl.innerHTML =
        `⚠️ 直近の自動投稿でエラーが発生しています（${formatDateTime(status.created_at)}）。` +
        `このままサポートへ、この画面のスクリーンショットか` +
        `<a href="${status.html_url}" target="_blank" rel="noopener">こちらの詳細画面のリンク</a>をお送りください。`;
    } else {
      statusEl.className = "post-status post-status-info";
      statusEl.textContent = `⏳ 自動投稿を実行中です…（${formatDateTime(status.created_at)}）`;
    }
    statusEl.classList.remove("hidden");
  }

  function renderHistory(history) {
    if (!history || history.length === 0) {
      historyEl.innerHTML = '<p class="empty-state">まだ実行履歴がありません。</p>';
      return;
    }
    historyEl.innerHTML = "";
    history.forEach((item) => {
      const row = document.createElement("div");
      row.className = "text-item";
      row.innerHTML = `
        <div class="meta">
          <div class="tag-list">
            <span class="tag">${STATE_ICON[item.state] || ""} ${STATE_LABEL[item.state] || item.state}</span>
            <span>${formatDateTime(item.created_at)}</span>
          </div>
          <a href="${item.html_url}" target="_blank" rel="noopener" class="btn secondary">詳細を見る</a>
        </div>
      `;
      historyEl.appendChild(row);
    });
  }

  async function loadStatus() {
    hideMessage();
    historyEl.innerHTML = '<div class="loading">読み込み中です…</div>';
    refreshBtn.disabled = true;
    refreshBtn.textContent = "更新しています…";
    try {
      const status = await Api.getPostStatus();
      renderStatus(status);
      renderHistory(status.history);
    } catch (e) {
      historyEl.innerHTML = "";
      showMessage(e.message, "error");
    } finally {
      refreshBtn.disabled = false;
      refreshBtn.textContent = "更新する";
    }
  }

  refreshBtn.addEventListener("click", loadStatus);

  const currentUser = await requireLogin();
  if (!currentUser) return;

  await loadStatus();
})();
