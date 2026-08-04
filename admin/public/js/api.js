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
    // 通信が固まって画面が「読み込み中」のまま動かなくなるのを防ぐため、必ずタイムアウトを設ける。
    const timeoutMs = options.timeoutMs || 20000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    let res;
    try {
      res = await fetch(url, {
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options,
        signal: controller.signal,
      });
    } catch (e) {
      if (e.name === "AbortError") {
        throw new Error("通信に時間がかかりすぎたため中断しました。もう一度お試しください。");
      }
      throw new Error("通信できませんでした。インターネット接続をご確認のうえ、もう一度お試しください。");
    } finally {
      clearTimeout(timeoutId);
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

    listTextStyles: () => request(withQuery({ resource: "text_styles" })),
    createTextStyle: (payload) =>
      request(withQuery({ resource: "text_styles" }), { method: "POST", body: JSON.stringify(payload) }),
    updateTextStyle: (id, payload) =>
      request(withQuery({ resource: "text_styles", id }), { method: "PUT", body: JSON.stringify(payload) }),
    deleteTextStyle: (id) => request(withQuery({ resource: "text_styles", id }), { method: "DELETE" }),

    listRoomTypes: () => request(withQuery({ resource: "room_types" })),
    createRoomType: (payload) =>
      request(withQuery({ resource: "room_types" }), { method: "POST", body: JSON.stringify(payload) }),
    updateRoomType: (name, payload) =>
      request(withQuery({ resource: "room_types", id: name }), { method: "PUT", body: JSON.stringify(payload) }),
    deleteRoomType: (name) => request(withQuery({ resource: "room_types", id: name }), { method: "DELETE" }),

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
    updateUser: (email, payload) =>
      request(withQuery({ resource: "users", id: email }), { method: "PUT", body: JSON.stringify(payload) }),
    deleteUser: (email) => request(withQuery({ resource: "users", id: email }), { method: "DELETE" }),

    createPreview: (payload) =>
      // Gemini生成を伴うため15〜30秒程度かかることがあり、既定のタイムアウトでは短すぎる。
      request(withQuery({ resource: "preview" }), { method: "POST", body: JSON.stringify(payload), timeoutMs: 60000 }),
  };
})();
