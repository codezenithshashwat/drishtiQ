"""Supplementary verification: archive/extraction equality and output reopening."""
from pathlib import Path
import json,zipfile,zlib,subprocess
import pandas as pd
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
ROOT=Path(__file__).resolve().parents[2]

def verify():
    correct_color_mask_analysis(ROOT)
    out=ROOT/'outputs/metrics'; raw=ROOT/'data/raw/IDRiD'; rows=[]
    for archive in sorted(raw.rglob('*.zip')):
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                if member.is_dir():continue
                p=raw/'original'/archive.stem/member.filename
                crc=0
                if p.exists():
                    with p.open('rb') as f:
                        for chunk in iter(lambda:f.read(1024*1024),b''):crc=zlib.crc32(chunk,crc)
                rows.append(dict(archive=archive.name,member=member.filename,extracted_path=str(p.relative_to(ROOT)),exists=p.exists(),size_matches=p.exists() and p.stat().st_size==member.file_size,crc_matches=p.exists() and crc==member.CRC))
    d=pd.DataFrame(rows);d.to_csv(out/'idrid_archive_extraction_comparison.csv',index=False)
    # Explicit MA collapse/merger tracing supplements net topology statistics.
    collapse=[]
    masks=pd.read_csv(out/'idrid_segmentation_metadata.csv')
    for row in masks[masks.mask_type=='MA'].itertuples():
        with Image.open(ROOT/row.path) as im:
            a=np.asarray(im)>0
            if a.ndim>2:a=a.any(2)
            labels,n=ndi.label(a,np.ones((3,3)))
            for width in [2048,1024,512,384,224]:
                height=round(im.height*width/im.width)
                sampled=np.asarray(Image.fromarray(labels.astype(np.int32)).resize((width,height),Image.Resampling.NEAREST))
                sampled_sizes=np.bincount(sampled.ravel(),minlength=n+1)[1:]
                target,tn=ndi.label(sampled>0,np.ones((3,3)))
                positive=sampled>0
                pairs=np.unique(np.stack((target[positive],sampled[positive]),axis=1),axis=0) if positive.any() else np.empty((0,2),int)
                target_members=np.bincount(pairs[:,0],minlength=tn+1)[1:]
                source_fragments=np.bincount(pairs[:,1],minlength=n+1)[1:]
                collapse.append(dict(mask_path=row.path,split=row.split,target_width=width,target_height=height,original_components=n,disappeared=int((sampled_sizes==0).sum()),collapsed_to_one_target_pixel=int((sampled_sizes==1).sum()),target_regions_merging_multiple_source_components=int((target_members>1).sum()),source_components_in_merged_regions=int(target_members[target_members>1].sum()),source_components_fragmented=int((source_fragments>1).sum())))
    collapse=pd.DataFrame(collapse);collapse.to_csv(out/'idrid_ma_component_topology.csv',index=False)
    collapse.groupby('target_width').sum(numeric_only=True).drop(columns=['target_height']).reset_index().to_csv(out/'idrid_ma_component_topology_summary.csv',index=False)
    checks=pd.read_csv(out/'idrid_integrity_checks.csv')
    loc=pd.read_csv(out/'idrid_localization_metadata.csv')
    blank=loc[['image_id','x','y']].isna().all(axis=1)
    if blank.any():
        loc.to_csv(out/'idrid_localization_metadata_raw_rows.csv',index=False)
        loc=loc[~blank].copy();loc.to_csv(out/'idrid_localization_metadata.csv',index=False)
    for name,status,detail in [
        ('localization_bounds','PASS' if loc.within_zero_based_bounds.all() else 'FAIL',f'{len(loc)} nonblank annotations; export padding excluded'),
        ('localization_unique_keys','PASS' if not loc.duplicated(['split','image_id','anatomy']).any() else 'FAIL',f'{len(loc)} nonblank annotations'),
        ('localization_coverage','PASS' if len(loc)==1032 and loc.image_matches.eq(1).all() else 'FAIL','nonblank annotation correspondence; padding is not orphan ground truth')]:
        checks.loc[checks.check==name,['status','detail']]=[status,detail]
    images=pd.read_csv(out/'idrid_image_metadata.csv'); grades=pd.read_csv(out/'idrid_grading_labels.csv')
    grading=images[images.component=='Disease Grading'].merge(grades,on=['split','image_id'],suffixes=('','_label'))
    conflicts=[]
    for content,group in grading.groupby('decoded_sha256'):
        if len(group)>1 and (group.DR_grade.nunique()>1 or group.DME_label.nunique()>1):
            for r in group.itertuples():conflicts.append(dict(content_sha256=content,split=r.split,image_id=r.image_id,DR_grade=r.DR_grade,DME_label=r.DME_label,path=r.path))
    pd.DataFrame(conflicts,columns=['content_sha256','split','image_id','DR_grade','DME_label','path']).to_csv(out/'idrid_content_label_conflicts.csv',index=False)
    new=[dict(check='archive_extraction_correspondence',status='PASS' if d[['exists','size_matches','crc_matches']].all().all() else 'FAIL',detail=f'{len(d)} archive members compared with extracted files by path, size, CRC32')]
    new.append(dict(check='content_label_consistency',status='FAIL' if conflicts else 'PASS',detail=str(conflicts)))
    schemas=pd.read_csv(out/'idrid_csv_schema.csv')
    issues=[]
    padding=[]
    for source in schemas.path:
        frame=pd.read_csv(ROOT/source)
        pad=frame.iloc[:,:3].isna().all(axis=1)
        padding.append(dict(path=source,raw_csv_rows=len(frame),blank_padding_rows=int(pad.sum()),annotation_rows=int((~pad).sum())))
        frame=frame[~pad]
        if frame.iloc[:,:3].isna().any().any():issues.append(source+': missing core values')
        extras=frame.iloc[:,3:].replace(r'^\s*$',np.nan,regex=True)
        if extras.notna().any().any():issues.append(source+': nonblank extra columns require interpretation')
        if frame.iloc[:,0].duplicated().any():issues.append(source+': duplicate image identifiers')
        if frame.duplicated().any():issues.append(source+': duplicate rows')
    pd.DataFrame(padding).to_csv(out/'idrid_csv_row_classification.csv',index=False)
    new.append(dict(check='all_annotation_csv_core_integrity',status='PASS' if not issues else 'FAIL',detail=str(issues) if issues else 'No missing core values, duplicate nonblank rows/IDs or nonblank extra fields after excluding all-blank export padding'))
    images=pd.read_csv(out/'idrid_image_metadata.csv');grading=images[images.component=='Disease Grading'];seg=images[images.component=='Segmentation']
    observed={'grading':len(grading),'grading_train':int((grading.split=='train').sum()),'grading_test':int((grading.split=='test').sum()),'segmentation':len(seg)}
    expected={'grading':516,'grading_train':413,'grading_test':103,'segmentation':81}
    for typ,n in {'MA':81,'HE':80,'EX':81,'SE':40,'OD':81}.items():observed[typ]=int((masks.mask_type==typ).sum());expected[typ]=n
    new.append(dict(check='published_total_comparison',status='PASS' if observed==expected else 'FAIL',detail=json.dumps({'observed':observed,'documented':expected,'source':'https://idrid.grand-challenge.org/Data/ and 2018 descriptor'})))
    extracted={str(p.relative_to(ROOT)) for p in (raw/'original').rglob('*') if p.is_file()}
    extras=extracted-set(d.extracted_path)
    new.append(dict(check='extracted_files_not_in_archives',status='PASS' if not extras else 'REVIEW',detail=str(sorted(extras))))
    derivatives=[str(p.relative_to(ROOT)) for folder in ['data/interim','data/processed','data/external'] for p in (ROOT/folder).rglob('*') if p.is_file()]
    new.append(dict(check='preprocessing_derived_file_scope',status='PASS' if not derivatives else 'REVIEW',detail=f'{len(derivatives)} files in interim/processed/external; '+str(derivatives)))
    copy_paths=[str(p.relative_to(ROOT)) for folder in ['src','outputs','docs','notebooks'] for p in (ROOT/folder).rglob('*') if p.suffix.lower() in ['.jpg','.jpeg','.tif','.tiff']]
    new.append(dict(check='original_format_copies_in_output_code',status='PASS' if not copy_paths else 'REVIEW',detail=str(copy_paths)))
    before=json.loads((out/'idrid_raw_manifest_before.json').read_text());after=json.loads((out/'idrid_raw_manifest_after.json').read_text())
    assert before==after,'Raw manifest mismatch'
    checks=pd.concat([checks[~checks.check.isin([r['check'] for r in new])],pd.DataFrame(new)],ignore_index=True)
    checks.to_csv(out/'idrid_integrity_checks.csv',index=False)
    from idrid_overlap import investigate
    similarities=investigate(ROOT)
    near=pd.read_csv(out/'idrid_near_duplicate_candidates.csv')
    checks.loc[checks.check=='near_duplicate_screen',['status','detail']]=['REVIEW' if len(near) else 'PASS',f'{len(near)} nonexact grading pairs with 64x64 grayscale correlation >=0.995 and RGB MAE <=5/255; cannot exclude arbitrary transforms or patient dependencies']
    additional=dict(check='cross_task_approximate_identity',status='REVIEW' if (~similarities.exact_decoded_match).any() else 'PASS',detail=str(similarities.match_status.value_counts().to_dict())+'; approximate matches are candidates, not confirmed identity')
    checks=pd.concat([checks[checks.check!='cross_task_approximate_identity'],pd.DataFrame([additional])],ignore_index=True)
    checks.to_csv(out/'idrid_integrity_checks.csv',index=False)
    from idrid_report import write_report
    write_report(ROOT)
    csvs=[]
    for p in out.glob('idrid_*.csv'):
        frame=pd.read_csv(p);csvs.append(dict(path=str(p.relative_to(ROOT)),rows=len(frame),columns=len(frame.columns),readable=True))
    pd.DataFrame(csvs).to_csv(out/'idrid_output_validation.csv',index=False)
    plots=[]
    for p in (ROOT/'outputs/figures/idrid_audit').glob('*.png'):
        with Image.open(p) as im:im.load();plots.append(dict(path=str(p.relative_to(ROOT)),width=im.width,height=im.height,readable=True))
    pd.DataFrame(plots).to_csv(out/'idrid_figure_validation.csv',index=False)
    for p in out.glob('idrid_*.csv'):pd.read_csv(p)
    print(f'Verified {len(csvs)} CSVs, {len(plots)} figures, {len(d)} archive members. No original-format image copies in code/output folders: {not copy_paths}.')
    print(checks[checks.status!='PASS'].to_string(index=False))
    finalize(ROOT)

def finalize(root):
    correct_color_mask_analysis(root)
    from audit_idrid import sha
    from idrid_overlap import localization_variability,render_duplicate_pairs
    from idrid_report import write_report
    out=root/'outputs/metrics';raw=root/'data/raw/IDRiD'
    localization_variability(root)
    render_duplicate_pairs(root)
    before=json.loads((out/'idrid_raw_manifest_before.json').read_text())
    current={str(p.relative_to(raw)):[p.stat().st_size,p.stat().st_mtime_ns,sha(p)] for p in sorted(raw.rglob('*')) if p.is_file()}
    (out/'idrid_raw_manifest_final.json').write_text(json.dumps(current,indent=2))
    checks=pd.read_csv(out/'idrid_integrity_checks.csv')
    item=dict(check='raw_immutability_including_supplemental_audits',status='PASS' if before==current else 'FAIL',detail='Every raw path, byte count, mtime_ns and SHA-256 compared again after supplementary analysis')
    checks=pd.concat([checks[checks.check!=item['check']],pd.DataFrame([item])],ignore_index=True);checks.to_csv(out/'idrid_integrity_checks.csv',index=False)
    write_report(root)
    rows=[]
    for p in out.glob('idrid_*.csv'):
        d=pd.read_csv(p);rows.append(dict(path=str(p.relative_to(root)),rows=len(d),columns=len(d.columns),readable=True))
    pd.DataFrame(rows).to_csv(out/'idrid_output_validation.csv',index=False)
    plots=[]
    for p in (root/'outputs/figures/idrid_audit').glob('*.png'):
        with Image.open(p) as im:im.load();plots.append(dict(path=str(p.relative_to(root)),width=im.width,height=im.height,readable=True))
    pd.DataFrame(plots).to_csv(out/'idrid_figure_validation.csv',index=False)
    print('FINAL VERIFIED IDRiD DATASET AUDIT COMPLETE')
    g=pd.read_csv(out/'idrid_grading_labels.csv');loc=pd.read_csv(out/'idrid_localization_metadata.csv');m=pd.read_csv(out/'idrid_segmentation_metadata.csv')
    images=pd.read_csv(out/'idrid_image_metadata.csv');gr=images[images.component=='Disease Grading'];seg=images[images.component=='Segmentation']
    print('Grading:',gr.groupby('split').size().to_dict(),'total:',len(gr),'distinct decoded photographs:',gr.decoded_sha256.nunique())
    print('DR distribution:',g.DR_grade.value_counts().sort_index().to_dict())
    print('Segmentation:',seg.groupby('split').size().to_dict(),'mask counts:',m.mask_type.value_counts().to_dict())
    print('Localization usable annotations:',len(loc),'export padding rows:',pd.read_csv(out/'idrid_csv_row_classification.csv').blank_padding_rows.sum())
    print('Corrupt images:',int((~images.readable).sum()+(~m.readable).sum()),'missing grading labels/orphans:',len(pd.read_csv(out/'idrid_grading_orphans.csv')),'absent masks:',len(pd.read_csv(out/'idrid_missing_masks.csv')))
    conflicts=pd.read_csv(out/'idrid_content_label_conflicts.csv')
    print('Exact grading duplicate groups:',int((gr.groupby('decoded_sha256').size()>1).sum()),'cross-split groups:',int((gr.groupby('decoded_sha256').split.nunique()>1).sum()),'conflicting DR/DME groups:',conflicts.content_sha256.nunique())
    print('Potential leakage: exact overlap and qualified cross-task candidates; patient-level leakage cannot be fully audited.')
    print('Major limitations: integrity conflicts, small selected domain, no patient IDs or gradability target.')
    print('Recommended role: internal annotation benchmark after conflict resolution; external validation required: YES.')
    print('Raw immutable:',before==current,'CSVs reopened:',len(rows),'figures decoded:',len(plots))
    for p in (root/'docs/dataset_audit').glob('*.md'):print(p)

def correct_color_mask_analysis(root):
    out=root/'outputs/metrics';m=pd.read_csv(out/'idrid_segmentation_metadata.csv');components=pd.read_csv(out/'idrid_component_areas.csv');res=pd.read_csv(out/'idrid_resolution_analysis.csv');encoding=[]
    for row in m.itertuples():
        with Image.open(root/row.path) as im:
            info=dict(path=row.path,mode=im.mode,channels=len(im.getbands()),foreground_rule='nonzero palette index' if im.mode=='P' else 'any RGB color channel >0; alpha excluded',palette_background='',palette_foreground='',alpha_values='')
            if im.mode=='P':
                palette=im.getpalette();info.update(palette_background=str(palette[:3]),palette_foreground=str(palette[3:6]))
            if im.mode=='RGBA':
                a=np.asarray(im);info['alpha_values']=str(np.unique(a[:,:,3]).tolist());b=(a[:,:,:3]>0).any(2);lab,n=ndi.label(b,np.ones((3,3)));sizes=np.bincount(lab.ravel())[1:]
                values=dict(positive_pixels=int(b.sum()),positive_image_percent=float(b.mean()*100),empty=not b.any(),component_count=n,component_min=int(sizes.min()) if n else 0,component_median=float(np.median(sizes)) if n else 0,component_max=int(sizes.max()) if n else 0)
                for k,v in values.items():m.loc[m.path==row.path,k]=v
                components=components[components.mask_path!=row.path]
                components=pd.concat([components,pd.DataFrame([dict(mask_path=row.path,mask_type=row.mask_type,split=row.split,component=i+1,area_pixels=int(v)) for i,v in enumerate(sizes)])],ignore_index=True)
                corrected=[]
                for width in [2048,1024,512,384,224]:
                    height=round(im.height*width/im.width);sampled=np.asarray(Image.fromarray(lab.astype(np.int32)).resize((width,height),Image.Resampling.NEAREST));rb=sampled>0;retained=int((np.unique(sampled)>0).sum());target_n=ndi.label(rb,np.ones((3,3)))[1];positive=int(rb.sum());expected=b.sum()*width*height/(im.width*im.height)
                    corrected.append(dict(mask_path=row.path,mask_type=row.mask_type,split=row.split,target_width=width,target_height=height,original_positive_pixels=int(b.sum()),resized_positive_pixels=positive,original_components=n,source_components_retained=retained,source_components_disappeared=n-retained,resized_components=target_n,merger_count_proxy=max(0,retained-target_n),area_ratio_to_expected=positive/expected if expected else np.nan,original_equivalent_pixels=positive*(im.width*im.height)/(width*height)))
                res=pd.concat([res[res.mask_path!=row.path],pd.DataFrame(corrected)],ignore_index=True)
            encoding.append(info)
    m.to_csv(out/'idrid_segmentation_metadata.csv',index=False);components.to_csv(out/'idrid_component_areas.csv',index=False);res.to_csv(out/'idrid_resolution_analysis.csv',index=False)
    pd.DataFrame(encoding).to_csv(out/'idrid_mask_encoding_audit.csv',index=False)
    coverage=pd.read_csv(out/'idrid_annotation_coverage.csv')
    for (split,typ),group in m.groupby(['split','mask_type']):
        for name,value in dict(empty_masks=int(group['empty'].sum()),min_positive_pixels=int(group.positive_pixels.min()),median_positive_pixels=float(group.positive_pixels.median()),mean_positive_pixels=float(group.positive_pixels.mean()),max_positive_pixels=int(group.positive_pixels.max()),median_image_percent=float(group.positive_image_percent.median())).items():coverage.loc[(coverage.split==split)&(coverage.mask_type==typ),name]=value
    coverage.to_csv(out/'idrid_annotation_coverage.csv',index=False)
    # Regenerate corrected resolution plots, especially the exceptional EX mask.
    import matplotlib.pyplot as plt
    for typ,group in res.groupby('mask_type'):
        z=group.groupby('target_width')[['original_components','source_components_retained','original_positive_pixels','original_equivalent_pixels']].sum()
        plt.plot(z.index,z.source_components_retained/z.original_components*100,'o-',label='Original components sampled (%)');plt.plot(z.index,z.original_equivalent_pixels/z.original_positive_pixels*100,'s-',label='Area relative to expected (%)');plt.title(typ);plt.xlabel('Target width, aspect preserved');plt.legend();plt.tight_layout();plt.savefig(root/'outputs/figures/idrid_audit'/f'resolution_{typ}.png',dpi=140);plt.close()

if __name__=='__main__':verify()
