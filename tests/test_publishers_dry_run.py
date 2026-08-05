from pathlib import Path

from rise_sns import config
from rise_sns.publishers.base import BasePublisher
from rise_sns.publishers.x_publisher import XPublisher, truncate_caption
from rise_sns.publishers.instagram_publisher import InstagramPublisher
from rise_sns.publishers.facebook_publisher import FacebookPublisher
from rise_sns.publishers.google_business_publisher import GoogleBusinessPublisher


# ---------- 共通: dry_run=True なら実通信せず成功扱いになること ----------

class _ExplodingPublisher(BasePublisher):
    platform = "test"

    def _publish(self, caption, image_path=None, image_url=None):
        raise AssertionError("dry_run=True のときは _publish が呼ばれてはいけない")


def test_base_publisher_dry_run_never_calls_publish():
    publisher = _ExplodingPublisher(dry_run=True)
    result = publisher.publish(caption="test", image_path=Path("x.jpg"))
    assert result.success is True
    assert "[dry-run]" in result.detail


class _FailingPublisher(BasePublisher):
    platform = "test"

    def _publish(self, caption, image_path=None, image_url=None):
        raise RuntimeError("boom")


def test_base_publisher_wraps_exceptions_as_failed_result():
    publisher = _FailingPublisher(dry_run=False)
    result = publisher.publish(caption="test")
    assert result.success is False
    assert "boom" in result.detail


# ---------- X ----------

def test_truncate_caption_short_text_unchanged():
    assert truncate_caption("短い文章") == "短い文章"


def test_truncate_caption_long_text_is_shortened():
    long_text = "あ" * 200
    result = truncate_caption(long_text, max_chars=10)
    assert len(result) == 10
    assert result.endswith("…")


class FakeMedia:
    media_id = "media-123"


class FakeXApi:
    def __init__(self):
        self.uploaded = None

    def media_upload(self, filename):
        self.uploaded = filename
        return FakeMedia()


class FakeTweetResponse:
    data = {"id": "tweet-999"}


class FakeXClient:
    def __init__(self):
        self.last_call = None

    def create_tweet(self, text, media_ids):
        self.last_call = {"text": text, "media_ids": media_ids}
        return FakeTweetResponse()


def test_x_publisher_dry_run():
    publisher = XPublisher(dry_run=True)
    result = publisher.publish(caption="テスト投稿", image_path=Path("room.jpg"))
    assert result.success is True
    assert "[dry-run]" in result.detail


def test_x_publisher_real_call_shape():
    api = FakeXApi()
    client = FakeXClient()
    publisher = XPublisher(dry_run=False, api=api, client=client)
    result = publisher.publish(caption="素敵な客室です", image_path=Path("room.jpg"))

    assert api.uploaded == "room.jpg"
    assert client.last_call["media_ids"] == ["media-123"]
    assert result.success is True
    assert result.post_id == "tweet-999"


def test_x_publisher_requires_image_path():
    publisher = XPublisher(dry_run=False, api=FakeXApi(), client=FakeXClient())
    result = publisher.publish(caption="テスト")
    assert result.success is False


class FakeTweetResponseNoData:
    data = None


class FakeXClientNoData:
    def create_tweet(self, text, media_ids):
        return FakeTweetResponseNoData()


def test_x_publisher_treats_missing_tweet_id_as_failure():
    # tweepyが例外を投げなくても、応答に投稿ID(data.id)が含まれていない場合は
    # 実際には投稿できていない可能性が高いため、黙って成功扱いにしてはいけない。
    publisher = XPublisher(dry_run=False, api=FakeXApi(), client=FakeXClientNoData())
    result = publisher.publish(caption="テスト投稿", image_path=Path("room.jpg"))
    assert result.success is False
    assert result.post_id is None


# ---------- Instagram / Facebook / Google 共通のFakeSession ----------

class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.text = str(json_data)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, data=None, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "data": data, "json": json, "headers": headers})
        return self._responses.pop(0)


# ---------- Instagram ----------

def test_instagram_publisher_dry_run():
    publisher = InstagramPublisher(dry_run=True)
    result = publisher.publish(caption="test", image_url="https://example.com/x.jpg")
    assert result.success is True
    assert "[dry-run]" in result.detail


def test_instagram_publisher_story_flow(monkeypatch):
    monkeypatch.setattr(config, "META_ACCESS_TOKEN", "token-abc")
    monkeypatch.setattr(config, "IG_USER_ID", "ig-1")

    session = FakeSession([
        FakeResponse({"id": "creation-1"}),
        FakeResponse({"id": "media-1"}),
    ])
    publisher = InstagramPublisher(dry_run=False, session=session)
    result = publisher.publish(caption="test", image_url="https://example.com/x.jpg")

    assert result.success is True
    assert result.post_id == "media-1"
    assert session.calls[0]["data"]["media_type"] == "STORIES"
    assert session.calls[0]["url"].endswith("/ig-1/media")
    assert session.calls[1]["url"].endswith("/ig-1/media_publish")


def test_instagram_publisher_requires_image_url():
    publisher = InstagramPublisher(dry_run=False)
    result = publisher.publish(caption="test")
    assert result.success is False


# ---------- Facebook ----------

def test_facebook_publisher_feed_mode_default(monkeypatch):
    monkeypatch.setattr(config, "META_ACCESS_TOKEN", "token-abc")
    monkeypatch.setattr(config, "FACEBOOK_PAGE_ID", "page-1")

    session = FakeSession([FakeResponse({"post_id": "page-1_555"})])
    publisher = FacebookPublisher(dry_run=False, session=session, post_mode="feed")
    result = publisher.publish(caption="今日のおすすめ客室です", image_url="https://example.com/x.jpg")

    assert result.success is True
    assert session.calls[0]["url"].endswith("/page-1/photos")
    assert session.calls[0]["data"]["caption"] == "今日のおすすめ客室です"
    assert "published" not in session.calls[0]["data"]


def test_facebook_publisher_story_mode(monkeypatch):
    monkeypatch.setattr(config, "META_ACCESS_TOKEN", "token-abc")
    monkeypatch.setattr(config, "FACEBOOK_PAGE_ID", "page-1")
    monkeypatch.setattr(config, "FACEBOOK_STORY_ENDPOINT", "photo_stories")

    session = FakeSession([
        FakeResponse({"id": "photo-1"}),
        FakeResponse({"id": "story-1"}),
    ])
    publisher = FacebookPublisher(dry_run=False, session=session, post_mode="story")
    result = publisher.publish(caption="test", image_url="https://example.com/x.jpg")

    assert result.success is True
    assert result.post_id == "story-1"
    assert session.calls[0]["data"]["published"] == "false"
    assert session.calls[1]["url"].endswith("/page-1/photo_stories")
    assert session.calls[1]["data"]["photo_id"] == "photo-1"


# ---------- Google Business ----------

def test_google_business_publisher_dry_run():
    publisher = GoogleBusinessPublisher(dry_run=True)
    result = publisher.publish(caption="test", image_url="https://example.com/x.jpg")
    assert result.success is True
    assert "[dry-run]" in result.detail


def test_google_business_publisher_real_call_shape(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setattr(config, "GOOGLE_REFRESH_TOKEN", "refresh-token")
    monkeypatch.setattr(config, "GOOGLE_BUSINESS_ACCOUNT_ID", "acct-1")
    monkeypatch.setattr(config, "GOOGLE_BUSINESS_LOCATION_ID", "loc-1")

    session = FakeSession([
        FakeResponse({"access_token": "access-xyz"}),
        FakeResponse({"name": "accounts/acct-1/locations/loc-1/localPosts/post-1"}),
    ])
    publisher = GoogleBusinessPublisher(dry_run=False, session=session)
    result = publisher.publish(caption="季節のお得情報です", image_url="https://example.com/x.jpg")

    assert result.success is True
    assert session.calls[0]["url"].endswith("/token")
    assert session.calls[1]["headers"]["Authorization"] == "Bearer access-xyz"
    assert session.calls[1]["json"]["summary"] == "季節のお得情報です"
