import unittest
from urllib.error import HTTPError

from scripts.check_pr import validate


class PolicyTests(unittest.TestCase):
    def check(self, body='Closes #2', labels=('maintenance',), fetch=lambda n: {'number': n}):
        validate({'body': body, 'labels': [{'name': n} for n in labels]},
                 'gloghry/icon', ['bug', 'enhancement', 'documentation', 'maintenance'], fetch)

    def test_closing_and_non_closing_references(self):
        for body in ('Closes #2', 'Related to #2; follow-up remains.',
                     'Fixes gloghry/icon#2', 'Resolves https://github.com/gloghry/icon/issues/2'):
            with self.subTest(body=body):
                self.check(body)

    def test_extra_non_type_labels_allowed(self):
        self.check(labels=('maintenance', 'help wanted'))

    def test_exactly_one_change_type(self):
        for labels in ((), ('help wanted',), ('bug', 'maintenance')):
            with self.subTest(labels=labels), self.assertRaisesRegex(ValueError, 'exactly one'):
                self.check(labels=labels)

    def test_missing_placeholder_comment_and_foreign_references_rejected(self):
        for body in ('', None, 'Closes #N', '<!-- Closes #2 -->',
                     'Closes gloghry/other#2', 'Closes https://github.com/other/repo/issues/2'):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, 'Reference'):
                self.check(body)

    def test_pr_reference_is_not_an_issue(self):
        with self.assertRaisesRegex(ValueError, 'must exist'):
            self.check(fetch=lambda n: {'pull_request': {'url': 'example'}})

    def test_missing_issue_rejected(self):
        def missing(n):
            raise HTTPError('example', 404, 'Not Found', {}, None)
        with self.assertRaisesRegex(ValueError, 'must exist'):
            self.check(fetch=missing)

    def test_valid_reference_among_multiple_references(self):
        self.check('Related to #1 and Closes #2', fetch=lambda n:
                   {'pull_request': {'url': 'example'}} if n == 1 else {'number': n})

    def test_access_error_does_not_masquerade_as_missing_issue(self):
        def forbidden(n):
            raise HTTPError('example', 403, 'Forbidden', {}, None)
        with self.assertRaises(HTTPError) as caught:
            self.check(fetch=forbidden)
        caught.exception.close()


if __name__ == '__main__':
    unittest.main()
