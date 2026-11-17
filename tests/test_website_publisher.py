import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote

from scripts.export_website import FILES, ROOT, load_export, stage, source_revision
from scripts.publish_website import APIError, MARKER, PREFIX, PRIORITY_FIELD, WEBSITE, blob_sha, publish, push_candidate

SHA = 'a' * 40


class Source:
    def __init__(self, heads=None):
        self.heads = iter(heads or [SHA] * 20)

    def request(self, method, path, data=None):
        assert method == 'GET' and path.endswith('/git/ref/heads/master')
        return {'object': {'sha': next(self.heads)}}


class Website:
    def __init__(self):
        self.main = {}
        self.branches = {}
        self.prs = []
        self.calls = []
        self.labels = {}
        self.fields = {}
        self.failure = None
        self.extra_change = None

    def push(self, base, branch, files):
        assert base == 'b' * 40
        self.branches[branch] = files.copy()

    def request(self, method, path, data=None):
        self.calls.append((method, path, data))
        if self.failure and self.failure in path:
            raise APIError(403)
        if path == '/user':
            return {'login': 'test-publisher'}
        route = path.removeprefix('/repos/' + WEBSITE)
        if route == '':
            return {'default_branch': 'main', 'private': False}
        if route == '/git/ref/heads/main':
            return {'object': {'sha': 'b' * 40}}
        if route.startswith('/git/ref/heads/'):
            if route.removeprefix('/git/ref/heads/') in self.branches:
                return {'object': {'sha': 'c' * 40}}
            raise APIError(404)
        if route.startswith('/contents/'):
            name, query = route.removeprefix('/contents/').split('?')
            ref = parse_qs(query)['ref'][0]
            files = self.branches.get(ref, self.main)
            if name not in files:
                raise APIError(404)
            return {'type': 'file', 'sha': blob_sha(files[name])}
        if route.startswith('/pulls?'):
            query = parse_qs(route.split('?')[1])
            if 'head' in query:
                return [p for p in self.prs if p['head']['ref'] == query['head'][0].split(':')[1]]
            return [p for p in self.prs if p['state'] == 'open']
        if route.startswith('/compare/main...'):
            changed = list(FILES) + ([self.extra_change] if self.extra_change else [])
            return {'files': [{'filename': name} for name in changed]}
        if route == '/pulls' and method == 'POST':
            pr = {'number': len(self.prs) + 100, 'state': 'open', 'body': data['body'],
                  'head': {'ref': data['head'], 'repo': {'full_name': WEBSITE}}}
            self.prs.append(pr)
            return pr
        if route.startswith('/pulls/') and method == 'PATCH':
            next(p for p in self.prs if p['number'] == int(route.split('/')[-1]))['state'] = data['state']
            return {}
        if route.startswith('/issues/'):
            number = int(route.split('/')[2])
            if route.endswith('/issue-field-values'):
                self.fields[number] = [{'issue_field_id': PRIORITY_FIELD,
                                        'single_select_option': {'name': data['issue_field_values'][0]['value']}}]
                return self.fields[number]
            if '/labels/' in route and method == 'DELETE':
                self.labels[number].remove(unquote(route.split('/labels/')[1]))
                return None
            if route.endswith('/labels'):
                labels = self.labels.setdefault(number, [])
                if method == 'POST':
                    labels[:] = sorted(set(labels + data['labels']))
                return [{'name': n} for n in labels]
            return {'issue_field_values': self.fields.get(number, [
                {'issue_field_id': PRIORITY_FIELD, 'single_select_option': {'name': 'High'}}])}
        raise AssertionError((method, route, data))


class WebsitePublisherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bundle = self.root / 'export'
        self.config = json.loads((ROOT / 'gl_assets/variants/original/config.json').read_text())
        self.files = stage(ROOT / 'generated/original', self.bundle, self.config, SHA)
        self.api = Website()

    def publish(self, source=None):
        return publish(self.api, source or Source(), self.bundle, SHA, self.api.push)

    def mutations(self):
        return [c for c in self.api.calls if c[0] != 'GET']

    def proposal(self, branch, number=50, state='open', body=MARKER):
        return {'number': number, 'state': state, 'body': body,
                'head': {'ref': branch, 'repo': {'full_name': WEBSITE}}}

    def test_exact_bundle_reproducible_with_source_identity(self):
        self.assertEqual(set(self.files), set(FILES))
        other = self.root / 'again'
        self.assertEqual(self.files, stage(ROOT / 'generated/original', other, self.config, SHA))
        self.assertEqual(load_export(self.bundle)[1], load_export(other)[1])
        provenance = json.loads(self.files['docs/gl-mark-provenance.json'])
        self.assertEqual(provenance['source_commit'], SHA)
        self.assertEqual(provenance['source_repository'], 'https://github.com/gloghry/icon')
        self.assertEqual(provenance['source_directory'], 'generated/original/web')
        self.assertIn(SHA.encode(), self.files['docs/gl-mark.md'])
        self.assertFalse(any(p.suffix in ('.blend', '.glb', '.py') for p in self.bundle.rglob('*')))

    def test_missing_extra_tampered_and_symlink_rejected(self):
        for mode in ('extra', 'missing', 'tampered', 'symlink'):
            with self.subTest(mode=mode):
                folder = self.root / mode
                shutil.copytree(self.bundle, folder)
                path = folder / FILES[0]
                if mode == 'extra':
                    (folder / 'private.txt').write_text('must not cross repositories')
                elif mode == 'tampered':
                    path.write_bytes(b'bad')
                else:
                    path.unlink()
                    if mode == 'symlink':
                        path.symlink_to(self.bundle / FILES[0])
                with self.assertRaises(ValueError):
                    load_export(folder)

    def test_missing_source_identity_rejected_even_with_updated_manifest(self):
        name = 'docs/gl-mark-provenance.json'
        path = self.bundle / name
        provenance = json.loads(path.read_text())
        del provenance['source_commit']
        path.write_text(json.dumps(provenance))
        manifest_path = self.bundle / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'source commit'):
            load_export(self.bundle)

    def test_asset_revision_survives_publisher_changes_and_rejects_dirty_exports(self):
        root = self.root / 'history'
        root.mkdir()

        def git(*args):
            return subprocess.run(['git', *args], cwd=root, check=True,
                                  capture_output=True, text=True).stdout.strip()

        def commit(message):
            git('add', '.')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                'commit', '-m', message)
            return git('rev-parse', 'HEAD')

        git('init')
        assets = root / 'generated/original'
        assets.mkdir(parents=True)
        mark = assets / 'test.png'
        mark.write_bytes(b'approved asset')
        approved = commit('Approved asset')
        (root / 'publisher.py').write_text('Publisher-only change')
        commit('Update publisher')
        self.assertEqual(source_revision(root), approved)
        mark.write_bytes(b'new asset')
        with self.assertRaisesRegex(ValueError, 'Commit regenerated'):
            source_revision(root)
        changed = commit('New asset')
        self.assertNotEqual(changed, approved)
        self.assertEqual(source_revision(root), changed)
        shallow = self.root / 'shallow'
        subprocess.run(['git', 'clone', '--depth', '1', root.as_uri(), str(shallow)],
                       check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, 'Full asset history'):
            source_revision(shallow)

    def test_staging_refuses_stale_config_hash_and_existing_directory(self):
        config = copy.deepcopy(self.config)
        config['seed'] += 1
        with self.assertRaisesRegex(ValueError, 'config'):
            stage(ROOT / 'generated/original', self.root / 'bad-config', config, SHA)
        with self.assertRaisesRegex(ValueError, 'not exist'):
            stage(ROOT / 'generated/original', self.bundle, self.config, SHA)
        source = self.root / 'source'
        shutil.copytree(ROOT / 'generated/original', source)
        (source / 'web/gl-mark.png').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'manifest'):
            stage(source, self.root / 'bad-hash', self.config, SHA)

    def test_atomic_allowlisted_proposal_and_supersession(self):
        old = self.proposal(PREFIX + 'old')
        human = self.proposal('human-change', 51, body='Human PR')
        self.api.prs = [old, human]
        result = self.publish()
        self.assertEqual(result['status'], 'opened')
        self.assertEqual(set(next(iter(self.api.branches.values()))), set(FILES))
        self.assertEqual(old['state'], 'closed')
        self.assertEqual(human['state'], 'open')
        pr = self.api.prs[-1]
        self.assertNotIn(SHA, pr['body'])
        self.assertIn('Related to #86', pr['body'])
        self.assertIn('test-publisher', pr['body'])
        self.assertEqual(self.api.labels[pr['number']], ['enhancement'])
        self.assertEqual(self.api.fields[pr['number']][0]['single_select_option']['name'], 'High')
        self.assertFalse(any('/merge' in c[1] for c in self.api.calls))

    def test_identical_content_no_new_commit_or_pr(self):
        self.api.main = self.files
        self.assertEqual(self.publish()['status'], 'unchanged')
        self.assertEqual(self.mutations(), [])
        self.assertFalse(self.api.branches)

    def test_stale_run_cannot_touch_website(self):
        self.assertEqual(self.publish(Source(['c' * 40]))['status'], 'skipped-stale')
        self.assertEqual(self.api.calls, [])

    def test_source_advances_before_push(self):
        self.assertEqual(self.publish(Source([SHA, 'c' * 40]))['status'], 'skipped-stale')
        self.assertFalse(self.api.branches)
        self.assertFalse(self.api.prs)

    def test_source_advances_after_push(self):
        self.assertEqual(self.publish(Source([SHA, SHA, 'c' * 40]))['status'], 'skipped-stale')
        self.assertTrue(self.api.branches)
        self.assertFalse(self.api.prs)

    def test_existing_open_repairs_labels_and_priority_without_push(self):
        branch = PREFIX + load_export(self.bundle)[1][:24]
        self.api.branches[branch] = self.files
        self.api.prs = [self.proposal(branch)]
        self.api.labels[50] = ['bug', 'priority:P1', 'accessibility']
        self.assertEqual(self.publish()['status'], 'existing-open')
        self.assertEqual(self.api.labels[50], ['accessibility', 'enhancement'])
        self.assertEqual(len(self.api.prs), 1)

    def test_closed_identical_proposal_not_reopened(self):
        branch = PREFIX + load_export(self.bundle)[1][:24]
        self.api.prs = [self.proposal(branch, state='closed')]
        self.assertEqual(self.publish()['status'], 'existing-closed')
        self.assertEqual(self.mutations(), [])

    def test_orphan_branch_reused_only_when_exact_and_allowlisted(self):
        branch = PREFIX + load_export(self.bundle)[1][:24]
        self.api.branches[branch] = self.files
        self.api.extra_change = '.github/workflows/pages.yml'
        with self.assertRaisesRegex(ValueError, 'unrelated'):
            self.publish()
        self.assertFalse(self.api.prs)
        self.api.extra_change = None
        self.assertEqual(self.publish()['status'], 'opened')

    def test_foreign_or_changed_branch_rejected(self):
        branch = PREFIX + load_export(self.bundle)[1][:24]
        self.api.prs = [self.proposal(branch, body='Human change')]
        with self.assertRaisesRegex(ValueError, 'not publisher-owned'):
            self.publish()
        self.api.prs[0]['body'] = MARKER
        self.api.branches[branch] = {**self.files, FILES[0]: b'other'}
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.publish()

    def test_permission_failure_retry_repairs_existing_pr(self):
        self.api.failure = '/labels'
        with self.assertRaises(APIError):
            self.publish()
        self.assertEqual(len(self.api.prs), 1)
        self.api.failure = None
        self.assertEqual(self.publish()['status'], 'existing-open')
        self.assertEqual(len(self.api.prs), 1)

    def test_native_priority_failure_is_reported_and_retryable(self):
        self.api.failure = '/issue-field-values'
        with self.assertRaises(APIError):
            self.publish()
        self.assertEqual(len(self.api.prs), 1)
        self.api.failure = None
        self.assertEqual(self.publish()['status'], 'existing-open')

    def test_real_git_commit_only_candidate_branch_and_allowlisted_changes(self):
        # Exercise real git end to end against a local bare remote, never GitHub.
        remote, seed = self.root / 'remote.git', self.root / 'seed'
        run = subprocess.run

        def git(*args, cwd=None):
            return run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

        git('init', '--bare', str(remote))
        git('init', '-b', 'main', str(seed))
        (seed / 'unrelated.txt').write_text('preserve this website content')
        git('add', '.', cwd=seed)
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
            'commit', '-m', 'Seed website', cwd=seed)
        base = git('rev-parse', 'HEAD', cwd=seed)
        git('remote', 'add', 'origin', str(remote), cwd=seed)
        git('push', 'origin', 'main', cwd=seed)

        def local_run(command, **kwargs):
            self.assertNotIn('test-secret', ' '.join(command))
            if command[:4] == ['git', 'remote', 'add', 'origin']:
                self.assertEqual(command[4], 'https://github.com/' + WEBSITE + '.git')
                command = command[:4] + [str(remote)]
            return run(command, **kwargs)

        branch = PREFIX + 'local-test'
        with patch('scripts.publish_website.subprocess.run', side_effect=local_run):
            push_candidate('test-secret', base, branch, self.files)
        self.assertEqual(git('rev-parse', 'refs/heads/main', cwd=remote), base)
        changed = git('diff', '--name-only', base, 'refs/heads/' + branch, cwd=remote).splitlines()
        self.assertEqual(set(changed), set(FILES))
        for name, data in self.files.items():
            self.assertEqual(run(['git', 'show', branch + ':' + name], cwd=remote,
                                 check=True, capture_output=True).stdout, data)
