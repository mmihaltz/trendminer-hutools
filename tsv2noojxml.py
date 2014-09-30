#!/usr/bin/env python

# Input file: tsv with 5 columns with all annotations (see *.ner)
# Output (stdout): XML format of input that NooJ likes

# Author: Marton Mihaltz

import re
import sys
from pytimeout import Timeout


GRUBER_URLINTEXT_PAT = re.compile(ur'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')
# from https://gist.github.com/uogbuji/705383


def print_token_old(t):
  """
  Print token XML tag, take 1
  t: list of input file's columns for this token
  """
  lem = t[1].replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
  surf = t[0].replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
  pos = t[2].split('/')[-1].split('<')[0].replace('-', '').replace('_', '') # Nooj doesn't like CAT="UTT-INT" :(
  postag = t[2].replace('-', '').replace('_', '').replace('<', '{').replace('>', '}')
  morf = t[3].replace('<', '{').replace('>', '}').replace('&', '&amp;').replace('"', '&quot;')
  if lem == ',':
    lem = 'COMMA' # Nooj doesn't like LEMMA="," :(
  is_url = False
  try:
    with Timeout(5):
      is_url = (GRUBER_URLINTEXT_PAT.match(t[0]) != None)
  except Timeout.Timeout:
    sys.stderr.write('Oops, URL regex matching timed out on line:\n{0}\n'.format(line))
  if is_url: # a URL:
    pos = 'NOUN'
    morf = pos
    lem = surf 
  print('<LU LEMMA="{0}" CAT="{1}" postag="{2}" morph="{3}">{4}</LU>'.format(lem, pos, postag, morf, surf))


def print_token(t):
  """
  Print a token's XML "tag" with NooJ compatible magic. Try to use morphana string for main PoS label.
  t: list of input file's columns for this token
  """
  surf = t[0].replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
  lemma = t[1].replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
  postag = t[2].replace('-', '').replace('_', '')
  morph = t[3].replace('&', '&amp;').replace('"', '&quot;')
  feat = []
  if lemma == ',':
    lemma = 'COMMA' # Nooj doesn't like LEMMA="," :(
  is_url = False
  try:
    with Timeout(5):
      is_url = (GRUBER_URLINTEXT_PAT.match(t[0]) != None)
  except Timeout.Timeout:
    sys.stderr.write('Oops, URL regex matching timed out on line:\n{0}\n'.format(line))
  if is_url: # a URL:
    lemma = surf
    cat = 'NOUN'
  else: # not a URL
    if '+' in morph or '[' in morph or morph == 'OOV': # if compound or derivation or OOV: use postag as morph analysis
      morph = postag
    else: # not compound/derivation/unknown
      # get rid of lemma in morph
      morph = morph.split('/')[-1]
    # get cat (main PoS) from morph analysis
    cat = morph.split('<')[0].replace('-', '') # Nooj doesn't like CAT="UTT-INT" :(
    if '<' in morph: # if there are any iflectional tags in morph
      morph = morph[morph.index('<'):] # get rid of main PoS label in morph
      morph = morph.replace('-','')  # Nooj doesn't like "SUBJUNC-IMP"
      # get morphological features form remaining morphanal string
      morph2 = ''
      d = 0 # depth in the feature tree
      for i, ch in enumerate(morph): # iterate over all characters in morph
        if ch == '<':
          d += 1
          if d > 1:
            morph2 += '_'
        elif ch == '>':
          d -= 1
          if d == 0 and i < len(morph)-1:
            morph2 += ' '
        else:
          morph2 += ch
      for f in morph2.split(' '):
        if f != '':
          feat.append(f)
  # bugfixes:
  if lemma == 'egy[ORDINAL]':
    lemma = 'egy'
  # print XML tag:
  feats = (' ' + ' '.join(feat)) if feat != [] else '' # morph. features as NooJ XML import likes them, not valid XML :)
  #feats = ' feat="{0}"'.format(' '.join(feat)) if feat != [] else '' # valid XML
  print('<LU LEMMA="{lemma}" CAT="{cat}"{feats}>{surf}</LU>'.format(lemma=lemma, cat=cat, postag=postag, feats=feats, surf=surf))


if len(sys.argv) != 2:
  sys.exit('Missing input file name\n')


inp = open(sys.argv[1])

print('<?xml version="1.0" encoding="UTF-8"?>\n<docset>')

dcnt = 0
last = ''
ins = False
thiss = ''

for line in inp:
  
  line = line.rstrip()
  
  if line.startswith('#START_'):
    if dcnt > 0:
      print('</doc>')
    id = line.split('\t')[0][7:]
    print('<doc id="{0}">'.format(id))
    dcnt += 1
    last = line
    continue
  
  elif line == '':
    if not last.startswith('#START_'):
      if thiss != '': # f*d up NE tag sequence
        print('</NE>')
        thiss = ''
      print('</s>')
    last = line
    ins = False
    continue
  
  else:
  
    if not ins:
      print('<s>')
      ins = True
    t = line.split('\t')
    
    okay = True
    if len(t) != 5:
      # try to fix f*d up tokenizatons, eg. "500\tezer"
      n = len(t) -3 # last 3 columns must be ok, the fist n-3 could be the rogue toks
      if n % 2 == 0 and '_'.join(t[0:n/2]) == '_'.join(t[n/2:n]) :
        t = ['_'.join(t[0:n/2]), '_'.join(t[0:n/2])] + t[n:] # fix t
      else:
        sys.stderr.write('Warning, incorrect line format:' + line + '\n')
        okay = False

    if okay: # not invalid num. of fields

      # NE tag
      endner = False
      if t[4].startswith('1-'):
        print('<NE type="{0}">'.format(t[4][2:]))
        endner = True
        thiss = ''
      elif t[4].startswith('B-'):
        print('<NE type="{0}">'.format(t[4][2:]))
        thiss = t[0]
      elif t[4].startswith('I-'):
        thiss += ' ' + t[0]
      elif t[4].startswith('E-'):
        endner = True
        thiss = ''
      elif t[4] == 'O' and thiss != '':
        endner = True
        thiss = ''
            
      # Construct and print token XML tag
      #print_token_old(t)
      print_token(t)

      if endner:
        print('</NE>')
      
    last = line

print('</doc>\n</docset>')
