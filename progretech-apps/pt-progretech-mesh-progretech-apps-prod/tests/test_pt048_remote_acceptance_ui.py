import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class TestPT048RemoteAcceptanceUi(unittest.TestCase):
    def setUp(self):
        self.html=(ROOT/"templates/index.html").read_text()
        self.js=(ROOT/"static/js/app.js").read_text()
        self.buddy=(ROOT/"static/js/buddy.js").read_text()
    def test_buddy_is_docked_in_hero(self):
        self.assertIn('class="buddy-slot buddy-hero-dock"',self.html)
        self.assertNotIn('id="buddySectionHead"',self.html)
    def test_buddy_has_drag_handle_and_anchor_sprite(self):
        self.assertIn('id="buddyDragHandle"',self.html)
        self.assertIn('id="buddyAnchorSprite"',self.html)
        self.assertIn('drag?.addEventListener("pointerdown",dragStart)',self.buddy)
    def test_dedicated_buddy_controller_is_authoritative(self):
        self.assertIn("Buddy UI/event ownership lives in static/js/buddy.js.",self.js)
        self.assertIn("window.ProgreBuddy?.refreshFleet?.()",self.js)
    def test_direct_peer_race_is_bounded_retry(self):
        self.assertIn('reason === "direct_peer_not_found"',self.js)
        self.assertIn("directTransientRetryCount < 2",self.js)
        self.assertIn('setRouteStatus("Direct path retrying")',self.js)
if __name__=="__main__": unittest.main()
