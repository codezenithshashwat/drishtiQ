"""Consistent numeric scoring from preserved predictions; never fits/retunes a model."""
from common import *

def run():
    records=[]
    for path in OUT.glob('*/result.json'):
        r=json.loads(path.read_text())
        if r.get('task')!='grading':continue
        p=pd.read_csv(path.parent/'validation_predictions.csv');prob=p[['p'+str(i) for i in range(5)]].values
        new,cm,perclass=metrics(p.DR_grade.values,prob)
        for key in ['macro_f1','qwk','accuracy','balanced_accuracy']:assert np.isclose(new[key],r[key],atol=1e-12)
        original=path.parent/'result_before_numeric_scoring_standardization.json'
        if not original.exists():original.write_bytes(path.read_bytes())
        records.append(dict(tag=r['tag'],max_probability_row_sum_error=float(abs(prob.sum(1)-1).max()),old_nll=r['nll'],standardized_nll=new['nll'],predictions_and_selection_metrics_unchanged=True))
        r.update(new,confusion_matrix=cm,per_class=perclass,scoring_numerics='float64 row renormalization for round-trip epsilon; explicit NLL floor 1e-12; no fitted calibration')
        dump(path,r)
    pd.DataFrame(records).to_csv(OUT/'numeric_scoring_standardization.csv',index=False)
    print('Standardized numeric scoring for',len(records),'grading fits; hard predictions, macro-F1 and QWK unchanged.')

if __name__=='__main__':run()
