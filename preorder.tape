#!/usr/bin/env ducttape

global {
  ducttape_experimental_submitters=enable
  ducttape_experimental_imports=enable
  ducttape_experimental_packages=true

  # options
  sym_heuristic=(SymHeuristic:
                      grow_diag_final_and="grow-diag-final-and"
                      grow_diag_final="grow-diag-final"
                      grow_diag="grow-diag"
                      intersect="intersect"
                      union="union")
  
  l1=(L1: thousand=1000  
          hundred=100
          ten=10
          one=1
          point_one=0.1
          point_o_one=0.01
          zero=0)

  l2=(L2: thousand=1000  
          hundred=100
          ten=10
          one=1
          point_one=0.1
          point_o_one=0.01
          zero=0)

}

# clone TurboParser and download trained models for tagging and parsing English
package turboparser :: .versioner=git .repo="https://github.com/andre-martins/TurboParser.git" .ref=HEAD {
  ./install_deps.sh
  ./configure && make && make install
  export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:`pwd;`/deps/local/lib:"
}

task ProcessSource : turboparser
:: cdec_dir=@
:: tag_model=(Language: hi=$tag_model_hi de=$tag_model_de)
:: parse_model=(Language: hi=$parse_model_hi de=$tag_model_de)
:: fine2coarse=(Language: hi=$fine2coarse de=$de_negra_map)
:: preordering_home=@
< corpus=(Language: hi=(Corpus: train=$corpus dev=$dev_set) de=(Corpus: train=$corpus_de dev=$dev_de))
> conll_parse
> tags
{
  cat $corpus | $cdec_dir/corpus/cut-corpus.pl 1 | $preordering_home/turbotag.py $tag_model $turboparser > $tags
  cat $tags | $preordering_home/turboparse.py -m $parse_model -t $turboparser --coarse $fine2coarse > conll_parse_nonprojective
  python $preordering_home/projectivize_trees.py -n conll_parse_nonprojective -p $conll_parse
}

task ClusterSource
:: clusterize=@
< corpus=(Language: hi=(Corpus: train=$corpus dev=$dev_set) de=(Corpus: train=$corpus_de dev=$dev_de))
< cluster_paths=(Language: hi=$cluster_path_hi de=$cluster_path_de)
> cluster_source
{
  cat $corpus | $clusterize $cluster_paths > $cluster_source
}

task FastAlignS2T
    > alignment
    :: corpus=(Language: hi=$corpus de=$corpus_de)
    :: cdec_dir=@
    #:: .submitter=torque_shared .walltime="12:00:00" .cpus=1 .vmem=32g .q=shared 
{
  $cdec_dir/word-aligner/fast_align -i $corpus -d -v -o > $alignment
}

task FastAlignT2S
    > alignment
    :: corpus=(Language: hi=$corpus de=$corpus_de)
    :: cdec_dir=@
   # :: .submitter=torque_shared .walltime="12:00:00" .cpus=1 .vmem=32g .q=shared
 {
  $cdec_dir/word-aligner/fast_align -i $corpus -d -v -o -r > $alignment
}


task GizaAlignS2T
    > alignment
    > output_dir
    :: corpus=@
    :: giza_bin=@
    :: moses_train_script=@
    :: cores=@
    :: src=@
    :: tgt=@
    :: cdec_dir=@
  #  :: .submitter=torque_normal .walltime="12:00:00" .cpus=1 .vmem=32g .q=normal 
{
  cp $corpus corpus
  $cdec_dir/corpus/cut-corpus.pl 1 $corpus > corpus.$src
  $cdec_dir/corpus/cut-corpus.pl 2 $corpus > corpus.$tgt

  $moses_train_script --first-step 1 --last-step 3 --parallel --root-dir $output_dir --corpus corpus --f $src --e $tgt --external-bin-dir $giza_bin --mgiza $giza_bin --mgiza-cpus=$cores --alignment srctotgt 
  cp $output_dir/model/aligned.srctotgt $alignment
}

task Symmetrize
    < s2tAlignment=(Aligner:
                      giza=$alignment@GizaAlignS2T
                      giza_none=$alignment@GizaAlignS2T
                      none_giza=$alignment@GizaAlignT2S
                      fast=$alignment@FastAlignS2T
                      fast_none=$alignment@FastAlignS2T
                      none_fast=$alignment@FastAlignT2S)
    < t2sAlignment=(Aligner:
                      giza=$alignment@GizaAlignT2S
                      giza_none=$alignment@GizaAlignS2T
                      none_giza=$alignment@GizaAlignT2S
                      fast=$alignment@FastAlignT2S
                      fast_none=$alignment@FastAlignS2T
                      none_fast=$alignment@FastAlignT2S)
    > alignment
    :: sym_heuristic=@
    :: cdec_dir=@
   # :: .submitter=torque_shared .walltime="01:00:00" .cpus=1 .vmem=2g .q=shared 
{
  $cdec_dir/utils/atools -i $s2tAlignment -j $t2sAlignment -c $sym_heuristic > $alignment
}

task GizaAlignT2S
    < corpus=@
    < output_dir=$output_dir@GizaAlignS2T
    > alignment
    :: giza_bin=@
    :: moses_train_script=@
    :: cores=@
    :: src=@
    :: tgt=@
    :: cdec_dir=@
  #  :: .submitter=torque_normal .walltime="12:00:00" .cpus=32 .vmem=32g .q=normal
 {
  cp $corpus corpus
  $cdec_dir/corpus/cut-corpus.pl 1 $corpus > corpus.$src
  $cdec_dir/corpus/cut-corpus.pl 2 $corpus > corpus.$tgt

  $moses_train_script --first-step 3 --last-step 3 --parallel --root-dir $output_dir --corpus corpus --f $src --e $tgt --external-bin-dir $giza_bin --mgiza $giza_bin --mgiza-cpus=$cores --alignment tgttosrc 
  cp $output_dir/model/aligned.tgttosrc $alignment
}

task InducePairwiseReordering
 :: corpus=(Language: hi=(Corpus: train=$corpus dev=$dev_set) de=(Corpus: train=$corpus_de dev=$dev_de))
 :: preordering_home=@
 :: use_alignments=(Corpus: train=yes dev=no)
 < parses=(Corpus: train=(Language: hi=$conll_parse@ProcessSource[Corpus:train] de=$parses_de)
                   dev=$conll_parse@ProcessSource[Corpus:dev]) 
 < alignment=$alignment@Symmetrize
 > reorderings
 > potentials
{
  if [[ $use_alignments == no ]]; then
    echo "i'm not going to use alignments"
    python $preordering_home/induce_pairwise_reordering.py -p $parses -ir $reorderings -pr $potentials
  else
    echo "i'm going to use alignments"
    python $preordering_home/induce_pairwise_reordering.py  -a $alignment -p $parses -ir $reorderings -pr $potentials
  fi
}

task Evaluate
{
}

task ExtractDeletionFeatures
 :: preordering_home=@
 :: cdec_dir=@
 < cluster_source=@ClusterSource
# < training
 < parses=(Corpus:  train=(Language: hi=$conll_parse@ProcessSource[Corpus:train] de=$parses_de)
                    dev=$conll_parse@ProcessSource[Corpus:dev])
 < corpus=(Language: hi=(Corpus: train=$corpus dev=$dev_set) de=(Corpus: train=$corpus_de dev=$dev_de))
 > features
 > responses
 > log {
  $cdec_dir/corpus/cut-corpus.pl 1 $corpus > source
  python $preordering_home/extract_deletion_features.py -s source -d $parses -t $training -f $features -r $responses -c $cluster_source > $log
  rm source
}

task ExtractLeftRightClassifierFeatures
 :: preordering_home=@
 :: add_relation=(RelationFeatures: yes='--extra' no='')
 :: cdec_dir=@
 < cluster_source=@ClusterSource
 < training=(Corpus: train=$reorderings@InducePairwiseReordering[Corpus:train]
                     dev=$potentials@InducePairwiseReordering[Corpus:dev])
 < parses=(Corpus:  train=(Language: hi=$conll_parse@ProcessSource[Corpus:train] de=$parses_de)
                    dev=$conll_parse@ProcessSource[Corpus:dev])
 < corpus=(Language: hi=(Corpus: train=$corpus dev=$dev_set) de=(Corpus: train=$corpus_de dev=$dev_de))
 > features
 > responses
 > log 
{
  $cdec_dir/corpus/cut-corpus.pl 1 $corpus > source
  python $preordering_home/extract_features.py $add_relation -s source -d $parses -t $training -f $features -r $responses -c $cluster_source > $log
  rm source
}

task TrainLeftRightClassifier
 :: creg_bin=@
 :: wammar_utils_dir=@
 :: l1=@
 :: l2=@
 < features=$features@ExtractLeftRightClassifierFeatures
 < responses=$responses@ExtractLeftRightClassifierFeatures
 > features_train  >  features_dev >  features_test
 > responses_train >  responses_dev > responses_test
 > model
{
  python $wammar_utils_dir/vertical-split-parallel-corpus.py -ratio 100:1:1 -corpus-src $features -corpus-tgt $responses -train-src $features_train -train-tgt $responses_train -dev-src $features_dev -dev-tgt $responses_dev -test-src $features_test -test-tgt $responses_test
  $creg_bin -x $features_train -y $responses_train --l1 $l1 --l2 $l2 --tx $features_dev --ty $responses_dev --z $model -d 0.001 -e 0.1 

}

task ReorderSourceSentences
  :: l1=@
  :: l2=@
  :: dev_set=@
  :: cdec_dir=@
  :: preordering_home=@
  :: creg_bin=@
  :: wammar_utils_dir=@
  :: corpus=(Language: hi=$corpus de=$corpus_de)
  < train_parses=(Language: hi=$conll_parse@ProcessSource[Corpus:train]
                            de=$parses_de)
  < dev_word_pairs=$potentials@InducePairwiseReordering[Corpus:dev]
  < dev_features=$features@ExtractLeftRightClassifierFeatures[Corpus:dev]
  < dev_parses=$conll_parse@ProcessSource[Corpus:dev]
  < train_word_pairs_partial_order=$reorderings@InducePairwiseReordering[Corpus:train]
  < train_potentials=$potentials@InducePairwiseReordering[Corpus:train]
  < train_features=$features@ExtractLeftRightClassifierFeatures[Corpus:train]
  < train_responses=$responses@ExtractLeftRightClassifierFeatures[Corpus:train]
  > dev_reordered
  > dev_reordered_indexes
  > train_reordered
  > train_reordered_indexes
  > model
{
  # train partial reordering classifier
  $creg_bin -x $train_features -y $train_responses --l1 $l1 --l2 $l2 --z $model -e 0.1 -d 0.00001

  # classifying candidate word pairs
  $creg_bin --tx $dev_features -w $model -p -W > ids_responses
  # then gluing the prediction in the "reversed \t sent_id \t first_word \t second_word" format
  python $wammar_utils_dir/horizontal-split-parallel-corpus.py -d 'tab' -i $dev_word_pairs -o auto_responses sent_ids first_positions second_positions
  python $wammar_utils_dir/horizontal-split-parallel-corpus.py -d 'tab' -i ids_responses -o ids responses
  python $wammar_utils_dir/paste.py -i responses sent_ids first_positions second_positions -o dev_word_pairs_partial_order

  # reordering src side of train data
  $cdec_dir/corpus/cut-corpus.pl 1 $corpus > train_source
  $cdec_dir/corpus/cut-corpus.pl 2 $corpus > train_target
  python $preordering_home/reorder_src_sents.py -p $train_parses -s train_source -w $train_potentials -o train_reordered_source -oi $train_reordered_indexes
  python $wammar_utils_dir/paste.py -i train_reordered_source train_target -o $train_reordered -d " ||| "

  # reordering src side of dev data
  $cdec_dir/corpus/cut-corpus.pl 1 $dev_set > dev_source
  $cdec_dir/corpus/cut-corpus.pl 2 $dev_set > dev_target
  python $preordering_home/reorder_src_sents.py -p $dev_parses -s dev_source -w dev_word_pairs_partial_order -o dev_reordered_source -oi $dev_reordered_indexes
  python $wammar_utils_dir/paste.py -i dev_reordered_source dev_target -o $dev_reordered -d " ||| "

}

plan features {
  reach TrainLeftRightClassifier via (Aligner: fast) * (L1: point_one) * (L2: zero) * (SymHeuristic: intersect) * (Language: hi)
}

plan cluster {
  reach ClusterSource via (Corpus: dev) * (SymHeuristic: intersect) * (Language: de)
}

plan test_parser {
  reach ProcessSource via (Corpus: dev) * (SymHeuristic: intersect) * (Language: de)
}

plan Full 
{
  reach ReorderSourceSentences via (Aligner: fast) * (Corpus: dev) * (L1: point_one) * (L2: zero) * (SymHeuristic: intersect) * (Language: hi)
}
