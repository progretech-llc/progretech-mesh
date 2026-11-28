import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class TestBuddyModeContract(unittest.TestCase):
    def test_contract(self):
        t=(ROOT/'templates'/'index.html').read_text(); j=(ROOT/'static'/'js'/'app.js').read_text(); b=(ROOT/'static'/'js'/'buddy.js').read_text(); c=(ROOT/'static'/'css'/'buddy.css').read_text()
        for m in ('buddySlot','buddyTile','buddySettingsModal','buddyAgentSelect','buddySpriteGrid','css/buddy.css','js/buddy.js'): self.assertIn(m,t)
        self.assertIn('MeshBuddyBridge',j); self.assertIn('ProgreBuddy',j)
        for m in ('mesh-buddy-settings-v1','ResizeObserver','126','animateSpeakingForAgent'): self.assertIn(m,b)
        for m in ('buddy-hero-dock','resize:both','buddy-settings-card','buddy-sprite-grid'): self.assertIn(m,c)
        base=ROOT/'static'/'buddy'/'default-progre'
        for n in ('idle.png','eyes-closed.png','mouth-open.png','mouth-closed.png'): self.assertTrue((base/n).is_file())
if __name__=='__main__': unittest.main()
