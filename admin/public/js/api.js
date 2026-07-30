// 画面の裏側で使う通信ヘルパー。専門用語はここに閉じ込め、画面には出さない。
//
// 【重要】Vercel上のPython実行環境の制約により、実際のURLパス(/api/materials等)は
// 使わず、単一のエンドポイント /api/index に resource/id をクエリパラメータとして
// 付けて呼び出す方式にしている（admin/api/index.py 側の実装と対応関係にある）。
const Api = (() => {
  const ENDPOINT = "/api/index";

  function withQuery(params) {
    const query = new URLSearchParams(params).toString();
    return `${ENDPOINT}?${query}`;
  }

  async function request(url, options = {}) {
    let res;
    try {
      res = await fetch(url, {
        credentials: "same-origin",
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

    if (res.status === 401 && !url.includes("resource=session") && !url.includes("resource=login")) {
      window.location.href = "login.html";
      throw new Error("ログインが必要です。");
    }

    if (!res.ok) {
      const message = (body && body.error) || "保存に失敗しました。もう一度お試しください。";
      throw new Error(message);
    }
    return body;
  }

  return {
    getConfig: () => request(withQuery({ resource: "config" })),

    listMaterials: () => request(withQuery({ resource: "materials" })),
    createMaterial: (payload) =>
      request(withQuery({ resource: "materials" }), { method: "POST", body: JSON.stringify(payload) }),
    updateMaterial: (id, payload) =>
      request(withQuery({ resource: "materials", id }), { method: "PUT", body: JSON.stringify(payload) }),
    deleteMaterial: (id) => request(withQuery({ resource: "materials", id }), { method: "DELETE" }),

    listTexts: () => request(withQuery({ resource: "texts" })),
    createText: (payload) =>
      request(withQuery({ resource: "texts" }), { method: "POST", body: JSON.stringify(payload) }),
    updateText: (id, payload) =>
      request(withQuery({ resource: "texts", id }), { method: "PUT", body: JSON.stringify(payload) }),
    deleteText: (id) => request(withQuery({ resource: "texts", id }), { method: "DELETE" }),

    listDecorations: () => request(withQuery({ resource: "decorations" })),
    createDecoration: (payload) =>
      request(withQuery({ resource: "decorations" }), { method: "POST", body: JSON.stringify(payload) }),
    updateDecoration: (id, payload) =>
      request(withQuery({ resource: "decorations", id }), { method: "PUT", body: JSON.stringify(payload) }),
    deleteDecoration: (id) => request(withQuery({ resource: "decorations", id }), { method: "DELETE" }),

    getBootstrapStatus: () => request(withQuery({ resource: "bootstrap" })),
    bootstrap: (payload) => request(withQuery({ resource: "bootstrap" }), { method: "POST", body: JSON.stringify(payload) }),
    login: (payload) => request(withQuery({ resource: "login" }), { method: "POST", body: JSON.stringify(payload) }),
    logout: () => request(withQuery({ resource: "logout" }), { method: "POST" }),
    getSession: () => request(withQuery({ resource: "session" })),

    listUsers: () => request(withQuery({ resource: "users" })),
    createUser: (payload) => request(withQuery({ resource: "users" }), { method: "POST", body: JSON.stringify(payload) }),
    deleteUser: (email) => request(withQuery({ resource: "users", id: email }), { method: "DELETE" }),
  };
})();
