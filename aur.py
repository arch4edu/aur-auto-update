import os
import re
import requests
import pickle

class AUR:

    base_url = 'https://aur.archlinux.org'
    comment_id_re = re.compile(r'<a href="#comment-([^"]*)"')

    def __init__(self, username, password, cookies=None):
        self.username = username
        self.password = password

        self.session = requests.session()
        self.cookies_file = cookies

        if not self.cookies_file is None and os.path.exists(self.cookies_file):
            with open(self.cookies_file, 'rb') as f:
                self.session.cookies.update(pickle.load(f))

    def login(self):
        url = self.base_url + '/login'
        data = {
            'user': self.username,
            'passwd': self.password,
            'referer': AUR.base_url,
            'next': "/account/" + self.username,
            'remember_me': 'on'
        }
        headers = {'Referer': AUR.base_url + '/login?next=/account/' + self.username}
        response = self.session.post(url, data=data, headers=headers, allow_redirects=False)
        assert response.status_code == 303

        if not self.cookies_file is None:
            with open(self.cookies_file, 'wb') as f:
                pickle.dump(self.session.cookies, f)

    def get_profile(self):
        url = '/'.join([AUR.base_url, 'account', self.username])
        response = self.session.get(url)
        if response.status_code != 200:
            self.login()
        response = self.session.get(url)
        assert response.status_code == 200
        return response.text

    def flag(self, package, comment):
        pass

    def unflag(self, package, comment):
        pass

    def comment(self, pkgbase, comment):
        url = '/'.join([AUR.base_url, 'pkgbase', pkgbase, 'comments'])
        data = {'comment': comment}
        response = self.session.post(url, data=data, allow_redirects=False)
        assert response.status_code == 303

    def get_latest_comment_id(self, pkgbase, username=None):
        url = '/'.join([AUR.base_url, 'pkgbase', pkgbase])
        response = self.session.get(url)
        assert response.status_code == 200

        username = self.username if username is None else username
        lines = response.text.split('\n')
        line = [line for line in lines if username in line and '#comment-' in line][0]
        comment_id = AUR.comment_id_re.search(line).group(1)
        return comment_id

    def update_comment(self, pkgbase, comment_id, comment):
        url = '/'.join([AUR.base_url, 'pkgbase', pkgbase, 'comments', comment_id])
        data = {'comment': comment}
        response = self.session.post(url, data=data, allow_redirects=False)
        assert response.status_code == 303

    def pin_comment(self, pkgbase, comment_id):
        url = '/'.join([AUR.base_url, 'pkgbase', pkgbase, 'comments', comment_id, 'pin'])
        response = self.session.post(url, allow_redirects=False)
        assert response.status_code == 303

    def unpin_comment(self, pkgbase, comment_id):
        url = '/'.join([AUR.base_url, 'pkgbase', pkgbase, 'comments', comment_id, 'unpin'])
        response = self.session.post(url, allow_redirects=False)
        assert response.status_code == 303
