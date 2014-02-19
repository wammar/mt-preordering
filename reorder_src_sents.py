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
argParser.add_argument('-oi', '--reordered_indexes_filename',
                       help='reordered indexes of tokens in a source sentence. one sentence per line.')
args = argParser.parse_args()

parses_file=io.open(args.parses_filename, encoding='utf8')
src_file=io.open(args.source_filename, encoding='utf8')
word_pair_order_file=io.open(args.word_pair_order_filename, encoding='utf8')
output_file=io.open(args.output_filename, encoding='utf8', mode='w')
reordered_indexes_file = io.open(args.reordered_indexes_filename, encoding='utf8', mode='w')
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
  if root_position not in parent2children:
    return
  # recurse
  for child_position in parent2children[root_position]:
    postorder_traverse(child_position, visit_function)
  # visit
  visit_function(root_position)

sent_id = -1
sent_ids_with_multiple_roots = []
sent_ids_with_bad_parses = []
while True:
  sent_id += 1
  if sent_id % 1000 == 0:
    #print '==========================='
    print 'processing sent_id', sent_id

  # read source sentence
  src_line = src_file.readline()
  if not src_line:
    break
  src_tokens = src_line.strip().split(' ')
  #print src_tokens
  
  # read all source word pairs partial reorderings for this sentence
  word_pair_order = {}
  while True:
    prev_line_starts_at = word_pair_order_file.tell()
    line = word_pair_order_file.readline()
    if not line: break
    splits = line.strip().split('\t')
    reverse, word_pair_sent_id, first_position, second_position = int(splits[0]), int(splits[1]), int(splits[2]), int(splits[3])
    if sent_id != word_pair_sent_id:
      word_pair_order_file.seek(prev_line_starts_at)
      break
    #print sent_id, 'reverse[', first_position,', ',second_position,']=',reverse
    word_pair_order[(first_position, second_position,)] = reverse
      
  # reading sentence parse
  parent2children = defaultdict(list)
  child2parent = defaultdict(int)
  max_child_position = 0
  root = -1
  several_roots = False
  while True:
    conll_fields = parses_file.readline().strip().split('\t')
    if len(conll_fields) != 8: break
    child_position, child_string, whatever1, child_fine_pos, child_coarse_pos, whatever2, parent_position, dependency_relation = int(conll_fields[0])-1, conll_fields[1], conll_fields[2], conll_fields[3], conll_fields[4], conll_fields[5], int(conll_fields[6])-1, conll_fields[7]
    max_child_position = child_position
    if parent_position != -1:
      parent2children[parent_position].append(child_position)
      child2parent[child_position] = parent_position
    else:
      if root == -1:
        root = child_position
      else:
        several_roots = True
        parent2children[root].append(child_position)
        child2parent[child_position] = root
    
  if several_roots:
    sent_ids_with_multiple_roots.append(sent_id)
    reordered_indexes_file.write(u'{}\n'.format(' '.join( [str(i) for i in xrange(len(src_tokens))])))
    output_file.write(src_line)
    continue

  # skip weird parses
  if len(child2parent) != len(src_tokens)-1 or root == -1:
    sent_ids_with_bad_parses.append(sent_id)
    reordered_indexes_file.write(u'{}\n'.format(' '.join( [str(i) for i in xrange(len(src_tokens))])))
    output_file.write(src_line)
    continue
  
  # skip sentences which have fewer than 5 src words
  if len(src_tokens) < min_src_sent_length:
    reordered_indexes_file.write(u'{}\n'.format(' '.join( [str(i) for i in xrange(len(src_tokens))])))
    output_file.write(src_line)
    continue

  #print 'word_pair_order = ', word_pair_order
  # skip sentences which don't have any flips
  if len( [word_pair for word_pair in word_pair_order.keys() if word_pair_order[word_pair] ] ) == 0:
    reordered_indexes_file.write(u'{}\n'.format(' '.join( [str(i) for i in xrange(len(src_tokens))])))
    output_file.write(src_line)
    continue

  # now we do one postorder traversal of all nodes in the dependency tree. while visiting a node X, we determine a complete order for the members of the family rooted at X (i.e. X and its direct children), based on partial reorderings between pairs of those members.
  parent2order=defaultdict(list)
  postorder_traverse(root, order_family)
  #print 'parent2order=',parent2order
  
  # then, we repeatedly replace every parent with a complete ordering of its family
  complete_order = [root]
  while len(complete_order) < len(src_tokens):
    #print 'complete_order=',complete_order
    #print 'len(complete_order) = ', len(complete_order)
    expandables = [parent for parent in complete_order if parent in parent2children]
    #print 'expandables = ', expandables
    for expandable in expandables:
      expandable_index = complete_order.index(expandable)
      #print 'now expanding the parent ', expandable, ' which has index ', expandable_index, ' in compete_order list'
      #print 'will replace it with parent2order[',expandable,'] = ', parent2order[expandable]
      #print 'note that parent2order = ', parent2order
      complete_order = complete_order[:expandable_index] + parent2order[expandable] + complete_order[expandable_index+1:]
      #print 'now complete_order = ', complete_order
      del parent2children[expandable]

  # we are done!
  #print complete_order
  # write the reordered indexes to file
  reordered_indexes_file.write(u'{}\n'.format(' '.join( [str(position) for position in complete_order] )))
  # replace each index with the actual source word
  for i in xrange(len(complete_order)):
    complete_order[i] = src_tokens[ complete_order[i] ]
  # write the reordered tokens to another file
  output_file.write(u'{}\n'.format(' '.join(complete_order)))

reordered_indexes_file.close()
output_file.close()

print len(sent_ids_with_multiple_roots), 'sent_ids_with_multiple_roots = '
print ' '.join( [str(sent_id) for sent_id in sent_ids_with_multiple_roots] )
print 
print len(sent_ids_with_bad_parses), 'sent_ids_with_bad_parses = '
print ' '.join( [str(sent_id) for sent_id in sent_ids_with_bad_parses] )
print
