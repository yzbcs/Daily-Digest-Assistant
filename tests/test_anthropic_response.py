import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from llm.filter_and_summarize import _call_anthropic


class AnthropicResponseTests(unittest.TestCase):
    def test_all_text_blocks_are_used_without_thinking(self):
        msg = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=""),
                     SimpleNamespace(type="thinking", thinking="private reasoning"),
                     SimpleNamespace(type="text", text='[{"id":"p1"}]')],
            stop_reason="end_turn", usage=SimpleNamespace(output_tokens=100),
        )
        with patch("anthropic.Anthropic") as client, redirect_stdout(io.StringIO()) as log:
            client.return_value.messages.create.return_value = msg
            raw = _call_anthropic("prompt", "dummy", "https://open.bigmodel.cn/api/anthropic", "glm-5.3")
            self.assertEqual(raw.strip(), '[{"id":"p1"}]')
            self.assertEqual(client.return_value.messages.create.call_args.kwargs['max_tokens'], 16384)
            self.assertIn("stop_reason=end_turn", log.getvalue())
            self.assertNotIn("private reasoning", log.getvalue())

    def test_thinking_only_truncation_is_visible_in_log(self):
        msg = SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking="private reasoning")],
                              stop_reason="max_tokens", usage=SimpleNamespace(output_tokens=8192))
        with patch("anthropic.Anthropic") as client, redirect_stdout(io.StringIO()) as log:
            client.return_value.messages.create.return_value = msg
            self.assertEqual(_call_anthropic("prompt", "dummy", None, "glm-5.3"), "")
            self.assertIn("stop_reason=max_tokens", log.getvalue())
            self.assertIn("text_chars=0", log.getvalue())


if __name__ == "__main__":
    unittest.main()
