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
:: tag_model=$tag_model_hi
:: parse_model=$parse_model_hi
:: fine2coarse=@
:: preordering_dir=@
< corpus=(Corpus: train=$corpus dev=$tune_set)
> conll_parse
> tags
{
  cat $corpus | $cdec_dir/corpus/cut-corpus.pl 1 | $preordering_dir/turbotag.py $tag_model $turboparser > $tags
  cat $tags | $preordering_dir/turboparse.py -m $parse_model -t $turboparser --coarse $fine2coarse > $conll_parse
}

task ClusterSource
:: clusterize=@
< corpus=(Corpus: train=$corpus dev=$tune_set)
< cluster_paths=$cluster_path_hi
> cluster_source
{
  cat $corpus | $clusterize $cluster_paths > $cluster_source
}

task FastAlignS2T
    > alignment
    :: corpus=@
    :: cdec_dir=@
    #:: .submitter=torque_shared .walltime="12:00:00" .cpus=1 .vmem=32g .q=shared 
{
  $cdec_dir/word-aligner/fast_align -i $corpus -d -v -o > $alignment
}

task FastAlignT2S
    > alignment
    :: corpus=@
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
 :: corpus=@
 :: parses=@
 :: preordering_home=@
 < alignment=$alignment@Symmetrize
 > reorderings
{
  python $preordering_home/induce_pairwise_reordering.py -a $alignment -p $parses -o $reorderings
}

task Evaluate
{
}

task ExtractDeletionFeatures
 :: preordering_home=@
 :: cdec_dir=@
 < cluster_source=@ClusterSource
# < training
 < parses=@
 < corpus=@
 > features
 > responses
 > log {
  $cdec_dir/corpus/cut-corpus.pl 1 $corpus > source
  python $preordering_home/extract_deletion_features.py -s source -d $parses -t $training -f $features -r $responses -c $cluster_source > $log
  rm source
}

task ExtractLeftRightClassifierFeatures
 :: preordering_home=@
 :: test=(Test: no='' yes='--test')
 :: add_relation=(RelationFeatures: yes='--extra' no='')
 :: cdec_dir=@
 < cluster_source=@ClusterSource
 < training=$reorderings@InducePairwiseReordering
 < parses=@
 < corpus=@
 > features
 > responses
 > log 
{
  $cdec_dir/corpus/cut-corpus.pl 1 $corpus > source
  python $preordering_home/extract_features.py $add_relation $test -s source -d $parses -t $training -f $features -r $responses -c $cluster_source > $log
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
  $creg_bin -x $features_train -y $responses_train --l1 $l1 --l2 $l2 --tx $features_dev --ty $responses_dev --z $model -e 0.1 -d 0.00001
}

task ReorderSourceSentences
  :: l1=@
  :: l2=@
  :: tune_set=@
  :: cdec_dir=@
  :: preordering_home=@
  :: creg_bin=@
  :: wammar_utils_dir=@
  < cluster_source=@ClusterSource
  < tune_parses=$conll_parse@ProcessSource
  < train_features=$features@ExtractLeftRightClassifierFeatures
  < train_responses=$responses@ExtractLeftRightClassifierFeatures
  > log
  > reordered
  > model
{
  $cdec_dir/corpus/cut-corpus.pl 1 $tune_set > source

  python $preordering_home/induce_pairwise_reordering.py -p $tune_parses -o word_pairs --test
  python $preordering_home/extract_features.py --test -s source -d $tune_parses -t word_pairs -f features -r empty_responses  -c $cluster_source > $log
  $creg_bin -x $train_features -y $train_responses --l1 $l1 --l2 $l2 --tx features --z $model -e 0.1 -d 0.00001 > ids_responses
  python $wammar_utils_dir/horizontal-split-parallel-corpus.py -d 'tab' -i word_pairs -o auto_responses sent_ids first_positions second_positions
  python $wammar_utils_dir/horizontal-split-parallel-corpus.py -d 'tab' -i ids_responses -o ids responses
  python $wammar_utils_dir/paste.py -i responses sent_ids first_positions second_positions -o word_pairs_partial_order
  python $preordering_home/reorder_src_sents.py -p $tune_parses -s source -w word_pairs_partial_order -o $reordered
}

plan features {
  reach TrainLeftRightClassifier via (Test: no) * (Aligner: fast) * (L1: point_one) * (L2: zero) * (RelationFeatures: *)
}

plan cluster {
  reach ClusterSource via (Corpus: dev)
}

plan test_parser {
  reach ProcessSource via (Corpus: dev)
}

plan Full 
{
  reach ReorderSourceSentences via (Aligner: fast) * (Corpus: dev) 
}

