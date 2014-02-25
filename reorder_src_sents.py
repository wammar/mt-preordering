import re
import time
import io
import sys
import argparse
from collections import defaultdict
from multiprocessing import Process, Queue
import os

# given a parent, and a direction (left xor right), reorders the direct children at that direction with respect to each other. 
# reordering is communicated via parent2order.
def order_siblings_on_one_side(parent, parent2children, parent2order, word_pair_label, left=False, right=False):
  assert left or right
  assert not (left and right)
  if left:
    unordered_members = list( parent2order[parent][0:parent2order[parent].index(parent)] )
  else:
    unordered_members = list( parent2order[parent][parent2order[parent].index(parent)+1:] )
  assert sorted(unordered_members) == unordered_members

  ordered_members = []
  while len(unordered_members) > 0:
    leftmost = -1
    for member in unordered_members:
      assert(leftmost < member)
      if leftmost == -1:
        leftmost = member
      elif (leftmost, member,) in word_pair_label and word_pair_label[ (leftmost, member,) ] == 1:
        leftmost = member
    # add/remove the member which was determined to be leftmost
    unordered_members.remove(leftmost)
    ordered_members.append(leftmost)

  if left:
    parent2order[parent][0:parent2order[parent].index(parent)] = ordered_members
  else:
    parent2order[parent][parent2order[parent].index(parent)+1:] = ordered_members
  assert len(parent2order[parent]) == len(parent2children[parent]) + 1 and len(unordered_members) == 0

def order_family(root_position, parent2children, parent2order, word_pair_label):
  # first, sort children with respect to their parent
  for child in parent2children[root_position]:
    pair = (child, root_position,)
    ordered_pair = (min([child,root_position]), max([child,root_position]),) 
    if ordered_pair not in word_pair_label and child < root_position or\
          ordered_pair in word_pair_label and child < root_position and word_pair_label[ordered_pair] != 1 or \
          ordered_pair in word_pair_label and child > root_position and word_pair_label[ordered_pair] == 1:
      parent2order[root_position].append(child)
  parent2order[root_position].append(root_position)
  for child in parent2children[root_position]:
    if child not in parent2order[root_position]:
      parent2order[root_position].append(child)

  # if that's all you wanted, return  
  if args.parent_child_only:
    return

  # now, order each side independently
  order_siblings_on_one_side(root_position, parent2children, parent2order, word_pair_label, left=True)
  order_siblings_on_one_side(root_position, parent2children, parent2order, word_pair_label, right=True)

def postorder_traverse(root_position, visit_function, parent2children, parent2order, word_pair_label):
  # base case
  if root_position not in parent2children:
    return
  # recurse
  for child_position in parent2children[root_position]:
    postorder_traverse(child_position, visit_function, parent2children, parent2order, word_pair_label)
  # visit
  visit_function(root_position, parent2children, parent2order, word_pair_label)

# keeps receiving workloads via in_queue and sending output via out_queue, until a workload = None is encountered
def process_target(in_queue, out_queue):
  print 'i\'m PID=', os.getpid()
  sents_counter = -1
  while True:
    sents_counter += 1
    if sents_counter % 1000 == 0:
      print 'pid', os.getpid(), ' reordered ', sents_counter ' sentences'
    # receive next workload
    workload = in_queue.get()
    # stop signal
    if workload == 'stop':
      sys.stdout.write('in_queue.get()')
      break
    # grasp workload
    (sent_id, root, order_family, word_pair_label, src_tokens, parent2children,) = workload
    #print 'proc ', os.getpid(), ' will reorder sent_id ', sent_id 
    # to determine a complete reorder, we do one postorder traversal of all nodes in the dependency tree. while visiting a node X, 
    # we determine a complete order for the members of the family rooted at X (i.e. X and its direct children), 
    # based on partial reorderings between pairs of those members.
    parent2order=defaultdict(list)
    postorder_traverse(root, order_family, parent2children, parent2order, word_pair_label)  
    # then, we repeatedly replace every parent with a complete ordering of its family
    complete_order = [root]
    while len(complete_order) < len(src_tokens):
      expandables = [parent for parent in complete_order if parent in parent2children]
      for expandable in expandables:
        expandable_index = complete_order.index(expandable)
        complete_order = complete_order[:expandable_index] + parent2order[expandable] + complete_order[expandable_index+1:]
        del parent2children[expandable]
    # communicate the result
    out_queue.put( (sent_id, complete_order,) )
    #print 'proc ', os.getpid(), ' done reordering sent_id ', sent_id 
    
if __name__ == "__main__":
  # parse/validate arguments
  argParser = argparse.ArgumentParser()
  argParser.add_argument("-p", "--parses_filename", required=True, 
                         help="CoNLL formatted dependency parses of source side sentences of the parallel corpus.")
  argParser.add_argument('-s','--source_filename', required=True,
                         help='source text. one sentence per line.')
  argParser.add_argument('-w', '--word_pair_order_filename', required=True,
                         help='partial order between some source word pairs. one word pair per line, with four tab-separated fields: reverse, sent_id, first_word_zero_based_position, second_word_zero_based_position')
  argParser.add_argument('-o', '--output_filename', required=True,
                         help='reordered source text. one sentence per line.')
  argParser.add_argument('-oi', '--reordered_indexes_filename', required=True,
                         help='reordered indexes of tokens in a source sentence. one sentence per line.')
  argParser.add_argument('--parent_child_only', action='store_true', 
                         help='if specified, only reorder child-parent word pairs. right siblings and left siblings each maintain their original order')
  argParser.add_argument('-np', '--processes', default=1, type=int,
                         help='if specified, only reorder child-parent word pairs. right siblings and left siblings each maintain their original order')
  args = argParser.parse_args()

  print 'creating a pool of ', args.processes, ' processes'
  procs = []
  out_queue = Queue()
  in_queue = Queue()
  for proc in xrange(args.processes):
    new_process = Process(target = process_target, args = (in_queue, out_queue,))
    new_process.start()
    procs.append(new_process)

  parses_file=io.open(args.parses_filename, encoding='utf8')
  src_file=io.open(args.source_filename, encoding='utf8')
  word_pair_order_file=io.open(args.word_pair_order_filename, encoding='utf8')
  min_src_sent_length=5

  parent2order=defaultdict(list)
  word_pair_label = {}
  
  sent_id = -1
  sent_ids_with_multiple_roots = []
  sent_ids_with_bad_parses = []
  sent_id_to_process = {}
  sent_id_to_complete_order = {}
  buffered_word_pair_line = None
  while True:
    sent_id += 1

    if sent_id % 1000 == 0:
      print 'extracting workload of sent_id', sent_id

    # read source sentence
    src_line = src_file.readline()
    if not src_line:
      break
    src_tokens = src_line.strip().split(' ')
    #print src_tokens

    # read all source word pairs partial reorderings for this sentence
    word_pair_label = {}
    while True:
      #prev_line_starts_at = word_pair_order_file.tell()
      if buffered_word_pair_line:
        line = buffered_word_pair_line
        buffered_word_pair_line = None
      else:
        line = word_pair_order_file.readline()
      if not line: break
      splits = line.strip().split('\t')
      label, word_pair_sent_id, first_position, second_position = int(splits[0]), int(splits[1]), int(splits[2]), int(splits[3])
      if sent_id != word_pair_sent_id:
        buffered_word_pair_line = line
        #word_pair_order_file.seek(prev_line_starts_at)
        break
      #print sent_id, 'label[', first_position,', ',second_position,']=',label
      word_pair_label[(first_position, second_position,)] = label

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
      sent_id_to_complete_order[sent_id] = [i for i in xrange(len(src_tokens))]
      continue

    # skip weird parses
    if len(child2parent) != len(src_tokens)-1 or root == -1:
      sent_ids_with_bad_parses.append(sent_id)
      sent_id_to_complete_order[sent_id] = [i for i in xrange(len(src_tokens))]
      continue

    # skip sentences which have fewer than 5 src words
    if len(src_tokens) < min_src_sent_length:
      sent_id_to_complete_order[sent_id] = [i for i in xrange(len(src_tokens))]
      continue

    if len( [word_pair for word_pair in word_pair_label.keys() if word_pair_label[word_pair] == 1 ] ) == 0:
      sent_id_to_complete_order[sent_id] = [i for i in xrange(len(src_tokens))]
      continue

    # add this workload
    in_queue.put((sent_id, root, order_family, word_pair_label, src_tokens, parent2children,))

  # send stop signal
  print 'master finished putting all workloads in in_queue. waiting for slaves to do the actual reordering.'
  for proc in procs:
    in_queue.put('stop')

  # close all input files
  src_file.close()
  parses_file.close()
  word_pair_order_file.close()

  # reorganize the output in a dictionary
  print 'reorganizing results'
  sents_count = sent_id
  while len(sent_id_to_complete_order) < sents_count:
    (sent_id, complete_order,) = out_queue.get()
    sent_id_to_complete_order[sent_id] = complete_order

  print 'all slaves finished their workloads!'

  # sync
  for proc in procs:
    proc.join()

  print 'master & slaves united'

  # done with all sentences! time to persist results
  print 'persisting results'
  src_file = io.open(args.source_filename, encoding='utf8')
  output_file=io.open(args.output_filename, encoding='utf8', mode='w')
  reordered_indexes_file = io.open(args.reordered_indexes_filename, encoding='utf8', mode='w')
  for sent_id in xrange( len(sent_id_to_complete_order) ):
    complete_order = sent_id_to_complete_order[sent_id]
    # write the reordered indexes to file
    reordered_indexes_file.write(u'{}\n'.format(' '.join( [str(position) for position in complete_order] )))
    # replace each index with the actual source word
    src_tokens = src_file.readline().strip().split(' ')
    for i in xrange(len(complete_order)):
      complete_order[i] = src_tokens[ complete_order[i] ]
    # write the reordered tokens to another file
    output_file.write(u'{}\n'.format(' '.join(complete_order)))
  # close input/output files
  src_file.close()
  reordered_indexes_file.close()
  output_file.close()

  print len(sent_ids_with_multiple_roots), 'sent_ids_with_multiple_roots = '
  print ' '.join( [str(sent_id) for sent_id in sent_ids_with_multiple_roots] )
  print 
  print len(sent_ids_with_bad_parses), 'sent_ids_with_bad_parses = '
  print ' '.join( [str(sent_id) for sent_id in sent_ids_with_bad_parses] )
  print

  
