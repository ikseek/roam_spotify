#!/usr/bin/env python3
from argparse import ArgumentParser
from os import environ, path, makedirs, walk
from re import sub
from subprocess import Popen
from sys import exit
from time import sleep

def main():
	args = parseArgs()
	base = Userbase(args.users_dir)
	spotify = Spotify()
	if args.add:
		addCurrentUser(spotify.config, base)
	if args.login:
		loginAllUsers(spotify, base, args.ssh, args.wait)
	if not args.add and not args.login:
		print('Users:', *base)
	return 0

def parseArgs():
	parser = ArgumentParser(description='Auto login spotify users through given ssh server')
	parser.add_argument('users_dir', help='users database directory', nargs='?', default='data')
	parser.add_argument('-a', '--add', help='add current user to database', action='store_true')
	parser.add_argument('-l', '--login', help='login all users from database', action='store_true')
	parser.add_argument('-s', '--ssh', metavar='HOST', help='ssh server to use as socks5 proxy')
	parser.add_argument('-w', '--wait', metavar='SECS', type=int, default=5,
		help='time to assure spotify logged in, default is %(default)s seconds')
	return parser.parse_args()

def addCurrentUser(config, base):
	login_info_keys = ['autologin.username', 'autologin.blob', 'core.facebook_machine_id']
	login_info = { key: config[key] for key in login_info_keys }
	login_data_filename = sub(r'^"|"$', '', login_info['autologin.username'])
	base[login_data_filename] = login_info

def loginAllUsers(spotify, base, ssh, wait_seconds):
	config_backup = spotify.config.copy()	
	if ssh:
		proxy = SSHProxy(ssh, 51234)
		spotify.config['network.proxy.mode'] = 2
		spotify.config['network.proxy.addr'] = '"{0}:{1}@socks5"'.format('localhost', proxy.port)
	try:
		for user in base.values():
			loginUser(spotify, user, wait_seconds)
	finally:
		spotify.config.clear()
		spotify.config.update(config_backup)
		spotify.config.save()

def loginUser(spotify, login_data, wait_seconds):
	spotify.config.update(login_data)
	spotify.config.save()
	spotify.run()
	sleep(wait_seconds)
	spotify.kill()

class SSHProxy:
	def __init__(self, host, port):
		self.host = host
		self.port = port
		self._process = None
		self._process = Popen(['ssh', host, '-N', '-D', str(port)])

	def kill(self):
		self._process.kill()
		self._process = None

	def __del__(self):
		if self._process:
			try:
				self.kill()
			except OSError:
				pass

class Spotify:
	def __init__(self):
		spotydir = path.join(environ['APPDATA'], 'Spotify')
		self.config = Config(path.join(spotydir, 'prefs'))
		self._bin_file_path = path.join(spotydir, 'spotify.exe')
		self._process = None

	def run(self):
		self._process = Popen(self._bin_file_path)

	def kill(self):
		self._process.kill()
		self._process = None

	def __del__(self):
		if self._process:
			self.kill()

class Config(dict):
	def __init__(self, filename):
		self.filename = filename
		if path.exists(filename):
			with open(filename, encoding='utf-8') as file:
				lines = file.read().splitlines()
				key_values = ( line.split('=', 1) for line in lines if line )
				self.update(key_values)

	def save(self):
		with open(self.filename, 'w', encoding='utf-8') as file:
			for key, value in self.items():
				print(key, value, sep='=', file=file)

class Userbase:
	def __init__(self, dirname):
		self.dirname = dirname

	def __iter__(self):
		return iter(self.keys())

	def __getitem__(self, key):
		return Config(path.join(self.dirname, key))

	def __setitem__(self, key, value):
		makedirs(self.dirname, exist_ok=True)
		config = Config(path.join(self.dirname, key))
		config.update(value)
		config.save() 

	def keys(self):
		for root, dirs, files in walk(self.dirname):
			return files # don't recurse
		else:
			return []

	def values(self):
		for key in self:
			yield self[key]

	def items(self):
		for key in self:
			yield (key, self[key])

if __name__ == '__main__':
	try:
		exit(main())
	except (KeyboardInterrupt, SystemExit):
		exit(1)