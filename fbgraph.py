#!/usr/bin/python
# coding=utf8

"""
Dowload public comments and posts from list of fb pages within given dates
Authors: Ivan Mittelholcz, Marton Mihaltz
https://github.com/mmihaltz/trendminer-hutools
"""

import sys
import json
import argparse
import datetime
import dateutil.parser
import requests
import os.path


def get_access_token():
	"""Register as a FB developer at https://developers.facebook.com/ oldalon,
	   create a new Application, use the id and secret key from there
	"""
	client_id = 'YOURCLIENTIDHERE'
	client_secret = 'YOURCLIENTSECRETHERE'
	link = 'https://graph.facebook.com/oauth/access_token?grant_type=client_credentials&client_id={0}&client_secret={1}'
	r = requests.get(link.format(client_id, client_secret))
	access_token = r.text.split('=')[1]
	return r.text

def date_check(date_str):
	"""	Ellenőrzi a date_str érvényességét.
			Formátum: YYYY-MM-DD
			Ha érvényes, akkor egy datetime.datetime objektummal tér vissza,
			kiegészítve a dátumot GMT+1 szerinti 0 óra 0 perccel
	"""
	try: return dateutil.parser.parse(date_str+'T00:00:00+0100')
	except: raise argparse.ArgumentTypeError('Valid date format: YYYY-MM-DD')

def input_check(inp_str):
	"""	Bemeneti fájl ellenőrzése, visszatérés a leíróval.
	"""
	try: return open(inp_str, 'r')
	except: raise

def target_check(dir_str):
	"""	Kimeneti könyvtár ellenőrzése.
	"""
	dir_str = dir_str.rstrip('/') + '/'
	if os.path.exists(dir_str): return dir_str
	else: raise IOError('Nincs ilyen könyvtár!')

def args_handling():
	"""	Parse command line arguments
	"""
	desc_prog = 'Download posts and comments from FB into json files'
	desc_date = 'Download data starting from given date (YYYY-MM-DD)'
	desc_until = 'Download data until given date (YYYY-MM-DD)'
	desc_input = 'Input is a csv file with the FB page ids in the 1st column'
	desc_target = 'Directory for output files'
	pars = argparse.ArgumentParser(description=desc_prog)
	pars.add_argument('-d', '--date', help=desc_date, type=date_check, required=True)
	pars.add_argument('-u', '--until', help=desc_until, type=date_check, required=False)
	pars.add_argument('-i', '--input', help=desc_input, type=input_check, required=True)
	pars.add_argument('-t', '--target', help=desc_target, type=target_check, required=True)
	args = pars.parse_args()
	if args.until and args.date >= args.until:
		sys.stderr.write('\n\tInvalid dates!\n\n')
		sys.exit(1)
	return {'date':args.date, 'until':args.until, 'file': args.input, 'target': args.target}


class FB:
	def __init__(self, id_, date, until):
		self.since = date
		self.until = until
		fields = '?fields=posts.fields(shares,from.fields(id),caption,message,comments.fields(created_time,id,message,from,comments.fields(created_time,id,message,from)))'
		self.access = '&' + get_access_token() # újra kérünk minden id-hez, nehogy lejárjon menet közben
		self.base_link = 'https://graph.facebook.com/v2.0/' + id_
		link = self.base_link + fields + self.access
		self.data = {'id':id_, 'posts':{'data':[]}}
		self.get_data(link, self.data['posts']['data'])

	def check_item(self, item, data, com):
		"""	ellenőrzi az item dátumát
				ha ez ok ÉS tartalmaz hasznos adatot, akkor self.data-t bővíti
				ha a dátum nem ok, akkor hamissal tér vissz, get_data() leáll
		"""
		ct = dateutil.parser.parse(item['created_time'])
		fresh = com or ct >= self.since
		too_fresh = ct >= self.until if self.until else False
		ok = fresh and not too_fresh  if not com else True # kommentek mindig kellenek, posztok csak ha a két dátum közé esnek
		if ok and ('message' in item or 'comments' in item or 'caption' in item): data += [item]
		return fresh

	def get_data(self, link, data, com = False):
		"""	rekurzívan hívja magát, amíg a paging/next-tel tovább lehet menni
				ÉS még nem találtunk since-nél régebbi elemet
		"""
		try:
			req = json.loads(requests.get(link).text)
			dl_date = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+0000') # letöltés időpontja
		except:
			self.data = { 'error':link }
			sys.stderr.write('\tProcessing error!')
			return
		if 'posts' in req: req = req['posts'] # posts-on kívüli adatok nem fontosak
		ok = True # lesz-e rekurzív hívás
		new = req.get('data', [])
		link = req.get('paging', {}).get('next')
		for item in new:
			if not self.check_item(item, data, com):
				ok = False # since-nél régebbit találtunk, a rekurzióval leállunk
				break # az elemek sorban vannak (kommentek nem egészen!), nem kell tovább ellenőrizni
			else: # az elem jó, megnézzük van-e komment mezője, ha igen, azon is végig lapozunk
				com_link = item.get('comments', {}).get('paging', {}).get('next')
				com_data = item.get('comments', {}).get('data')
				if not com and com_data: # letöltési idő beállítása a posztok alap 25 kommentjére
					for i in com_data:
						i['download_date'] = dl_date
				if com_link and com_data: self.get_data(com_link, com_data, True)
				item['download_date'] = dl_date # letöltési idő beállítása posztokra és lapozott kommentekre
				item.get('comments', {}).pop('paging', None) # felesleges lapozó mező eldobása
		if ok and link: self.get_data(link, data, com)


def main():
	params = args_handling() # dict mezői: (input)file, date, target(dirextory)
	for line in params['file']:
		id_ = line.rstrip('\n').split(',')[0]
		if not id_.isdigit(): continue
		sys.stderr.write(line) # log
		fb = FB(id_, params['date'], params['until'])
		with open(params['target'] + id_ + '_' + \
				params['date'].strftime('%Y-%m-%d') + '_' + \
				(params['until'] if params['until'] else datetime.datetime.today()).strftime('%Y-%m-%d') + \
				'.json', 'w') as f:
			json.dump(fb.data, f, indent=2)


if __name__ == '__main__':
	main()

