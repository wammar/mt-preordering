import re
import time
import io
import sys
import argparse
from collections import defaultdict

# parse/validate arguments
argParser = argparse.ArgumentParser()
argParser.add_argument("-g", "--gold_filename", help="true responses, creg formatted")
argParser.add_argument("-p", "--guess_filename", help="guessed responses, creg formatted")
args = argParser.parse_args()

labels = set()
confusion = defaultdict(float)
total = 0.0

for (gold, guess) in zip( open(args.gold_filename), open(args.guess_filename) ):
  gold_example, gold_label = gold.strip().split()
  guess_example, guess_label = guess.split()
  total += 1
  assert gold_example == guess_example
  confusion[ (gold_label, guess_label,) ] += 1.0
  if guess_label not in labels:
    labels.add(guess_label)
  if gold_label not in labels: 
    labels.add(gold_label)
  
correct = 0.0
for (gold_label, guess_label,) in confusion.keys():
  print 'count(gold=', gold_label, 'vs. guess=', guess_label, ') = ', confusion[(gold_label, guess_label,)]
  print 'p(gold=', gold_label, ', guess=', guess_label, ') = ', confusion[(gold_label, guess_label,)] / total
  if gold_label == guess_label: 
    correct += 1.0

print 'accuracy = ', correct / total

