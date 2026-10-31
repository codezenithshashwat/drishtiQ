"""Validate study outputs without opening a test manifest or any test image."""
from common import *
from report import load_runs

def run():
    g,seg,ann,allowed=prepare();guard(allowed);checks=[]
    def add(name,ok,detail):checks.append(dict(check=name,status='PASS' if ok else 'FAIL',detail=str(detail)))
    trusted=json.loads((ROOT/'outputs/metrics/idrid_integrity_resolution_raw_after.json').read_text())
    add('raw_metadata_matches_integrity_stage',raw_stat()=={k:v[:2] for k,v in trusted.items()},'All raw paths, sizes and mtime_ns; no test pixels read for rehashing')
    scope=json.loads((OUT/'selection_scope.json').read_text())
    add('test_access_disabled',not scope['grading_test_manifest_opened'] and not scope['grading_test_pixels_opened'] and scope['grading_test_evaluations']==0,'Runner has no test-evaluation entry point; audit hook blocks test and unregistered raw reads')
    expected=g.set_index('sample_key');rows,details=load_runs();grade_count=0
    for tag,r in details.items():
        if r.get('task')!='grading':continue
        p=pd.read_csv(OUT/tag/'validation_predictions.csv');keys=set(p.sample_key);correct=keys<=set(g.sample_key) and p.sample_key.nunique()==len(p)
        correct=correct and expected.loc[p.sample_key,'fold'].eq(r['fold']).all() and expected.loc[p.sample_key,'DR_grade'].to_numpy().tolist()==p.DR_grade.tolist()
        probs=p[['p'+str(i) for i in range(5)]].values
        correct=correct and np.isfinite(probs).all() and (probs>=0).all() and (probs<=1).all() and np.allclose(probs.sum(1),1,atol=1e-5)
        computed,_,_=metrics(p.DR_grade.values,probs)
        correct=correct and all(np.isclose(computed[k],r[k],atol=1e-6) for k in ['macro_f1','qwk','accuracy','balanced_accuracy'])
        add('predictions_'+tag,correct,'Development membership, fold, labels, probabilities and recomputed metrics');grade_count+=1
        add('finite_training_'+tag,np.isfinite(pd.read_csv(OUT/tag/'history.csv').train_loss).all(),'Finite fitting history; no invalid epoch hidden in checkpoint selection')
        add('config_'+tag,(CFG/(tag+'.json')).exists() and (CKPT/(tag+'.pt')).exists(),'Recorded fit configuration and checkpoint present')
    masks=pd.read_csv(ROOT/'outputs/metrics/idrid_segmentation_metadata.csv');seg_count=0
    expected_seg=ann[ann.sample_key.isin(seg.loc[seg.role=='validation','sample_key'])&ann.annotation_available&ann.annotation_type.isin(['MA','HE','EX','SE'])]
    expected_pairs=set(zip(expected_seg.sample_key,expected_seg.annotation_type))
    areas={}
    for r in expected_seg.itertuples():
        m=masks[(masks.split==r.original_split)&(masks.image_id==r.image_id)&(masks.mask_type==r.annotation_type)]
        areas[(r.sample_key,r.annotation_type)]=int(m.iloc[0].positive_pixels)
    for path in list(OUT.glob('seg_*/result.json'))+list(OUT.glob('ma_*/result.json')):
        r=json.loads(path.read_text());p=pd.read_csv(path.parent/'native_validation_metrics.csv');pairs=set(zip(p.sample_key,p.annotation_type))
        history=pd.read_csv(path.parent/'history.csv')
        if r.get('study_role')=='exploratory_mixed_precision_probe':
            add('probe_excluded_from_primary_'+r['tag'],True,'Exploratory AMP probe not in primary MA comparison; '+str(r.get('failure_reason','finite training, but matched primary suite rerun in FP32')))
            continue
        add('finite_training_'+r['tag'],np.isfinite(history.train_loss).all(),'Nonfinite losses invalidate a run; they cannot be scored as empty-mask predictions')
        target_pairs={p for p in expected_pairs if p[1]=='MA'} if r.get('task')=='segmentation_MA_specialist' else expected_pairs
        correct=pairs==target_pairs and not p.duplicated(['sample_key','annotation_type']).any()
        correct=correct and (p[['tp','fp','fn']]>=0).all().all() and all(int(x.tp+x.fn)==areas[(x.sample_key,x.annotation_type)] for x in p.itertuples())
        correct=correct and all(x.matched_components<=min(x.true_components,x.predicted_components) for x in p.itertuples())
        add('native_segmentation_'+r['tag'],correct,'Every available validation annotation once; missing supervision excluded; native reference areas match audit; component matching bounded');seg_count+=1
        add('config_'+r['tag'],(CFG/(r['tag']+'.json')).exists() and (CKPT/(r['tag']+'.pt')).exists(),'Recorded fit configuration and checkpoint present')
    accesses=[]
    if (OUT/'raw_image_access.jsonl').exists():accesses=[json.loads(line) for line in (OUT/'raw_image_access.jsonl').read_text().splitlines()]
    allowed_paths=set(p.replace('\\','/') for p in allowed)
    add('recorded_raw_image_reads_in_scope',all(x['filepath'].replace('\\','/') in allowed_paths and '/b. Testing Set/' not in x['filepath'].replace('\\','/') for x in accesses),f'{len(accesses)} raw image cache source access records; audit hook separately enforces all other image/mask reads')
    add('no_image_content_overlap_grading_folds',g.content_hash.nunique()==len(g),'404 unique development contents; patient independence still unknown')
    add('segmentation_split_before_patches',not set(seg.loc[seg.role=='train','image_content_hash'])&set(seg.loc[seg.role=='validation','image_content_hash']),'Native image identities, not extracted patches, define train/validation')
    add('grader_four_families_tested',set(rows.architecture)==set(MODELS),'All required grading families have actual results')
    frozen_initial=rows[(rows.stage=='frozen')&(rows.resolution==224)&rows.preprocessing.eq('baseline')]
    add('frozen_three_folds_two_seeds_all_families',len(frozen_initial)==24 and all(len(frozen_initial[frozen_initial.architecture==m])==6 for m in MODELS),'24 head fits, not 24 architecture families')
    common_screen=rows[(rows.stage=='partial_fine_tuning')&(rows.resolution==224)&(rows.fold==0)&rows.preprocessing.eq('baseline')&rows.augmentation.eq('none')&rows.objective.eq('ce')]
    add('controlled_common_screen_two_seeds_all_families',len(common_screen)==8,'Same development fold, seeds, input, objective and budget')
    segmodels={json.loads(p.read_text())['architecture'] for p in OUT.glob('seg_*/result.json')}
    add('segmenter_four_families_tested',segmodels=={'Unet','UnetPlusPlus','DeepLabV3Plus','Segformer'},segmodels)
    primary_ma=[json.loads(p.read_text()) for p in OUT.glob('ma_*/result.json') if json.loads(p.read_text()).get('precision')=='FP32' and json.loads(p.read_text()).get('valid_for_comparison')]
    add('matched_MA_FP32_suite_complete',{(r['mode'],r['seed']) for r in primary_ma}=={(m,s) for m in ['full','patch'] for s in [17,29]},'Two input modes × two seeds; exploratory AMP probes excluded')
    frame=pd.DataFrame(checks);frame.to_csv(OUT/'study_validation_checks.csv',index=False)
    manifests=[OUT/'grading_folds.csv',OUT/'segmentation_development_split.csv',OUT/'selection_scope.json',OUT/'development_inputs_lock.json']
    weights=list((ROOT/'models/pretrained').rglob('*.pth'))+list((ROOT/'models/pretrained').rglob('*.safetensors'))
    checkpoint_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in CKPT.glob('*.pt')}
    dump(OUT/'checkpoint_and_input_hashes.json',{'checkpoints_sha256':checkpoint_hashes,'development_scope_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in manifests},'pretrained_weights_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in weights},'test_manifest_hashed_or_opened':False})
    for path in OUT.rglob('*.csv'):pd.read_csv(path)
    image_count=0
    for path in FIG.glob('*.png'):
        with Image.open(path) as im:im.verify();image_count+=1
    probes=[json.loads(p.read_text()) for p in OUT.glob('ma_*/result.json') if json.loads(p.read_text()).get('study_role')=='exploratory_mixed_precision_probe']
    summary={'grading_fits':grade_count,'validated_segmentation_fits':seg_count,'unranked_MA_AMP_probes':len(probes),'excluded_numerically_failed_probes':sum(not r.get('valid_for_comparison',True) for r in probes),'checks':frame.status.value_counts().to_dict(),'figures_decoded':image_count,'test_evaluations':0,'test_manifest_opened':False,'patient_independence':'UNKNOWN','external_validation':'NOT PERFORMED'}
    dump(OUT/'study_validation_summary.json',summary);print(json.dumps(summary,indent=2))
    assert not frame.status.eq('FAIL').any(),'See study_validation_checks.csv for failed checks'

if __name__=='__main__':run()
