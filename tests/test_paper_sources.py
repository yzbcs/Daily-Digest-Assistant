import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import MagicMock, mock_open, patch

import arxiv
import requests

import main
from fetchers.arxiv_fetcher import fetch_papers
from fetchers.semantic_scholar_fetcher import fetch_semantic_scholar_papers
from render.email_renderer import render_email


START, END = date(2026, 10, 9), date(2026, 10, 12)
ITEM = {
    "paperId": "example", "title": "Coding agent study", "abstract": "An agent study.",
    "authors": [{"name": "Author"}], "publicationDate": "2026-10-12",
    "externalIds": {"ArXiv": "2610.12345v2"},
    "url": "https://www.semanticscholar.org/paper/example", "openAccessPdf": None,
}


def response(data):
    result = MagicMock()
    result.json.return_value = data
    return result


class PaperSourceTests(unittest.TestCase):
    def test_mapping_dedup_missing_abstract_and_pagination(self):
        other = {**ITEM, "paperId": "other", "externalIds": {}, "openAccessPdf": None}
        with patch('fetchers.semantic_scholar_fetcher.requests.Session') as session, \
             patch('fetchers.semantic_scholar_fetcher.time.sleep') as sleep:
            get = session.return_value.__enter__.return_value.get
            get.side_effect = [
                response({"data": [ITEM, ITEM, {**ITEM, "abstract": None},
                                   {**ITEM, "publicationDate": "2026-10-13"}], "token": "next"}),
                response({"data": [other]}),
            ]
            papers = fetch_semantic_scholar_papers(['Coding agent'], 80, START, END)
            self.assertEqual([p['id'] for p in papers], ['2610.12345', 'S2:other'])
            self.assertEqual(papers[0]['url'], 'https://arxiv.org/abs/2610.12345')
            self.assertEqual(papers[1]['link_label'], 'Semantic Scholar')
            self.assertIsNone(papers[1]['pdf_url'])
            self.assertEqual(papers[0]['matched_keywords'], ['Coding agent'])
            self.assertEqual(get.call_args.kwargs['params']['token'], 'next')
            self.assertEqual(get.call_args.kwargs['params']['publicationDateOrYear'], '2026-10-09:2026-10-12')
            sleep.assert_called_once_with(3)
        html = render_email(papers, ['Coding agent'], paper_source='Semantic Scholar',
                            paper_notice='备用来源，按发布日期检索')
        self.assertIn('Semantic Scholar 论文', html)
        self.assertIn('备用来源，按发布日期检索', html)
        self.assertNotIn('href="None"', html)

    def test_candidate_limit(self):
        with patch('fetchers.semantic_scholar_fetcher.requests.Session') as session:
            get = session.return_value.__enter__.return_value.get
            get.return_value = response({"data": [ITEM], "token": "unused"})
            self.assertEqual(len(fetch_semantic_scholar_papers(['agent'], 1, START, END)), 1)
            get.assert_called_once()

    def test_anonymous_rate_limit_is_not_retried(self):
        with patch('fetchers.semantic_scholar_fetcher.requests.Session') as session:
            get = session.return_value.__enter__.return_value.get
            get.return_value.raise_for_status.side_effect = requests.HTTPError('429')
            with self.assertRaises(requests.HTTPError):
                fetch_semantic_scholar_papers(['agent'], 80, START, END)
            get.assert_called_once()

    def test_arxiv_retry_budget(self):
        with patch('fetchers.arxiv_fetcher.arxiv.Client') as client, \
             patch('fetchers.arxiv_fetcher.time.sleep') as sleep:
            client.return_value.results.side_effect = arxiv.HTTPError('https://example.com', 0, 429)
            with self.assertRaises(arxiv.HTTPError):
                fetch_papers(['agent'], [], 80)
            client.assert_called_once_with(num_retries=0, delay_seconds=10)
            self.assertEqual(client.return_value.results.call_count, 3)
            self.assertEqual([c.args[0] for c in sleep.call_args_list], [10, 30])

    def test_main_fallback_reaches_llm_and_render_without_sending(self):
        paper = {'id': 'S2:example', 'title': ITEM['title'], 'abstract': ITEM['abstract']}
        with patch.object(main, 'load_config', return_value={'keywords': ['agent']}), \
             patch.dict(os.environ, {'LLM_API_KEY': 'mock-key', 'XHS_COOKIE': ''}), \
             patch.object(main, 'fetch_papers', side_effect=arxiv.HTTPError('https://example.com', 0, 429)), \
             patch.object(main, 'fetch_semantic_scholar_papers', return_value=[paper]) as fallback, \
             patch.object(main, 'filter_and_summarize_papers', return_value=[paper]) as llm, \
             patch.object(main, 'render_email', return_value='preview') as render, \
             patch.object(main, 'send_email') as send, \
             patch('builtins.open', mock_open()), redirect_stdout(io.StringIO()):
            main.main(dry_run=True, target_date=END)
            fallback.assert_called_once_with(['agent'], 50, START, END)
            self.assertEqual(llm.call_args.args[0], [paper])
            self.assertEqual(render.call_args.kwargs['paper_source'], 'Semantic Scholar')
            self.assertIn('HTTP 429', render.call_args.kwargs['paper_notice'])
            send.assert_not_called()

    def test_main_primary_empty_uses_fallback(self):
        with patch.object(main, 'load_config', return_value={}), \
             patch.dict(os.environ, {'LLM_API_KEY': 'test', 'XHS_COOKIE': ''}), \
             patch.object(main, 'fetch_papers', return_value=[]), \
             patch.object(main, 'fetch_semantic_scholar_papers', return_value=[]) as fallback, \
             patch.object(main, 'render_email', return_value='preview'), \
             patch('builtins.open', mock_open()), redirect_stdout(io.StringIO()):
            main.main(dry_run=True, target_date=END)
            fallback.assert_called_once()

    def test_both_sources_fail_skip_without_llm_or_email(self):
        failed = requests.Response()
        failed.status_code = 429
        with patch.object(main, 'load_config', return_value={}), \
             patch.dict(os.environ, {'LLM_API_KEY': 'test'}), \
             patch.object(main, 'fetch_papers', side_effect=arxiv.HTTPError('https://example.com', 0, 503)), \
             patch.object(main, 'fetch_semantic_scholar_papers',
                          side_effect=requests.HTTPError('rate limited', response=failed)), \
             patch.object(main, '_save_skip_html') as skip, \
             patch.object(main, 'filter_and_summarize_papers') as llm, \
             patch.object(main, 'send_email') as send, redirect_stdout(io.StringIO()):
            main.main(dry_run=True, target_date=END)
            self.assertIn('arXiv（HTTP 503）及 Semantic Scholar（HTTP 429）', skip.call_args.args[0])
            llm.assert_not_called()
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
