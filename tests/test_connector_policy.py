"""Policy choices confirmed after the architecture audit; decision-only, no sends."""
import contextlib
import io
import json
from unittest.mock import patch

from test_guard_writes import GuardCase, guard_writes
import egress


class ConnectorPolicy(GuardCase):
    def grant(self, *tools):
        with open(self.path('jobsearch.config.json'), 'w') as f:
            json.dump({'identity': {'full_name': 'Jordan Example'}, 'privacy': {
                'approved_destinations': [{'type': 'mcp_tool', 'tool': t} for t in tools]}}, f)

    def test_final_delivery_denied_even_with_exact_grants(self):
        for tool in ('mcp__gmail__send_message', 'mcp__slack__reply', 'mcp__chat__post_message',
                     'mcp__ats__submit_application', 'mcp__ats__apply', 'mcp__mail__sendDraft'):
            self.grant(tool)
            self.assertEqual(self.decide(tool, {})[0], 'deny', tool)
            self.assertIn('hard rule 1', self.decide(tool, {})[1])

    def test_explicit_delivery_action_overrides_read_or_write_names(self):
        for tool in ('mcp__notion__get_page', 'mcp__notion__create_page'):
            self.grant(tool)
            for ti in ({'action': 'send_message'}, {'operation': 'submitApplication'},
                       {'actions': [{'name': 'reply'}]}):
                self.assertIn('hard rule 1', self.decide(tool, ti)[1], (tool, ti))

    def test_unknown_and_generic_tools_denied_despite_grants_or_get_hint(self):
        for tool in ('mcp__artifact_session__js', 'mcp__service__execute', 'mcp__service__request',
                     'mcp__newservice__get_page', 'mcp__service__execute_write', 'mcp__service__mystery'):
            self.grant(tool)
            for ti in ({}, {'method': 'GET'}, {'action': 'read'}, {'operation': 'create'}):
                decision = self.decide(tool, ti)
                self.assertEqual(decision[0], 'deny', (tool, ti))
                self.assertIn('classif', decision[1], (tool, ti))

    def test_reviewed_reads_check_personal_values_in_connector_queries(self):
        self.grant()
        self.assertIsNone(self.decide('mcp__notion__search', {'query': 'QA jobs'}))
        self.assertIsNone(self.decide('mcp__notion__get_page', {'page_id': 'example'}))
        self.assertEqual(self.decide('mcp__notion__search', {'query': 'Jordan Example'})[0], 'deny')

    def test_document_and_local_drafts_still_possible(self):
        tool = 'mcp__gmail__create_draft'
        self.grant(tool, 'mcp__notion__create_page')
        self.assertEqual(self.decide(tool, {'body': 'Draft', 'name': 'Reply'})[0], 'ask')
        self.assertEqual(self.decide('mcp__notion__create_page', {})[0], 'ask')
        self.assertIsNone(self.decide('Write', {'file_path': self.path('applications/draft.md')}))

    def test_browser_mutations_cannot_be_confirmed_into_submission(self):
        for tool, ti in (('mcp__playwright__browser_click', {'element': 'Send'}),
                         ('mcp__browser__submit', {}),
                         ('mcp__Claude_Browser__computer', {'action': 'left_click'})):
            self.grant(tool)
            self.assertEqual(self.decide(tool, ti, cwd=self.dd)[0], 'deny')

    def test_unknown_connector_fails_closed_on_check_error(self):
        data = json.dumps({'cwd': self.proj, 'tool_name': 'mcp__service__mystery', 'tool_input': {}})
        out = io.StringIO()
        with patch.object(guard_writes, 'decide', side_effect=RuntimeError('failure')), contextlib.redirect_stdout(out):
            guard_writes.main(io.StringIO(data), self.env)
        self.assertEqual(json.loads(out.getvalue())['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_final_delivery_endpoint_not_authorized_by_host_grant(self):
        with open(self.path('jobsearch.config.json'), 'w') as f:
            json.dump({'privacy': {'approved_destinations': [{'type': 'host', 'host': 'example.org'}]}}, f)
        for path in ('/send', '/submit', '/reply', '/apply', '/%73end'):
            result = self.decide('Bash', {'command': 'curl -d @draft.txt https://example.org' + path})
            self.assertEqual(result[0], 'deny', path)
            self.assertIn('hard rule 1', result[1])
        self.assertEqual(self.decide('Bash', {'command': 'curl -d @draft.txt https://example.org/upload'})[0], 'ask')
        self.assertEqual(self.decide('Artifact', {'action': 'submit'})[0], 'deny')

    def test_unconfigured_projects_unaffected(self):
        for tool in ('mcp__gmail__send_message', 'mcp__artifact_session__js'):
            self.assertIsNone(self.decide(tool, {}, env={}))
