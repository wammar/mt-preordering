import re
import time
import io
import sys
import argparse
from collections import defaultdict

# parse/validate arguments
argParser = argparse.ArgumentParser()
argParser.add_argument("-n", "--nonprojective_filename", 
                       help="CoNLL formatted dependency parses which may be nonprojective.")
argParser.add_argument("-p", "--projective_filename", 
                       help="(output) CoNLL formatted projectivized dependency parses, using the algorithm in Pseudo-Projective Dependency Parsing (Nivre and Nilsson, 2005).")
args = argParser.parse_args()

nonprojective_file = io.open(args.nonprojective_filename, encoding='utf8')
projective_file = io.open(args.projective_filename, encoding='utf8', mode='w')

def get_nonprojective_arc(gap_to_arcs, child_parent_map):
  old_arcs = set()
  shortest_bad_arc = None
  for gap in sorted(gap_to_arcs.keys()):
    for new_arc in gap_to_arcs[gap]:
      new_child, new_parent = new_arc
      for (old_child, old_parent,) in old_arcs:
        # where is old child and old parent w.r.t new arc
        inside, outside, neutral = 0, 0, 0
        for old in [old_child, old_parent]:
          if old > min(new_child, new_parent) and old < max(new_child, new_parent):
            inside += 1
          elif old < min(new_child, new_parent) or old > max(new_child, new_parent):
            outside += 1
          else:
            neutral += 1
        # if one of the members in the old arc is strictly within the new arc
        # and the other old member is strictly outside the new arc, 
        # then we have a projectivity-breaking arc pair
        if inside == 1 and outside == 1:
          # we never raise an arc when parent = root. so, if the old arc has a root, raise the new arc instead
          if child_parent_map[old_parent] < 0:
            old_child, old_parent = new_child, new_parent
          # if the bad arc here has a smaller gap, than the shortest bad arc encountered, use it
          if not shortest_bad_arc or \
                abs(old_child-old_parent) < abs(shortest_bad_arc[0]-shortest_bad_arc[1]):
            shortest_bad_arc = (old_child, old_parent,)
      old_arcs.add( new_arc )

  #print 'shortest_bad_arc = ', shortest_bad_arc
  return shortest_bad_arc
  
projective_parses=0
nonprojective_parses=0
projectivization_attempts=0    
sent_id = -1
conll_line = -1
while True:

  # reading a parse
  sent_id += 1
  parent_children_map=defaultdict(list)
  child_parent_map={}
  gap_to_arcs=defaultdict(set)
  tokens = []

  end_of_file = False
  root = -1
  while True:
    conll_line += 1
    line = nonprojective_file.readline()
    #print line
    if not line: 
      end_of_file = True
      break
    conll_fields = line.strip().split('\t')
    tokens.append(conll_fields)
    #print conll_fields
    if len(conll_fields) != 8: 
      break
    child_position, child_string, whatever1, child_fine_pos, child_coarse_pos, whatever2, parent_position, dependency_relation = int(conll_fields[0])-1, conll_fields[1], conll_fields[2], conll_fields[3], conll_fields[4], conll_fields[5], int(conll_fields[6])-1, conll_fields[7]

    # if this is root
    if parent_position == -1:
      # and it's the first root found in this parse
      if root == -1:
        # designate it as THE root
        root = child_position
      # but if someone else claimed this position before
      else:
        # defer to the one who claimed it earlier
        parent_position = root
        tokens[child_position][6] = str(root+1)
        
    # increase the gap between the root and a direct child
    if parent_position == -1:
      parent_position = -1000

    # save the parse
    parent_children_map[parent_position].append(child_position)
    child_parent_map[child_position] = parent_position
    gap_to_arcs[abs(child_position - parent_position)].add( (child_position, parent_position,) )

  if end_of_file:
    break

  attempts = 0
  while True:
    bad_arc = get_nonprojective_arc(gap_to_arcs, child_parent_map)
    if not bad_arc: 
      if attempts == 0:
        projective_parses += 1
      else:
        nonprojective_parses += 1
      break
    # raise the problematic arc
    attempts += 1
    projectivization_attempts += 1
    child, bad_parent = bad_arc
    #print 'bad_parent = ', bad_parent
    better_parent = child_parent_map[bad_parent]
    gap_to_arcs[abs(child-bad_parent)].remove(bad_arc)
    better_arc = (child, better_parent,)
    gap_to_arcs[abs(child-better_parent)].add(better_arc)
    child_parent_map[child] = better_parent
    if better_parent < 0:
      assert False
    else:
      tokens[child][6] = str(better_parent + 1)
    tokens[child][7] = 'raised'

  for token in tokens:
    projective_file.write(u'{}\n'.format('\t'.join(token)))
  #projective_file.write(u'\n')

print 'projective_parses = ', projective_parses  
print 'nonprojective_parses = ', nonprojective_parses  
print 'projectivization_attempts = ', projectivization_attempts

projective_file.close()
nonprojective_file.close()
