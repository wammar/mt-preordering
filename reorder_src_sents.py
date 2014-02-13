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
argParser.add_argument('-s','--source_filename',
                       help='source text. one sentence per line.')
argParser.add_argument('-w', '--word_pair_order_filename', 
                       help='partial order between some source word pairs. one word pair per line, with four tab-separated fields: reverse, sent_id, first_word_zero_based_position, second_word_zero_based_position')
argParser.add_argument('-o', '--output_filename',
                       help='reordered source text. one sentence per line.')
args = argParser.parse_args()

parses_file=io.open(args.parses_filename, encoding='utf8')
src_file=io.open(args.source_filename, encoding='utf8')
word_pair_order_file=io.open(args.word_pair_order_filename, encoding='utf8')
output_file=io.open(args.output_filename, encoding='utf8', mode='w')
min_src_sent_length=5

parent2order=defaultdict(list)
word_pair_order = {}
def order_family(root_position):
  # identify family members
  unordered_members = list(parent2children[root_position])
  unordered_members.append(root_position)
  unordered_members.sort()
  while len(unordered_members) > 0:
    leftmost = -1
    for member in unordered_members:
      assert(leftmost < member)
      if leftmost == -1:
        leftmost = member
      elif (leftmost, member,) in word_pair_order and word_pair_order[ (leftmost, member,) ] == 1:
        leftmost = member
    # add/remove the member which was determined to be leftmost
    unordered_members.remove(leftmost)
    parent2order[root_position].append(leftmost)
  assert len(parent2order[root_position]) == len(parent2children[root_position]) + 1 and len(unordered_members) == 0

def postorder_traverse(root_position, visit_function):
  # base case
  if root_position not in parent2child:
    return
  # recurse
  for child_position in parent2children[root_position]:
    visit_function(child_position)
  # visit
  visit_function(root_position)

sent_id = -1
while True:
  sent_id += 1

  # read source sentence
  src_line = src_file.readline()
  src_tokens = src_line.strip().split(' ')

  # read all source word pairs partial reorderings for this sentence
  word_pair_order = {}
  while True:
    prev_line_starts_at=word_pair_order_file.tell()
    line = word_pair_order_file.readline()
    if not line: break
    splits = line.strip().split('\t')
    reverse, word_pair_sent_id, first_position, second_position = int(splits[0]), int(splits[1]), int(splits[2]), int(splits[3])
    if sent_id != word_pair_sent_id:
      word_pair_order_file.seek(prev_line_starts_at)
      break
    word_pair_order[(first_position, second_position,)] = reverse
    
  # reading sentence parse
  parent2children = defaultdict(list)
  child2parent = defaultdict(int)
  max_child_position = 0
  root = -1
  while True:
    conll_fields = parses_file.readline().strip().split('\t')
    if len(conll_fields) != 8: break
    child_position, child_string, whatever1, child_fine_pos, child_coarse_pos, whatever2, parent_position, dependency_relation = int(conll_fields[0])-1, conll_fields[1], conll_fields[2], conll_fields[3], conll_fields[4], conll_fields[5], int(conll_fields[6])-1, conll_fields[7]
    max_child_position = child_position
    if parent_position != -1:
      parent2children[parent_position].append(child_position)
      child2parent[child_position] = parent_position
    else:
      root = child_position
  assert root != -1
  assert len(child2parent) == len(src_tokens)-1

  # skip sentences which have fewer than 5 src words
  if max_child_position < min_src_sent_length-1:
    output_file.write(src_line)
    continue

  # now we do one postorder traversal of all nodes in the dependency tree. while visiting a node X, we determine a complete order for the members of the family rooted at X (i.e. X and its direct children), based on partial reorderings between pairs of those members.
  postorder_traverse(root, order_family)

  # then, we repeatedly replace every parent with a complete ordering of its family
  complete_order = [root]
  while len(complete_order) < len(src_tokens):
    for expandable in [parent for parent in complete_order if parent in parent2children]:
      explandable_index = complete_order.index(expandable)
      complete_order = complete_order[:expandable_index] + \
          parent2order[expandable_index] + \
          complete_order[expandable_index+1:]
      del parent2children[expandable]

  # we are done!
  for i in xrange(len(complete_order)):
    complete_order[i] = src_tokens[ complete_order[i] ]
  output_file.write(u'{}\n'.format(' '.join(complete_order)))

output_file.close()
