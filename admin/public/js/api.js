// 画面の裏側で使う通信ヘルパー。専門用語はここに閉じ込め、画面には出さない。
const Api = (() => {
  async function request(path, options = {}) {
    let res;
    try {
      res = await fetch(path, {
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options,
      });
    } catch (e) {
      throw new Error("通信できませんでした。インターネット接続をご確認のうえ、もう一度お試しください。");
    }

    let body = null;
    try {
      body = await res.json();
    } catch (e) {
      body = null;
    }

    if (!res.ok) {
      const message = (body && body.error) || "保存に失敗しました。もう一度お試しください。";
      throw new Error(message);
    }
    return body;
  }

  return {
    getConfig: () => request("/api/config"),
    listMaterials: () => request("/api/materials"),
    createMaterial: (payload) => request("/api/materials", { method: "POST", body: JSON.stringify(payload) }),
    updateMaterial: (id, payload) =>
      request(`/api/materials/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(payload) }),
    deleteMaterial: (id) => request(`/api/materials/${encodeURIComponent(id)}`, { method: "DELETE" }),

    listTexts: () => request("/api/texts"),
    createText: (payload) => request("/api/texts", { method: "POST", body: JSON.stringify(payload) }),
    updateText: (id, payload) =>
      request(`/api/texts/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(payload) }),
    deleteText: (id) => request(`/api/texts/${encodeURIComponent(id)}`, { method: "DELETE" }),
  };
})();
