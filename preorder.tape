#!/usr/bin/env ducttape

global {
  ducttape_experimental_submitters=enable
  ducttape_experimental_imports=enable
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
{
}

task ExtractReorderingClassifierFeatures
{
}

task TrainLeftRightClassifier
{
}

task TrainReorderingClassifier
{
}

task WordAlign
{
}

plan Full
{
  reach Test 
}