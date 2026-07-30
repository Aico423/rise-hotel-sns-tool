import io

import pytest
from PIL import Image

from rise_sns import image_generator


def _png_bytes(size=(600, 600), color=None):
    if color is None:
        # 単色ではない画像（品質チェックを通す用）
        img = Image.new("RGB", size)
        pixels = img.load()
        for x in range(size[0]):
            for y in range(size[1]):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    else:
        img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class FakeInlineData:
    def __init__(self, data):
        self.data = data


class FakePart:
    def __init__(self, inline_data=None):
        self.inline_data = inline_data


class FakeContent:
    def __init__(self, parts):
        self.parts = parts


class FakeCandidate:
    def __init__(self, content):
        self.content = content


class FakeResponse:
    def __init__(self, candidates):
        self.candidates = candidates


def _response_with_image(image_bytes) -> FakeResponse:
    part = FakePart(inline_data=FakeInlineData(data=image_bytes))
    return FakeResponse(candidates=[FakeCandidate(FakeContent(parts=[part]))])


class FakeModels:
    def __init__(self, side_effects):
        self._side_effects = list(side_effects)
        self.calls = 0

    def generate_content(self, model, contents):
        self.calls += 1
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


class FakeClient:
    def __init__(self, side_effects):
        self.models = FakeModels(side_effects)


@pytest.fixture
def room_photo():
    return Image.new("RGB", (800, 600), color=(100, 100, 100))


def test_generate_composite_image_succeeds_first_try(room_photo):
    client = FakeClient([_response_with_image(_png_bytes())])
    result = image_generator.generate_composite_image(room_photo, "夏の思い出", client=client)
    assert result.size == (600, 600)


def test_generate_composite_image_retries_on_blank_then_succeeds(room_photo):
    blank_response = _response_with_image(_png_bytes(color=(10, 10, 10)))
    good_response = _response_with_image(_png_bytes())
    client = FakeClient([blank_response, good_response])
    result = image_generator.generate_composite_image(
        room_photo, "夏の思い出", client=client, max_retries=3
    )
    assert result.size == (600, 600)
    assert client.models.calls == 2


def test_generate_composite_image_raises_after_exhausting_retries(room_photo):
    blank_response = _response_with_image(_png_bytes(color=(10, 10, 10)))
    client = FakeClient([blank_response, blank_response])
    with pytest.raises(image_generator.ImageGenerationError):
        image_generator.generate_composite_image(room_photo, "夏の思い出", client=client, max_retries=2)


def test_generate_composite_image_handles_missing_image_part(room_photo):
    no_image_response = FakeResponse(candidates=[FakeCandidate(FakeContent(parts=[FakePart()]))])
    client = FakeClient([no_image_response, no_image_response])
    with pytest.raises(image_generator.ImageGenerationError):
        image_generator.generate_composite_image(room_photo, "夏の思い出", client=client, max_retries=2)


def test_generate_composite_image_handles_api_exception(room_photo):
    client = FakeClient([RuntimeError("network error"), _response_with_image(_png_bytes())])
    result = image_generator.generate_composite_image(room_photo, "夏の思い出", client=client, max_retries=3)
    assert result.size == (600, 600)
