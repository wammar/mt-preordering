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
  parser.add_argument('-c','--cluster',help='source as brown clusters')
  args = parser.parse_args()

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
    label, sent_num, a_index = line.split('\t')
    sent_num, a_index = int(sent_num), int(a_index)
    while sent_num > source_line: 
      src = source_file.readline().strip()
      source = src.split()
      clusters = cluster_file.readline().strip().split()
      source_line +=1
      dependency['token']=[]
      dependency['pos']=[]
      dependency['head']=[]
      dependency['mod']=[]
      #print source_line, dep_line, a_index, instance
      parse = dependency_file.readline().strip()
      while parse:
        conll = parse.split('\t')
        dependency['token'].append(conll[1])
        dependency['pos'].append(conll[3])
        dependency['head'].append(int(conll[6])-1)
        dependency['mod'].append(conll[7])
        dep_line += 1
        parse = dependency_file.readline().strip()

    if not source==dependency['token']:
      print source_line, dep_line, a_index, instance
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

    features = extract(source, clusters, a_index, dependency) 
    json_feat = json.dumps(features)    
    feature_file.write('{}\t{}\n'.format(instance,json_feat))
    instance += 1
  training.close()
  dependency_file.close()
  source_file.close()
  response_file.close()
  feature_file.close()

def extract(source, clusters, a_index, b_index, dependency):
  features = dict()
  features['a_token_'+source[a_index]] = 1
  features['a_cluster_'+clusters[a_index]] = 1
  features['a_pos_'+dependency['pos'][a_index]] = 1
  features['a_num_siblings'] = dependency['head'].count(dependency['head'][a_index]) - 1
  if dependency['head'][a_index] < 0:
    features['a_root'] = 1
  else:
    a_parent = dependency['head'][a_index]
    features['a_head_token_'+source[a_parent]] = 1
    features['a_head_cluster_'+clusters[a_parent]] = 1
    features['a_head_pos_'+dependency['pos'][a_parent]] = 1
    features['a_head_mod_'+dependency['mod'][a_parent]] = 1
    if not dependency['head'][a_parent] < 0:
      a_grand = dependency['head'][a_parent]
      features['a_grandparent_token_'+source[a_grand]] = 1
      features['a_grandparent_cluster_'+clusters[a_grand]] = 1
      features['a_grandparent_pos_'+dependency['pos'][a_grand]] = 1
      features['a_grandparent_mod_'+dependency['mod'][a_grand]] = 1
 
  a_child = 0
  for i in range(len(source)):
    mod = dependency['mod'][i]
    if dependency['head'][i]==a_index:
      a_child += 1
      features['a_child_'+mod+'_token_'+source[i]] = 1
      features['a_child_'+mod+'_cluster_'+clusters[i]] = 1 
      features['a_child_'+mod+'_pos_'+dependency['pos'][i]] = 1
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

  features['a_num_children'] = a_child
 
  return features

if __name__=='__main__':
  main()
