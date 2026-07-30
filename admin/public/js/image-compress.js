// 写真をアップロードする前に、ブラウザ内で軽く圧縮する（通信エラーを防ぐため）。
// mimeType に "image/png" を指定すると、スタンプ画像などの透明部分を保ったまま縮小できる。
async function compressImageToDataUrl(file, maxEdge = 1600, quality = 0.8, mimeType = "image/jpeg") {
  const originalDataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("写真の読み込みに失敗しました。"));
    reader.readAsDataURL(file);
  });

  const image = await new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("写真の読み込みに失敗しました。"));
    img.src = originalDataUrl;
  });

  let { width, height } = image;
  if (width > maxEdge || height > maxEdge) {
    if (width >= height) {
      height = Math.round((height * maxEdge) / width);
      width = maxEdge;
    } else {
      width = Math.round((width * maxEdge) / height);
      height = maxEdge;
    }
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(image, 0, 0, width, height);

  return canvas.toDataURL(mimeType, quality);
}
