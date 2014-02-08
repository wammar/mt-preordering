import re
import time
import io
import sys
import argparse
from collections import defaultdict

# parse/validate arguments
argParser = argparse.ArgumentParser()
argParser.add_argument("-p", "--parses_filename", 
                       help="CoNLL formatted dependency parses of source side sentences of the parallel corpus.")
argParser.add_argument("-a", "--align_filename", 
                       help="Source-Target word alignments of the parallel corpus. One sentence pair per line.")
argParser.add_argument("-o", "--output_filename",
                       help="Output pairwise preordering training data.")
args = argParser.parse_args()

parses_file=io.open(args.parses_filename, encoding='utf8')
align_file=io.open(args.align_filename)
output_file=io.open(args.output_filename, mode='w')

sent_id = -1
for sent_align in align_file:
  sent_id += 1
  print 'reading alignments in sent_id = ', sent_id
  src_tgt_pairs = sent_align.split()
  src2tgt_alignments, tgt2src_alignments = defaultdict(set), defaultdict(set)
  for i in xrange(len(src_tgt_pairs)):
    src_position, tgt_position = src_tgt_pairs[i].split('-')
    src2tgt_alignments[int(src_position)].add(int(tgt_position))
    tgt2src_alignments[int(tgt_position)].add(int(src_position))
  print 'reading dependency parse in sent_id = ', sent_id
  src_family_word_pairs=[]
  parent_children_map=defaultdict(list)
  while True:
    conll_fields = parses_file.readline().strip().split(' ')
    if len(conll_fields) == 0: break
    child_position, child_string, whatever1, child_fine_pos, 
    child_coarse_pos, whatever2, parent_position, dependency_relation = 
    int(conll_fields[0])-1, conll_fields[1], conll_fields[2], conll_fields[3],
    conll_fields[4], conll_fields[5], int(conll_fields[6])-1, conll_fields[7]
    parent_children_map[parent_position].append(child_position)
    # add parent-child word pair to the family
    src_family_word_pairs.append( tuple( min(child_position, parent_position), 
                                         max(child_position, parent_position) ) )
  for parent_position in parent_children_map.keys():
    for i in xrange(len(parent_children_map[parent_position])-1):
      for j in range(i+1, len(parent_children_map[parent_position])):
        # add child-child word pair to the family
        src_family_word_pairs.append( tuple( parent_children_map[parent_position][i],
                                             parent_children_map[parent_position][j] ) )
  # now that we captured all src word pairs that belong to the same family according to the depparse, 
  # it's time to find out how they should be reordered, based on word alignments to the target side
  for src_word_pair in src_family_word_pairs:
    assert( src_word_pair[0] < src_word_pair[1] )
    # first, skip the pairs where one of the source words don't align to anything in the target
    if len(src2tgt_alignments[src_word_pair[0]]) == 0 or len(src2tgt_alignments[src_word_pair[0]]) == 0: continue
    # then, determine whether all mappings of the first src word are strictly smaller than the mappings of the second src word
    monotonic = max(src2tgt_alignments[src_word_pair[0]]) < min(src2tgt_alignments[src_word_pair[1]])
    # then, determine whether all mappings of the first src word are strictly larger than the mappings of the second src word
    reversed = min(src2tgt_alignments[src_word_pair[0]]) > max(src2tgt_alignments[src_word_pair[1]])
    # if the word alignments don't induce a monotonic reordering, and don't induce a reversed reordering, skip this pair
    if not monotonic and not reversed: continue
    
    # now, it's time to write this word pair and its word-alignment-induced reordering to the output file
    output_file.write('{}{}{}{}\n'.format(reversed, sent_id, src_word_pair[0], src_word_pair[1]))

output_file.close()
