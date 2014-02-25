#!/usr/bin/env python
import sys, io
import os
from itertools import izip
import subprocess as sp
import multiprocessing as mp
import argparse

MODEL = '/home/eschling/tools/TurboParser-2.1.0/models/hindi_parser_full.model'
PARSER = '/home/eschling/tools/TurboParser-2.1.0'
os.environ['LD_LIBRARY_PATH'] = '/home/eschling/tools/TurboParser-2.1.0/deps/local/lib'

parser = None
pos_map = dict()
lemma_map = dict()
unknown_tags = 0
def start_parser(model=MODEL,parser_loc=PARSER, coarse='', lemma_filename=''):
    global lemma_map
    global pos_map
    global parser
    parser = sp.Popen([parser_loc+'/TurboParser', '--test', '--file_model='+model,
        '--file_test=/dev/stdin', '--file_prediction=/dev/stdout'],
        stdin=sp.PIPE, stdout=sp.PIPE)

    # use coarse pos tag when available
    if coarse:
      fine2coarse = open(coarse)
      for line in fine2coarse:
        fine_pos, coarse_pos = line.strip().split('\t')
        pos_map[fine_pos] = coarse_pos 
    
    # use lemmas when available
    if lemma_filename:
      lemma_file = open(lemma)
      for line in lemma_file:
        splits = line.strip().split('\t')
        if len(splits) != 2:
          sys.stderr.write('warning: strange line found in '+ lemma +':\n'+ line)
          continue
        token, lemma = splits
        lemma_map[token] = lemma

def parse(line):
    global parser
    global pos_map
    global unknown_tags
    global lemma_map
    sentence, tagged = line[:-1].split(' ||| ')
    words = sentence.split()
    tags = tagged.split()
    assert len(words) == len(tags)
    for i, (word, tag) in enumerate(izip(words, tags), 1):
        stag = '_'
        if len(pos_map)==0:
          stag = tag if tag in ('PRP', 'PRP$') else tag[:2]
        elif tag in pos_map:
          stag = pos_map[tag]
        else:
          unknown_tags += 1
          #sys.stderr.write('{} does not have coarse mapping'.format(tag)) 
        lemma = lemma_map[word] if word in lemma_map else word
        parser.stdin.write('{}\t{}\t{}\t{}\t{}\t_\t_\t_\n'.format(i, word, lemma, stag, tag))
    parser.stdin.write('\n')
    parser.stdin.flush()
    parse = []
    conll = ''
    line = parser.stdout.readline()
    while line != '\n':
        _, _, _, _, _, _, head, mod = line.split()
        parse.append((head, mod))
        conll += line
        line = parser.stdout.readline()
    assert len(parse) == len(words)
    parsed = ' '.join('{}-{}'.format(head, mod) for head, mod in parse)
    return sentence, tagged, parsed, conll

def main():
    arg_parser = argparse.ArgumentParser(description='Parse tagged sentences using TurboParser')
    arg_parser.add_argument('-j', '--jobs', type=int, default=1,
            help='number of instances of the parser to start')
    arg_parser.add_argument('-c', '--chunk', type=int, default=100,
            help='data chunk size')
    arg_parser.add_argument('-t','--turbo', help='turboparser location')
    arg_parser.add_argument('-m','--model',help='TurboParser model to use', required=False)
    arg_parser.add_argument('--coarse',help='fine to coarse POS tag mapping to use',required=False)
    arg_parser.add_argument('--lemma',help='token to lemma mapping',required=False)
    args = arg_parser.parse_args()

    pool = mp.Pool(processes=args.jobs, initializer=start_parser(model=args.model,parser_loc=args.turbo, coarse=args.coarse, lemma=args.lemma))

    for fields in pool.imap(parse, sys.stdin, chunksize=args.chunk):
        if len(fields) != 4:
            print fields
        sentence, tagged, parsed, conll  = fields
        #print('{} ||| {} ||| {}'.format(sentence, tagged, parsed))
        print(conll)
    sys.stderr.write('{} tags without fine to coarse mappings'.format(unknown_tags))
        
if __name__ == '__main__':
    main()
