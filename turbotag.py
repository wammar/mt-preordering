#!/usr/bin/env python
import sys
import os
import subprocess as sp

MODEL = '/home/eschling/tools/TurboParser-2.1.0/models/hindi_tagger_full.model'
#MODEL = os.path.dirname(__file__)+'/models/english_proj_tagger.model'
TAGGER = '/home/eschling/tools/TurboParser-2.1.0'
os.environ['LD_LIBRARY_PATH'] = '/home/eschling/tool/TurboParser-2.1.0/deps/local/lib'
def main(model=MODEL, tagger=TAGGER):
    sys.stderr.write(model)
    sys.stderr.write(tagger)
    os.environ['LD_LIBRARY_PATH'] = tagger+'/deps/local/lib'    
    tagger = sp.Popen([tagger+'/src/tagger/TurboTagger', '--test', '--file_model='+model,
        '--file_test=/dev/stdin', '--file_prediction=/dev/stdout'],
        stdin=sp.PIPE, stdout=sp.PIPE)

    def tag(words):
        tagger.stdin.write('\n'.join('{}\t_'.format(word) for word in words)+'\n\n')
        tagger.stdin.flush()
        tags = []
        line = tagger.stdout.readline()
        while line != '\n':
            tags.append(line.split()[1])
            line = tagger.stdout.readline()
        assert len(words) == len(tags)
        return ' '.join(tags)

    for line in sys.stdin:
        sentence = line[:-1]
        print('{} ||| {}'.format(sentence, tag(sentence.split())))

if __name__ == '__main__':
    if len(sys.argv)==3:
      sys.stderr.write(' '.join(sys.argv))
      main(sys.argv[1],sys.argv[2])
    else:
      main()

