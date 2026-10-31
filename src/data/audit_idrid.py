"""Reproducible, read-only IDRiD audit. Run from project root."""
from pathlib import Path
import hashlib,json,re,zipfile,sys,platform,subprocess
from collections import Counter
import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'data/raw/IDRiD'
OUT=ROOT/'outputs/metrics'
FIG=ROOT/'outputs/figures/idrid_audit'
DOC=ROOT/'docs/dataset_audit'
SEED=20261028

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def context(p):
    s=p.as_posix().lower()
    task=next((t for t in ['Segmentation','Disease Grading','Localization'] if t.lower() in s),'Archive/other')
    split='train' if 'training' in s else 'test' if 'testing' in s else 'unspecified'
    ident=re.search(r'IDRiD_\d+',p.name,re.I)
    return task,split,ident.group().upper().replace('IDRID','IDRiD') if ident else ''
def save(rows,name):
    df=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    df.to_csv(OUT/(name+'.csv'),index=False)
    return df

def run():
    for p in [OUT,FIG,DOC]:p.mkdir(parents=True,exist_ok=True)
    paths=sorted(p for p in RAW.rglob('*') if p.is_file())
    before={str(p.relative_to(RAW)):(p.stat().st_size,p.stat().st_mtime_ns,sha(p)) for p in paths}
    (OUT/'idrid_raw_manifest_before.json').write_text(json.dumps(before,indent=2))
    inv=[]; checks=[]; images=[]; masks=[]; resize=[]; components=[]; csvinfo=[]; grades=[]; locs=[]; cache={}
    def check(name,status,detail):checks.append(dict(check=name,status=status,detail=str(detail)))
    for i,p in enumerate(paths):
        task,split,ident=context(p); ext=p.suffix.lower(); mask=ext in ['.tif','.tiff','.png'] and 'groundtruth' in p.as_posix().lower()
        row=dict(path=str(p.relative_to(ROOT)),component=task,split=split,image_id=ident,filename=p.name,extension=ext,size_bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,sha256=before[str(p.relative_to(RAW))][2],kind='mask' if mask else 'fundus' if ext in ['.jpg','.jpeg'] else 'table' if ext=='.csv' else 'archive' if ext=='.zip' else 'documentation' if ext=='.txt' else 'unexpected')
        inv.append(row)
        if ext=='.zip':
            with zipfile.ZipFile(p) as z:
                bad=z.testzip(); check('archive_crc:'+p.name,'PASS' if bad is None else 'FAIL',bad or 'all members CRC valid')
                members=[dict(archive=p.name,member=x.filename,size_bytes=x.file_size,crc=x.CRC) for x in z.infolist() if not x.is_dir()]
                save(members,'idrid_archive_members_'+p.stem.split('.')[0])
            continue
        if ext=='.csv':
            d=pd.read_csv(p); cols=list(d.columns); essential=d.iloc[:,:3].copy()
            csvinfo.append(dict(path=row['path'],columns=json.dumps(cols),rows=len(d),dtypes=json.dumps({c:str(v) for c,v in d.dtypes.items()}),missing_values=json.dumps(d.isna().sum().to_dict()),duplicated_rows=int(d.duplicated().sum()),duplicated_identifiers=int(d.iloc[:,0].duplicated().sum()),blank_trailing_columns=json.dumps([c for c in cols[3:] if d[c].isna().all()])))
            for vals in essential[~essential.isna().all(axis=1)].itertuples(index=False,name=None):
                if task=='Disease Grading':grades.append(dict(split=split,image_id=str(vals[0]).strip(),DR_grade=vals[1],DME_label=vals[2],source=row['path']))
                else:locs.append(dict(split=split,image_id=str(vals[0]).strip(),anatomy='OD' if 'Optic Disc' in str(p) else 'fovea',x=vals[1],y=vals[2],source=row['path']))
            continue
        if row['kind'] not in ['fundus','mask']:continue
        try:
            with Image.open(p) as im:
                im.load(); a=np.asarray(im); meta=dict(row,width=im.width,height=im.height,aspect_ratio=im.width/im.height,mode=im.mode,channels=len(im.getbands()),format=im.format,dtype=str(a.dtype),readable=True,error='',decoded_sha256=hashlib.sha256(str((im.mode,im.size)).encode()+a.tobytes()).hexdigest())
                if not mask:
                    if row['sha256'] not in cache:
                        small=np.asarray(im.convert('RGB').resize((512,340),Image.Resampling.BILINEAR)).astype(float)
                        gray=small.mean(2); fg=small.max(2)>15
                        ys,xs=np.where(fg)
                        stats=dict(pixel_min=int(a.min()),pixel_max=int(a.max()),pixel_mean=float(a.mean()),pixel_std=float(a.std()),brightness=float(gray.mean()),contrast=float(gray.std()),black_fraction=float((~fg).mean()),laplacian_variance=float(ndi.laplace(gray).var()),fov_bbox_proxy=json.dumps([int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]) if len(xs) else '',perceptual_hash=''.join('1' if v else '0' for v in (np.asarray(im.convert('L').resize((16,16)))>gray.mean()).flat))
                        for c,k in enumerate('RGB'):stats[k+'_mean']=float(a[:,:,c].mean());stats[k+'_std']=float(a[:,:,c].std())
                        cache[row['sha256']]=stats
                    meta.update(cache[row['sha256']]);images.append(meta)
                else:
                    typ=next((t for t in ['MA','HE','EX','SE','OD'] if re.search('_'+t+r'$',p.stem)), 'UNKNOWN')
                    b=(a[:,:,:3] if a.ndim==3 and im.mode=='RGBA' else a)>0
                    if b.ndim>2:b=b.any(2)
                    lab,n=ndi.label(b,structure=np.ones((3,3)))
                    counts=np.bincount(lab.ravel())[1:]
                    meta.update(mask_type=typ,unique_values=json.dumps(np.unique(a).tolist()),binary=bool(len(np.unique(a))<=2 and 0 in np.unique(a)),positive_pixels=int(b.sum()),positive_image_percent=float(b.mean()*100),empty=not b.any(),component_count=n,component_min=int(counts.min()) if n else 0,component_median=float(np.median(counts)) if n else 0,component_max=int(counts.max()) if n else 0)
                    masks.append(meta)
                    for j,area in enumerate(counts):components.append(dict(mask_path=row['path'],mask_type=typ,split=split,component=j+1,area_pixels=int(area)))
                    if typ!='OD':
                        for size in [2048,1024,512,384,224]:
                            wh=(size,round(im.height*size/im.width))
                            resized=np.asarray(Image.fromarray(lab.astype(np.int32)).resize(wh,Image.Resampling.NEAREST))
                            rb=resized>0; ids=np.unique(resized); retained=int((ids>0).sum()); rn=ndi.label(rb,structure=np.ones((3,3)))[1]; pos=int(rb.sum()); expected=b.sum()*wh[0]*wh[1]/(im.width*im.height)
                            resize.append(dict(mask_path=row['path'],mask_type=typ,split=split,target_width=size,target_height=wh[1],original_positive_pixels=int(b.sum()),resized_positive_pixels=pos,original_components=n,source_components_retained=retained,source_components_disappeared=n-retained,resized_components=rn,merger_count_proxy=max(0,retained-rn),area_ratio_to_expected=pos/expected if expected else np.nan,original_equivalent_pixels=pos*(im.width*im.height)/(wh[0]*wh[1])))
        except Exception as e:
            check('read:'+row['path'],'FAIL',repr(e));(masks if mask else images).append(dict(row,readable=False,error=repr(e)))
        if i%100==0:print(f'Processed {i}/{len(paths)} files',flush=True)
    inventory=save(inv,'idrid_inventory'); image=save(images,'idrid_image_metadata'); mask=save(masks,'idrid_segmentation_metadata'); g=save(grades,'idrid_grading_labels'); loc=pd.DataFrame(locs)
    save(csvinfo,'idrid_csv_schema'); save(resize,'idrid_resolution_analysis');save(components,'idrid_component_areas')
    (DOC/'idrid_directory_tree.txt').write_text('\n'.join(str(p.relative_to(RAW))+'/' for p in sorted(RAW.rglob('*')) if p.is_dir()))
    save(inventory.groupby(['component','kind','extension']).size().reset_index(name='count'),'idrid_inventory_summary')
    save(inventory[inventory.filename.duplicated(False)],'idrid_filename_collisions')
    save(image[image.sha256.duplicated(False)],'idrid_exact_duplicate_groups')
    save(image[image.decoded_sha256.duplicated(False)],'idrid_decoded_duplicate_groups')
    grading=image[image.component=='Disease Grading'].copy()
    joined=grading.merge(g,on=['split','image_id'],how='outer',indicator=True,suffixes=('','_label'))
    save(joined[joined._merge!='both'],'idrid_grading_orphans')
    check('grading_bidirectional_correspondence','PASS' if (joined._merge=='both').all() else 'FAIL',joined._merge.value_counts().to_dict())
    check('grading_valid_values','PASS' if g.DR_grade.isin(range(5)).all() and g.DME_label.isin(range(3)).all() else 'FAIL','DR 0..4; DME 0..2; missing invalid')
    check('grading_unique_split_ids','PASS' if not g.duplicated(['split','image_id']).any() else 'FAIL',len(g))
    dist=[]
    for split in ['train','test','all']:
        sub=g if split=='all' else g[g.split==split]
        for grade in range(5):dist.append(dict(split=split,DR_grade=grade,count=int((sub.DR_grade==grade).sum()),percent=float((sub.DR_grade==grade).mean()*100)))
    dist=save(dist,'idrid_grading_distribution')
    save(g.groupby(['split','DME_label']).size().reset_index(name='count'),'idrid_dme_distribution')
    save(pd.crosstab([g.split,g.DR_grade],g.DME_label).reset_index(),'idrid_dr_dme_crosstab')
    segimgs=image[image.component=='Segmentation']; coverage=[]; corr=[]
    for r in mask.to_dict('records'):
        match=segimgs[(segimgs.split==r['split'])&(segimgs.image_id==r['image_id'])]
        corr.append(dict(mask_path=r['path'],image_matches=len(match),dimensions_match=bool(len(match)==1 and match.iloc[0].width==r['width'] and match.iloc[0].height==r['height'])))
    save(corr,'idrid_mask_correspondence')
    missing=[]
    for split in ['train','test']:
        si=segimgs[segimgs.split==split]
        for typ in ['MA','HE','EX','SE','OD']:
            m=mask[(mask.split==split)&(mask.mask_type==typ)]; absent=sorted(set(si.image_id)-set(m.image_id))
            coverage.append(dict(split=split,mask_type=typ,images=len(si),masks=len(m),images_with_mask=m.image_id.nunique(),images_without_mask=len(absent),empty_masks=int(m.empty.sum()) if False else int(m['empty'].sum()),min_positive_pixels=int(m.positive_pixels.min()),median_positive_pixels=float(m.positive_pixels.median()),mean_positive_pixels=float(m.positive_pixels.mean()),max_positive_pixels=int(m.positive_pixels.max()),median_image_percent=float(m.positive_image_percent.median())))
            missing.extend(dict(split=split,image_id=x,mask_type=typ,status='mask absent; not automatically negative') for x in absent)
    save(coverage,'idrid_annotation_coverage');save(missing,'idrid_missing_masks')
    check('mask_correspondence','PASS' if all(x['dimensions_match'] for x in corr) else 'FAIL',len(corr))
    check('binary_masks','PASS' if mask.binary.all() else 'FAIL',mask.unique_values.value_counts().to_dict())
    mapping=[]
    for h,grp in image.groupby('decoded_sha256'):
        gr=grp[grp.component=='Disease Grading']; se=grp[grp.component=='Segmentation']; lo=grp[grp.component=='Localization']
        r=dict(content_sha256=h,grading_available=len(gr)>0,segmentation_available=len(se)>0,localization_image_available=len(lo)>0,split_information=json.dumps(grp[['component','split','image_id']].to_dict('records')),grading_image_id='',grading_split='',DR_grade=np.nan,DME_label=np.nan)
        if len(gr):
            q=gr.iloc[0]; labels=g[(g.split==q.split)&(g.image_id==q.image_id)];r.update(grading_image_id=q.image_id,grading_split=q.split)
            if len(labels):r.update(DR_grade=labels.iloc[0].DR_grade,DME_label=labels.iloc[0].DME_label)
        for typ in ['MA','HE','EX','SE','OD']:
            hits=[]
            for q in se.itertuples():hits.extend(mask[(mask.split==q.split)&(mask.image_id==q.image_id)&(mask.mask_type==typ)].path.tolist())
            r[typ+'_mask']=';'.join(hits)
        for anatomy in ['OD','fovea']:
            hits=[]
            for q in lo.itertuples():hits.extend(loc[(loc.split==q.split)&(loc.image_id==q.image_id)&(loc.anatomy==anatomy)].index.tolist())
            r[anatomy+'_annotation']=len(hits)>0
        r['cross_split_content']=grp.split.nunique()>1;mapping.append(r)
    mapping=save(mapping,'idrid_cross_task_mapping')
    locrows=[]
    for r in loc.to_dict('records'):
        matches=image[(image.component=='Localization')&(image.split==r['split'])&(image.image_id==r['image_id'])]
        valid=len(matches)==1 and pd.notna(r['x']) and pd.notna(r['y']) and 0<=r['x']<matches.iloc[0].width and 0<=r['y']<matches.iloc[0].height
        r.update(image_matches=len(matches),within_zero_based_bounds=bool(valid),within_one_based_bounds=bool(len(matches)==1 and 1<=r['x']<=matches.iloc[0].width and 1<=r['y']<=matches.iloc[0].height));locrows.append(r)
    loc=save(locrows,'idrid_localization_metadata')
    check('localization_bounds','PASS' if loc.within_zero_based_bounds.all() else 'FAIL',len(loc))
    check('localization_unique_keys','PASS' if not loc.duplicated(['split','image_id','anatomy']).any() else 'FAIL',len(loc))
    expected={(r.split,r.image_id,a) for r in image[image.component=='Localization'].itertuples() for a in ['OD','fovea']};actual=set(zip(loc.split,loc.image_id,loc.anatomy));save([dict(split=s,image_id=i,anatomy=a) for s,i,a in sorted(expected-actual)],'idrid_missing_localization')
    check('localization_coverage','PASS' if expected==actual else 'FAIL',f'missing {len(expected-actual)}, orphan {len(actual-expected)}')
    check('cross_split_content_duplicates','PASS' if not mapping.cross_split_content.any() else 'FAIL',int(mapping.cross_split_content.sum()))
    check('zero_byte_files','PASS' if not (inventory.size_bytes==0).any() else 'FAIL',int((inventory.size_bytes==0).sum()))
    check('unexpected_files','PASS' if not (inventory.kind=='unexpected').any() else 'REVIEW',inventory[inventory.kind=='unexpected'].path.tolist())
    check('patient_level_leakage','UNKNOWN','Patient-level leakage cannot be fully audited from the publicly available identifiers.')
    # Near duplicates: exhaustive 516-image 256-bit mean-threshold hash candidates, never asserted identity.
    near=[]; unique=grading.drop_duplicates('decoded_sha256').to_dict('records')
    for i,a in enumerate(unique):
        for b in unique[i+1:]:
            distance=sum(x!=y for x,y in zip(a['perceptual_hash'],b['perceptual_hash']))
            if distance<=8:near.append(dict(path_a=a['path'],path_b=b['path'],split_a=a['split'],split_b=b['split'],hamming_distance=distance,cross_split=a['split']!=b['split']))
    save(pd.DataFrame(near,columns=['path_a','path_b','split_a','split_b','hamming_distance','cross_split']),'idrid_near_duplicate_candidates')
    check('near_duplicate_screen','REVIEW' if near else 'PASS',f'{len(near)} candidates at <=8/256 bit distance; heuristic cannot exclude transformed duplicates')
    q=grading.copy();outliers=[]
    for col in ['brightness','contrast','black_fraction','laplacian_variance','R_mean','G_mean','B_mean']:
        low,high=q[col].quantile([.25,.75]);iqr=high-low
        for r in q[(q[col]<low-1.5*iqr)|(q[col]>high+1.5*iqr)].itertuples():outliers.append(dict(path=r.path,split=r.split,image_id=r.image_id,metric=col,value=getattr(r,col),lower_fence=low-1.5*iqr,upper_fence=high+1.5*iqr))
    save(outliers,'idrid_quality_outliers')
    figures(grading,g,segimgs,mask,loc,pd.DataFrame(resize))
    # No copies of original images are made; only annotated, downscaled figures are written.
    after={str(p.relative_to(RAW)):(p.stat().st_size,p.stat().st_mtime_ns,sha(p)) for p in sorted(RAW.rglob('*')) if p.is_file()}
    (OUT/'idrid_raw_manifest_after.json').write_text(json.dumps(after,indent=2))
    check('raw_immutability','PASS' if before==after else 'FAIL','before/after path, size, mtime_ns and SHA-256 comparison')
    try:
        git=subprocess.run(['git','ls-files'],cwd=ROOT,capture_output=True,text=True)
        tracked=[x for x in git.stdout.splitlines() if Path(x).suffix.lower() in ['.jpg','.jpeg','.tif','.tiff']]
        check('git_tracked_dataset_images','PASS' if git.returncode==0 and not tracked else 'UNKNOWN' if git.returncode else 'FAIL',tracked if git.returncode==0 else git.stderr.strip())
    except Exception as e:check('git_tracked_dataset_images','UNKNOWN',repr(e))
    check('figures_exist','PASS' if len(list(FIG.glob('*.png')))>=10 else 'FAIL',len(list(FIG.glob('*.png'))))
    # Empty audit tables retain explicit schema so they can be reopened.
    for p in OUT.glob('idrid_*.csv'):
        if p.stat().st_size<=3:p.write_text('status\n')
        pd.read_csv(p)
    check('csv_reopen','PASS','all generated idrid_*.csv reopened with pandas')
    save(checks,'idrid_integrity_checks')
    deps={k:__import__(k).__version__ for k in ['numpy','pandas','PIL','scipy','matplotlib']}
    (OUT/'idrid_environment.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),dependencies=deps,seed=SEED),indent=2))
    from idrid_report import write_report
    write_report(ROOT)
    print('IDRiD DATASET AUDIT COMPLETE',flush=True)
    print('Grading images:',grading.groupby('split').size().to_dict(),'Total:',len(grading))
    print('DR class distribution:',g.DR_grade.value_counts().sort_index().to_dict())
    print('Segmentation images:',segimgs.groupby('split').size().to_dict())
    print('Masks:',mask.mask_type.value_counts().to_dict(),'Localization annotations:',len(loc))
    print('Corrupt images:',sum(not r.get('readable',False) for r in images+masks),'Missing labels:',int((joined._merge!='both').sum()),'Absent masks:',len(missing))
    print('Exact train/test content overlaps:',int(mapping.cross_split_content.sum()))
    print('Potential leakage: task overlap requires content-group split protection; patient identity unavailable.')
    print('Major limitations: small, selected single-source dataset; no gradability labels; uncertain absent masks; no external domain evidence.')
    print('Recommended role: internal grading/lesion/anatomy research benchmark. External validation required: YES')
    for p in DOC.iterdir():print(p)
    from verify_idrid_audit import verify
    verify()

def figures(grading,g,segimgs,masks,loc,res):
    def finish(name):plt.tight_layout();plt.savefig(FIG/name,dpi=140);plt.close()
    d=pd.crosstab(g.DR_grade,g.split).reindex(range(5),fill_value=0)
    d.plot.bar();plt.ylabel('Images');finish('dr_counts.png')
    (d/d.sum()*100).plot.bar();plt.ylabel('Percent within split');finish('dr_percentages.png')
    ct=pd.crosstab(g.DR_grade,g.DME_label);plt.imshow(ct);plt.xticks(range(3),range(3));plt.yticks(range(5),range(5));plt.xlabel('DME risk');plt.ylabel('DR grade');plt.colorbar();finish('dr_dme.png')
    for grade in range(5):
        sample=g[g.DR_grade==grade].sample(min(6,int((g.DR_grade==grade).sum())),random_state=SEED)
        fig,axes=plt.subplots(2,3,figsize=(12,6))
        for ax in axes.flat:ax.axis('off')
        for ax,r in zip(axes.flat,sample.itertuples()):
            p=grading[(grading.split==r.split)&(grading.image_id==r.image_id)].iloc[0].path
            with Image.open(ROOT/p) as im:ax.imshow(im.resize((640,425)))
            ax.set_title(f'{r.split}/{r.image_id} DR={r.DR_grade} DME={r.DME_label}')
        finish(f'grading_grade_{grade}.png')
    # Stratify visualization by split, fixed random sample.
    selected=pd.concat([x.sample(min(2,len(x)),random_state=SEED) for _,x in segimgs.groupby('split')])
    colors={'MA':(1,0,1),'HE':(0,1,1),'EX':(1,1,0),'SE':(0,1,0)}
    for r in selected.itertuples():
        fig,axes=plt.subplots(1,5,figsize=(20,4))
        with Image.open(ROOT/r.path) as im:base=np.asarray(im.resize((900,598))).copy()/255.
        axes[0].imshow(base);axes[0].set_title(f'{r.split}/{r.image_id}')
        for ax,(typ,color) in zip(axes[1:],colors.items()):
            m=masks[(masks.split==r.split)&(masks.image_id==r.image_id)&(masks.mask_type==typ)]
            overlay=base.copy()
            if len(m):
                with Image.open(ROOT/m.iloc[0].path) as im:
                    arr=np.asarray(im.resize((900,598),Image.Resampling.NEAREST));b=(arr[:,:,:3] if im.mode=='RGBA' else arr)>0
                    if b.ndim>2:b=b.any(2)
                overlay[b]=overlay[b]*.3+np.array(color)*.7
            ax.imshow(overlay);ax.set_title(typ+(' absent mask' if not len(m) else ''))
        for ax in axes:ax.axis('off')
        finish(f'segmentation_{r.split}_{r.image_id}.png')
    fig,axes=plt.subplots(2,3,figsize=(13,7))
    for ax,col in zip(axes.flat,['brightness','contrast','black_fraction','laplacian_variance','R_mean','G_mean']):ax.hist(grading[col],bins=30);ax.set_title(col)
    finish('quality_distributions.png')
    for split in ['train','test']:
        sample=grading[grading.split==split].sample(3,random_state=SEED);fig,axes=plt.subplots(1,3,figsize=(14,5))
        for ax,r in zip(axes,sample.itertuples()):
            with Image.open(ROOT/r.path) as im:ax.imshow(im.resize((900,598)))
            for a,c in [('OD','cyan'),('fovea','magenta')]:
                mark=loc[(loc.split==split)&(loc.image_id==r.image_id)&(loc.anatomy==a)]
                if len(mark):ax.scatter(mark.x/r.width*900,mark.y/r.height*598,s=60,marker='+',color=c,label=a)
            ax.legend();ax.set_title(f'{split}/{r.image_id}');ax.axis('off')
        finish(f'localization_{split}.png')
    for typ,sub in res.groupby('mask_type'):
        z=sub.groupby('target_width')[['original_components','source_components_retained','original_positive_pixels','original_equivalent_pixels']].sum()
        plt.plot(z.index,z.source_components_retained/z.original_components*100,'o-',label='Original components sampled (%)')
        plt.plot(z.index,z.original_equivalent_pixels/z.original_positive_pixels*100,'s-',label='Area relative to expected (%)');plt.title(typ);plt.xlabel('Target width, aspect preserved');plt.legend();finish(f'resolution_{typ}.png')

if __name__=='__main__':run()
