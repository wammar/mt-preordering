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
  args = parser.parse_args()

  source_file = open(args.source)
  dependency_file = open(args.dependency)
  feature_file = open(args.feature, 'w')
  training = open(args.training)
  response_file = open(args.response,'w')

  instance = 0
  source_line = -1
  source = []
  dependency = dict()
  dep_line = 0

  for line in training:
    label, sent_num, a_index, b_index = line.split('\t')
    if not args.test:
      response_file.write('{}\t{}\n'.format(instance,label))
    sent_num, a_index, b_index = int(sent_num), int(a_index), int(b_index)
    while sent_num > source_line: 
      source = source_file.readline().strip().split()
      dependecy = dict()
      for i in range(len(source)):
        conll = dependency_file.readline().strip().split('\t')
        print conll
        if i==0:
          dependency['token']=[]
          dependency['pos']=[]
          dependency['head']=[]
          dependency['mod']=[]
        dependency['token'].append(conll[1])
        dependency['pos'].append(conll[3])
        dependency['head'].append(int(conll[6])-1)
        dependency['mod'].append(conll[7])
        dep_line+=1
      dependency_file.readline()
      source_line += 1
    assert(source==dependency['token'])
    print source_line, dep_line, a_index, b_index
    features = extract(source, a_index, b_index, dependency)    
    json_feat = json.dumps(features)    
    feature_file.write('{}\t{}\n'.format(instance,json_feat))
    instance += 1
  training.close()
  dependency_file.close()
  source_file.close()
  response_file.close()
  feature_file.close()
  
def extract(source, a_index, b_index, dependency):
  features = dict()
  features['a_token_'+source[a_index]] = 1
  features['b_token_'+source[b_index]] = 1
  features['a_pos_'+dependency['pos'][a_index]] = 1
  features['b_pos_'+dependency['pos'][b_index]] = 1
  if dependency['head'][a_index] < 0:
    features['a_root'] = 1
    b_parent = dependency['head'][b_index]
    features['b_head_token_'+source[b_parent]] = 1
    features['b_head_pos_'+dependency['pos'][b_parent]] = 1
    features['b_head_mod_'+dependency['mod'][b_parent]] = 1
  elif dependency['head'][b_index] < 0:
    features['b_root'] = 1
    a_parent = dependency['head'][a_index]
    features['a_head_token_'+source[a_parent]] = 1
    features['a_head_pos_'+dependency['pos'][a_parent]] = 1
    features['a_head_mod_'+dependency['mod'][a_parent]] = 1
  else:
    if dependency['head'][b_index]==dependency['head'][a_index]:
      features['same_head'] = 1
    elif dependency['head'][b_index]==a_index:
      features['a_head_of_b'] = 1
    elif dependency['head'][a_index]==b_index:
      features['b_head_of_a'] = 1
    b_parent = dependency['head'][b_index]
    features['b_head_token_'+source[b_parent]] = 1
    features['b_head_pos_'+dependency['pos'][b_parent]] = 1
    features['b_head_mod_'+dependency['mod'][b_parent]] = 1
    a_parent = dependency['head'][a_index]
    features['a_head_token_'+source[b_parent]] = 1
    features['a_head_pos_'+dependency['pos'][a_parent]] = 1
    features['a_head_mod_'+dependency['mod'][a_parent]] = 1
  if (b_index - a_index) == 2:
    features['between_token_'+source[a_index+1]] = 1
    features['between_pos_'+dependency['pos'][a_index+1]] = 1
  elif (b_index - a_index) > 2:
    features['between_a_token_'+source[a_index+1]] = 1
    features['between_a_pos_'+dependency['pos'][a_index+1]] = 1
    features['between_b_token_'+source[b_index-1]] = 1
    features['between_b_pos_'+dependency['pos'][b_index-1]] = 1
  
  for i in range(len(source)):
    mod = dependency['mod'][i]
    if dependency['head'][i]==a_index:
      features['a_child_'+mod+'_token_'+source[i]] = 1
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


    elif dependency['head'][i]==b_index:
      features['b_child_'+mod+'_token_'+source[i]] = 1
      features['b_child_'+mod+'_pos_'+dependency['pos'][i]] = 1

      if i < b_index:
        if (b_index-i)==1:
          features['b_child_'+mod+'_immediately_before'] = 1
        else:
          features['b_child_'+mod+'_before'] = 1
      else:
        if (i-a_index)==1:
          features['b_child_'+mod+'_immediately_after'] = 1
        else:
          features['b_child_'+mod+'_after'] = 1
  return features

if __name__=='__main__':
  main()
