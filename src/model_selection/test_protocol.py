"""Meaningful protocol/target-decoding checks; no test pixels or model training."""
import unittest
import numpy as np
import torch
from common import *
from grading import grading_loss
from segmentation import loss_for,full_view

class ProtocolTests(unittest.TestCase):
    def test_guard_blocks_test_and_raw_write_audit_events(self):
        guard([])
        # Emit the same event as filesystem open without performing an OS read/write.
        for path,mode,flags in [(ROOT/'data/interim/manifests/idrid_grading_test_clean.csv','r',os.O_RDONLY),(ROOT/'data/raw/IDRiD/synthetic_guard_probe','wb',os.O_WRONLY|os.O_CREAT),(ROOT/'data/raw/IDRiD/synthetic_guard_probe','rb',os.O_RDONLY)]:
            with self.assertRaises(PermissionError):sys.audit('open',str(path),mode,flags)
    def test_ordinal_distance_penalty(self):
        y=torch.tensor([4]);near=torch.tensor([[-8.,-8.,-8.,2.,0.]]);far=torch.tensor([[2.,-8.,-8.,-8.,0.]])
        self.assertGreater(grading_loss(far,y,'ordinal').item(),grading_loss(near,y,'ordinal').item())
        self.assertAlmostEqual(grading_loss(far,y,'ce').item(),grading_loss(near,y,'ce').item(),places=5)
    def test_unavailable_supervision_zero_gradient(self):
        logits=torch.zeros(1,4,16,16,requires_grad=True);target=torch.zeros_like(logits);target[:,1]=1
        availability=torch.tensor([[1.,0.,1.,0.]]);spatial=torch.ones(1,16,16)
        loss=loss_for(logits,target,availability,spatial,'bce_dice');loss.backward()
        self.assertEqual(logits.grad[:,1].abs().sum().item(),0);self.assertEqual(logits.grad[:,3].abs().sum().item(),0)
        self.assertGreater(logits.grad[:,0].abs().sum().item(),0)
    def test_rgba_alpha_not_foreground(self):
        a=np.zeros((8,8,4),np.uint8);a[:,:,3]=255;a[2,3,0]=255
        self.assertEqual(int((a[:,:,:3]>0).any(2).sum()),1)
    def test_clean_fold_membership(self):
        g=pd.read_csv(OUT/'grading_folds.csv');self.assertEqual(len(g),404);self.assertEqual(g.content_hash.nunique(),404)
        for fold in range(3):
            self.assertEqual(int(g.loc[g.fold==fold,'DR_grade'].eq(1).sum()),6)
            self.assertFalse(set(g.loc[g.fold==fold,'content_hash'])&set(g.loc[g.fold!=fold,'content_hash']))
    def test_native_patch_split_precedes_sampling(self):
        s=pd.read_csv(OUT/'segmentation_development_split.csv');self.assertFalse(set(s.loc[s.role=='train','sample_key'])&set(s.loc[s.role=='validation','sample_key']))
        self.assertEqual(s.image_content_hash.nunique(),len(s))
    def test_head_standardization_transfer(self):
        rng=np.random.default_rng(17);x=rng.normal(size=(8,10));mean=rng.normal(size=10);std=rng.uniform(.1,2,size=10);weight=rng.normal(size=(5,10));bias=rng.normal(size=5)
        before=((x-mean)/std)@weight.T+bias;after=x@(weight/std).T+bias-(weight*mean/std).sum(1)
        np.testing.assert_allclose(before,after,atol=1e-10)
    def test_cached_features_match_frozen_development_identities(self):
        g=pd.read_csv(OUT/'grading_folds.csv')
        for p in OUT.glob('features_*.npz'):
            with np.load(p) as z:
                np.testing.assert_array_equal(z['sample_keys'],g.sample_key.values)
                self.assertEqual(str(z['manifest_sha256']),sha(OUT/'grading_folds.csv'))

if __name__=='__main__':unittest.main()
