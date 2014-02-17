#!/usr/bin/env python
import sys, os, io
import argparse
import json
from collections import defaultdict
import operator

parser = argparse.ArgumentParser()
parser.add_argument('-t','--treebank_filename',help='treebank filename')
parser.add_argument('-o','--output_filename',help='deterministic mappings')
args = parser.parse_args()

coarse2fine = defaultdict(lambda: defaultdict(int))
fine2coarse = defaultdict(lambda: defaultdict(int))
for parse_line in io.open(args.treebank_filename, encoding='utf8'):
  splits = parse_line.split('\t')
  if len(splits) > 4:
    coarse, fine = splits[3], splits[4]
    if len(fine) == 0 or len(coarse) == 0:
      continue
    fine2coarse[fine][coarse] += 1
    coarse2fine[coarse][fine] += 1

output_file = io.open(args.output_filename, encoding='utf8', mode='w')
for fine in fine2coarse:
  print fine, [ (coarse, fine2coarse[fine][coarse]) for coarse in fine2coarse[fine].keys() ]
  coarse = max(fine2coarse[fine].iteritems(), key=operator.itemgetter(1))[0]
  output_file.write(u'{}\t{}\n'.format(fine, coarse))
output_file.close()

