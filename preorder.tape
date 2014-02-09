#!/usr/bin/env ducttape

global {
  ducttape_experimental_submitters=enable
  ducttape_experimental_imports=enable

  ducttape_output="/usr2/home/wammar/mt-preordering/hi-en-exp000/"
  preordering_home="/usr0/home/wammar/mt-preordering/"
  parses="/usr2/home/sswayamd/wmt/wmt_test.output.conll"
  corpus="/usr1/home/wammar/parallel/training/parallel.hi-en"
  giza_bin="/opt/tools/mgizapp-0.7.2/bin"
  moses_train_script="/home/wammar/mosesdecoder/scripts/training/train-model.perl"
  mkcls_bin="/mal0/tools/mosesdecoder/bin/mkcls"
  cdec_dir="/home/wammar/cdec/"
  creg_bin="./creg/bin/gcc-4.7/release/threading-multi/creg"
  cores=16
  src="hi"
  tgt="en"

  sym_heuristic=(SymHeuristic:
                      grow_diag_final_and="grow-diag-final-and"
                      grow_diag_final="grow-diag-final"
                      grow_diag="grow-diag"
                      intersect="intersect"
                      union="union")

}

task GizaAlignS2T
    < corpus=@
    > alignment
    > output_dir
    :: giza_bin=@
    :: moses_train_script=@
    :: cores=@
    :: src=@
    :: tgt=@
    :: cdec_dir=@
  #  :: .submitter=torque_normal .walltime="12:00:00" .cpus=1 .vmem=32g .q=normal 
{

  $cdec_dir/corpus/cut-corpus.pl 1 $corpus > $corpus.$src
  $cdec_dir/corpus/cut-corpus.pl 2 $corpus > $corpus.$tgt

  $moses_train_script --first-step 1 --last-step 3 --parallel --root-dir $output_dir --corpus $corpus --f $src --e $tgt --external-bin-dir $giza_bin --mgiza $giza_bin --mgiza-cpus=$cores --alignment srctotgt 
  cp $output_dir/model/aligned.srctotgt $alignment
}

task Symmetrize
    < s2tAlignment=(Aligner:
                      giza=$alignment@GizaAlignS2T
                      giza_none=$alignment@GizaAlignS2T
                      none_giza=$alignment@GizaAlignT2S)
    < t2sAlignment=(Aligner:
                      giza=$alignment@GizaAlignT2S
                      giza_none=$alignment@GizaAlignS2T
                      none_giza=$alignment@GizaAlignT2S)
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

  $cdec_dir/corpus/cut-corpus.pl 1 $corpus > $corpus.$src
  $cdec_dir/corpus/cut-corpus.pl 2 $corpus > $corpus.$tgt

  $moses_train_script --first-step 3 --last-step 3 --parallel --root-dir $output_dir --corpus $corpus --f $src --e $tgt --external-bin-dir $giza_bin --mgiza $giza_bin --mgiza-cpus=$cores --alignment tgttosrc 
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

task DependencyParse
{
}

task Evaluate
{
}

task LeftRightClassify
{
}

task ReorderingClassify
{
}

task ExtractLeftRightClassifierFeatures
 :: preordering_home=@
 :: test=(Test: yes='--test' no='')
 :: cdec_dir=@
 < training=$reorderings@InducePairwiseReordering
 < parses=@
 < corpus=@
 > features
 > responses
 > log 
{
  $cdec_dir/corpus/cut-corpus.pl 1 $corpus > source
  python $preordering_home/extract_features.py $test -s source -d $parses -t $training -f $features -r $responses > $log
  rm source
}

task TrainLeftRightClassifier
 < features=$features@ExtractLeftRightClassifierFeatures
 < responses=$responses@ExtractLeftRightClassifierFeatures
 > model
{
  /usr0/home/wammar/creg/bin/gcc-4.7/release/threading-multi/creg -x $features -y $responses  --l1 1000
}

plan features {
  reach TrainLeftRightClassifier via (Test: no) * (Aligner: giza)
}

plan full 
{
  reach Test via (Aligner: giza) 
}
