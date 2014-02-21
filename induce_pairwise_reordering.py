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
argParser.add_argument("-ir", "--induced_reorderings_filename",
                       help="Word pairs and their reordering as induced from word alignments. These are high quality reordering decisions later used to train a classifier.")
argParser.add_argument("-ii", "--induce_inconsistent_reorderings", action="store_true", 
                       help="Train the reordering classifier with three labels instead of two: monotonic, reverse, and inconsistent")
argParser.add_argument("-pr", "--potential_reorderings_filename",
                       help="All potential word pairs which are candidates for reordering, according to a dependency parse. If word alignments are provided, the label reflects the induced alignment, otherwise the label is zero.")
argParser.add_argument("-ml", "--minimum_sent_length", default=5, type=int, 
                       help="The minimum length of a sentence so that it qualifies for extraction of training examples for the reordering classifier.")
args = argParser.parse_args()

# constructs the yield of a node in the dependency tree as the union of the node itself
# and the yields of its direct children (i.e. must be applied bottom up)
def construct_yield(root_position, parent2children, parent2yield):
  for child in parent2children[root_position]:
    assert len(parent2yield[root_position] & parent2yield[child]) == 0
    parent2yield[root_position].update(  parent2yield[child]  )

# postorder traversal of the depenency tree
def postorder_traverse(root_position, visit_function, parent2children, parent2yield):
  parent2yield[root_position].add(root_position)
  # base case
  if root_position not in parent2children:
    return
  # recurse
  for child_position in parent2children[root_position]:
    postorder_traverse(child_position, visit_function, parent2children, parent2yield)
  # visit
  visit_function(root_position, parent2children, parent2yield)

# returns true if this sentence should be used to extract examples to train the reordering classifiers
# returns false otherwise.
def good_for_training(tokens, root):
  if len(tokens) < args.minimum_sent_length:
    return False
  if tokens[-1].isalpha() or tokens[-1] == ',':
    return False
  return True

# reads one line from the alignments file and populates  
# src2tgt_alignments and tgt2src_alignments which are defaultdict(set). 
# the return value indicates whether this is the last line of the alignments file
def read_word_alignments(align_file, src2tgt_alignments, tgt2src_alignments):
  if not align_file:
    return True
  sent_align = align_file.readline()
  if not sent_align:
    return False
  src_tgt_pairs = sent_align.split()
  for i in xrange(len(src_tgt_pairs)):
    src_position, tgt_position = src_tgt_pairs[i].split('-')
    src2tgt_alignments[int(src_position)].add(int(tgt_position))
    tgt2src_alignments[int(tgt_position)].add(int(src_position))
  return True

# reads one sentence from the conll-formatted depdency parses, 
# populates parent_children_map (a defaultdict(list) ) 
def read_parse(parse_file, parent_children_map, tokens):
  while True:
    line = parses_file.readline()
    if not line: 
      return False
    conll_fields = line.strip().split('\t')
    if len(conll_fields) != 8: 
      assert len(conll_fields) == 1
      break
    child_position, child_string, whatever1, child_fine_pos, child_coarse_pos, whatever2, parent_position, dependency_relation = (int(conll_fields[0])-1, conll_fields[1], conll_fields[2], conll_fields[3], conll_fields[4], conll_fields[5], int(conll_fields[6])-1, conll_fields[7])
    tokens.append(child_string)
    parent_children_map[parent_position].append(child_position)
  return True

# input files
parses_file=io.open(args.parses_filename, encoding='utf8')
align_file = io.open(args.align_filename) if args.align_filename else None

# output files
induced_reorderings_file=io.open(args.induced_reorderings_filename, mode='w')
potential_reorderings_file=io.open(args.potential_reorderings_filename, mode='w')

sent_id = -1
while True:
  sent_id += 1

  # reading word alignment
  src2tgt_alignments, tgt2src_alignments = defaultdict(set), defaultdict(set)
  if not read_word_alignments(align_file, src2tgt_alignments, tgt2src_alignments):
    break

  # reading parse
  parent_children_map, tokens = defaultdict(list), []
  if not read_parse(parses_file, parent_children_map, tokens):
    break
  assert len(parent_children_map) > 0
  assert len(parent_children_map[-1]) == 1
  root = parent_children_map[-1][0]

  # construct list of word pairs which belong to the same family   
  src_family_word_pairs = []
  for parent_position in parent_children_map.keys():
    for i in xrange(len(parent_children_map[parent_position])-1):
      # add parent-child word pair to the family
      src_family_word_pairs.append( ( min(parent_children_map[parent_position][i], parent_position), 
                                      max(parent_children_map[parent_position][i], parent_position),) )
      for j in range(i+1, len(parent_children_map[parent_position])):
        # add child-child word pair to the family
        src_family_word_pairs.append( ( parent_children_map[parent_position][i],
                                        parent_children_map[parent_position][j],) )

  # find the yield of each parent
  parent_yield_map = defaultdict(set)
  postorder_traverse(root, construct_yield, parent_children_map, parent_yield_map)

  # find the target alignments for each yield
  yield2tgt_alignments = defaultdict(set)
  for parent in parent_yield_map.keys():
    for node in parent_yield_map[parent]:
      yield2tgt_alignments[parent].update( src2tgt_alignments[node] )

  # is this sentence good for training the reordering classifier?
  good_sent = good_for_training(tokens, root)
  
  # now that we captured all src word pairs that belong to the same family according to the depparse, 
  # it's time to find out how they should be reordered, based on word alignments to the target side
  for src_word_pair in src_family_word_pairs:
    a, b = src_word_pair[0], src_word_pair[1]
    assert( a < b )
    
    # determine whether all mappings of the first src word are strictly smaller than the mappings 
    # of the second src word. Unlike (Lerner and Petrov, 2013), we use the union of alignments of a child's yield
    # to determine alignments
    a_alignments = yield2tgt_alignments[a] if b not in parent_children_map[a] else src2tgt_alignments[a]
    b_alignments = yield2tgt_alignments[b] if a not in parent_children_map[b] else src2tgt_alignments[b]
    monotonic = len(src2tgt_alignments[a]) > 0 and len(src2tgt_alignments[b]) > 0 and \
        max(a_alignments) < min(b_alignments)
    # determine whether all mappings of the first src word are strictly larger than the mappings of the second src word
    reverse = len(src2tgt_alignments[a]) > 0 and len(src2tgt_alignments[b]) > 0 and \
        min(a_alignments) > max(b_alignments)

    # there are three possible cases
    if monotonic and not reverse:
      if good_sent:
        induced_reorderings_file.write(u'{}\t{}\t{}\t{}\n'.format(0, sent_id, a, b))
      potential_reorderings_file.write(u'{}\t{}\t{}\t{}\n'.format(0, sent_id, a, b))
    elif not monotonic and reverse:
      if good_sent: 
        induced_reorderings_file.write(u'{}\t{}\t{}\t{}\n'.format(1, sent_id, a, b))
      potential_reorderings_file.write(u'{}\t{}\t{}\t{}\n'.format(1, sent_id, a, b))
    elif not monotonic and not reverse:
      if good_sent and args.induce_inconsistent_reorderings:
        induced_reorderings_file.write(u'{}\t{}\t{}\t{}\n'.format(2, sent_id, a, b))
      potential_reorderings_file.write(u'{}\t{}\t{}\t{}\n'.format(2, sent_id, a, b))
    else:
      assert False

induced_reorderings_file.close()
potential_reorderings_file.close()
