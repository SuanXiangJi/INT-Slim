from scripts.import_system_kb_v2 import clean_markdown, clean_title, detect_language


def test_clean_markdown_removes_navigation_but_preserves_code_html():
    source = """# Demo

## On this page
- [Intro](https://example.com/#intro)

## Intro
Useful content.

```html
<div>kept as code</div>
```
"""

    cleaned = clean_markdown(source)

    assert "On this page" not in cleaned
    assert "Useful content." in cleaned
    assert "<div>kept as code</div>" in cleaned


def test_language_is_detected_from_content_instead_of_trusting_source_metadata():
    assert detect_language("This is an English reference document with examples.") == "en"
    assert detect_language("这是一份包含完整示例的中文技术文档。") == "zh-CN"


def test_generic_titles_are_derived_from_stable_urls():
    assert clean_title({
        "title": "Git",
        "canonical_url": "https://git-scm.com/docs/git-status",
    }) == "git-status"
    assert clean_title({
        "title": "typing --",
        "canonical_url": "https://docs.python.org/zh-cn/3/library/typing.html",
    }) == "typing 模块"
