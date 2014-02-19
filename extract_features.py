#!/usr/bin/env python
import sys, os
import argparse
import json

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-s','--source',help='source text')
  parser.add_argument('-d','--dependency',help='dependency parses for src sentences (conll format)')
  parser.add_argument('-f','--feature',help='output file for features')
  parser.add_argument('-r','--response',help='output file for responses',required=False)
  parser.add_argument('-t','--training',help='file of responses and word pairs for classification')
  parser.add_argument('--test', action='store_true',help='features only, no response file produced')
  parser.add_argument('-c','--cluster',help='source as brown clusters')
  parser.add_argument('-e','--extra', action='store_true',help='for each feature, have two versions: one which explicitly contains the relationship between a and b, and one that does not')
  args = parser.parse_args()

  print 'args.test = ', args.test

  source_file = open(args.source)
  cluster_file = open(args.cluster)
  dependency_file = open(args.dependency)
  feature_file = open(args.feature, 'w')
  training = open(args.training)
  response_file = open(args.response,'w')

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
      print source_line, dep_line, a_index, b_index, instance
      parse = dependency_file.readline().strip()
      print parse
      while parse:
        conll = parse.split('\t')
        dependency['token'].append(conll[1])
        dependency['coarse'].append(conll[3])
        dependency['pos'].append(conll[4])
        dependency['head'].append(int(conll[6])-1)
        dependency['mod'].append(conll[7])
        dep_line += 1
        parse = dependency_file.readline().strip()

    if not source==dependency['token']:
      print source_line, dep_line, a_index, b_index, instance
      print src
      for t in dependency['token']:
        print t,
      print ''
      print dependency['token']
      response_file.write('{}\t0\n'.format(instance))
      feature_file.write("{}\t{{\"corrupted\": 1}}\n".format(instance))
      instance += 1
      continue

    if not args.test:
      response_file.write('{}\t{}\n'.format(instance,label))

    features = extract(source, clusters, a_index, b_index, dependency, args.extra)    
    json_feat = json.dumps(features)    
    feature_file.write('{}\t{}\n'.format(instance,json_feat))
    instance += 1
  training.close()
  dependency_file.close()
  source_file.close()
  response_file.close()
  feature_file.close()

def add_feature(features, new_feature, val, relation, add_relation=False):
  features[new_feature] = val
  features[new_feature[0]+relation+new_feature[1:]] = val
  
def extract(source, clusters, a_index, b_index, dependency, add_relation=False):
  features = dict()
  a_relation = ''
  b_relation = ''
  if dependency['head'][a_index]==dependency['head'][b_index]:
    a_relation = 'a_sibling_of_b'
    b_relation = 'b_sibling_of_a'
  elif dependency['head'][a_index]==b_index:
    a_relation = 'a_child_of_b'
    b_relation = 'b_parent_of_a'
  elif dependency['head'][b_index]==a_index:
    a_relation = 'a_parent_of_b'
    b_relation = 'b_child_of_a'

  features['gap_size'] = b_index - a_index - 1
  features['a_token_'+source[a_index]] = 1
  features['b_token_'+source[b_index]] = 1
  features['a_cluster_'+clusters[a_index]] = 1
  features['b_cluster_'+clusters[b_index]] = 1
  features['a_pos_'+dependency['pos'][a_index]] = 1
  features['b_pos_'+dependency['pos'][b_index]] = 1
  features['a_coarse_'+dependency['coarse'][a_index]] = 1
  features['b_coarse_'+dependency['coarse'][b_index]] = 1
  features['a_num_siblings'] = dependency['head'].count(dependency['head'][a_index]) - 1
  features['b_num_siblings'] = dependency['head'].count(dependency['head'][b_index]) - 1
  if dependency['head'][a_index] < 0:
    features['a_root'] = 1
    b_parent = dependency['head'][b_index]
    features['b_head_token_'+source[b_parent]] = 1
    features['b_head_cluster_'+clusters[b_parent]] = 1
    features['b_head_pos_'+   dependency['pos'][b_parent]] = 1
    features['b_head_coarse_'+dependency['coarse'][b_parent]] = 1
    features['b_head_mod_'+dependency['mod'][b_parent]] = 1
    if not dependency['head'][b_parent] < 0:
      b_grand = dependency['head'][b_parent]
      features['b_grandparent_token_'+source[b_grand]] = 1
      features['b_grandparent_cluster_'+clusters[b_grand]] = 1
      features['b_grandparent_pos_'+dependency['pos'][b_grand]] = 1
      features['b_grandparent_coarse_'+dependency['coarse'][b_grand]] = 1
      features['b_grandparent_mod_'+dependency['mod'][b_grand]] = 1
  elif dependency['head'][b_index] < 0:
    features['b_root'] = 1
    a_parent = dependency['head'][a_index]
    features['a_head_token_'+source[a_parent]] = 1
    features['a_head_cluster_'+clusters[a_parent]] = 1 
    features['a_head_pos_'+dependency['pos'][a_parent]] = 1
    features['a_head_coarse_'+dependency['coarse'][a_parent]] = 1
    features['a_head_mod_'+dependency['mod'][a_parent]] = 1
    if not dependency['head'][a_parent] < 0:
      a_grand = dependency['head'][a_parent]
      features['a_grandparent_token_'+source[a_grand]] = 1
      features['a_grandparent_cluster_'+clusters[a_grand]] = 1
      features['a_grandparent_pos_'+dependency['pos'][a_grand]] = 1
      features['a_grandparent_coarse_'+dependency['coarse'][a_grand]] = 1
      features['a_grandparent_mod_'+dependency['mod'][a_grand]] = 1
  else:
    if dependency['head'][b_index]==dependency['head'][a_index]:
      features['same_head'] = 1
    elif dependency['head'][b_index]==a_index:
      features['a_head_of_b'] = 1
    elif dependency['head'][a_index]==b_index:
      features['b_head_of_a'] = 1
    b_parent = dependency['head'][b_index]
    features['b_head_token_'+source[b_parent]] = 1
    features['b_head_cluster_'+clusters[b_parent]] = 1
    features['b_head_pos_'+dependency['pos'][b_parent]] = 1
    features['b_head_coarse_'+dependency['coarse'][b_parent]] = 1
    features['b_head_mod_'+dependency['mod'][b_parent]] = 1
    if not dependency['head'][b_parent] < 0:
      b_grand = dependency['head'][b_parent]
      features['b_grandparent_token_'+source[b_grand]] = 1
      features['b_grandparent_cluster_'+clusters[b_grand]] = 1
      features['b_grandparent_pos_'+dependency['pos'][b_grand]] = 1
      features['b_grandparent_coarse_'+dependency['coarse'][b_grand]] = 1
      features['b_grandparent_mod_'+dependency['mod'][b_grand]] = 1
    a_parent = dependency['head'][a_index]
    features['a_head_token_'+source[a_parent]] = 1
    features['a_head_cluster_'+clusters[a_parent]] = 1
    features['a_head_pos_'+dependency['pos'][a_parent]] = 1
    features['a_head_coarse_'+dependency['pos'][a_parent]] = 1
    features['a_head_mod_'+dependency['mod'][a_parent]] = 1
    if not dependency['head'][a_parent] < 0:
      a_grand = dependency['head'][a_parent]
      features['a_grandparent_token_'+source[a_grand]] = 1
      features['a_grandparent_cluster_'+clusters[a_grand]] = 1
      features['a_grandparent_pos_'+dependency['pos'][a_grand]] = 1
      features['a_grandparent_coarse_'+dependency['coarse'][a_grand]] = 1
      features['a_grandparent_mod_'+dependency['mod'][a_grand]] = 1
  if (b_index - a_index) == 2:
    features['between_token_'+source[a_index+1]] = 1
    features['between_cluster_'+clusters[a_index+1]] = 1
    features['between_coarse_'+dependency['coarse'][a_index+1]] = 1
    features['between_pos_'+dependency['pos'][a_index+1]] = 1

  if a_index - 1 > -1:
    features['a_-1_token_'+source[a_index-1]] = 1
    features['a_-1_pos_'+dependency['pos'][a_index-1]] = 1
    features['a_-1_cluster_'+clusters[a_index-1]] = 1
    features['a_-1_coarse_'+dependency['coarse'][a_index-1]] = 1
    features['a_bigram_'+source[a_index-1]+'_'+source[a_index]] = 1
  if b_index - 1 > -1:
    features['b_-1_token_'+source[b_index-1]] = 1
    features['b_-1_pos_'+dependency['pos'][b_index-1]] = 1
    features['b_-1_cluster_'+clusters[b_index-1]] = 1
    features['b_-1_coarse_'+dependency['coarse'][b_index-1]] = 1
    features['b_bigram_'+source[a_index-1]+'_'+source[b_index]] = 1
  if a_index + 1 < len(source):
    features['a_+1_token_'+source[a_index+1]] = 1
    features['a_+1_pos_'+dependency['pos'][a_index+1]] = 1
    features['a_+1_cluster_'+clusters[a_index+1]] = 1
    features['a_+1_coarse_'+dependency['coarse'][a_index+1]] = 1
    features['a_bigram_'+source[a_index]+'_'+source[a_index+1]] = 1
  if b_index + 1 > len(source):
    features['b_+1_token_'+source[b_index+1]] = 1
    features['b_+1_pos_'+dependency['pos'][b_index+1]] = 1
    features['b_+1_cluster_'+clusters[b_index+1]] = 1
    features['b_+1_coarse_'+dependency['coarse'][b_index+1]] = 1
    features['b_bigram_'+source[b_index]+'_'+source[b_index+1]] = 1
  

  a_child = 0
  b_child = 0
  for i in range(len(source)):
    mod = dependency['mod'][i]
    if dependency['head'][i]==a_index:
      a_child += 1
      features['a_child_'+mod+'_token_'+source[i]] = 1
      features['a_child_'+mod+'_cluster_'+clusters[i]] = 1 
      features['a_child_'+mod+'_pos_'+dependency['pos'][i]] = 1
      features['a_child_'+mod+'_coarse_'+dependency['coarse'][i]] = 1
      if i < a_index:
        if (a_index-i)==1:
          features['a_child_'+mod+'_immediately_before'] = 1
        else:
          features['a_child_'+mod+'_before'] = 1
      else:
        if (i-a_index)==1:
          features['a_child_'+mod+'_immediately_after'] = 1
        else:
          features['a_child_'+mod+'_after'] = 1


    elif dependency['head'][i]==b_index:
      b_child += 1
      features['b_child_'+mod+'_token_'+source[i]] = 1
      features['b_child_'+mod+'_cluster_'+clusters[i]] = 1
      features['b_child_'+mod+'_pos_'+dependency['pos'][i]] = 1
      features['b_child_'+mod+'_coarse_'+dependency['coarse'][i]] = 1

      if i < b_index:
        if (b_index-i)==1:
          features['b_child_'+mod+'_immediately_before'] = 1
        else:
          features['b_child_'+mod+'_before'] = 1
      else:
        if (i-b_index)==1:
          features['b_child_'+mod+'_immediately_after'] = 1
        else:
          features['b_child_'+mod+'_after'] = 1
  features['a_num_children'] = a_child
  features['b_num_children'] = b_child
 
  if add_relation and (a_relation or b_relation):
    for f in features.keys():
      if f[0:2]=='a_' and a_relation:
        features[a_relation+f[1:]] = features[f]
      elif f[0:2]=='b_' and b_relation:
        features[b_relation+f[1:]] = features[f]
  return features

if __name__=='__main__':
  main()
