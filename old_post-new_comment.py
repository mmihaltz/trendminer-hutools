#!/usr/bin/python
# coding=utf8

import sys
import json
import argparse
import datetime
import dateutil.parser
import requests
import os.path


def get_access_token():
	"""	regisztrálni kell FB fejlesztőként a https://developers.facebook.com/ oldalon
			ezután az 'Alkalmazások' menüpontban lehet új alkalmazást létrehozni
			az alkalmazás kap egy alkalmazás azonosítót és egy app secret-et
			ezeket megadva lehet access tokent igényelni
			alább toth ubul 'pro1' alkalmazásának azonosítója és titka szerepel
	"""
	client_id = 'client_id=626412687431595'
	client_secret = 'client_secret=1a0245613a34d8fa41ac85784f878074'
	link = 'https://graph.facebook.com/oauth/access_token?grant_type=client_credentials&{_id}&{_sec}'
	r = requests.get(link.format(_id=client_id, _sec=client_secret))
	access_token = r.text.split('=')[1]
	return r.text

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

def date_check(date_str):
	"""	Ellenőrzi a date_str érvényességét.
			Formátum: YYYY-MM-DD
			Ha érvényes, akkor egy datetime.datetime objektummal tér vissza,
	"""
	try:
		return dateutil.parser.parse(date_str+'T00:00:00+0000') # időzóna: utc
	except: raise argparse.ArgumentTypeError('Valid date format: YYYY-MM-DD')

def args_handling():
	"""	Parancssori argumentumok kezelése:
				-d DÁTUM: a d-nél nem újabb, de egy héttel nem is régibb posztok d-nél újabb kommetjeit keressük. Kötelező megadni.
				-h: Segítség megjelenítése.
				Más esetben használati utasítás kiírása és kilépés.
	"""
	desc_prog = '' + \
			'Letölti a megadott dátumnál újabb kommentjeit a dátumnál max 1 héttel régebbi posztoknak. ' + \
			'A program stdin-ről olvassa a felhasználók id-it, akiknek a posztjai kellenek. ' + \
			'A kimenet id-nként egy .json file, ami tartalmazza az érintett posztok id-it, keletkezési idejét és a hozzá tartozó kommenteket. ' + \
			'A kimeneti fájl neve tartalmazza a \'comments\' prefix után a felhasználó id-ját, a megadott dátumot és az aktuális datumot.'
	desc_date = 'Formátum: YYYY-MM-DD.'
	desc_input = 'Bemenő adatok: FB id-kat tartlmazó .cvs fájl. Az id-k az első oszlopban kell legyenek.'
	desc_target = 'Kimeneti fájlok könyvtára.'
	pars = argparse.ArgumentParser(description=desc_prog)
	pars.add_argument('-d', '--date', help=desc_date, type=date_check, required=True)
	pars.add_argument('-i', '--input', help=desc_input, type=input_check, required=True)
	pars.add_argument('-t', '--target', help=desc_target, type=target_check, required=True)
	args = pars.parse_args()
	return {'date':args.date, 'file': args.input, 'target': args.target}


class FB:
	"""	egy FB user-id-hoz tartozó objektumok osztálya,
			egy objektum tartalmazza
			- a hasznos adatokat (data)
			- a dátumokat, amik meghatározzák, hogy mely adatok hasznosak (since és until)
			- segéd információk az adatok begyűjtéséhez (link, stb)
	"""
	def __init__(self, id_, date ):
		self.since = date - datetime.timedelta(weeks=1)
		self.until = date
		fields = '?fields=posts.fields(shares,comments.fields(created_time,id,message,from,comments.fields(created_time,id,message,from)))'
		self.access = '&' + get_access_token() # újra kérünk minden id-hez, nehogy lejárjon menet közben
		self.base_link = 'https://graph.facebook.com/' + id_
		link = self.base_link + fields + self.access
		self.data = {'id':id_, 'posts':{'data':[]}}
		self.get_data(link, self.data['posts']['data'])

	def filter_post(self, item):
		"""	szűri a posztok alap 25 kommentjéből a régieket
		"""
		cct = dateutil.parser.parse(item['created_time'])
		return cct >= self.until

	def check_item(self, item, data, com):
		"""	item: az ellenőrzendő elem
				data: ha az elem rendben van, akkor a 'data' listához adjuk
				com: igaz, ha az item komment, hamis, ha poszt
				return:
					komment: mindig igaz (az összes kommentet végig kell nézni, mert nem jólrendezettek)
					poszt: igaz, ha nem régibb since-nél
		"""
		ct = dateutil.parser.parse(item['created_time'])
		useful = 'message' in item or 'comments' in item or 'caption' in item
		if useful: # ha az itemben nincs hasznos info, eldobjuk
			if not com and self.since <= ct <= self.until: # postnál a kezdő 25 komment szűrése
				if item.get('comments', {}).get('data', None): # persze csak ha van
					item['comments']['data'] = filter(self.filter_post, item['comments']['data'])
				data += [item] # ha a poszt rendben van, hozzáadjuk 'data'-hoz
			elif com and ct >= self.until: data += [item] # ha komment, és elég új, akkor hozzáadjuk 'data'-hoz
		return com or ct >= self.since # kommentnél folytatjuk a vizsgálatot, postnál csak ha nem túl régi

	def get_data(self, link, data, com = False):
		"""	rekurzívan hívja magát a paging/next-tel mind posztokra, mind kommentekre
				begyűjti a since-nél újabb de until-nál régibb posztokat
				végig nézi ezek kommentjeit és az untilnál újabbakat beírja self.data-ba
					- megj: a posztoknál feltesszük, hogy jól rendezettek, a kommenteket viszont mind végig nézzük
		"""
		try:
			req = json.loads(requests.get(link).text)
			dl_date = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+0000') # letöltés időpontja
		except:
			self.data = { 'error':link }
			sys.stderr.write('\tHiba a feldolgozásban!')
			return
		if 'posts' in req: req = req['posts'] # posts-on kívüli adatok nem fontosak
		ok = True # lesz-e rekurzív hívás (hamis lesz a since-nél régebbi posztokra)
		new = req.get('data', []) # a megvizsgálandó elemek
		link = req.get('paging', {}).get('next') # ha van, ezzel lehet tovább menni, ha nincs, None lesz
		for item in new: # elemek vizsgálata
			ok = self.check_item(item, data, com) # com: posztnál hamis, kommentnél igaz; ok: kommentnél mindig igaz lesz
			if not ok: break # since-nél régebbit találtunk, a) nem kell a többi posztot vizsgálni, b) rekurzióval leállunk
			else: # az elem jó, ha van komment mezője, azon is végig lapozunk
				com_link = item.get('comments', {}).get('paging', {}).get('next')
				com_data = item.get('comments', {}).get('data') # elvileg a comments-nek kell legyen datá-ja
				if not com and com_data: # letöltési idő beállítása a posztok alap 25 kommentjére
					for i in com_data:
						i['download_date'] = dl_date
				if com_link: self.get_data(com_link, com_data, True) # a data kiürülhet a post ellenőrzésénél, csak a linket ellenőrizzük
				item['download_date'] = dl_date # letöltési idő beállítása posztokra és lapozott kommentekre
				item.get('comments', {}).pop('paging', None) # immár felesleges mező eldobása
		if ok and link: self.get_data(link, data, com) # ha minden rendben, rekurzálunk



def main():
	params = args_handling() # dict mezői: (input)file, date, target(dirextory)
	for line in params['file']:
		id_ = line.split(',')[0]
		if not id_.isdigit(): continue
		sys.stderr.write(line) # log
		fb = FB(id_, params['date'])
		with open(params['target'] + 'comments_' + id_ + '_' + \
				params['date'].strftime('%Y-%m-%d') + '_' + \
				datetime.datetime.today().strftime('%Y-%m-%d') + \
				'.json', 'w') as f:
			json.dump(fb.data, f, indent=2)


if __name__ == '__main__':
	main()

