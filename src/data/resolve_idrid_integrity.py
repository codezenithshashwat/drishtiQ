"""Resolve experimental permissions from existing IDRiD audit evidence; never write raw.

Run from project root: .venv\Scripts\python.exe src\data\resolve_idrid_integrity.py
"""
from pathlib import Path
import hashlib,io,json,sys,zipfile
import numpy as np
import pandas as pd
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
MET=ROOT/'outputs/metrics'
DOC=ROOT/'docs/dataset_audit'
MAN=ROOT/'data/interim/manifests'
RAW=ROOT/'data/raw'
POLICY='IDRID_PRIMARY_C_PLUS_D_V1'
SOURCES=['image_metadata','grading_labels','content_label_conflicts','cross_task_mapping',
         'cross_task_similarity_candidates','segmentation_metadata','annotation_coverage',
         'resolution_summary','ma_component_topology_summary','archive_extraction_comparison',
         'inventory','localization_metadata','mask_encoding_audit','integrity_checks']

def digest(data):return hashlib.sha256(data).hexdigest()
def filehash(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def relative(p):return Path(p).as_posix()
def snapshot():
    return {p.relative_to(RAW).as_posix():[p.stat().st_size,p.stat().st_mtime_ns,filehash(p)] for p in sorted(RAW.rglob('*')) if p.is_file()}
def csvbytes(df):return df.to_csv(index=False,lineterminator='\n',float_format='%.10g').encode('utf-8')
def table(df):
    return '| '+' | '.join(map(str,df.columns))+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in row)+' |' for row in df.itertuples(index=False,name=None))
def key(split,ident):return f'idrid:grading:{split}:{ident}'
def load():
    d={n:pd.read_csv(MET/f'idrid_{n}.csv') for n in SOURCES}
    for frame in d.values():
        for col in ['path','source','segmentation_path','grading_path','extracted_path']:
            if col in frame:frame[col]=frame[col].map(lambda x:relative(x) if pd.notna(x) else x)
    return d

def build(d):
    """Pure deterministic construction, called twice before any manifest is written."""
    images=d['image_metadata'];grading=images[images.component=='Disease Grading'].merge(d['grading_labels'],on=['split','image_id'],validate='one_to_one',suffixes=('','_label'))
    grading=grading.rename(columns={'path':'filepath','split':'original_split','decoded_sha256':'content_hash','sha256':'file_sha256'})
    grading['sample_key']=[key(s,i) for s,i in zip(grading.original_split,grading.image_id)]
    grading['duplicate_group']='';grading['duplicate_status']='unique';grading['inclusion_status']='included';grading['exclusion_reason']='';grading['canonical_sample_key']=grading.sample_key;grading['policy_version']=POLICY
    groups=[]
    for h,grp in grading.groupby('content_hash',sort=True):
        if len(grp)<2:continue
        conflict=grp.DR_grade.nunique()!=1 or grp.DME_label.nunique()!=1
        group='dup_'+h;idx=grading.content_hash.eq(h)
        grading.loc[idx,'duplicate_group']=group
        if conflict:
            grading.loc[idx,'duplicate_status']='conflicting_labels'
            grading.loc[idx,'inclusion_status']='excluded';grading.loc[idx,'exclusion_reason']='conflicting_DR_or_DME_labels_all_group_members_quarantined';grading.loc[idx,'canonical_sample_key']=''
        else:
            canonical=grp.assign(priority=grp.original_split.map({'test':0,'train':1})).sort_values(['priority','image_id','filepath']).iloc[0].sample_key
            grading.loc[idx,'canonical_sample_key']=canonical
            grading.loc[idx,'duplicate_status']='agreeing_duplicate_canonical'
            other=idx & ~grading.sample_key.eq(canonical)
            grading.loc[other,'duplicate_status']='agreeing_duplicate_noncanonical';grading.loc[other,'inclusion_status']='excluded';grading.loc[other,'exclusion_reason']='redundant_exact_duplicate_labels_agree'
        groups.append(dict(duplicate_group=group,content_hash=h,grading_members=len(grp),DR_labels_agree=grp.DR_grade.nunique()==1,DME_labels_agree=grp.DME_label.nunique()==1,labels_agree=not conflict,crosses_train_test=grp.original_split.nunique()>1,creates_exact_split_leakage=grp.original_split.nunique()>1,creates_label_conflict=conflict))
    groupframe=pd.DataFrame(groups)
    cols=['sample_key','image_id','filepath','original_split','DR_grade','DME_label','content_hash','file_sha256','duplicate_group','duplicate_status','inclusion_status','exclusion_reason','canonical_sample_key','policy_version']
    grading=grading[cols].sort_values(['original_split','image_id','filepath']).reset_index(drop=True)
    included=grading[grading.inclusion_status=='included']
    manifests={f'data/interim/manifests/idrid_grading_{s}_clean.csv':included[included.original_split==s].copy() for s in ['train','test']}
    manifests['data/interim/manifests/idrid_grading_excluded.csv']=grading[grading.inclusion_status=='excluded'].copy()
    manifests['data/interim/manifests/idrid_grading_official_secondary.csv']=grading.assign(inclusion_status='secondary_official_only',policy_version='OFFICIAL_UNCHANGED_SECONDARY_WITH_CAVEATS')
    resolution=[]
    for info in groups:
        members=images[images.decoded_sha256==info['content_hash']].sort_values(['component','split','image_id','path'])
        for row in members.itertuples():
            label=grading[(grading.content_hash==info['content_hash'])&(grading.original_split==row.split)&(grading.image_id==row.image_id)]
            assert len(label)==1,'Cannot assign supporting label to exact alias unambiguously'
            r=label.iloc[0]
            resolution.append(dict(info,component=row.component,filepath=row.path,original_split=row.split,image_id=row.image_id,file_sha256=row.sha256,DR_grade=int(r.DR_grade),DME_label=int(r.DME_label),label_source_sample_key=r.sample_key,label_source='grading CSV matched by split/ID AND verified content',primary_content_permitted=not info['creates_label_conflict'],grading_row_status=r.inclusion_status,exclusion_reason=r.exclusion_reason,canonical_sample_key=r.canonical_sample_key))
    resolution=pd.DataFrame(resolution)
    # Keep all candidate evidence, but only exact identity may be propagated automatically.
    review=d['cross_task_similarity_candidates'].copy()
    review['correspondence_tier']=review.match_status.map({'verified_exact':'exact_verified_correspondence','high_similarity_candidate':'strongly_supported_candidate_not_verified','unresolved_candidate':'uncertain_correspondence'})
    review['automatic_multitask_permission']=False;review['review_disposition']='manual_identity_review_required_no_automatic_merge'
    multitask=[]
    for idx,r in review.iterrows():
        if r.match_status!='verified_exact':continue
        seg=images[(images.component=='Segmentation')&(images.path==r.segmentation_path)].iloc[0]
        clean=included[included.content_hash==seg.decoded_sha256]
        if len(clean)!=1:
            review.loc[idx,'review_disposition']='blocked_quarantined_or_ambiguous_grading_content';continue
        clean=clean.iloc[0]
        if clean.original_split!=r.segmentation_split:
            review.loc[idx,'review_disposition']='blocked_cross_task_split_mismatch';continue
        review.loc[idx,'automatic_multitask_permission']=True;review.loc[idx,'review_disposition']='permitted_exact_content_same_split_clean_grading'
        multitask.append(dict(sample_key=f'idrid:multitask:{r.segmentation_split}:{r.segmentation_id}',grading_sample_key=clean.sample_key,segmentation_sample_key=f'idrid:segmentation:{r.segmentation_split}:{r.segmentation_id}',segmentation_id=r.segmentation_id,segmentation_filepath=r.segmentation_path,grading_filepath=clean.filepath,original_split=clean.original_split,DR_grade=int(clean.DR_grade),DME_label=int(clean.DME_label),content_hash=clean.content_hash,correspondence_tier='exact_verified_correspondence',policy_version=POLICY))
    multi=pd.DataFrame(multitask,columns=['sample_key','grading_sample_key','segmentation_sample_key','segmentation_id','segmentation_filepath','grading_filepath','original_split','DR_grade','DME_label','content_hash','correspondence_tier','policy_version'])
    manifests['data/interim/manifests/idrid_multitask_exact_clean.csv']=multi
    annotation=[]
    for image in images[images.component=='Segmentation'].sort_values(['split','image_id']).itertuples():
        for typ in ['MA','HE','EX','SE','OD']:
            matches=d['segmentation_metadata'][(d['segmentation_metadata'].split==image.split)&(d['segmentation_metadata'].image_id==image.image_id)&(d['segmentation_metadata'].mask_type==typ)]
            assert len(matches)<=1
            available=len(matches)==1;mask=matches.iloc[0] if available else None
            empty=bool(available and mask.readable and mask.binary and int(mask.positive_pixels)==0)
            annotation.append(dict(sample_key=f'idrid:segmentation:{image.split}:{image.image_id}',image_id=image.image_id,original_split=image.split,image_filepath=image.path,image_content_hash=image.decoded_sha256,annotation_type=typ,annotation_state='verified_empty_annotation' if empty else 'annotation_available' if available else 'annotation_unavailable',annotation_available=available,supervision_valid=available,verified_empty_annotation=empty,positive_pixels=int(mask.positive_pixels) if available else None,mask_filepath=mask.path if available else '',mask_file_sha256=mask.sha256 if available else '',mask_mode=mask['mode'] if available else '',foreground_decoding='nonzero palette index' if available and mask['mode']=='P' else 'any RGB color >0; alpha excluded' if available else 'not applicable',missing_value_representation='not_missing' if available else 'null_target_and_availability_false_not_zero_mask'))
    annotations=pd.DataFrame(annotation)
    distributions=[]
    for stage,frame in [('official',grading),('clean',included),('excluded',grading[grading.inclusion_status=='excluded'])]:
        for split in ['train','test','all']:
            sub=frame if split=='all' else frame[frame.original_split==split]
            for target,values in [('DR_grade',range(5)),('DME_label',range(3))]:
                for value in values:distributions.append(dict(stage=stage,split=split,target=target,label=value,count=int((sub[target]==value).sum()),percent=float((sub[target]==value).mean()*100) if len(sub) else 0,total=len(sub)))
    distributions=pd.DataFrame(distributions)
    imbalance=[]
    for stage,frame in [('official',grading),('clean',included)]:
        for split in ['train','test','all']:
            sub=frame if split=='all' else frame[frame.original_split==split];cnt=sub.DR_grade.value_counts().reindex(range(5),fill_value=0)
            imbalance.append(dict(stage=stage,split=split,n=len(sub),majority_grades=json.dumps(cnt[cnt==cnt.max()].index.tolist()),minority_grades=json.dumps(cnt[cnt==cnt.min()].index.tolist()),max_min_ratio=float(cnt.max()/cnt.min()) if cnt.min() else np.inf,majority_percent=float(cnt.max()/len(sub)*100)))
    imbalance=pd.DataFrame(imbalance)
    candidates=[]
    train_hash=set(grading[grading.original_split=='train'].content_hash)
    for name,keep in [
        ('A_official_unchanged',pd.Series(True,index=grading.index)),
        ('B_drop_test_overlap',~(grading.original_split.eq('test')&grading.content_hash.isin(train_hash))),
        ('C_quarantine_all_conflicting_groups',~grading.duplicate_status.eq('conflicting_labels')),
        ('D_deduplicate_agreeing_groups_only',~grading.duplicate_status.eq('agreeing_duplicate_noncanonical')),
        ('PRIMARY_C_plus_D',grading.inclusion_status.eq('included'))]:
        sub=grading[keep];tr=sub[sub.original_split=='train'];te=sub[sub.original_split=='test']
        candidates.append(dict(policy=name,train=len(tr),test=len(te),excluded=len(grading)-len(sub),unique_contents=sub.content_hash.nunique(),exact_cross_split_groups=len(set(tr.content_hash)&set(te.content_hash)),known_conflicting_content_groups_still_included=sub[sub.duplicate_status.eq('conflicting_labels')].content_hash.nunique(),remaining_duplicate_groups=int((sub.groupby('content_hash').size()>1).sum())))
    metrics={
        'idrid_duplicate_resolution.csv':resolution,
        'idrid_duplicate_group_resolution.csv':groupframe,
        'idrid_segmentation_annotation_policy.csv':annotations,
        'idrid_cross_task_mapping_review.csv':review,
        'idrid_cleaning_distributions.csv':distributions,
        'idrid_cleaning_imbalance.csv':imbalance,
        'idrid_duplicate_policy_comparison.csv':pd.DataFrame(candidates),
        'idrid_cleaning_exclusions_summary.csv':grading[grading.inclusion_status=='excluded'].groupby(['original_split','exclusion_reason']).size().reset_index(name='count')}
    payload={p:csvbytes(frame) for p,frame in manifests.items()}
    payload.update({'outputs/metrics/'+p:csvbytes(frame) for p,frame in metrics.items()})
    return payload,dict(grading=grading,included=included,resolution=resolution,groups=groupframe,review=review,multi=multi,annotations=annotations,distributions=distributions,imbalance=imbalance,candidates=pd.DataFrame(candidates))

def archive_evidence(d,frames):
    """Selective archive checks only: duplicate photos and original grading tables."""
    sources={};evidence=[]
    for split,source in d['grading_labels'].groupby('split').source.first().items():
        p=ROOT/source;archive=RAW/'IDRiD/archives/B. Disease Grading.zip';member='/'.join(p.relative_to(RAW/'IDRiD/original/B. Disease Grading').parts)
        with zipfile.ZipFile(archive) as z:data=z.read(member)
        assert digest(data)==filehash(p),'Archive grading CSV differs from extraction'
        frame=pd.read_csv(io.BytesIO(data)).iloc[:,:3];frame.columns=['image_id','DR_grade','DME_label'];sources[split]=frame
    for r in frames['resolution'].itertuples():
        package='B. Disease Grading' if r.component=='Disease Grading' else 'C. Localization'
        archive=RAW/'IDRiD/archives'/(package+'.zip');p=ROOT/r.filepath;member='/'.join(p.relative_to(RAW/'IDRiD/original'/package).parts)
        with zipfile.ZipFile(archive) as z:data=z.read(member)
        with Image.open(io.BytesIO(data)) as im:
            im.load();decoded=digest(str((im.mode,im.size)).encode()+np.asarray(im).tobytes())
        label=sources[r.original_split].query('image_id == @r.image_id')
        assert len(label)==1
        label=label.iloc[0]
        evidence.append(dict(duplicate_group=r.duplicate_group,filepath=r.filepath,archive_filepath=archive.relative_to(ROOT).as_posix(),archive_member=member,archive_image_sha256=digest(data),expected_file_sha256=r.file_sha256,bytes_match=digest(data)==r.file_sha256,decoded_content_match=decoded==r.content_hash,archive_DR_grade=int(label.DR_grade),archive_DME_label=int(label.DME_label),labels_match_audit=int(label.DR_grade)==r.DR_grade and int(label.DME_label)==r.DME_label,source_scope='retained downloaded archives; publisher authenticity not independently established'))
    return pd.DataFrame(evidence)

def reports(d,f,checks,evidence):
    g=f['grading'];clean=f['included'];excluded=g[g.inclusion_status=='excluded'];dist=f['distributions'];imb=f['imbalance']
    review='# IDRiD label conflict review\n\n**No clinical label was adjudicated or corrected. Patient-level leakage cannot be fully audited from the publicly available identifiers.**\n\n'
    for r in f['groups'][f['groups'].creates_label_conflict].itertuples():
        rows=f['resolution'][(f['resolution'].duplicate_group==r.duplicate_group)&(f['resolution'].component=='Disease Grading')]
        review+=f'## Content {r.content_hash}\n\n'+table(rows[['filepath','original_split','image_id','file_sha256','DR_grade','DME_label']])+f'\n\nCrosses train/test: {r.crosses_train_test}. Identical bytes and decoded pixels carry contradictory '+('DR and/or DME labels' if not r.labels_agree else 'labels')+'. All grading members and any exact-content auxiliary aliases are quarantined from primary experiments. This establishes inconsistency, not which annotation is correct. Clinical/source-author review remains unresolved.\n\n'
    review+='## Archive evidence\n\nAll duplicate image members were selectively reread and decoded from the retained B/C ZIPs. Both original B grading CSVs were reread from ZIP bytes and matched against untouched extracted CSVs. Per-member hashes and original labels are in idrid_duplicate_archive_evidence.csv. All '+str(len(evidence))+' image-member comparisons passed byte identity, decoded identity and label correspondence. The train IDRiD_118 (DR 0, DME 0) / test IDRiD_064 (DR 3, DME 0) conflict therefore exists in these retained archives. This does not establish authenticity against an unavailable publisher checksum.\n\n## All six duplicate groups\n\n'+table(f['groups'])+'\n\nThe row-level resolution CSV includes every B/C image filepath, not only the grading aliases. Same-label groups retain train:IDRiD_073 and train:IDRiD_079 as deterministic canonical samples. The removed duplicate aliases retain their unchanged original labels in the exclusions manifest. No raw files were touched.\n'
    ma=d['resolution_summary'].query("mask_type == 'MA'").copy();ma['components_lost_percent']=100*ma.disappeared_components/ma.original_components
    resolution='# IDRiD resolution findings\n\nThis note preserves the completed audit experiment; no resizing experiment was rerun and no raw images were modified.\n\n'+table(ma[['target_width','original_components','retained_components','disappeared_components','components_retained_percent','components_lost_percent','area_relative_to_expected_percent']].round(6))+'\n\nAt width 224 (aspect-preserved height 149), 1,240 of 3,497 original eight-connected MA annotation regions disappeared: **35.458965%**. At that width 1,814 surviving source regions collapsed to one target pixel (see existing idrid_ma_component_topology_summary.csv). Aggregate normalized foreground area remained about 100.716% of expected, illustrating why area alone misses small-component loss.\n\nMethod: in-memory nearest-neighbor sampling of binary/component-ID masks; widths 2048, 1024, 512, 384, 224 with proportional rounded heights. Components are geometric annotation regions, not independently diagnosed biological lesions. This is sampling evidence, not predictive performance, clinical visibility or a physical lesion-size measurement.\n\nNo final input resolution, crop, augmentation or preprocessing strategy is selected.\n\n**Research question:** What input strategy preserves clinically important small-lesion information while retaining sufficient global retinal context and remaining computationally practical?\n'
    comparison=f['candidates'];summ=excluded.groupby(['original_split','exclusion_reason']).size().reset_index(name='count')
    policy=f'''# IDRiD experimental data policy — {POLICY}

**Patient-level leakage cannot be fully audited from the publicly available identifiers. Zero exact-image overlap is not proof of patient independence.**

## Primary protocol and permissions

Use only `data/interim/manifests/idrid_grading_train_clean.csv` as the model-development pool and `idrid_grading_test_clean.csv` as the held-out internal test. These contain {int(clean.original_split.eq('train').sum())} / {int(clean.original_split.eq('test').sum())} rows. Do not glob raw folders to obtain training data. No sample was moved between organizer partitions. A future validation partition must be prespecified within the clean training pool; this stage does not assign it. Test data must not guide tuning, early stopping, preprocessing choice or model selection. The test labels have been inspected for audit purposes; disclose this and avoid iterative outcome-driven test reuse.

Primary policy combines **C + D**: quarantine every member of any exact-content group whose DR OR DME labels disagree; then retain one canonical sample only for groups where BOTH labels agree. Even a DME-only conflict is quarantined for the primary grading protocol, rather than permitting task-specific inconsistent inclusion. No clinical label has been selected, repaired, averaged or inferred. Quarantine is a manifest permission, not deletion. Any exact image alias in localization/segmentation inherits the content-level prohibition; excluded content may not re-enter through auxiliary supervision, pretraining, augmentation or validation.

Canonical order is deterministic: prefer official test over train if an agreeing group ever spans partitions, then lexicographically smallest image ID, then normalized raw-relative filepath. Prioritizing test in that hypothetical case protects the original holdout; no such agreeing cross-split group exists here. Current agreeing groups keep train IDRiD_073 and IDRiD_079; train IDRiD_375 and IDRiD_279 are redundant exclusions. This selects a representation of identical pixels with identical labels, not the clinically correct label. Canonical localization annotations, if used later, must come from the same retained split/ID verified by content; do not average repeated centers automatically.

`sample_key` = `idrid:grading:<original_split>:<image_id>`. `filepath` is project-root-relative with forward slashes; resolve against the project root, not the current shell directory. `content_hash` is the audit's SHA-256 over mode/size plus decoded pixels; `file_sha256` hashes original bytes. Labels and official assignments are preserved. Duplicate group IDs contain the full decoded hash. Manifest rows are sorted deterministically. Primary inclusion/exclusion is explicit and all 516 official rows are accounted for.

## Exact changes and exclusions

{table(comparison)}

{table(summ)}

Excluded rows with original labels, paths, group and rationale:

{table(excluded[['sample_key','DR_grade','DME_label','duplicate_status','exclusion_reason']])}

## Candidate policy comparison

- **A — official unchanged:** maximum benchmark faithfulness and full sample size; leaves exact train/test leakage and all annotation contradictions. Reproducible but scientifically compromised as an independent primary evaluation.
- **B — remove overlapping test photographs:** removes exact train/test overlap by dropping the overlapping test row. It leaves conflicting training duplicate groups and a train-side member whose held-out alias disagreed; it does not adjudicate that remaining label. The smaller test is no longer the official benchmark, and training still contains redundant images.
- **C — quarantine all conflicting groups:** removes contradictions without choosing labels and blocks the observed cross-split duplicate. Same-label training duplicates remain, overweighting identical photographs and risking leakage if a later validation split ignores content.
- **D — deduplicate agreeing groups only:** reduces redundant sample weighting reproducibly but, as a stand-alone policy, leaves conflicting groups unchanged and does not fix the exact train/test conflict. It is not sufficient for primary experiments. D is never permission to pick a winner in a conflicting group.
- **C + D — recommended primary:** removes the eight conflicting rows and two redundant agreeing rows, yielding a content-unique, exact-overlap-free primary set. Costs 10 rows and departs from published official sample counts. It is conservative and traceable but cannot repair labels, establish patient independence or guarantee labels in singleton groups are correct.

All alternatives preserve immutable raw data; each candidate's train/test/excluded and remaining risk counts are computed in idrid_duplicate_policy_comparison.csv. The unchanged official manifest is available only as a separately labeled **secondary official comparison with known duplicate/leakage/label-conflict caveats**. It is not an additional primary training pool. Never report its scores as leakage-free, combine its results with the clean test, or choose a policy because it improves observed performance. Preserve the same fitting procedure for any later comparisons and disclose differing evaluation counts.

## Class and DME distributions

{table(dist[dist.stage.isin(['official','clean'])])}

{table(imb.round(6))}

Interpretation: inspect percentage-point changes as descriptive quantities, not a test of clinical representativeness. Cleaning changes training DR counts from [134,20,136,74,49] to [133,18,132,73,48]; test from [34,5,32,19,13] to [34,5,32,18,13]. Grade 1 remains the smallest class, loses 2/20 training examples, and the training max/min ratio rises from 6.8 to 7.388889. The overall imbalance structure remains, with a modest proportional change but a meaningful 10% reduction of the already rare training grade. No class-weight or sampling decision is made. DME counts and percentages are separate above; DME retains its photographic risk interpretation and is not OCT-confirmed thickening.

## Segmentation annotation availability

The policy table has one row per segmentation image and annotation type (MA, HE, EX, SE, OD), not just rows with files. Available nonempty masks: 363; unavailable image/type combinations: 42; verified empty mask files: 0. MA/EX/OD coverage is 81 each, HE 80, SE 40. An absent mask is **unavailable supervision**, not a negative lesion label. `annotation_available` / `supervision_valid` must gate any future supervised calculation; an unavailable target is null. If a batching interface later needs a placeholder tensor, it must carry validity=false and contribute no supervised loss or segmentation metric; the placeholder never becomes a clinical negative. Only an explicitly supplied readable binary all-zero annotation can be marked verified empty. This rule describes annotation content, not independent clinical adjudication. No such mask was observed.

Preserve palette indices for P masks. For the RGBA EX mask, derive foreground from RGB channels only and exclude opaque alpha. Do not silently grayscale a red mask with a threshold that changes its meaning. OD is anatomical supervision, not a lesion class. Stand-alone segmentation train/test assignments stay organizer-provided; this stage does not authorize mixing all 54 segmentation training images into grading training.

## Cross-task correspondence and safeguards

{table(f['review'].groupby(['correspondence_tier','automatic_multitask_permission']).size().reset_index(name='images'))}

The three exact segmentation/grading matches are eligible automatically only because they map to one permitted clean grading record and share the same organizer partition. They appear in idrid_multitask_exact_clean.csv. The 47 high-similarity cases are strongly supported **candidates**, not verified identity; the 31 uncertain nearest candidates are not mappings. Neither category is merged or receives automatic grading labels for segmentation use. All raw candidate evidence and split discrepancies remain in idrid_cross_task_mapping_review.csv. Thirteen strong candidates and seventeen uncertain candidates point across task partitions. These are unresolved risks, not thirty proven duplicate identities. Restrict combined grading/segmentation experiments to the exact manifest until review resolves correspondence. Any future approval requires explicit documented evidence, a versioned mapping and a new cross-task content/split check. Approximate alternatives may not be silently promoted. Unmapped auxiliary images may not be used for primary grading training merely because their segmentation folder says train.

All localization images can be matched by exact content to grading imagery, but repeated content may have differing center annotations. For future anatomy supervision, select only the permitted clean grading sample's content-verified same-split/ID localization record; quarantine excluded contents and retain the canonical record for agreeing groups. No patient identity is inferred from names, coordinates or visual similarity.

## Raw data, evidence and reproduction

Raw files, ZIPs, labels and split folders are read-only inputs. No copies, moves, relabeling, crops or image derivatives are created in raw. Full path/size/mtime_ns/SHA-256 snapshots bracket this focused stage and are compared with the completed audit snapshot. Access timestamps are not covered. Existing audit artifacts and resolution experiments are consumed, not regenerated. Selective duplicate/archive evidence checks are new focused verification. Input checksums and exact generated artifact hashes are recorded in idrid_integrity_resolution_provenance.json. Manifests are byte-reproducible from the same inputs; two independent in-memory builds are compared, and a second complete invocation is validated separately.

Run from D:\\DR_Hackathon: `.venv\\Scripts\\python.exe src\\data\\resolve_idrid_integrity.py`. Uses the existing requirements-audit.txt environment; no new model dependency. Generated manifests live in data/interim/manifests, policy reports in docs/dataset_audit, and evidence/checks under outputs/metrics. The interim directory is ignored by the existing .gitignore; code/policy plus source fingerprints provide regeneration even when manifests are not tracked.

## Validation scope, unknowns and external validation

{table(checks)}

Mechanical checks can pass while patient-level independence remains unknown and approximate cross-task identities remain under review. No patient identifiers are available; patient-level leakage cannot be ruled out. Zero exact overlap does not exclude transformed images, paired eyes, visits or institutions' sampling dependencies. Cleaned labels remain original labels, not re-adjudicated ground truth. Existing singleton errors may remain. Publisher authenticity is not independently established by agreement of local ZIPs and extraction. The clean test is still an internal IDRiD test, not external validation. Independent institutions/cameras/populations and compatible licensed labels with overlap screening remain necessary.

No CNN, Transformer, segmentation model, loss, optimizer, augmentation pipeline, final resolution or referral threshold was selected, and no training was run.
'''
    return {'docs/dataset_audit/IDRiD_LABEL_CONFLICT_REVIEW.md':review.encode(),'docs/dataset_audit/IDRiD_RESOLUTION_FINDINGS.md':resolution.encode(),'docs/dataset_audit/IDRiD_EXPERIMENT_POLICY.md':policy.encode()}

def run():
    for p in [MET,DOC,MAN]:p.mkdir(parents=True,exist_ok=True)
    checks=[]
    def check(name,passed,detail,status=None):checks.append(dict(check=name,status=status or ('PASS' if passed else 'FAIL'),detail=str(detail)))
    inputpaths=[MET/f'idrid_{n}.csv' for n in SOURCES]+[DOC/n for n in ['IDRiD_DATASET_AUDIT.md','IDRiD_LIMITATIONS.md','IDRiD_SUITABILITY_MATRIX.md']]+[MET/'idrid_raw_manifest_final.json']
    inputs={p.relative_to(ROOT).as_posix():filehash(p) for p in inputpaths}
    before=snapshot();reference=json.loads((MET/'idrid_raw_manifest_final.json').read_text());reference={'IDRiD/'+k.replace('\\','/'):v for k,v in reference.items()}
    check('raw_matches_completed_audit',all(before.get(k)==v for k,v in reference.items()) and set(k for k in before if k.startswith('IDRiD/'))==set(reference),'IDRiD path, size, mtime_ns and bytes agree with final completed audit snapshot')
    if checks[-1]['status']=='FAIL':
        pd.DataFrame(checks).to_csv(MET/'idrid_clean_manifest_checks.csv',index=False);raise RuntimeError('Raw differs from audited evidence; no clean manifests generated')
    d=load();payload,f=build(d);again,_=build(d)
    check('two_independent_manifest_builds_identical',payload==again,'All constructed manifest/policy-table bytes identical for repeated pure builds')
    evidence=archive_evidence(d,f);check('duplicate_archive_evidence',evidence[['bytes_match','decoded_content_match','labels_match_audit']].all().all(),f'{len(evidence)} duplicate image aliases; both archive grading CSVs also byte-matched')
    payload['outputs/metrics/idrid_duplicate_archive_evidence.csv']=csvbytes(evidence)
    clean=f['included'];excluded=f['grading'][f['grading'].inclusion_status=='excluded'];g=f['grading']
    train=clean[clean.original_split=='train'];test=clean[clean.original_split=='test'];conflict_hashes=set(d['content_label_conflicts'].content_sha256)
    check('six_duplicate_groups_and_four_conflicts_reconciled',len(f['groups'])==6 and f['groups'].creates_label_conflict.sum()==4 and set(f['groups'].query('creates_label_conflict').content_hash)==conflict_hashes,'Grouped existing image hashes independently and reconciled audited conflicts')
    check('zero_clean_train_test_exact_overlap',not (set(train.content_hash)&set(test.content_hash)),len(set(train.content_hash)&set(test.content_hash)))
    check('zero_within_clean_exact_duplicates',not clean.content_hash.duplicated().any(),f'{len(clean)} included rows; {clean.content_hash.nunique()} content hashes')
    check('all_included_filepaths_exist',all((ROOT/p).is_file() for p in clean.filepath),len(clean))
    check('all_manifest_paths_within_raw',all((ROOT/p).resolve().is_relative_to(RAW.resolve()) for p in g.filepath),'Included and excluded grading rows reference immutable raw inputs')
    check('manifest_file_hashes_match_current_raw',all(before[Path(r.filepath).relative_to('data/raw').as_posix()][2]==r.file_sha256 for r in g.itertuples()),'All 516 grading rows checked against the current raw snapshot, not just path existence')
    check('included_valid_DR_DME_labels',clean.DR_grade.isin(range(5)).all() and clean.DME_label.isin(range(3)).all(),'No missing or out-of-domain included targets')
    check('included_labels_match_raw_CSV',True,'checked below against original raw CSV fields')
    rawlabels=[]
    for split,source in d['grading_labels'].groupby('split').source.first().items():
        z=pd.read_csv(ROOT/source).iloc[:,:3];z.columns=['image_id','DR_grade','DME_label'];z['original_split']=split;rawlabels.append(z)
    joined=clean.merge(pd.concat(rawlabels),on=['original_split','image_id'],suffixes=('','_raw'),validate='one_to_one')
    checks[-1]['status']='PASS' if len(joined)==len(clean) and joined.DR_grade.eq(joined.DR_grade_raw).all() and joined.DME_label.eq(joined.DME_label_raw).all() else 'FAIL'
    check('no_quarantined_content_included',not clean.content_hash.isin(conflict_hashes).any(),'All aliases of four conflicting content groups excluded from primary grading')
    check('no_excluded_key_included',not (set(clean.sample_key)&set(excluded.sample_key)),len(set(clean.sample_key)&set(excluded.sample_key)))
    check('grading_sample_keys_globally_unique',not g.sample_key.duplicated().any(),len(g))
    check('official_partition_fully_accounted_for',len(clean)+len(excluded)==len(g) and set(clean.sample_key)|set(excluded.sample_key)==set(g.sample_key),'Primary included/excluded partition of all official grading rows')
    check('no_cross_partition_reassignment',all(key(r.original_split,r.image_id)==r.sample_key for r in clean.itertuples()),'Every clean row retains original split')
    check('mask_absence_never_negative',f['annotations'].loc[~f['annotations'].annotation_available,'positive_pixels'].isna().all() and (~f['annotations'].loc[~f['annotations'].annotation_available,'supervision_valid']).all(),'42 unavailable masks carry null target and validity=false')
    check('annotation_table_complete',len(f['annotations'])==5*len(d['image_metadata'].query("component == 'Segmentation'")) and not f['annotations'].duplicated(['sample_key','annotation_type']).any(),len(f['annotations']))
    check('available_mask_paths_exist',all((ROOT/p).is_file() for p in f['annotations'].loc[f['annotations'].annotation_available,'mask_filepath']),int(f['annotations'].annotation_available.sum()))
    check('available_masks_valid_in_completed_audit',d['segmentation_metadata'].readable.all() and d['segmentation_metadata'].binary.all(),'All available masks fully decoded and binary in unchanged audited files')
    check('multitask_only_exact_permitted_same_split',f['multi'].correspondence_tier.eq('exact_verified_correspondence').all() and f['multi'].grading_sample_key.isin(clean.sample_key).all() and not f['multi'].content_hash.isin(conflict_hashes).any(),len(f['multi']))
    check('multitask_train_no_clean_test_content',not set(f['multi'].loc[f['multi'].original_split=='train','content_hash'])&set(test.content_hash),'Only permitted exact same-split links; approximate candidates blocked')
    check('cross_task_candidates_not_auto_merged',not f['review'].loc[f['review'].match_status!='verified_exact','automatic_multitask_permission'].any(),'47 strong candidates and 31 uncertain candidates remain review-only')
    check('patient_level_independence',False,'Patient-level leakage cannot be fully audited from the publicly available identifiers.',status='UNKNOWN')
    check('approximate_cross_task_identity',False,'47 strong and 31 uncertain candidates unresolved; primary combined use restricted to exact links',status='REVIEW')
    for rel,data in payload.items():
        p=ROOT/rel;assert not p.resolve().is_relative_to(RAW.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    for rel,data in payload.items():
        frame=pd.read_csv(ROOT/rel);assert (ROOT/rel).read_bytes()==data
    check('written_CSVs_reopen_and_match_generated_bytes',True,len(payload))
    # Verify stage inputs stayed fixed, including prior reports and existing resolution tables.
    check('prior_audit_artifacts_unchanged',inputs=={p.relative_to(ROOT).as_posix():filehash(p) for p in inputpaths},len(inputs))
    after=snapshot();check('raw_unchanged_during_resolution',before==after,'All files under data/raw: path, byte count, mtime_ns and SHA-256; access times excluded')
    (MET/'idrid_integrity_resolution_raw_before.json').write_text(json.dumps(before,sort_keys=True,indent=2)+'\n')
    (MET/'idrid_integrity_resolution_raw_after.json').write_text(json.dumps(after,sort_keys=True,indent=2)+'\n')
    checkframe=pd.DataFrame(checks);(MET/'idrid_clean_manifest_checks.csv').write_bytes(csvbytes(checkframe))
    for rel,data in reports(d,f,checkframe,evidence).items():(ROOT/rel).write_bytes(data);payload[rel]=data
    # Track content-addressed reproducibility across complete invocations, not timestamps.
    outputs={p:digest(b) for p,b in sorted(payload.items())};provenance_path=MET/'idrid_integrity_resolution_provenance.json'
    source_sha=filehash(Path(__file__))
    previous=json.loads(provenance_path.read_text()) if provenance_path.exists() else None
    same_run_inputs=previous is not None and previous.get('inputs_sha256')==inputs and previous.get('driver_sha256')==source_sha
    same_outputs=same_run_inputs and previous.get('generated_artifacts_sha256')==outputs
    if same_run_inputs and not same_outputs:raise RuntimeError('Reproducibility failed: same driver and inputs produced different artifact bytes')
    repetition=dict(previous_comparable_run_exists=same_run_inputs,all_generated_artifacts_byte_identical_to_previous=bool(same_outputs),two_in_memory_builds_byte_identical=payload is not None and all(again[p]==payload[p] for p in again))
    provenance=dict(policy_version=POLICY,driver='src/data/resolve_idrid_integrity.py',driver_sha256=source_sha,inputs_sha256=inputs,generated_artifacts_sha256=outputs,reproducibility=repetition,clinical_labels_adjudicated=False,training_run=False,model_selected=False,mechanical_integrity_pass=not checkframe.status.eq('FAIL').any(),patient_independence='UNKNOWN',cross_task_approximate_identity='REVIEW',raw_unchanged=before==after,python=sys.version,pandas=pd.__version__,numpy=np.__version__)
    provenance_path.write_text(json.dumps(provenance,sort_keys=True,indent=2)+'\n')
    print('IDRiD INTEGRITY RESOLUTION COMPLETE')
    print('Official train/test:',len(g[g.original_split=='train']),len(g[g.original_split=='test']))
    print('Clean train/test:',len(train),len(test),'Excluded:',len(excluded))
    print(excluded[['sample_key','exclusion_reason']].to_string(index=False))
    print('Checks:',checkframe.status.value_counts().to_dict(),'Exact clean overlap:',len(set(train.content_hash)&set(test.content_hash)))
    print('Reproducibility:',repetition)
    print('Raw unchanged:',before==after,'Patient independence: UNKNOWN; external validation required: YES')
    print('Reports:');[print(ROOT/p) for p in payload if p.endswith('.md')]
    if checkframe.status.eq('FAIL').any():raise RuntimeError('One or more integrity checks failed; see idrid_clean_manifest_checks.csv')

if __name__=='__main__':run()
