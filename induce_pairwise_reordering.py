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
argParser.add_argument('-t', '--test', action='store_true',
                       help='Find all reorderings potentially needed at test time. No alignments file needed. the responses column in output is always 0.')

args = argParser.parse_args()

parses_file=io.open(args.parses_filename, encoding='utf8')
if args.test: align_file = None
else: align_file=io.open(args.align_filename)

output_file=io.open(args.output_filename, mode='w')
min_src_sent_length=5

sent_id = -1
conll_line = -1
while True:
  sent_id += 1
  # reading word alignment
  if not args.test:
    sent_align = align_file.readline()
    if not sent_align:
      break
    max_src_position = 0
    src_tgt_pairs = sent_align.split()
    src2tgt_alignments, tgt2src_alignments = defaultdict(set), defaultdict(set)
    for i in xrange(len(src_tgt_pairs)):
      src_position, tgt_position = src_tgt_pairs[i].split('-')
      src2tgt_alignments[int(src_position)].add(int(tgt_position))
      tgt2src_alignments[int(tgt_position)].add(int(src_position))
      max_src_position = max(max_src_position, int(src_position))

  # reading parse
  src_family_word_pairs=[]
  parent_children_map=defaultdict(list)

  max_child_position = 0
  length_of_pcm=0
  end_of_file = False
  while True:
    conll_line += 1
    line = parses_file.readline()
    if not line: 
      end_of_file = True
      break
    conll_fields = line.strip().split('\t')
    if len(conll_fields) != 8: 
      length_of_pcm += 0.5
      break
    length_of_pcm += 1
    child_position, child_string, whatever1, child_fine_pos, child_coarse_pos, whatever2, parent_position, dependency_relation = int(conll_fields[0])-1, conll_fields[1], conll_fields[2], conll_fields[3], conll_fields[4], conll_fields[5], int(conll_fields[6])-1, conll_fields[7]
    max_child_position = child_position
    parent_children_map[parent_position].append(child_position)
    # add parent-child word pair to the family, unless this is root
    if parent_position == -1: continue
    src_family_word_pairs.append( ( min(child_position, parent_position), 
                                    max(child_position, parent_position),) )
  
  if end_of_file:
    break

  if len(parent_children_map) == 0:
    print 'conll_line=',conll_line
    print 'length_of_pcm=',length_of_pcm
    print 'len(conll_fields)=',len(conll_fields)
    print 'sent_id = ', sent_id
    print 'parent_child_map',parent_children_map

  assert len(parent_children_map) > 0
  for parent_position in parent_children_map.keys():
    for i in xrange(len(parent_children_map[parent_position])-1):
      for j in range(i+1, len(parent_children_map[parent_position])):
        # add child-child word pair to the family
        src_family_word_pairs.append( ( parent_children_map[parent_position][i],
                                        parent_children_map[parent_position][j],) )

  # skip sentences which have different number of src words according to word alignment vs. dependency parses
  if not args.test and max_child_position > max_src_position:
    continue

  # skip sentences which have fewer than 5 src words
  if max_child_position < min_src_sent_length-1:
    continue

  # now that we captured all src word pairs that belong to the same family according to the depparse, 
  # it's time to find out how they should be reordered, based on word alignments to the target side
  for src_word_pair in src_family_word_pairs:
    assert( src_word_pair[0] < src_word_pair[1] )
    if args.test:
      reversed = 0
    else:
      # first, skip the pairs where one of the source words don't align to anything in the target
      if len(src2tgt_alignments[src_word_pair[0]]) == 0 or \
            len(src2tgt_alignments[src_word_pair[1]]) == 0:
        continue
      # then, determine whether all mappings of the first src word are strictly smaller than the mappings of the second src word
      monotonic = max(src2tgt_alignments[src_word_pair[0]]) < min(src2tgt_alignments[src_word_pair[1]])
      # then, determine whether all mappings of the first src word are strictly larger than the mappings of the second src word
      reversed = min(src2tgt_alignments[src_word_pair[0]]) > max(src2tgt_alignments[src_word_pair[1]])
      # if the word alignments don't induce a monotonic reordering, and don't induce a reversed reordering, skip this pair
      if not monotonic and not reversed: continue
    
      if reversed: reversed = 1
      else: reversed = 0

    # now, it's time to write this word pair and its word-alignment-induced reordering (if available) to the output file
    output_file.write(u'{}\t{}\t{}\t{}\n'.format(reversed, sent_id, src_word_pair[0], src_word_pair[1]))

output_file.close()
