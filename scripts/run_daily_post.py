"""GitHub Actionsから毎日呼び出されるオーケストレーター。

1. 客室写真×投稿文言を選ぶ（selector）
2. Geminiで人物等を合成し、Pillowでキャプションを焼き込む
3. SNSごとのサイズに変換する
4. X（有効）、Instagram/Facebook/Google（審査待ちの間はdry-run）へ投稿を試みる
5. 投稿履歴を記録し、失敗があれば通知する

Instagram/Facebook/Google Business は投稿に公開URLを要求するため、実際に投稿する場合のみ
生成画像をこのリポジトリにコミット・pushして raw.githubusercontent.com 経由で参照できるようにする
（無効化されている間はpush不要なので行わない）。
"""
from __future__ import annotations

import logging
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from PIL import Image

# rise_sns パッケージは admin/ 配下にある（Vercel管理画面からもimportできるようにするため）。
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))

from rise_sns import (  # noqa: E402
    config,
    data_store,
    decorations,
    image_generator,
    logging_setup,
    notifier,
    platform_formats,
    selector,
    text_template,
)
from rise_sns.publishers.base import BasePublisher  # noqa: E402
from rise_sns.publishers.facebook_publisher import FacebookPublisher  # noqa: E402
from rise_sns.publishers.google_business_publisher import GoogleBusinessPublisher  # noqa: E402
from rise_sns.publishers.instagram_publisher import InstagramPublisher  # noqa: E402
from rise_sns.publishers.x_publisher import XPublisher  # noqa: E402

logger = logging.getLogger(__name__)

# プラットフォーム名 -> (投稿クラス, 本番投稿を有効化するかどうかのフラグ)
PUBLISHERS: dict[str, tuple[type[BasePublisher], bool]] = {
    "x": (XPublisher, config.ENABLE_X),
    "instagram": (InstagramPublisher, config.ENABLE_INSTAGRAM),
    "facebook": (FacebookPublisher, config.ENABLE_FACEBOOK),
    "google": (GoogleBusinessPublisher, config.ENABLE_GOOGLE_BUSINESS),
}

# ローカルファイルの直接アップロードを受け付けず、公開URLが必要なプラットフォーム
NEEDS_PUBLIC_URL = {"instagram", "facebook", "google"}

PUBLISHED_DIR_NAME = "published"


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=False, capture_output=True, text=True)


def _commit_and_push(paths: list[Path], message: str) -> None:
    repo_root = config.PROJECT_ROOT
    _git("add", *[str(p) for p in paths], cwd=repo_root)
    commit = _git(
        "-c", "user.email=github-actions[bot]@users.noreply.github.com",
        "-c", "user.name=github-actions[bot]",
        "commit", "-m", message,
        cwd=repo_root,
    )
    if commit.returncode != 0:
        logger.info("コミットする変更がありませんでした（既に同一内容の可能性）: %s", (commit.stdout + commit.stderr).strip())
        return
    push = _git("push", cwd=repo_root)
    if push.returncode != 0:
        raise RuntimeError(f"生成画像のpushに失敗しました: {push.stderr.strip()}")


def _public_image_url(local_path: Path) -> str:
    if not config.GITHUB_REPO:
        raise RuntimeError("GITHUB_REPO が設定されていません（公開URLの生成に必要です）。")
    relative = local_path.relative_to(config.PROJECT_ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{config.GITHUB_REPO}/{config.GITHUB_BRANCH}/{relative}"


def run() -> int:
    logging_setup.setup_logging()
    today = date.today()

    materials = data_store.load_materials()
    texts = data_store.load_texts()
    history = data_store.load_post_history()

    try:
        selection = selector.select_daily_pair(materials, texts, history, today=today)
    except (selector.NoEligibleMaterialError, selector.NoEligibleTextError) as exc:
        logger.error(str(exc))
        notifier.notify_failure(f"本日の投稿をスキップしました: {exc}")
        return 1

    material = selection.material
    text = selection.text
    logger.info("選択結果: material_id=%s text_id=%s platforms=%s", material["id"], text["id"], selection.platforms_for_text)

    if not selection.platforms_for_text:
        logger.info("選ばれた文言に投稿先が設定されていないため、本日は投稿を行いません。")
        return 0

    config_data = data_store.load_config()
    room_type_defs = text_template.room_types_by_name(config_data)
    rendered_text = text_template.render_text(text["text"], material, room_type_defs)
    room_type_def = room_type_defs.get(material.get("room_type", ""), {})
    badge_text = material.get("room_number") or None
    accent_text = room_type_def.get("max_guests") or None
    text_style = config_data.get("text_style")

    room_photo = Image.open(data_store.resolve_image_path(material["image_path"]))

    if material.get("ready_made"):
        # すでに人物が入った完成写真として登録されている場合は、AIによる人物合成を行わずそのまま使う
        # （毎回の生成に伴う予測不能な仕上がり・マナー違反等のリスクを避けるため）。
        logger.info("この写真は完成写真として登録されているため、AI画像生成をスキップします。")
        generated = room_photo
    else:
        try:
            generated = image_generator.generate_composite_image(room_photo, rendered_text)
        except image_generator.ImageGenerationError as exc:
            logger.error(str(exc))
            notifier.notify_failure(f"画像生成に失敗したため本日の投稿をスキップしました: {exc}")
            return 1

    creative_tags = selector.compute_creative_tags(material, text)
    matched_decorations = decorations.select_decorations(data_store.load_decorations(), creative_tags)
    if matched_decorations:
        logger.info(
            "合成するスタンプ・ハッシュタグ画像: %s",
            [d.get("name", d["id"]) for d in matched_decorations],
        )

    def _open_stamp(decoration: dict) -> Image.Image:
        return Image.open(data_store.resolve_image_path(decoration["image_path"]))

    published_dir = config.DATA_DIR / PUBLISHED_DIR_NAME / today.isoformat()
    published_dir.mkdir(parents=True, exist_ok=True)

    # フェーズ1: 各SNS向けにサイズ変換し、スタンプ・ハッシュタグ画像を合成してローカルに書き出す
    local_paths: dict[str, Path] = {}
    for platform in selection.platforms_for_text:
        if platform not in PUBLISHERS:
            logger.warning("未知の投稿先が指定されています: %s", platform)
            continue
        rendered = platform_formats.render_for_platform(
            generated, platform, caption_text=rendered_text,
            badge_text=badge_text, accent_text=accent_text, text_style=text_style,
        )
        if matched_decorations:
            rendered = decorations.apply_decorations(rendered, matched_decorations, open_stamp=_open_stamp)
        local_path = published_dir / f"{platform}.jpg"
        rendered.save(local_path, format="JPEG", quality=90)
        local_paths[platform] = local_path

    # フェーズ2: 公開URLが必要かつ本番投稿が有効なものは、投稿を試みる前にリポジトリへpushしておく
    paths_to_push = [
        local_paths[p]
        for p in local_paths
        if p in NEEDS_PUBLIC_URL and PUBLISHERS[p][1]
    ]
    any_failure = False
    if paths_to_push:
        try:
            _commit_and_push(paths_to_push, f"chore: 投稿画像を追加 ({today.isoformat()})")
        except RuntimeError as exc:
            logger.error(str(exc))
            notifier.notify_failure(str(exc))
            any_failure = True

    # フェーズ3: 各SNSへ投稿を試みる
    platforms_posted: list[str] = []
    for platform, local_path in local_paths.items():
        publisher_cls, enabled = PUBLISHERS[platform]

        image_url: Optional[str] = None
        if platform in NEEDS_PUBLIC_URL and enabled:
            image_url = _public_image_url(local_path)

        publisher = publisher_cls(dry_run=not enabled)
        result = publisher.publish(
            caption=rendered_text,
            image_path=local_path if platform not in NEEDS_PUBLIC_URL else None,
            image_url=image_url,
        )

        logger.info("%s: success=%s detail=%s", platform, result.success, result.detail)
        if result.success:
            platforms_posted.append(platform)
        else:
            any_failure = True
            notifier.notify_failure(f"{platform} への投稿に失敗しました: {result.detail}")

    data_store.append_post_history(
        {
            "date": today.isoformat(),
            "material_id": material["id"],
            "text_id": text["id"],
            "platforms_posted": platforms_posted,
        }
    )

    return 1 if any_failure else 0


if __name__ == "__main__":
    sys.exit(run())
