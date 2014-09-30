#!/usr/bin/env python3
# coding: UTF-8
"""
Input1: .xml.txt file name (NooJ XML output w/ NooJ annotations + structural and NLP annotations)
Input2: .xml file name (full NLP annotation, same texts as Input1; for lemmatisation)

(Disabled:
Output: tsv file to stdout:
doc_id sentence_id start_tok_idx end_tok_idx annotated_tex annotated_text_with_lemmatized_head tag#attribute=value(...)
)

Insert new record into dbtrendminer.fb_comments_annots for each annotation.

Calculate scores for each document and insert records into dbtrendminer.fb_comments_scores.

@author: Marton Mihaltz
"""

import collections
import pymysql
import re
import sys
import xml.parsers.expat


# Ok, global variables, but how else to share data among expat callback functions?!
docid = '' # document id
sid = -1 # sentece id
toks = [] # sentence tokens
annots = []  # [(tag, attrs, start_tok_idx), ...]
nlp = {} # {docid: [[lemma, ...], ...], ...} (lemmas for each token in each sentence in the docs, read from file2
cnt = 0 # count rows inserted into fb_comments_annots
cnt2 = 0 # count rows inserted into fb_comments_scores
docannots = collections.Counter() # counts for all annotations in a doc


# XML handler functions
def start_element(name, attrs):
  global docid, sid, toks, annots, nlp
  if name == 'NE':
    return
  annots.append( (name, attrs, len(toks)-1) )

def end_element(name):
  global docid, sid, toks, annots, cnt
  if name == 'NE':
    return
  if len(annots) == 0 or annots[-1][0] != name:
    print('Error: annots = {} vs. end_element({})'.format(annots, name))
    return
  anno = annots[-1][0]
  for a, v in annots[-1][1].items():
    anno += '#' + a + '=' + v
  start = annots[-1][2]
  end = len(toks)-1
  txt = ' '.join(toks[start:])
  ltxt = txt
  if docid in nlp and len(nlp[docid]) > sid and len(nlp[docid][sid]) > end and nlp[docid][sid][end] != '#!LEMMA_UNKNOWN!#': # lemmatize last token if possible
    ltxt = ' '.join(toks[start:end]) # up to the head
    ltxt += (' ' if ltxt != '' else '') + nlp[docid][sid][end] # lemmatized head
  #print('\t'.join([docid, str(sid), str(start), str(end), txt, ltxt, anno]))
  tdocid = docid.split('_')
  db_insert_annot(tdocid[0], tdocid[1], tdocid[2], str(sid), str(start), str(end), txt, ltxt, anno)
  docannots.update([anno])
  annots.pop()


# Parse NooJ annotation file & output annotations to stdout
def parse_file(xmlfile):
  global docid, sid, toks, annots
  parser = xml.parsers.expat.ParserCreate(encoding='UTF-8')
  parser.StartElementHandler = start_element
  parser.EndElementHandler = end_element
  parser.Parse('<bigbang>') # dummy root tag
  skipthisdoc = False
  for line in open(xmlfile):
    line = line.rstrip()
    #print(line)
    #if line == '</s>':
    #  print('{}\t{}\t{}'.format(docid, sid, toks))
    if line.startswith('<?xml ') or line in ['', '</s>', '<docset>', '</docset>']: # skip these
      continue
    if line == '</doc>': # end of a doc
      #print(docannots)
      tdocid = docid.split('_')
      db_insert_scores(tdocid[0], tdocid[1], tdocid[2])
      continue
    if line.startswith('<doc id='): # new doc
      docid = line[9:-2]
      sid = -1
      skipthisdoc = False
      docannots.clear()
      continue
    if line == '<s>': # new sentence
      sid += 1
      toks = []
      annots = []
      continue
    else:
      t = re.sub('<[^>]+>', '', line) # remove XML tags
      if t != '':
        toks.append(t) # new token
      try:
        if not skipthisdoc:
          parser.Parse(line) # parse possible XML in line
      except xml.parsers.expat.ExpatError as err:
        sys.stderr.write('{}: Exception while parsing XML: "{}" in the following line:\n{}\n'.format(xmlfile, str(err), line))
        # reset parser, set flag to skip remainder of this doc
        parser = xml.parsers.expat.ParserCreate(encoding='UTF-8')
        parser.StartElementHandler = start_element
        parser.EndElementHandler = end_element
        parser.Parse('<bigbang>') # dummy root tag
        skipthisdoc = True


# populate global map nlp
def read_lemmas(xmlfile):
  global nlp
  _docid = ''
  for line in open(xmlfile):
    line = line.rstrip()
    #print(line)
    if line.startswith('<doc id='): # new doc
      _docid = line[9:-2]
      nlp[_docid] = []
      continue
    if line == '<s>': # new sentence
      nlp[_docid].append([])
      continue
    if line.startswith('<LU '): # a token
      lemma = '#!LEMMA_UNKNOWN!#'
      m = re.match(r'<LU LEMMA="([^"]+)" .+<\/LU>', line)
      if m:
        lemma = m.group(1)
      nlp[_docid][-1].append(lemma)
      #print(lemma)


# Insert new record into dbtrendminer.fb_comments_annots
def db_insert_annot(page_id, post_id, comment_id, sid, start, end, txt, ltxt, tag):
  global dbcur, cnt
  if txt.startswith('http://'): # some exceptions
    return
  q = "INSERT IGNORE INTO fb_comments_annots (page_id, post_id, comment_id, sentence, start_tok, end_tok, text, text_lem, tag) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);"
  v = (page_id, post_id, comment_id, sid, start, end, txt, ltxt, tag)
  r = dbcur.execute(q, v)
  cnt += r


# Calculate scores based on annotations for current doc, and insert new record into .fb_comments_scores
# NOTE: THIS IS HEAVILY DEPENDENT ON SPECIFIC ANNOTATION TAGS!!!
def db_insert_scores(page_id, post_id, comment_id):
  global dbcur, nlp, docannots, cnt2
  ntoks = 0
  for sent in nlp.get(docid, []):
    ntoks += len(sent)
  sentiment = 0
  if ntoks > 0:
    sentiment = (docannots['VALENCIA#TYPE=POZ'] - docannots['VALENCIA#TYPE=NEG']) / ntoks
  #print(nlp.get(docid))
  valency_pos = docannots['VALENCIA#TYPE=POZ']
  valency_neg = docannots['VALENCIA#TYPE=NEG']
  rid_primary = docannots['E#TYPE=ELSODLEGESX']
  rid_secondary = docannots['E#TYPE=MASODLAGOSX']
  agency = 0
  agency_pos = docannots['AGENCY#TYPE=POSITIVE']
  agency_neg = docannots['AGENCY#TYPE=NEGATIVE']
  if ntoks > 0:
    agency = (agency_pos - agency_neg) / ntoks
  communion = 0
  communion_pos = docannots['COMMUNION#TYPE=POSITIVE']
  communion_neg = docannots['COMMUNION#TYPE=NEGATIVE']
  if ntoks > 0:
    communion = (communion_pos - communion_neg) / ntoks
  individualism = 0
  suff = docannots['SUFF']
  if suff > 0:
    individualism = docannots['PP'] / suff
  optimism1 = 0
  optimism2 = 0
  verb_past = docannots['VERB#TYPE=PAST']
  if verb_past > 0:
    optimism1 = docannots['VERB#TYPE=FUTURE'] / docannots['VERB#TYPE=PAST']
    optimism2 = docannots['VERB#TYPE=NO_PAST'] / docannots['VERB#TYPE=PAST']
  q = """INSERT IGNORE INTO fb_comments_scores (page_id, post_id, comment_id, ntoks, sentiment, valency_pos, valency_neg, rid_primary, rid_secondary, agency, agency_pos, agency_neg,
                     communion, communion_pos, communion_neg, individualism, optimism1, optimism2)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
  v = (page_id, post_id, comment_id, ntoks, sentiment, valency_pos, valency_neg, rid_primary, rid_secondary, agency, agency_pos, agency_neg, 
       communion, communion_pos, communion_neg, individualism, optimism1, optimism2)
  r = dbcur.execute(q, v)
  cnt2 += r


if __name__ == '__main__':


  if len(sys.argv) != 3:
    sys.exit('Usage: <xml.txt file> <xml file>')

  print('Connecting to DB...')
  db = pymysql.connect(host="localhost", user="trenduser", passwd="tR3Ndm11nR", db="dbtrendminer", charset="UTF8")
  dbcur = db.cursor()
  print('Done')

  read_lemmas(sys.argv[2])
  #print(nlp)
  
  parse_file(sys.argv[1])
  print('{0}: {1} annotation record(s) + {2} score records inserted'.format(sys.argv[1], cnt, cnt2))

