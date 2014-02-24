import re
import time
import io
import sys
import argparse
from collections import defaultdict

# parse/validate arguments
argParser = argparse.ArgumentParser()
argParser.add_argument("-ia", "--input_alignments_filename", 
                       help="Word alignments based on source preordered sentence.")
argParser.add_argument('-r','--reordered_indexes_filename',
                       help='"1 0 2 3" corresponds to a sentence of length four where the first two words were flipped.')
argParser.add_argument('-oa', '--output_alignments_filename',
                       help='Word alignments based on the original order of source sentences.')
args = argParser.parse_args()

input_alignments_file = open(args.input_alignments_filename)
output_alignments_file = open(args.output_alignments_filename, mode='w')
reordered_indexes_file = open(args.reordered_indexes_filename)

sent_id = -1
while True:

  sent_id += 1
  if sent_id % 1000 == 0:
    print 'processing sent_id ', sent_id

  input_alignments = input_alignments_file.readline()
  reordered_indexes = reordered_indexes_file.readline()

  if not input_alignments:
    break

  # read reorderings
  new_index_to_old_index = {}
  old_indexes = reordered_indexes.strip().split()
  new_index = -1
  for old_index in old_indexes:
    new_index += 1
    old_index = int(old_index)
    new_index_to_old_index[new_index] = old_index
  
  # read alignments
  links = input_alignments.strip().split()
  for i in xrange(len(links)):
    src, tgt = links[i].split('-')
    src = new_index_to_old_index[int(src)]
    links[i]='{}-{}'.format(src, tgt)
  output_alignments_file.write('{}\n'.format(' '.join(links)))

output_alignments_file.close()
input_alignments_file.close()
reordered_indexes_file.close()
