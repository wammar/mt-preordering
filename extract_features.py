#!/usr/bin/env python
import sys, os, io
import argparse
import json

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-s','--source',help='source text')
  parser.add_argument('-d','--dependency',help='dependency parses for src sentences (conll format)')
  parser.add_argument('-f','--feature',help='output file for features')
  parser.add_argument('-r','--response',help='output file for responses',required=False)
  parser.add_argument('-t','--training',help='file of responses and word pairs for classification')
  parser.add_argument('-c','--cluster',help='source as brown clusters')
  args = parser.parse_args()

  source_file = io.open(args.source, encoding='utf8')
  cluster_file = io.open(args.cluster, encoding='utf8')
  dependency_file = io.open(args.dependency, encoding='utf8')
  feature_file = io.open(args.feature, mode='w', encoding='utf8')
  training = io.open(args.training)
  response_file = io.open(args.response, mode='w', encoding='utf8')

  instance = 0
  source_line = -1
  source = []
  clusters = []
  dep_line = 0
  dependency = dict()
  for line in training:
    label, sent_num, a_index, b_index = line.split('\t')
    sent_num, a_index, b_index = int(sent_num), int(a_index), int(b_index)
    while sent_num > source_line: 
      src = source_file.readline().strip()
      source = src.split()
      clusters = cluster_file.readline().strip().split()
      source_line +=1
      dependency['token']=[]
      dependency['coarse']=[]
      dependency['pos']=[]
      dependency['head']=[]
      dependency['mod']=[]
      dependency['children']=[ [] for i in xrange(len(source)) ]
      #print source_line, dep_line, a_index, b_index, instance
      parse = dependency_file.readline().strip()
      #print parse.encode('utf8')
      while parse:
        conll = parse.split('\t')
        index = int(conll[0])-1
        dependency['token'].append(conll[1])
        dependency['coarse'].append(conll[3])
        dependency['pos'].append(conll[4])
        head = int(conll[6])-1
        dependency['head'].append(head)
        dependency['mod'].append(conll[7])
        if head >= 0:
          dependency['children'][head].append(index)
        dep_line += 1
        parse = dependency_file.readline().strip()

    # count number of children of each token
    dependency['fanout'] = []
    for i in xrange(len(dependency['token'])):
      dependency['fanout'].append( dependency['head'].count(i)) 
    
    # find the level of each token in the dependency parse
    levels = []
    levels.append( set( [i for i in xrange(len(source)) if dependency['head'][i] < 0] ) )
    levels_total = len(levels[0])
    while levels_total < len(source):
      levels.append( set( [i for i in xrange(len(source)) if dependency['head'][i] in levels[-1]] ) )
      levels_total += len(levels[-1])
    dependency['level'] = [-1 for i in xrange(len(source))]
    for level in xrange(len(levels)):
      for token_index in levels[level]:
        dependency['level'][token_index] = level

    # find left and right siblings
    dependency['lsibling'] = []
    dependency['rsibling'] = []
    for i in xrange(len(source)):
      head = dependency['head'][i]
      index_of_i_among_siblings = dependency['children'][head].index(i) if head >= 0 else 0
      # first sibling?
      if index_of_i_among_siblings == 0:
        dependency['lsibling'].append(-1)
      else:
        dependency['lsibling'].append( dependency['children'][head][index_of_i_among_siblings-1] )
      # last sibling?
      if index_of_i_among_siblings == len(dependency['children'][head])-1 or head < 0:
        dependency['rsibling'].append(-1)
      else:
        dependency['rsibling'].append( dependency['children'][head][index_of_i_among_siblings+1] )

    if not source==dependency['token']:
      #print source_line, dep_line, a_index, b_index, instance
      #print src
      #for t in dependency['token']:
      #  print t,
      #print ''
      #print dependency['token']
      response_file.write(u'{}\t0\n'.format(instance))
      feature_file.write(u"{}\t{{\"corrupted\": 1}}\n".format(instance))
      instance += 1
      assert False
      continue

    response_file.write(u'{}\t{}\n'.format(instance,label))

    features = extract(source, clusters, a_index, b_index, dependency, True)
    feature_value_strings = [u'"{}": {}'.format(f.replace('"',"'"), features[f]) for f in features.keys()]
    feature_file.write(u'{}\t{{{}}}\n'.format(instance, ', '.join(feature_value_strings)))
    instance += 1
  training.close()
  dependency_file.close()
  source_file.close()
  response_file.close()
  feature_file.close()

#def add_feature(features, new_feature, val, relation, add_relation=False):
#  features[new_feature] = val
#  features[new_feature[0]+relation+new_feature[1:]] = val
  
def extract(source, clusters, a_index, b_index, dependency, add_relation=True):

  features = dict()

  # how large is the gap between a and b
  gap = b_index - a_index
  gap_gt1 = '>' if gap > 1 else '='

  # level of a (b's level is a function of a's level and the relationship between them)
  a_level = dependency['level'][a_index]

  # identity of a, b
  lexical = False
  if lexical:
    features[u'a={}_gap{}1'.format(source[a_index], gap_gt1)] = 1
    features[u'b={}_gap{}1'.format(source[b_index], gap_gt1)] = 1

  # brown clusters of a, b, and (a,b)
  features[u'brown(a)={}_brown(b)={}'.format(clusters[a_index], clusters[b_index])] = 1

  # fine POS tag of a, b, and (a,b)
  features[u'fine(a)={}_fine(b)={}'.format(dependency['pos'][a_index], 
                                           dependency['pos'][b_index])] = 1
  features[u'level(a)={}_fine(a)={}_fine(b)={}'.format(a_level, dependency['pos'][a_index], 
                                                       dependency['pos'][b_index])] = 1

  # coarse POS tag of a, b, and (a,b)
  features[u'coarse(a)={}_coarse(b)={}'.format(dependency['coarse'][a_index], 
                                               dependency['coarse'][b_index])] = 1
  features[u'level(a)={}_coarse(a)={}_coarse(b)={}'.format(a_level, dependency['coarse'][a_index], 
                                                           dependency['coarse'][b_index])] = 1

  # features specific to the relationship between a and b
  if dependency['head'][a_index]==dependency['head'][b_index]:
    relation = u'head(a)=head(b)_'
    features[u'fanout(head)={}_gap{}1'.format(dependency['fanout'][ dependency['head'][a_index] ], 
                                                     gap_gt1)] = 1
    features[u'mod(a)={}_fine(a)={}_mod(b)={}_fine(b)={}'.format(dependency['mod'][a_index], 
                                                                     dependency['pos'][a_index], 
                                                                     dependency['mod'][b_index], 
                                                                     dependency['pos'][b_index])] = 1
    head = dependency['head'][a_index]
    features[u'fine(head)={}'.format(dependency['pos'][head])] = 1
    head_left_sibling = dependency['lsibling'][head]
    head_right_sibling = dependency['rsibling'][head]
    if head_left_sibling >= 0:
      features[u'fine(head)={}_fine(head_left_sibling)={}'.format(dependency['pos'][head],
                                                                  dependency['pos'][head_left_sibling])]=1
    if head_right_sibling >= 0:
      features[u'fine(head)={}_fine(head_right_sibling)={}'.format(dependency['pos'][head],
                                                                   dependency['pos'][head_right_sibling])]=1
    
    if dependency['lsibling'][a_index] == b_index:
      features[u'contiguous_siblings'] = 1
    else:
      features[u'noncontiguous_siblings'] = 1
      if dependency['lsibling'][a_index] == dependency['rsibling'][b_index]:
        features[u'fine(a_right_sibling==b_left_sibling)={}'.format(dependency['rsibling'][a_index])]=1
      else:
        features[u'fine(a_right_sibling)={}_fine(b_left_sibling)={}'.format(dependency['rsibling'][a_index],
                                                                            dependency['lsibling'][b_index])]=1
    features[u'|head_children|={}'.format(len(dependency['children'][head]))] = 1

  elif dependency['head'][a_index]==b_index:
    relation = u'b=head(a)_'
    features[u'fanout(b)={}_gap{}1'.format(dependency['fanout'][b_index], gap_gt1)] = 1
    features[u'mod(a)={}_fine(a)={}_fine(b)={}'.format(dependency['mod'][a_index], 
                                                       dependency['pos'][a_index], 
                                                       dependency['pos'][b_index])] = 1
    b_left_sibling = dependency['lsibling'][b_index]
    b_right_sibling = dependency['rsibling'][b_index]
    features[u'fine(b_left_sibling)={}'.format(dependency['pos'][b_left_sibling])] = 1
    features[u'fine(b_right_sibling)={}'.format(dependency['pos'][b_right_sibling])] = 1
    features[u'|b_children|={}'.format(len(dependency['children'][b_index]))] = 1
  elif dependency['head'][b_index]==a_index:
    relation = u'a=head(b)_'
    features[u'fanout(a)={}_gap{}1'.format(dependency['fanout'][a_index], gap_gt1)] = 1
    features[u'mod(b)={}_fine(a)={}_fine(b)={}'.format(dependency['mod'][b_index], 
                                                       dependency['pos'][a_index], 
                                                       dependency['pos'][b_index])] = 1             
    a_left_sibling = dependency['lsibling'][a_index]
    a_right_sibling = dependency['rsibling'][a_index]
    features[u'fine(a_left_sibling)={}'.format(dependency['pos'][a_left_sibling])] = 1
    features[u'fine(a_right_sibling)={}'.format(dependency['pos'][a_right_sibling])] = 1
    features[u'|a_children|={}'.format(len(dependency['children'][a_index]))] = 1
  else:
    print 'a_index=', a_index, ', b_index=', b_index, ', dependency[head]=', dependency['head']
    print source
    assert False

  # fine pos ngram features
  before_b = dependency['pos'][b_index-1] if b_index > 0 else u'sos'
  after_a = dependency['pos'][a_index+1] if a_index < len(source)-1 else u'eos'
  features[u'fine(a)={}_fine(a+1)={}_gap={}_fine(b-1)={}_fine(b)={}'.format(dependency['pos'][a_index],
                                                                            after_a, gap, before_b,
                                                                            dependency['pos'][b_index])] = 1

  if dependency['head'][a_index] < 0:
    features[u'root=a_mod(b)={}'.format(dependency['mod'][b_index])] = 1

  if dependency['head'][b_index] < 0:
    features[u'root=b_mod(a)={}'.format(dependency['mod'][a_index])] = 1           
             
  #  if not dependency['head'][b_parent] < 0:
  #    b_grand = dependency['head'][b_parent]
  #    features[u'b_grandparent_token_'+source[b_grand]] = 1
  #    features[u'b_grandparent_cluster_'+clusters[b_grand]] = 1
  #    features[u'b_grandparent_pos_'+dependency['pos'][b_grand]] = 1
  #    features[u'b_grandparent_coarse_'+dependency['coarse'][b_grand]] = 1
  #    features[u'b_grandparent_mod_'+dependency['mod'][b_grand]] = 1
  #elif dependency['head'][b_index] < 0:
  #  features[u'b_root'] = 1
  #  a_parent = dependency['head'][a_index]
  #  features[u'a_head_token_'+source[a_parent]] = 1
  #  features[u'a_head_cluster_'+clusters[a_parent]] = 1 
  #  features[u'a_head_pos_'+dependency['pos'][a_parent]] = 1
  #  features[u'a_head_coarse_'+dependency['coarse'][a_parent]] = 1
  #  features[u'a_head_mod_'+dependency['mod'][a_parent]] = 1
  #  if not dependency['head'][a_parent] < 0:
  #    a_grand = dependency['head'][a_parent]
  #    features[u'a_grandparent_token_'+source[a_grand]] = 1
  #    features[u'a_grandparent_cluster_'+clusters[a_grand]] = 1
  #    features[u'a_grandparent_pos_'+dependency['pos'][a_grand]] = 1
  #    features[u'a_grandparent_coarse_'+dependency['coarse'][a_grand]] = 1
  #    features[u'a_grandparent_mod_'+dependency['mod'][a_grand]] = 1
  #else:
  #  if dependency['head'][b_index]==dependency['head'][a_index]:
  #    features[u'same_head'] = 1
  #  elif dependency['head'][b_index]==a_index:
  #    features[u'a_head_of_b'] = 1
  #  elif dependency['head'][a_index]==b_index:
  #    features[u'b_head_of_a'] = 1
  #  b_parent = dependency['head'][b_index]
  #  features[u'b_head_token_'+source[b_parent]] = 1
  #  features[u'b_head_cluster_'+clusters[b_parent]] = 1
  #  features[u'b_head_pos_'+dependency['pos'][b_parent]] = 1
  #  features[u'b_head_coarse_'+dependency['coarse'][b_parent]] = 1
  #  features[u'b_head_mod_'+dependency['mod'][b_parent]] = 1
  #  if not dependency['head'][b_parent] < 0:
  #    b_grand = dependency['head'][b_parent]
  #    features[u'b_grandparent_token_'+source[b_grand]] = 1
  #    features[u'b_grandparent_cluster_'+clusters[b_grand]] = 1
  #    features[u'b_grandparent_pos_'+dependency['pos'][b_grand]] = 1
  #    features[u'b_grandparent_coarse_'+dependency['coarse'][b_grand]] = 1
  #    features[u'b_grandparent_mod_'+dependency['mod'][b_grand]] = 1
  #  a_parent = dependency['head'][a_index]
  #  features[u'a_head_token_'+source[a_parent]] = 1
  #  features[u'a_head_cluster_'+clusters[a_parent]] = 1
  #  features[u'a_head_pos_'+dependency['pos'][a_parent]] = 1
  #  features[u'a_head_coarse_'+dependency['pos'][a_parent]] = 1
  #  features[u'a_head_mod_'+dependency['mod'][a_parent]] = 1
  #  if not dependency['head'][a_parent] < 0:
  #    a_grand = dependency['head'][a_parent]
  #    features[u'a_grandparent_token_'+source[a_grand]] = 1
  #    features[u'a_grandparent_cluster_'+clusters[a_grand]] = 1
  #    features[u'a_grandparent_pos_'+dependency['pos'][a_grand]] = 1
  #    features[u'a_grandparent_coarse_'+dependency['coarse'][a_grand]] = 1
  #    features[u'a_grandparent_mod_'+dependency['mod'][a_grand]] = 1
  #if (b_index - a_index) == 2:
  #  features[u'between_token_'+source[a_index+1]] = 1
  #  features[u'between_cluster_'+clusters[a_index+1]] = 1
  #  features[u'between_coarse_'+dependency['coarse'][a_index+1]] = 1
  #  features[u'between_pos_'+dependency['pos'][a_index+1]] = 1


  #a_child = 0
  #b_child = 0
  #for i in range(len(source)):
  #  mod = dependency['mod'][i]
  #  if dependency['head'][i]==a_index:
  #    a_child += 1
  #    features[u'a_child_'+mod+u'_token_'+source[i]] = 1
  #    features[u'a_child_'+mod+u'_cluster_'+clusters[i]] = 1 
  #    features[u'a_child_'+mod+u'_pos_'+dependency['pos'][i]] = 1
  #    features[u'a_child_'+mod+u'_coarse_'+dependency['coarse'][i]] = 1
  #    if i < a_index:
  #      if (a_index-i)==1:
  #        features[u'a_child_'+mod+u'_immediately_before'] = 1
  #      else:
  #        features[u'a_child_'+mod+u'_before'] = 1
  #    else:
  #      if (i-a_index)==1:
  #        features[u'a_child_'+mod+u'_immediately_after'] = 1
  #      else:
  #        features[u'a_child_'+mod+u'_after'] = 1
#

  #  elif dependency['head'][i]==b_index:
  #    b_child += 1
  #    features[u'b_child_'+mod+u'_token_'+source[i]] = 1
  #    features[u'b_child_'+mod+u'_cluster_'+clusters[i]] = 1
  #    features[u'b_child_'+mod+u'_pos_'+dependency['pos'][i]] = 1
  #    features[u'b_child_'+mod+u'_coarse_'+dependency['coarse'][i]] = 1
#
  #    if i < b_index:
  #      if (b_index-i)==1:
  #        features[u'b_child_'+mod+u'_immediately_before'] = 1
  #      else:
  #        features[u'b_child_'+mod+u'_before'] = 1
  #    else:
  #      if (i-b_index)==1:
  #        features[u'b_child_'+mod+u'_immediately_after'] = 1
  #      else:
  #        features[u'b_child_'+mod+u'_after'] = 1
  #features[u'a_num_children'] = a_child
  #features[u'b_num_children'] = b_child
 
  if add_relation:
    for key in features.keys():
      features[relation+key] = features[key]
      del features[key]
  return features

if __name__=='__main__':
  main()
