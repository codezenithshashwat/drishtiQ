"""Approximate cross-task matching: candidates remain distinct from exact identity."""
import numpy as np
import pandas as pd
import json
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def investigate(root):
    out=root/'outputs/metrics';fig=root/'outputs/figures/idrid_audit'
    images=pd.read_csv(out/'idrid_image_metadata.csv');g=pd.read_csv(out/'idrid_grading_labels.csv')
    sg=images[images.component=='Segmentation'];gr=images[images.component=='Disease Grading']
    def thumbnail(p):
        with Image.open(root/p) as im:return np.asarray(im.convert('RGB').resize((64,64),Image.Resampling.BILINEAR)).astype(np.float32)
    a=np.stack([thumbnail(p) for p in gr.path]);rows=[]
    gray=a.mean(3).reshape(len(a),-1);center=gray-gray.mean(1,keepdims=True)
    normalized=center/np.maximum(np.linalg.norm(center,axis=1,keepdims=True),1e-12)
    correlations=normalized@normalized.T;near=[]
    for i in range(len(gr)):
        for j in np.flatnonzero(correlations[i,i+1:]>=.995)+i+1:
            if gr.iloc[i].decoded_sha256==gr.iloc[j].decoded_sha256:continue
            error=float(np.abs(a[i]-a[j]).mean())
            if error<=5:near.append(dict(path_a=gr.iloc[i].path,path_b=gr.iloc[j].path,split_a=gr.iloc[i].split,split_b=gr.iloc[j].split,normalized_correlation=float(correlations[i,j]),thumbnail_mae_0_255=error,cross_split=gr.iloc[i].split!=gr.iloc[j].split))
    pd.DataFrame(near,columns=['path_a','path_b','split_a','split_b','normalized_correlation','thumbnail_mae_0_255','cross_split']).to_csv(out/'idrid_near_duplicate_candidates.csv',index=False)
    for r in sg.itertuples():
        t=thumbnail(r.path);errors=np.abs(a-t).mean(axis=(1,2,3));order=np.argsort(errors);best=gr.iloc[order[0]];second=float(errors[order[1]])
        labels=g[(g.split==best.split)&(g.image_id==best.image_id)].iloc[0]
        corr=float(np.corrcoef(t.ravel(),a[order[0]].ravel())[0,1])
        exact=r.decoded_sha256==best.decoded_sha256
        high=float(errors[order[0]])<=2 and corr>=.995 and second-float(errors[order[0]])>=5
        row=dict(segmentation_path=r.path,segmentation_id=r.image_id,segmentation_split=r.split,grading_path=best.path,grading_id=best.image_id,grading_split=best.split,DR_grade=labels.DR_grade,DME_label=labels.DME_label,thumbnail_mae_0_255=float(errors[order[0]]),second_best_mae=second,thumbnail_correlation=corr,exact_decoded_match=exact,match_status='verified_exact' if exact else 'high_similarity_candidate' if high else 'unresolved_candidate',candidate_cross_split=r.split!=best.split)
        if high and not exact:
            with Image.open(root/r.path) as im:sa=np.asarray(im.convert('RGB')).astype(np.int16)
            with Image.open(root/best.path) as im:ga=np.asarray(im.convert('RGB')).astype(np.int16)
            if sa.shape==ga.shape:
                delta=np.abs(sa-ga);row.update(full_resolution_mae=float(delta.mean()),full_resolution_max_error=int(delta.max()),full_resolution_equal_pixel_fraction=float((delta==0).all(2).mean()))
        rows.append(row)
    result=pd.DataFrame(rows);result.to_csv(out/'idrid_cross_task_similarity_candidates.csv',index=False)
    mapping=pd.read_csv(out/'idrid_cross_task_mapping.csv')
    mapping['identity_evidence']='exact_decoded_content_group'
    mapping['all_grading_labels']=''
    mapping['grading_label_conflict']=False
    for content,group in gr.merge(g,on=['split','image_id'],suffixes=('','_labels')).groupby('decoded_sha256'):
        idx=mapping.content_sha256==content
        mapping.loc[idx,'all_grading_labels']=json.dumps(group[['split','image_id','DR_grade','DME_label']].to_dict('records'))
        if group.DR_grade.nunique()>1 or group.DME_label.nunique()>1:
            mapping.loc[idx,'grading_label_conflict']=True
            mapping.loc[idx,['DR_grade','DME_label']]=np.nan
            mapping.loc[idx,'grading_image_id']=';'.join(group.split+':'+group.image_id)
            mapping.loc[idx,'grading_split']=';'.join(sorted(group.split.unique()))
    for col in ['candidate_grading_id','candidate_grading_split','candidate_match_status','candidate_DR_grade','candidate_DME_label']:mapping[col]=''
    for r in result.itertuples():
        content=sg[sg.path==r.segmentation_path].iloc[0].decoded_sha256
        idx=mapping.content_sha256==content
        mapping.loc[idx,'candidate_grading_id']=r.grading_id;mapping.loc[idx,'candidate_grading_split']=r.grading_split;mapping.loc[idx,'candidate_match_status']=r.match_status
        mapping.loc[idx,'candidate_DR_grade']=str(r.DR_grade);mapping.loc[idx,'candidate_DME_label']=str(r.DME_label)
    mapping.to_csv(out/'idrid_cross_task_mapping.csv',index=False)
    samples=result[~result.exact_decoded_match].sort_values('thumbnail_mae_0_255').iloc[[0,-1]] if (~result.exact_decoded_match).any() else result.head(2)
    f,axes=plt.subplots(len(samples),2,figsize=(12,5*len(samples)),squeeze=False)
    for axs,r in zip(axes,samples.itertuples()):
        for ax,p,title in zip(axs,[r.segmentation_path,r.grading_path],[f'Seg {r.segmentation_split}/{r.segmentation_id}',f'Candidate grade {r.grading_split}/{r.grading_id}\nMAE={r.thumbnail_mae_0_255:.4f}; {r.match_status}']):
            with Image.open(root/p) as im:ax.imshow(im.resize((800,531)))
            ax.set_title(title);ax.axis('off')
    plt.tight_layout();plt.savefig(fig/'cross_task_candidate_pairs.png',dpi=140);plt.close()
    # Show all exact grading train/test duplicate pairs with their labels.
    merged=gr.merge(g,on=['split','image_id'],suffixes=('','_labels'))
    duplicate=merged[merged.decoded_sha256.duplicated(False)]
    if len(duplicate):
        ordered=pd.concat([z for _,z in duplicate.groupby('decoded_sha256')])
        f,axes=plt.subplots(len(ordered)//2,2,figsize=(12,4*(len(ordered)//2)),squeeze=False)
        for ax,r in zip(axes.flat,ordered.itertuples()):
            with Image.open(root/r.path) as im:ax.imshow(im.resize((800,531)))
            ax.set_title(f'{r.split}/{r.image_id}\nDR={r.DR_grade}; DME={r.DME_label}');ax.axis('off')
        plt.tight_layout();plt.savefig(fig/'exact_duplicate_label_conflict.png',dpi=140);plt.close()
    localization_variability(root)
    return result

def localization_variability(root):
    out=root/'outputs/metrics';loc=pd.read_csv(out/'idrid_localization_metadata.csv');images=pd.read_csv(out/'idrid_image_metadata.csv')
    joined=loc.merge(images[images.component=='Localization'][['split','image_id','decoded_sha256']],on=['split','image_id'])
    rows=[]
    for (content,anatomy),group in joined.groupby(['decoded_sha256','anatomy']):
        if len(group)>1:rows.append(dict(content_sha256=content,anatomy=anatomy,annotation_rows=len(group),x_range_pixels=float(group.x.max()-group.x.min()),y_range_pixels=float(group.y.max()-group.y.min()),split_ids=';'.join(group.split+':'+group.image_id)))
    pd.DataFrame(rows).to_csv(out/'idrid_repeated_content_localization_variation.csv',index=False)

def render_duplicate_pairs(root):
    out=root/'outputs/metrics';images=pd.read_csv(out/'idrid_image_metadata.csv');g=pd.read_csv(out/'idrid_grading_labels.csv')
    merged=images[images.component=='Disease Grading'].merge(g,on=['split','image_id'],suffixes=('','_labels'))
    groups=[z for _,z in merged.groupby('decoded_sha256') if len(z)>1]
    if not groups:return
    f,axes=plt.subplots(len(groups),2,figsize=(12,4*len(groups)),squeeze=False)
    for axs,group in zip(axes,groups):
        for ax,r in zip(axs,group.itertuples()):
            with Image.open(root/r.path) as im:ax.imshow(im.resize((800,531)))
            ax.set_title(f'{r.split}/{r.image_id} DR={r.DR_grade} DME={r.DME_label}');ax.axis('off')
    plt.tight_layout();plt.savefig(root/'outputs/figures/idrid_audit/exact_duplicate_label_conflict.png',dpi=120);plt.close()
