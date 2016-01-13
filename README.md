trendminer-hutools
==================

This package contains tools (python) that were used to collect and process Hungarian data in the Trendminer project: 

1) tools to periodically download new and updated public posts and comments published on specific Facebook pages (`fbgraph.py` and `old_post-new_comment.py`)
2) a tool to convert NLP output files (from trendminer-hunlp) to NooJ input XML files (`tsv2noojxml.py`)
3) a tool to extract annotations from NooJ output files (`annots.py`)


Authors: Márton Miháltz <mmihaltz@gmail.com>, Iván Mittelholcz

##Installation

Run `pip install -r requirements.txt` (or something equivalent matching
 your permissions) to install the dependencies.

For using `fbgraph.py`, register on https://developers.facebook.com/ to 
get a client id (App ID) and client secret (App Secret). Provide these in
 `fbgraph.py` in lines 26-27:

```
	client_id = 'YOURCLIENTIDHERE'
	client_secret = 'YOURCLIENTSECRETHERE'
```

*Important: these scripts only work if you have have a Facebook application 
(developer identity) that uses v2.0 of the Facebook API. Unfortunately, 
if you register as a new developer and create a new application you will
start from the current version (v2.5 at this point) and will not be
able to use these scripts. Contact us if you need to use the script with
 API v2.5 and would like us to upgrade the script, or feel free to upgrade it 
 yourself and then please send us a pull request :)
 
##Usage

Please run `python fbgraph.py -h` for usage information.

The input file (`-i` option) is a csv file where the Fb page ids of 
the source pages to be harvested are the first values. Remaining columns 
and lines whose 1st columns are not integers will be ignored.

##About Trendminer Project: 
* http://www.trendminer-project.eu/ 
* http://www.nytud.hu/depts/corpus/trendminer.html
